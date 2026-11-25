from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from polaris_server.ai.provider import call_chat_completions
from polaris_server.ai.service import AiTriageService, compact_pr_context, compute_adaptive_max_tokens, extract_structured_ai_json


class TestAiLayer(unittest.TestCase):
    def test_disabled_when_base_url_empty(self) -> None:
        res = call_chat_completions(messages=[{"role": "user", "content": "hi"}], max_tokens=500, base_url="")
        self.assertEqual(res["status"], "disabled")

    def test_adaptive_token_calibration_500_vs_1200(self) -> None:
        self.assertEqual(compute_adaptive_max_tokens(language="python", snippet="os.system(x)", flow_steps=[{"a": 1}]), 500)
        self.assertEqual(compute_adaptive_max_tokens(language="csharp", snippet="new SqlCommand(q)", flow_steps=[]), 1200)

    def test_cache_hit_and_daily_budget(self) -> None:
        svc = AiTriageService()
        with patch.dict(os.environ, {"POLARIS_AI_BASE_URL": "http://localhost:11434/v1", "POLARIS_AI_DAILY_TOKEN_BUDGET": "100"}):
            with patch("polaris_server.ai.service.call_chat_completions", return_value={"status": "ok", "content": "{}", "tokens_used": 60}):
                r1 = svc.analyze_issue(fingerprint="fp1", rule_id="PY-SEC-001", severity="CRITICAL", language="python", snippet="os.system(x)")
                self.assertFalse(r1["cached"])
                self.assertEqual(r1["max_tokens_applied"], 500)
                r2 = svc.analyze_issue(fingerprint="fp1", rule_id="PY-SEC-001", severity="CRITICAL", language="python", snippet="os.system(x)")
                self.assertTrue(r2["cached"])
                self.assertEqual(svc.tokens_used_today(), 60)

                with patch.dict(os.environ, {"POLARIS_AI_DAILY_TOKEN_BUDGET": "50"}):
                    r3 = svc.analyze_issue(fingerprint="fp2", rule_id="PY-SEC-001", severity="CRITICAL", language="python", snippet="eval(x)")
                    self.assertEqual(r3["status"], "budget_exceeded")

    def test_extract_structured_ai_json_and_fallback(self) -> None:
        fenced = '```json\n{"verdict":"CONFIRMED_EXPLOITABLE","summary":"ok","suggested_snippet":"x()","needs_broader_refactor":true}\n```'
        parsed = extract_structured_ai_json(fenced)
        self.assertEqual(parsed["verdict"], "CONFIRMED_EXPLOITABLE")
        self.assertEqual(parsed["suggested_snippet"], "x()")
        self.assertTrue(parsed["needs_broader_refactor"])
        fb = extract_structured_ai_json("not json")
        self.assertEqual(fb["verdict"], "NEEDS_REVIEW")

    def test_mega_pr_84k_lines_compacted_o1(self) -> None:
        issues = [{"ruleId": f"R-{i}", "severity": "CRITICAL" if i < 10 else "MINOR", "file_path": f"f{i}.py", "start_line": i + 1, "message": "x" * 200} for i in range(120)]
        ctx, meta = compact_pr_context("PR-84K", issues, max_chars=3500)
        self.assertLessEqual(len(ctx), 3500)
        self.assertTrue(meta["context_compacted"])
        self.assertEqual(meta["total_findings_omitted"], 115)


if __name__ == "__main__":
    unittest.main()
