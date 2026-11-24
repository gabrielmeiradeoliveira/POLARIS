from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RuleEvalCase:
    rule_id: str
    expected_positive: bool
    detected: bool


def compute_rule_metrics(cases: list[RuleEvalCase]) -> dict[str, dict[str, Any]]:
    """Compute TP, FP, TN, FN, Precision, Recall, F1 per rule_id."""
    counts: dict[str, dict[str, int]] = {}
    for c in cases:
        bucket = counts.setdefault(c.rule_id, {"tp": 0, "fp": 0, "tn": 0, "fn": 0})
        if c.expected_positive and c.detected:
            bucket["tp"] += 1
        elif not c.expected_positive and c.detected:
            bucket["fp"] += 1
        elif not c.expected_positive and not c.detected:
            bucket["tn"] += 1
        else:
            bucket["fn"] += 1

    results: dict[str, dict[str, Any]] = {}
    for rid, b in sorted(counts.items()):
        tp, fp, tn, fn = b["tp"], b["fp"], b["tn"], b["fn"]
        prec = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
        rec = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
        f1 = round((2 * prec * rec) / (prec + rec), 4) if (prec + rec) > 0 else 0.0
        results[rid] = {
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "total_cases": tp + fp + tn + fn,
        }
    return results
