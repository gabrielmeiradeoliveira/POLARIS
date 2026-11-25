from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from typing import Any

from polaris_server.ai.provider import call_chat_completions

_LEGACY_MARKERS = ("SqlCommand", "DataSet", "DataTable", "BinaryFormatter", "WebForms", "mysql_query", "<?php")


def extract_structured_ai_json(raw: str) -> dict[str, Any]:
    """Extract verdict, summary, suggested_snippet, and needs_broader_refactor from fenced or raw LLM output."""
    text = raw.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            cleaned = part.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            if cleaned.startswith("{") and "}" in cleaned:
                text = cleaned
                break
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return {
                    "verdict": parsed.get("verdict", "NEEDS_REVIEW"),
                    "summary": parsed.get("summary", ""),
                    "suggested_snippet": parsed.get("suggested_snippet", ""),
                    "needs_broader_refactor": bool(parsed.get("needs_broader_refactor", False)),
                }
        except json.JSONDecodeError:
            pass
    return {"verdict": "NEEDS_REVIEW", "summary": "", "suggested_snippet": "", "needs_broader_refactor": False}


def compute_adaptive_max_tokens(
    *,
    language: str,
    snippet: str,
    flow_steps: list[dict[str, Any]] | None = None,
) -> int:
    """Return 500 for modern/lean code or 1200 for legacy/high-coupling monoliths."""
    modern_max = int(os.environ.get("POLARIS_AI_MAX_TOKENS_MODERN", "500"))
    legacy_max = int(os.environ.get("POLARIS_AI_MAX_TOKENS_LEGACY", "1200"))
    steps = flow_steps or []
    if len(steps) >= 3 or any(m in snippet for m in _LEGACY_MARKERS) or language.lower() in {"php", "legacy"}:
        return legacy_max
    return modern_max


class AiTriageService:
    """Surgical on-demand AI triage with (fingerprint, snippet_hash, model) cache and daily token budget."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._daily_tokens: dict[str, int] = {}

    def _today_key(self) -> str:
        return date.today().isoformat()

    def tokens_used_today(self) -> int:
        return self._daily_tokens.get(self._today_key(), 0)

    def status(self) -> dict[str, Any]:
        base_url = os.environ.get("POLARIS_AI_BASE_URL", "").strip()
        return {
            "enabled": bool(base_url),
            "provider_url": base_url or None,
            "model": os.environ.get("POLARIS_AI_MODEL", "qwen2.5-coder:3b"),
            "tokens_used_today": self.tokens_used_today(),
            "daily_budget": int(os.environ.get("POLARIS_AI_DAILY_TOKEN_BUDGET", "50000")),
        }

    def analyze_issue(
        self,
        *,
        fingerprint: str,
        rule_id: str,
        severity: str,
        language: str,
        snippet: str,
        cwe: str | None = None,
        flow_steps: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        model = os.environ.get("POLARIS_AI_MODEL", "qwen2.5-coder:3b").strip()
        snippet_hash = hashlib.sha256(snippet.encode("utf-8")).hexdigest()
        cache_key = (fingerprint, snippet_hash, model)
        if cache_key in self._cache:
            return {**self._cache[cache_key], "cached": True}

        budget = int(os.environ.get("POLARIS_AI_DAILY_TOKEN_BUDGET", "50000"))
        if self.tokens_used_today() >= budget:
            return {"status": "budget_exceeded", "cached": False, "tokens_used": 0}

        max_tokens = compute_adaptive_max_tokens(language=language, snippet=snippet, flow_steps=flow_steps)
        prompt = (
            f"Regra: {rule_id} ({severity}, {cwe or 'N/A'}) em {language}.\n"
            f"Flow: {json.dumps(flow_steps or [], ensure_ascii=False)}\n"
            f"Codigo:\n{snippet}\n\n"
            "Regras obrigatorias de remediacao segura: NUNCA sugira shell=True, eval(), exec() ou concatenacao de strings em SQL/comandos. "
            "Para command injection em Python, use subprocess.run([...], shell=False) com lista de argumentos ou allowlist. "
            "Para SQL injection, use queries parametrizadas (SqlParameter, %s ou ?).\n"
            "Responda APENAS em JSON valido com: verdict (CONFIRMED_EXPLOITABLE|LIKELY_FALSE_POSITIVE|NEEDS_REVIEW), "
            "summary (2-3 frases em portugues), suggested_snippet (codigo corrigido completo), needs_broader_refactor (bool)."
        )
        res = call_chat_completions(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            model=model,
        )
        if res["status"] != "ok":
            return {**res, "cached": False, "max_tokens_applied": max_tokens}

        today = self._today_key()
        self._daily_tokens[today] = self._daily_tokens.get(today, 0) + res.get("tokens_used", 0)
        structured = extract_structured_ai_json(res["content"] or "")
        out = {
            "status": "ok",
            "cached": False,
            "model": model,
            "max_tokens_applied": max_tokens,
            "tokens_used": res.get("tokens_used", 0),
            **structured,
            "raw_response": res["content"],
        }
        self._cache[cache_key] = out
        return out
