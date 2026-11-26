from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from polaris_server.ai.provider import call_chat_completions
from polaris_server.ai.service import (
    TOKEN_FIELDS,
    AiTriageService,
    compact_pr_context,
    compute_adaptive_max_tokens,
    ensure_token_metrics,
    estimate_tokens,
    extract_structured_ai_json,
)


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

    def test_error_paths_always_include_the_five_token_fields(self) -> None:
        disabled = ensure_token_metrics({"status": "disabled", "cached": False, "tokens_used": 0}, estimated_fallback=640)
        for field in TOKEN_FIELDS:
            self.assertIn(field, disabled)
        self.assertEqual(disabled["estimated_tokens"], 640)
        self.assertEqual(disabled["actual_total_tokens"], 0)
        self.assertEqual(disabled["saved_tokens"], 0)

    def test_pr_summary_endpoint_returns_token_fields_on_first_generation(self) -> None:
        import polaris_server.api as api_mod
        from polaris_server.ai import summary_cache

        generated = {
            "status": "ok",
            "cached": False,
            "model": "qwen2.5-coder:3b",
            "verdict": "NEEDS_REVIEW",
            "summary": "ok",
            "estimated_tokens": 900,
            "actual_input_tokens": 400,
            "actual_output_tokens": 100,
            "actual_total_tokens": 500,
            "saved_tokens": 400,
        }
        with patch.object(api_mod._ai_service, "analyze_issue", return_value=generated), patch.object(
            summary_cache, "load_pr_summary", return_value=None
        ), patch.object(summary_cache, "save_pr_summary", return_value=True) as save:
            out = api_mod.ai_pr_summary("PR-1", {"issues": [{"severity": "CRITICAL"}]})

        for field in TOKEN_FIELDS:
            self.assertIn(field, out)
        self.assertEqual(out["status"], "ok")
        self.assertFalse(out["cached"])
        save.assert_called_once()

    def test_pr_summary_endpoint_returns_all_token_fields_on_cache_hit(self) -> None:
        import polaris_server.api as api_mod
        from polaris_server.ai import summary_cache

        stored = {
            "status": "ok",
            "cached": False,
            "verdict": "NEEDS_REVIEW",
            "summary": "cached",
            "estimated_tokens": 900,
            "actual_input_tokens": 400,
            "actual_output_tokens": 100,
            "actual_total_tokens": 500,
            "saved_tokens": 400,
        }
        with patch.object(summary_cache, "load_pr_summary", return_value=stored):
            out = api_mod.ai_pr_summary("PR-1", {"issues": []})

        for field in TOKEN_FIELDS:
            self.assertIn(field, out)
        self.assertTrue(out["cached"])
        self.assertEqual(out["actual_input_tokens"], 0)
        self.assertEqual(out["actual_output_tokens"], 0)
        self.assertEqual(out["actual_total_tokens"], 0)
        self.assertEqual(out["estimated_tokens"], 900)
        self.assertEqual(out["saved_tokens"], 900)

    def test_mega_pr_84k_lines_compacted_o1(self) -> None:
        issues = [{"ruleId": f"R-{i}", "severity": "CRITICAL" if i < 10 else "MINOR", "file_path": f"f{i}.py", "start_line": i + 1, "message": "x" * 200} for i in range(120)]
        ctx, meta = compact_pr_context("PR-84K", issues, max_chars=3500)
        self.assertLessEqual(len(ctx), 3500)
        self.assertTrue(meta["context_compacted"])
        self.assertEqual(meta["total_findings_omitted"], 115)
        self.assertLessEqual(estimate_tokens(ctx), 875)

    def test_compact_pr_context_and_endpoint_defensive_against_invalid_issues(self) -> None:
        import json
        import polaris_server.api as api_mod
        from polaris_server.ai import summary_cache

        invalid_cases = [None, 123, "not-a-list", {"a": 1}, True, False]
        for bad_issues in invalid_cases:
            ctx, meta = compact_pr_context("PR-DEF", bad_issues)
            self.assertTrue(meta["context_compacted"])
            self.assertEqual(meta["total_findings_omitted"], 0)
            data = json.loads(ctx)
            self.assertEqual(data["total"], 0)
            self.assertEqual(data["top5"], [])

        # List with nulls, primitives, dicts with None severity
        mixed = [None, "invalid", 42, {}, {"severity": None}, {"severity": "CRITICAL", "message": "SQLi"}]
        ctx, meta = compact_pr_context("PR-DEF-MIXED", mixed)
        data = json.loads(ctx)
        self.assertEqual(data["total"], 3)  # {}, {"severity": None}, {"severity": "CRITICAL", ...}
        self.assertIn("CRITICAL", data["severities"])
        self.assertEqual(data["severities"]["CRITICAL"], 1)

        # Integration via endpoint with bad payload types
        with patch.object(summary_cache, "load_pr_summary", return_value=None), patch.object(
            summary_cache, "save_pr_summary", return_value=True
        ), patch.object(
            api_mod._ai_service,
            "analyze_issue",
            return_value={"status": "ok", "verdict": "CONFIRMED", "tokens_used": 10},
        ):
            res_null = api_mod.ai_pr_summary("PR-DEF", {"issues": None})
            self.assertEqual(res_null["status"], "ok")
            for field in TOKEN_FIELDS:
                self.assertIn(field, res_null)

            res_str = api_mod.ai_pr_summary("PR-DEF", {"issues": "corrupted"})
            self.assertEqual(res_str["status"], "ok")

            res_items_null = api_mod.ai_pr_summary("PR-DEF", {"issues": [None, 123, {"severity": "BLOCKER"}]})
            self.assertEqual(res_items_null["status"], "ok")


if __name__ == "__main__":
    unittest.main()
