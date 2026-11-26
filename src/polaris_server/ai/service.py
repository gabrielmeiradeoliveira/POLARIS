from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from typing import Any

from polaris_server.ai.provider import call_chat_completions

_LEGACY_MARKERS = ("SqlCommand", "DataSet", "DataTable", "BinaryFormatter", "WebForms", "mysql_query", "<?php")


def estimate_tokens(text: str) -> int:
    """Deterministic token estimator (~4 chars/token)."""
    return max(1, len(text) // 4)


_SEV_RANK = {"BLOCKER": 5, "CRITICAL": 4, "MAJOR": 3, "MINOR": 2, "INFO": 1}
_CONF_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

TOKEN_FIELDS = (
    "estimated_tokens",
    "actual_input_tokens",
    "actual_output_tokens",
    "actual_total_tokens",
    "saved_tokens",
)


def build_token_metrics(
    *,
    estimated_tokens: int,
    actual_input_tokens: int,
    actual_output_tokens: int = 0,
    actual_total_tokens: int | None = None,
    saved_tokens: int | None = None,
) -> dict[str, int]:
    """Single source of truth for the 5 token fields returned by the AI endpoints."""
    est = max(0, int(estimated_tokens))
    actual_in = max(0, int(actual_input_tokens))
    actual_out = max(0, int(actual_output_tokens))
    actual_total = max(0, int(actual_in + actual_out if actual_total_tokens is None else actual_total_tokens))
    saved = max(0, est - actual_total) if saved_tokens is None else max(0, int(saved_tokens))
    return {
        "estimated_tokens": est,
        "actual_input_tokens": actual_in,
        "actual_output_tokens": actual_out,
        "actual_total_tokens": actual_total,
        "saved_tokens": saved,
    }


def ensure_token_metrics(result: dict[str, Any], *, estimated_fallback: int = 0) -> dict[str, Any]:
    """Guarantee the 5 token fields exist even on error, disabled or budget paths."""
    estimated = result.get("estimated_tokens", estimated_fallback)
    metrics = build_token_metrics(
        estimated_tokens=int(estimated or 0),
        actual_input_tokens=int(result.get("actual_input_tokens") or 0),
        actual_output_tokens=int(result.get("actual_output_tokens") or 0),
        actual_total_tokens=int(result.get("actual_total_tokens") or result.get("tokens_used") or 0),
        saved_tokens=int(result.get("saved_tokens") or 0),
    )
    return {**result, **metrics}


def compact_pr_context(pr_key: str, issues: Any, max_chars: int = 3500) -> tuple[str, dict[str, Any]]:
    """Build O(1)-bounded PR summary context (<= max_chars) with Top-5 priority findings.

    Defensively filters non-iterable issues and invalid/null issue entries.
    """
    valid_issues: list[dict[str, Any]] = []
    if isinstance(issues, (list, tuple, set)):
        valid_issues = [i for i in issues if isinstance(i, dict)]

    sev_counts: dict[str, int] = {}
    for i in valid_issues:
        s = str(i.get("severity") or "MAJOR").upper()
        sev_counts[s] = sev_counts.get(s, 0) + 1
    ranked = sorted(
        valid_issues,
        key=lambda i: (
            _SEV_RANK.get(str(i.get("severity") or "MAJOR").upper(), 0),
            _CONF_RANK.get(str(i.get("confidence") or "HIGH").upper(), 0),
        ),
        reverse=True,
    )
    top5 = [
        {
            "rule_id": i.get("ruleId") or i.get("rule_id"),
            "severity": i.get("severity"),
            "loc": f"{i.get('file_path') or (i.get('location') or {}).get('file') or ''}:{i.get('start_line') or (i.get('location') or {}).get('startLine') or 1}",
            "msg": str(i.get("message", ""))[:120],
            "snippet": str(i.get("snippet") or i.get("code_snippet") or "")[:200],
        }
        for i in ranked[:5]
    ]
    omitted = max(0, len(valid_issues) - len(top5))
    text = json.dumps({"pr": pr_key, "total": len(valid_issues), "severities": sev_counts, "top5": top5}, ensure_ascii=False)[:max_chars]
    return text, {"context_compacted": True, "total_findings_omitted": omitted}


def extract_structured_ai_json(raw: str, original_snippet: str = "", start_line: int | None = None) -> dict[str, Any]:
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
                verdict = parsed.get("verdict", "NEEDS_REVIEW")
                summary = parsed.get("summary", "")
                suggested = parsed.get("suggested_snippet") or parsed.get("suggestedSnippet") or ""
                needs_refactor = bool(parsed.get("needs_broader_refactor", False))
                diff_before = parsed.get("diff_before") or original_snippet
                diff_after = parsed.get("diff_after") or suggested
                corrected_line = parsed.get("corrected_line") or (suggested.splitlines()[0] if suggested else "")
                return {
                    "verdict": verdict,
                    "summary": summary,
                    "suggested_snippet": suggested,
                    "needs_broader_refactor": needs_refactor,
                    "diff_before": diff_before,
                    "diff_after": diff_after,
                    "corrected_line": corrected_line,
                    "start_line": start_line,
                }
        except json.JSONDecodeError:
            pass
    return {
        "verdict": "NEEDS_REVIEW",
        "summary": "",
        "suggested_snippet": "",
        "needs_broader_refactor": False,
        "diff_before": original_snippet,
        "diff_after": "",
        "corrected_line": "",
        "start_line": start_line,
    }


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

    def model_name(self) -> str:
        return os.environ.get("POLARIS_AI_MODEL", "qwen2.5-coder:3b").strip()

    def analyze_issue(
        self,
        *,
        fingerprint: str,
        rule_id: str,
        severity: str,
        language: str,
        snippet: str,
        cwe: str | None = None,
        file_path: str | None = None,
        start_line: int | None = None,
        flow_steps: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        model = self.model_name()
        snippet_hash = hashlib.sha256(snippet.encode("utf-8")).hexdigest()
        cache_key = (fingerprint, snippet_hash, model)
        if cache_key in self._cache:
            cached_out = self._cache[cache_key]
            est = int(cached_out.get("estimated_tokens", 500) or 500)
            return {
                **cached_out,
                "cached": True,
                **build_token_metrics(
                    estimated_tokens=est,
                    actual_input_tokens=0,
                    actual_total_tokens=0,
                    saved_tokens=est,
                ),
            }

        max_tokens = compute_adaptive_max_tokens(language=language, snippet=snippet, flow_steps=flow_steps)
        est_in = estimate_tokens(snippet)
        est_total = est_in + max_tokens

        budget = int(os.environ.get("POLARIS_AI_DAILY_TOKEN_BUDGET", "50000"))
        if self.tokens_used_today() >= budget:
            return {
                "status": "budget_exceeded",
                "cached": False,
                "tokens_used": 0,
                **build_token_metrics(
                    estimated_tokens=est_total, actual_input_tokens=0, actual_total_tokens=0, saved_tokens=0
                ),
            }

        loc_desc = f"{file_path or 'unknown'}:{start_line or 1}"
        prompt = (
            f"Você é um especialista em AppSec e qualidade de software analisando um achado estático específico.\n"
            f"Alvo:\n"
            f"- Regra: {rule_id}\n"
            f"- Severidade: {severity}\n"
            f"- CWE: {cwe or 'N/A'}\n"
            f"- Arquivo: {file_path or 'N/A'}\n"
            f"- Linha: {start_line or 'N/A'} (Localização: {loc_desc})\n"
            f"- Linguagem: {language}\n\n"
            f"Fluxo de execução / Taint steps:\n{json.dumps(flow_steps or [], ensure_ascii=False)}\n\n"
            f"Trecho de código real analisado:\n{snippet}\n\n"
            f"INSTRUÇÕES OBRIGATÓRIAS DE ANCORAGEM:\n"
            f"1. Sua análise DEVE focar estritamente na regra '{rule_id}' no arquivo '{file_path or 'alvo'}' e na linha '{start_line or 'alvo'}'.\n"
            f"2. NUNCA dê respostas genéricas sobre regras não relacionadas (ex: não fale de shell=True se a regra for Path Traversal ou Resource Leak; não fale de SQL Injection se for XSS ou Reliability).\n"
            f"3. Explique a causa raiz exata e apresente uma correção cirúrgica (suggested_snippet) preservando o contexto da linha original.\n"
            f"4. Responda APENAS em JSON válido contendo:\n"
            f"   - verdict: (CONFIRMED_EXPLOITABLE | LIKELY_FALSE_POSITIVE | NEEDS_REVIEW)\n"
            f"   - summary: (2-3 frases objetivas em português explicando o impacto e a causa na regra {rule_id})\n"
            f"   - suggested_snippet: (código corrigido específico substituindo ou corrigindo o trecho)\n"
            f"   - corrected_line: (a linha de código corrigida correspondente à linha original {start_line or 1})\n"
            f"   - diff_before: (linha ou trecho original com o problema)\n"
            f"   - diff_after: (linha ou trecho corrigido)\n"
            f"   - needs_broader_refactor: (boolean)\n"
        )
        res = call_chat_completions(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            model=model,
        )
        if res["status"] != "ok":
            return {
                **res,
                "cached": False,
                "max_tokens_applied": max_tokens,
                **build_token_metrics(
                    estimated_tokens=est_total, actual_input_tokens=0, actual_total_tokens=0, saved_tokens=0
                ),
            }

        today = self._today_key()
        used = res.get("tokens_used", 0)
        est_in = estimate_tokens(prompt)
        est_total = est_in + max_tokens
        self._daily_tokens[today] = self._daily_tokens.get(today, 0) + used
        structured = extract_structured_ai_json(res["content"] or "", original_snippet=snippet, start_line=start_line)
        out = {
            "status": "ok",
            "cached": False,
            "model": model,
            "max_tokens_applied": max_tokens,
            "tokens_used": used,
            "rule_id": rule_id,
            "cwe": cwe,
            "file_path": file_path,
            "start_line": start_line,
            **build_token_metrics(
                estimated_tokens=est_total,
                actual_input_tokens=est_in,
                actual_output_tokens=max(0, used - est_in),
                actual_total_tokens=used,
            ),
            **structured,
            "raw_response": res["content"],
        }
        self._cache[cache_key] = out
        return out
