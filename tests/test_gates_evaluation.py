import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def evaluate_conditions(conditions: list[dict], metrics: dict, analysis_status: str = "COMPLETED") -> str:
    if analysis_status != "COMPLETED":
        return "NOT_COMPUTED"
    if not conditions:
        return "PASSED"
    for cond in conditions:
        metric = cond.get("metric", "")
        if metric not in metrics or metrics[metric] is None:
            return "NOT_COMPUTED"
        actual = float(metrics[metric])
        threshold = float(cond.get("threshold", 0))
        op = cond.get("operator", "GT").upper()
        violated = (
            (op == "GT" and actual > threshold)
            or (op == "LT" and actual < threshold)
            or (op == "EQ" and actual != threshold)
        )
        if violated:
            return "FAILED"
    return "PASSED"


class TestGatesEvaluation(unittest.TestCase):
    def test_gate_passed(self):
        conds = [{"metric": "bugs", "operator": "GT", "threshold": 0}]
        self.assertEqual(evaluate_conditions(conds, {"bugs": 0}, "COMPLETED"), "PASSED")

    def test_gate_failed(self):
        conds = [{"metric": "bugs", "operator": "GT", "threshold": 0}]
        self.assertEqual(evaluate_conditions(conds, {"bugs": 2}, "COMPLETED"), "FAILED")

    def test_gate_not_computed_missing_metric(self):
        conds = [{"metric": "coverage", "operator": "LT", "threshold": 80}]
        self.assertEqual(evaluate_conditions(conds, {"bugs": 0}, "COMPLETED"), "NOT_COMPUTED")

    def test_gate_not_computed_incomplete_analysis(self):
        conds = [{"metric": "bugs", "operator": "GT", "threshold": 0}]
        self.assertEqual(evaluate_conditions(conds, {"bugs": 0}, "PARTIAL"), "NOT_COMPUTED")
