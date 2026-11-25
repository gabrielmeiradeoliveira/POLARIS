from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def call_chat_completions(
    *,
    messages: list[dict[str, str]],
    max_tokens: int,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Pure-stdlib HTTP client for OpenAI-compatible /v1/chat/completions endpoints."""
    url_base = (base_url if base_url is not None else os.environ.get("POLARIS_AI_BASE_URL", "")).strip().rstrip("/")
    if not url_base:
        return {"status": "disabled", "content": None, "tokens_used": 0}

    key = (api_key if api_key is not None else os.environ.get("POLARIS_AI_API_KEY", "")).strip()
    mdl = (model if model is not None else os.environ.get("POLARIS_AI_MODEL", "qwen2.5-coder:3b")).strip()
    tout = timeout if timeout is not None else int(os.environ.get("POLARIS_AI_TIMEOUT", "60"))

    endpoint = f"{url_base}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    body = json.dumps({
        "model": mdl,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }).encode("utf-8")

    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=tout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices") or []
        content = choices[0]["message"]["content"] if choices else ""
        usage = data.get("usage") or {}
        tokens = int(usage.get("total_tokens", 0))
        return {"status": "ok", "content": content, "tokens_used": tokens, "model": mdl}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError) as exc:
        return {"status": "error", "error": str(exc), "content": None, "tokens_used": 0}
