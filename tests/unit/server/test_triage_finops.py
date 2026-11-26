from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from polaris_server.ai.summary_cache import invalidate_pr_summary_cache
from polaris_server.issues_service import BatchTriageRequest, apply_batch_triage, list_issues
from polaris_server.triage import (
    IssueRecord,
    compute_finding_fingerprint,
    compute_persistent_fingerprint,
)


class TestTriageAndFinops(unittest.TestCase):
    def test_fingerprint_deterministic_and_line_immune(self) -> None:
        # Same rule, path, flow steps with different line numbers / formatting
        steps1 = [
            {"kind": "SOURCE", "file": "app.py:12", "message": "user input"},
            {"kind": "SINK", "file": "db.py:88", "message": "query execution"},
        ]
        steps2 = [
            {"kind": "SOURCE", "file": "app.py:540", "message": "  user   input  "},
            {"kind": "SINK", "file": "db.py:910:5", "message": "query execution"},
        ]
        fp1 = compute_finding_fingerprint("SEC-001", "src\\app.py:12", steps1)
        fp2 = compute_finding_fingerprint("SEC-001", "src/app.py", steps2)
        self.assertEqual(len(fp1), 64)
        self.assertEqual(fp1, fp2)

        # Fallback signature when flow_steps is empty
        fp_noflow1 = compute_finding_fingerprint("SEC-002", "api.py", fallback_signature="cursor.execute(q):10")
        fp_noflow2 = compute_finding_fingerprint("SEC-002", "api.py", fallback_signature="cursor.execute(q)")
        self.assertEqual(fp_noflow1, fp_noflow2)

    def test_batch_triage_request_validation(self) -> None:
        from fastapi import HTTPException

        # Invalid status
        with self.assertRaises(HTTPException) as cm:
            apply_batch_triage(
                BatchTriageRequest(
                    fingerprints=["fp1"],
                    status="INVALID_STATUS",
                    justification="Valid justification here",
                )
            )
        self.assertEqual(cm.exception.status_code, 400)

        # Short justification
        with self.assertRaises(HTTPException) as cm:
            apply_batch_triage(
                BatchTriageRequest(
                    fingerprints=["fp1"],
                    status="FALSE_POSITIVE",
                    justification="  a ",
                )
            )
        self.assertEqual(cm.exception.status_code, 400)

        # expires_at with status != ACCEPTED_RISK
        future_iso = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        with self.assertRaises(HTTPException) as cm:
            apply_batch_triage(
                BatchTriageRequest(
                    fingerprints=["fp1"],
                    status="FALSE_POSITIVE",
                    justification="Safe by design",
                    expires_at=future_iso,
                )
            )
        self.assertEqual(cm.exception.status_code, 400)

        # expires_at in the past
        past_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        with self.assertRaises(HTTPException) as cm:
            apply_batch_triage(
                BatchTriageRequest(
                    fingerprints=["fp1"],
                    status="ACCEPTED_RISK",
                    justification="Risk accepted temporarily",
                    expires_at=past_iso,
                )
            )
        self.assertEqual(cm.exception.status_code, 400)

        # empty targets
        with self.assertRaises(HTTPException) as cm:
            apply_batch_triage(
                BatchTriageRequest(
                    fingerprints=[],
                    issue_ids=[],
                    status="ACCEPTED_RISK",
                    justification="Valid justification",
                )
            )
        self.assertEqual(cm.exception.status_code, 400)

    def test_finops_ai_pr_summary_short_circuit_and_suppression(self) -> None:
        import polaris_server.api as api_mod

        # 1. Short-circuit: when all issues are suppressed or no issues passed
        res_empty = api_mod.ai_pr_summary("PR-ZERO", {"issues": []})
        self.assertEqual(res_empty["status"], "ok")
        self.assertEqual(res_empty["verdict"], "LIKELY_FALSE_POSITIVE")
        self.assertEqual(res_empty["actual_total_tokens"], 0)
        self.assertEqual(res_empty["actual_input_tokens"], 0)
        self.assertEqual(res_empty["actual_output_tokens"], 0)

        # 2. When issues match suppressed triages (FALSE_POSITIVE or valid ACCEPTED_RISK)
        fp_false_pos = compute_finding_fingerprint("PY-SEC-001", "app.py")
        fp_accepted = compute_finding_fingerprint("PY-SEC-002", "db.py")

        future_exp = datetime.now(timezone.utc) + timedelta(days=30)
        mock_triages = [
            (fp_false_pos, "FALSE_POSITIVE", None),
            (fp_accepted, "ACCEPTED_RISK", future_exp),
        ]

        # Simula retorno do banco para finding_triages
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = mock_triages
        mock_conn = MagicMock()
        mock_conn.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("polaris_server.api.get_connection", return_value=mock_conn):
            res_suppressed = api_mod.ai_pr_summary(
                "PR-SUPP",
                {
                    "issues": [
                        {"ruleId": "PY-SEC-001", "location": {"file": "app.py"}},
                        {"ruleId": "PY-SEC-002", "location": {"file": "db.py"}},
                    ]
                },
            )
            # Both were suppressed -> short circuit!
            self.assertEqual(res_suppressed["verdict"], "LIKELY_FALSE_POSITIVE")
            self.assertEqual(res_suppressed["actual_total_tokens"], 0)

    def test_invalidate_pr_summary_cache(self) -> None:
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("polaris_server.ai.summary_cache.get_connection", return_value=mock_conn):
            ok = invalidate_pr_summary_cache("PR-999")
            self.assertTrue(ok)
            mock_cursor.execute.assert_called_once_with(
                "DELETE FROM ai_pr_summaries WHERE pr_key = %s;",
                ("PR-999",),
            )


if __name__ == "__main__":
    unittest.main()
