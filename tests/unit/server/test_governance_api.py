from __future__ import annotations

import unittest

from polaris_server.gates_service import GateEvaluateRequest, evaluate_gate_endpoint
from polaris_server.issues_service import (
    HotspotReviewRequest,
    IssueTransitionRequest,
    list_issues,
    review_hotspot,
    transition_issue,
    upsert_issue_occurrence,
)
from polaris_server.metrics_service import (
    compute_code_metrics,
    compute_python_complexity,
    get_project_metrics,
    store_project_metrics,
)
from polaris_server.profiles_service import ProfileCreateRequest, create_profile, list_profiles
from polaris_server.rules_router import list_rules


class TestGovernanceAPI(unittest.TestCase):
    def test_issues_lifecycle_and_hotspots(self) -> None:
        rec = upsert_issue_occurrence(
            project_key="proj-a",
            rule_id="PY001",
            severity="CRITICAL",
            issue_type="SECURITY_HOTSPOT",
            file_path="app.py",
            line=10,
            message="Use of eval",
            fingerprint="fp-1234567890abcdef",
        )
        listed = list_issues(project_key="proj-a")
        self.assertGreaterEqual(listed["total"], 1)

        tr = transition_issue(rec.issue_id, IssueTransitionRequest(target_status="CONFIRMED", comment="Verified"))
        self.assertEqual(tr["status"], "CONFIRMED")

        hr = review_hotspot(rec.issue_id, HotspotReviewRequest(status="SAFE"))
        self.assertEqual(hr["hotspot_status"], "SAFE")

    def test_metrics_and_complexity(self) -> None:
        comp = compute_python_complexity("def f(x):\n    if x > 0 and x < 10:\n        return x\n    return 0\n")
        self.assertGreaterEqual(comp["cyclomatic"], 3)
        self.assertGreaterEqual(comp["cognitive"], 2)

        metrics = compute_code_metrics(
            files_count=2,
            lines=50,
            ncloc=40,
            comment_lines=10,
            issues=[{"severity": "MAJOR", "issue_type": "CODE_SMELL", "effort_minutes": 15}],
            cyclomatic_complexity=comp["cyclomatic"],
            cognitive_complexity=comp["cognitive"],
        )
        store_project_metrics("proj-a", metrics)
        res = get_project_metrics("proj-a")
        self.assertEqual(res["technical_debt_minutes"], 15)
        self.assertEqual(res["ratings"]["maintainability"], "C")

    def test_profiles_gates_and_rules(self) -> None:
        r_rules = list_rules(language="python")
        self.assertGreaterEqual(r_rules["total"], 1)

        r_prof = create_profile(ProfileCreateRequest(name="Strict Python", language="python"))
        self.assertEqual(r_prof["language"], "python")
        self.assertGreaterEqual(list_profiles(language="python")["total"], 2)

        r_gate = evaluate_gate_endpoint("polaris-default", GateEvaluateRequest(metrics={"issues_total": 10, "technical_debt_minutes": 100}))
        self.assertEqual(r_gate["status"], "PASSED")

        r_gate_fail = evaluate_gate_endpoint("polaris-default", GateEvaluateRequest(metrics={"issues_total": 100, "technical_debt_minutes": 100}))
        self.assertEqual(r_gate_fail["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
