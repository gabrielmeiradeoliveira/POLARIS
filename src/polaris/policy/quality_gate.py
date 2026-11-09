"""Security Quality Gates and Policy Engine (GOAL 37).

Evaluates findings against declarative polaris.yaml policy thresholds,
managing baseline comparisons and suppressions.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from polaris.evidence.platform import CanonicalSecurityFinding

logger = logging.getLogger(__name__)


class GateDecision(StrEnum):
    """Quality gate decision."""

    PASS = "PASS"  # noqa: S105
    WARN = "WARN"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class PolarisSecurityPolicy(BaseModel):
    """Declarative security policy configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fail_on_severity: list[str] = Field(default_factory=lambda: ["CRITICAL", "HIGH"])
    allow_suppressions: bool = True
    suppressed_finding_ids: list[str] = Field(default_factory=list)
    max_tolerated_vulnerabilities: int = 0
    fail_on_new: bool = False
    fail_on_incomplete: bool = False

    @classmethod
    def load_from_repo(cls, repo_path: str | Path) -> PolarisSecurityPolicy | None:
        """Load polaris.yaml or polaris.yml policy if present in repository root, or return None."""
        root = Path(repo_path)
        for fname in ("polaris.yaml", "polaris.yml"):
            policy_file = root / fname
            if policy_file.is_file():
                try:
                    data = yaml.safe_load(policy_file.read_text(encoding="utf-8")) or {}
                    if not isinstance(data, dict):
                        logger.warning("Invalid %s format, expected dictionary. Falling back to default policy.", fname)
                        return cls()
                    policy_data = data.get("policy", data)
                    if not isinstance(policy_data, dict):
                        return cls()
                    filtered_args: dict[str, Any] = {}
                    if "fail_on_severity" in policy_data and isinstance(policy_data["fail_on_severity"], list):
                        filtered_args["fail_on_severity"] = [str(s) for s in policy_data["fail_on_severity"]]
                    if "allow_suppressions" in policy_data and isinstance(policy_data["allow_suppressions"], bool):
                        filtered_args["allow_suppressions"] = policy_data["allow_suppressions"]
                    if "suppressed_finding_ids" in policy_data and isinstance(policy_data["suppressed_finding_ids"], list):
                        filtered_args["suppressed_finding_ids"] = [str(sid) for sid in policy_data["suppressed_finding_ids"]]
                    if "max_tolerated_vulnerabilities" in policy_data and isinstance(policy_data["max_tolerated_vulnerabilities"], int):
                        filtered_args["max_tolerated_vulnerabilities"] = policy_data["max_tolerated_vulnerabilities"]
                    if "fail_on_new" in policy_data and isinstance(policy_data["fail_on_new"], bool):
                        filtered_args["fail_on_new"] = policy_data["fail_on_new"]
                    if "fail_on_incomplete" in policy_data and isinstance(policy_data["fail_on_incomplete"], bool):
                        filtered_args["fail_on_incomplete"] = policy_data["fail_on_incomplete"]
                    return cls(**filtered_args)
                except Exception as exc:
                    logger.warning("Failed to parse %s (%s). Falling back to default policy.", fname, type(exc).__name__)
                    return cls()
        return None


class SecurityQualityGateEngine:
    """Evaluates canonical security findings against policy thresholds."""

    @classmethod
    def evaluate(
        cls,
        findings: list[CanonicalSecurityFinding],
        policy: PolarisSecurityPolicy | None = None,
        *,
        is_complete: bool = True,
        incompleteness_reasons: list[str] | None = None,
    ) -> tuple[GateDecision, list[str]]:
        """Evaluate findings against policy."""
        pol = policy or PolarisSecurityPolicy()
        blocking_findings: list[str] = []

        if not is_complete and pol.fail_on_incomplete:
            reasons = incompleteness_reasons or ["Analysis is incomplete or truncated."]
            for r in reasons:
                blocking_findings.append(f"[INCOMPLETE] {r}")
            return GateDecision.FAIL, blocking_findings

        for f in findings:
            if pol.allow_suppressions and f.finding_id in pol.suppressed_finding_ids:
                continue

            if f.severity.upper() in [s.upper() for s in pol.fail_on_severity]:
                blocking_findings.append(f"[{f.severity}] {f.title} ({f.rule_or_cve}) at {f.file_path}:{f.line}")

        if len(blocking_findings) > pol.max_tolerated_vulnerabilities:
            return GateDecision.FAIL, blocking_findings
        elif blocking_findings:
            return GateDecision.WARN, blocking_findings
        return GateDecision.PASS, []
