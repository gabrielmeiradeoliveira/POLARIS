from __future__ import annotations

import unittest

from polaris_server.history_service import compare_analyses, get_project_history, record_snapshot


class TestHistoryService(unittest.TestCase):
    def test_snapshot_history_and_compare(self) -> None:
        record_snapshot("proj-h", "anl-1", branch="main", quality_gate_status="FAILED", metrics={"issues_total": 2}, issue_fingerprints={"fp1", "fp2"})
        record_snapshot("proj-h", "anl-2", branch="main", quality_gate_status="PASSED", metrics={"issues_total": 1}, issue_fingerprints={"fp2", "fp3"})

        hist = get_project_history("proj-h", branch="main")
        self.assertEqual(hist["total"], 2)

        cmp = compare_analyses("proj-h", "anl-1", "anl-2")
        self.assertEqual(cmp["new_issues"], ["fp3"])
        self.assertEqual(cmp["resolved_issues"], ["fp1"])
        self.assertEqual(cmp["persistent_issues"], ["fp2"])
        self.assertEqual(cmp["metrics_delta"]["issues_total"], -1.0)


if __name__ == "__main__":
    unittest.main()
