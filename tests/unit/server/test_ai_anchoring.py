from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from polaris_server.ai.service import AiTriageService, extract_structured_ai_json
from polaris_server.issues_service import extract_code_snippet, get_issue_flow, list_issues


class TestAiAnchoringAndSnippets(unittest.TestCase):
    def test_extract_code_snippet_real_repo_file(self) -> None:
        snip = extract_code_snippet("src/polaris_server/db.py", 10, context_lines=2)
        self.assertIsNotNone(snip)
        self.assertIn("psycopg.connect", snip)

        # non-existent file returns None without raising
        none_snip = extract_code_snippet("non_existent_folder/missing_file.py", 15)
        self.assertIsNone(none_snip)

    def test_extract_structured_ai_json_anchoring_fields(self) -> None:
        raw_json = json.dumps({
            "verdict": "CONFIRMED_EXPLOITABLE",
            "summary": "Path traversal confirmed on user input.",
            "suggested_snippet": "target = safe_path(user_input)",
            "corrected_line": "target = safe_path(user_input)",
            "diff_before": "target = open(user_input)",
            "diff_after": "target = safe_path(user_input)",
            "needs_broader_refactor": False,
        })
        parsed = extract_structured_ai_json(raw_json, original_snippet="target = open(user_input)", start_line=42)
        self.assertEqual(parsed["verdict"], "CONFIRMED_EXPLOITABLE")
        self.assertEqual(parsed["corrected_line"], "target = safe_path(user_input)")
        self.assertEqual(parsed["diff_before"], "target = open(user_input)")
        self.assertEqual(parsed["diff_after"], "target = safe_path(user_input)")
        self.assertEqual(parsed["start_line"], 42)

    def test_ai_analyze_issue_prompt_contains_anchoring_rules_and_fields(self) -> None:
        svc = AiTriageService()
        captured_messages = []

        def mock_call(*, messages, max_tokens, model):
            captured_messages.extend(messages)
            return {
                "status": "ok",
                "content": json.dumps({
                    "verdict": "CONFIRMED_EXPLOITABLE",
                    "summary": "Specific flaw detected in rule PY-SEC-PATH-001.",
                    "suggested_snippet": "safe_join(base, path)",
                    "corrected_line": "safe_join(base, path)",
                    "diff_before": "os.path.join(base, path)",
                    "diff_after": "safe_join(base, path)",
                    "needs_broader_refactor": False,
                }),
                "tokens_used": 150,
            }

        with patch("polaris_server.ai.service.call_chat_completions", side_effect=mock_call):
            res = svc.analyze_issue(
                fingerprint="fp-path-1",
                rule_id="PY-SEC-PATH-001",
                severity="CRITICAL",
                language="python",
                snippet="p = os.path.join(base, path)",
                cwe="CWE-22",
                file_path="src/polaris_server/files.py",
                start_line=88,
            )

        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["rule_id"], "PY-SEC-PATH-001")
        self.assertEqual(res["cwe"], "CWE-22")
        self.assertEqual(res["file_path"], "src/polaris_server/files.py")
        self.assertEqual(res["start_line"], 88)
        self.assertEqual(res["corrected_line"], "safe_join(base, path)")

        self.assertTrue(len(captured_messages) > 0)
        prompt_content = captured_messages[0]["content"]
        self.assertIn("PY-SEC-PATH-001", prompt_content)
        self.assertIn("CWE-22", prompt_content)
        self.assertIn("src/polaris_server/files.py", prompt_content)
        self.assertIn("88", prompt_content)
        self.assertIn("INSTRUÇÕES OBRIGATÓRIAS DE ANCORAGEM", prompt_content)

    def test_ai_explain_endpoints_in_api(self) -> None:
        import polaris_server.api as api_mod

        mock_analyze = MagicMock(return_value={
            "status": "ok",
            "verdict": "NEEDS_REVIEW",
            "rule_id": "PY-REL-002",
            "file_path": "src/polaris_server/api.py",
            "start_line": 70,
            "corrected_line": "except OSError:",
        })

        with patch.object(api_mod._ai_service, "analyze_issue", mock_analyze):
            # Test /api/v1/issues/{id}/ai-explain
            r1 = api_mod.ai_explain_issue_v1("10", {"rule_id": "PY-REL-002", "file_path": "src/polaris_server/api.py", "start_line": 70})
            self.assertEqual(r1["status"], "ok")
            self.assertEqual(r1["rule_id"], "PY-REL-002")

            # Test /api/issues/{id}/ai-analyze
            r2 = api_mod.ai_analyze_issue("10", {"rule_id": "PY-REL-002", "file_path": "src/polaris_server/api.py", "start_line": 70})
            self.assertEqual(r2["status"], "ok")

    def test_flow_and_overview_returns_code_snippet(self) -> None:
        import polaris_server.api as api_mod

        # Test get_issue_flow snippet extraction
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (10, "PY-SEC-001", "CWE-89", [], "src/polaris_server/db.py", 10)
        mock_conn = MagicMock()
        mock_conn.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("polaris_server.issues_service.get_connection", return_value=mock_conn):
            flow_res = get_issue_flow("10")
            self.assertEqual(flow_res["issue_id"], "10")
            self.assertEqual(flow_res["rule_id"], "PY-SEC-001")
            self.assertIn("code_snippet", flow_res)
            self.assertIsNotNone(flow_res["code_snippet"])
            self.assertIn("psycopg.connect", flow_res["code_snippet"])

        # Test get_project_overview snippet inclusion
        mock_cur_ov = MagicMock()
        mock_cur_ov.fetchone.side_effect = [
            ("proj-test", "Project Test"),
            ("anl-1", "main", "COMPLETED", 5, "2026-11-26T00:00:00Z"),
        ]
        mock_cur_ov.fetchall.return_value = [
            (1, "PY-SEC-001", "python", "CRITICAL", "src/polaris_server/db.py", 10, "sql injection"),
        ]
        mock_conn_ov = MagicMock()
        mock_conn_ov.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cur_ov

        with patch("polaris_server.api.get_connection", return_value=mock_conn_ov):
            overview_res = api_mod.get_project_overview("proj-test")
            self.assertEqual(len(overview_res["issues"]), 1)
            iss = overview_res["issues"][0]
            self.assertIn("code_snippet", iss)
            self.assertIn("snippet", iss)
            self.assertIsNotNone(iss["code_snippet"])
            self.assertIn("psycopg.connect", iss["code_snippet"])


if __name__ == "__main__":
    unittest.main()
