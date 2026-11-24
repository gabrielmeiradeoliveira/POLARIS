import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from polaris_server.domain_core import (
    QualityProfile,
    compute_rating,
    evaluate_quality_gate,
    match_issues_between_analyses,
    transition_issue_state,
)


class TestDomainCore(unittest.TestCase):
    def test_issue_lifecycle_and_tracking(self) -> None:
        self.assertEqual(transition_issue_state("OPEN", "CONFIRMED"), "CONFIRMED")
        with self.assertRaises(ValueError):
            transition_issue_state("FALSE_POSITIVE", "RESOLVED")
        diff = match_issues_between_analyses({"fp1", "fp2"}, {"fp2", "fp3"})
        self.assertEqual(diff["new"], {"fp3"})
        self.assertEqual(diff["persistent"], {"fp2"})
        self.assertEqual(diff["resolved"], {"fp1"})

    def test_ratings_profiles_and_quality_gates(self) -> None:
        self.assertEqual(compute_rating({"MAJOR": 1}), "C")
        self.assertEqual(compute_rating({}), "A")
        prof = QualityProfile("default-py", "python", {"PY-SYN-001"})
        prof.deactivate("PY-SYN-001")
        self.assertEqual(prof.active_rules, set())
        gate = evaluate_quality_gate({"bugs": 2}, [{"metric": "bugs", "operator": "GT", "threshold": 0}])
        self.assertEqual(gate["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
