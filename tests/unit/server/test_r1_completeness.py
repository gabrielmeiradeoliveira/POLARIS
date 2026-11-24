from __future__ import annotations

import unittest

from polaris_server.git_new_code import compute_new_code_issues, parse_git_diff_added_lines
from polaris_server.rule_metrics import RuleEvalCase, compute_rule_metrics


class TestR1Completeness(unittest.TestCase):
    def test_rule_metrics_tp_fp_tn_fn(self) -> None:
        cases = [
            RuleEvalCase("PY001", True, True),
            RuleEvalCase("PY001", True, True),
            RuleEvalCase("PY001", False, False),
            RuleEvalCase("PY001", False, True),
        ]
        m = compute_rule_metrics(cases)["PY001"]
        self.assertEqual(m["tp"], 2)
        self.assertEqual(m["fp"], 1)
        self.assertEqual(m["tn"], 1)
        self.assertEqual(m["fn"], 0)
        self.assertAlmostEqual(m["precision"], 0.6667, places=4)
        self.assertAlmostEqual(m["recall"], 1.0, places=4)

    def test_git_new_code_separation(self) -> None:
        diff = "+++ b/src/app.py\n@@ -10,0 +11,2 @@\n+eval(x)\n+y = 1\n"
        changed = parse_git_diff_added_lines(diff)
        self.assertEqual(changed["src/app.py"], {11, 12})
        issues = [
            {"file_path": "src/app.py", "line": 11, "rule_id": "PY001"},
            {"file_path": "src/app.py", "line": 3, "rule_id": "PY002"},
        ]
        res = compute_new_code_issues(issues, changed)
        self.assertEqual(res["new_issues_count"], 1)
        self.assertEqual(res["historical_issues_count"], 1)


if __name__ == "__main__":
    unittest.main()
