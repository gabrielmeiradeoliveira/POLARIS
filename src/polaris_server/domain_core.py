from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

VALID_ISSUE_STATES = ("OPEN", "CONFIRMED", "ACCEPTED", "FALSE_POSITIVE", "RESOLVED", "REOPENED")
VALID_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "OPEN": ("CONFIRMED", "ACCEPTED", "FALSE_POSITIVE", "RESOLVED"),
    "CONFIRMED": ("ACCEPTED", "FALSE_POSITIVE", "RESOLVED"),
    "ACCEPTED": ("REOPENED", "RESOLVED"),
    "FALSE_POSITIVE": ("REOPENED",),
    "RESOLVED": ("REOPENED",),
    "REOPENED": ("CONFIRMED", "ACCEPTED", "FALSE_POSITIVE", "RESOLVED"),
}


def transition_issue_state(current_state: str, target_state: str) -> str:
    """Validate and apply an issue lifecycle transition."""
    if current_state not in VALID_ISSUE_STATES or target_state not in VALID_ISSUE_STATES:
        raise ValueError(f"Invalid issue state: {current_state} -> {target_state}")
    if target_state not in VALID_TRANSITIONS[current_state]:
        raise ValueError(f"Transition not allowed: {current_state} -> {target_state}")
    return target_state


def match_issues_between_analyses(previous_fingerprints: set[str], current_fingerprints: set[str]) -> dict[str, set[str]]:
    """Track new, persistent, and resolved issues between two analyses."""
    return {
        "new": current_fingerprints - previous_fingerprints,
        "persistent": current_fingerprints & previous_fingerprints,
        "resolved": previous_fingerprints - current_fingerprints,
    }


def compute_rating(issue_count_by_severity: dict[str, int]) -> str:
    """Compute A-E rating based on highest severity present."""
    if issue_count_by_severity.get("BLOCKER", 0) > 0:
        return "E"
    if issue_count_by_severity.get("CRITICAL", 0) > 0:
        return "D"
    if issue_count_by_severity.get("MAJOR", 0) > 0:
        return "C"
    if issue_count_by_severity.get("MINOR", 0) > 0:
        return "B"
    return "A"


_CONFIDENCE_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


def filter_issues_by_min_confidence(issues: list[dict[str, Any]], min_confidence: str) -> list[dict[str, Any]]:
    """Return issues whose confidence is >= min_confidence (defaulting missing confidence to HIGH)."""
    min_rank = _CONFIDENCE_RANK.get(min_confidence.upper(), 1)
    return [
        issue
        for issue in issues
        if _CONFIDENCE_RANK.get(str(issue.get("confidence", "HIGH")).upper(), 3) >= min_rank
    ]


def evaluate_quality_gate(
    metrics: dict[str, float],
    conditions: list[dict[str, Any]],
    issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate a Quality Gate against computed metrics, with optional min_confidence filtering."""
    if not conditions:
        return {"status": "NOT_COMPUTED", "conditions": []}
    results = []
    overall = "PASSED"
    for cond in conditions:
        metric = cond["metric"]
        op = cond["operator"]  # GT | LT | EQ
        threshold = float(cond["threshold"])
        min_conf = cond.get("min_confidence")
        if min_conf and issues is not None:
            filtered = filter_issues_by_min_confidence(issues, str(min_conf))
            if metric in ("vulnerabilities", "bugs", "code_smells"):
                target_type = {"vulnerabilities": "VULNERABILITY", "bugs": "BUG", "code_smells": "CODE_SMELL"}[metric]
                val = float(sum(1 for i in filtered if i.get("type") == target_type))
            elif metric in ("blocker_issues", "critical_issues", "major_issues", "minor_issues", "info_issues"):
                target_sev = metric.replace("_issues", "").upper()
                val = float(sum(1 for i in filtered if i.get("severity") == target_sev))
            elif metric == "total_issues":
                val = float(len(filtered))
            elif metric in metrics:
                val = float(metrics[metric])
            else:
                results.append({"metric": metric, "status": "NOT_COMPUTED", "min_confidence": min_conf})
                overall = "NOT_COMPUTED" if overall == "PASSED" else overall
                continue
        else:
            if metric not in metrics:
                results.append({"metric": metric, "status": "NOT_COMPUTED"})
                overall = "NOT_COMPUTED" if overall == "PASSED" else overall
                continue
            val = float(metrics[metric])
        failed = (op == "GT" and val > threshold) or (op == "LT" and val < threshold) or (op == "EQ" and val == threshold)
        status = "FAILED" if failed else "PASSED"
        if failed:
            overall = "FAILED"
        entry: dict[str, Any] = {"metric": metric, "value": val, "threshold": threshold, "status": status}
        if min_conf:
            entry["min_confidence"] = min_conf
        results.append(entry)
    return {"status": overall, "conditions": results}


@dataclass
class QualityProfile:
    name: str
    language: str
    active_rules: set[str] = field(default_factory=set)

    def activate(self, rule_id: str) -> None:
        self.active_rules.add(rule_id)

    def deactivate(self, rule_id: str) -> None:
        self.active_rules.discard(rule_id)
