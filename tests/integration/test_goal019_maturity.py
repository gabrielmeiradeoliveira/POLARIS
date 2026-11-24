from __future__ import annotations

import unittest

from polaris_server.auth_service import check_permission, hash_password, verify_password
from polaris_server.coverage_duplication import detect_duplications, parse_cobertura_xml
from polaris_server.gates_service import GateEvaluateRequest, evaluate_gate_endpoint
from polaris_server.git_branch_service import list_branches, list_pull_requests, register_branch, register_pull_request
from polaris_server.git_new_code import compute_new_code_issues, parse_git_diff_added_lines
from polaris_server.history_service import compare_analyses, get_project_history, record_snapshot
from polaris_server.issues_service import (
    IssueAssignRequest,
    IssueCommentRequest,
    IssueTransitionRequest,
    add_comment,
    assign_issue,
    transition_issue,
    upsert_issue_occurrence,
)
from polaris_server.profiles_service import (
    RuleActivationRequest,
    activate_rule,
    deactivate_rule,
    list_profiles,
)
from polaris_server.rule_metrics import RuleEvalCase, compute_rule_metrics
from polaris_server.rules_catalog import RULES_CATALOG
from polaris_server.webhooks_service import sign_webhook_payload, validate_webhook_url


class TestGoal019Maturity(unittest.TestCase):
    def test_01_rule_catalog_and_metrics(self) -> None:
        self.assertEqual(len(RULES_CATALOG), 8)
        cases = []
        for r in RULES_CATALOG:
            cases.append(RuleEvalCase(r.ruleId, True, True))
            cases.append(RuleEvalCase(r.ruleId, False, False))
        metrics = compute_rule_metrics(cases)
        for r in RULES_CATALOG:
            self.assertEqual(metrics[r.ruleId]["precision"], 1.0)
            self.assertEqual(metrics[r.ruleId]["recall"], 1.0)
            self.assertEqual(metrics[r.ruleId]["f1"], 1.0)

    def test_02_profiles_and_gates_integration(self) -> None:
        activate_rule("polaris-way-python", RuleActivationRequest(rule_id="PY-SYN-001", severity="CRITICAL"))
        profs = {p["profile_id"]: p for p in list_profiles("python")["items"]}
        self.assertIn("PY-SYN-001", profs["polaris-way-python"]["active_rules"])
        deactivate_rule("polaris-way-python", "PY-SYN-001")
        profs_after = {p["profile_id"]: p for p in list_profiles("python")["items"]}
        self.assertNotIn("PY-SYN-001", profs_after["polaris-way-python"]["active_rules"])

        self.assertEqual(evaluate_gate_endpoint("polaris-default", GateEvaluateRequest(metrics={"issues_total": 5, "technical_debt_minutes": 30}))["status"], "PASSED")
        self.assertEqual(evaluate_gate_endpoint("polaris-default", GateEvaluateRequest(metrics={"issues_total": 99, "technical_debt_minutes": 30}))["status"], "FAILED")
        self.assertEqual(evaluate_gate_endpoint("polaris-default", GateEvaluateRequest(metrics={}))["status"], "NOT_COMPUTED")

    def test_03_issue_lifecycle_and_history_three_analyses(self) -> None:
        rec = upsert_issue_occurrence("proj-019", "PY-SYN-001", "CRITICAL", "VULNERABILITY", "a.py", 12, "eval used", "fp-019-1")
        assign_issue(rec.issue_id, IssueAssignRequest(assignee="dev1"))
        add_comment(rec.issue_id, IssueCommentRequest(author="dev1", text="Fixing"))
        transition_issue(rec.issue_id, IssueTransitionRequest(target_status="CONFIRMED"))
        transition_issue(rec.issue_id, IssueTransitionRequest(target_status="RESOLVED"))
        reopened = upsert_issue_occurrence("proj-019", "PY-SYN-001", "CRITICAL", "VULNERABILITY", "a.py", 15, "eval used", "fp-019-1")
        self.assertEqual(reopened["status"] if isinstance(reopened, dict) else reopened.status, "REOPENED")

        record_snapshot("proj-019", "a1", "main", "FAILED", {"issues_total": 3}, {"fp1", "fp2", "fp3"})
        record_snapshot("proj-019", "a2", "main", "FAILED", {"issues_total": 2}, {"fp2", "fp3"})
        record_snapshot("proj-019", "a3", "main", "PASSED", {"issues_total": 1}, {"fp3"})
        self.assertEqual(get_project_history("proj-019")["total"], 3)
        cmp = compare_analyses("proj-019", "a1", "a3")
        self.assertEqual(cmp["resolved_issues"], ["fp1", "fp2"])
        self.assertEqual(cmp["persistent_issues"], ["fp3"])

    def test_04_coverage_duplication_new_code_branches(self) -> None:
        xml = '<coverage><packages><package><classes><class filename="a.py"><lines><line number="1" hits="1"/><line number="2" hits="0"/></lines></class></classes></package></packages></coverage>'
        cov = parse_cobertura_xml(xml, {"a.py"})
        self.assertEqual(cov["coverage_percent"], 50.0)
        dup = detect_duplications({"a.py": "def f(x): return x + 1", "b.py": "def f(x): return x + 1"}, window_size=5)
        self.assertGreaterEqual(dup["duplicated_blocks_count"], 1)

        diff = "+++ b/a.py\n@@ -1,0 +10,1 @@\n+eval(x)\n"
        changed = parse_git_diff_added_lines(diff)
        nc = compute_new_code_issues([{"file_path": "a.py", "line": 10}, {"file_path": "a.py", "line": 2}], changed)
        self.assertEqual(nc["new_issues_count"], 1)
        self.assertEqual(nc["historical_issues_count"], 1)

        register_branch("proj-019", "main", is_main=True, last_commit="c1")
        register_branch("proj-019", "feat/x", is_main=False, last_commit="c2")
        register_pull_request("proj-019", "10", "feat/x", "main", "c2")
        self.assertEqual(list_branches("proj-019")["total"], 2)
        self.assertEqual(list_pull_requests("proj-019")["total"], 1)

    def test_05_security_rbac_and_webhooks(self) -> None:
        h = hash_password("Secret#2026")
        self.assertTrue(verify_password("Secret#2026", h))
        self.assertTrue(check_permission("GLOBAL_ADMIN", "ADMIN_USERS"))
        self.assertFalse(check_permission("VIEWER", "ADMIN_USERS"))
        with self.assertRaises(ValueError):
            validate_webhook_url("http://127.0.0.1:8000/hook")
        self.assertEqual(len(sign_webhook_payload("k", b"payload")), 64)


if __name__ == "__main__":
    unittest.main()
