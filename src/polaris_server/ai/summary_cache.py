"""PostgreSQL persistence for PR AI summaries (cache survives API restarts)."""

from __future__ import annotations

import json
import logging
from typing import Any

from polaris_server.db import get_connection

logger = logging.getLogger("polaris.ai.summary_cache")

_SELECT = (
    "SELECT payload, estimated_tokens, actual_input_tokens, actual_output_tokens, "
    "actual_total_tokens, saved_tokens "
    "FROM ai_pr_summaries WHERE pr_key = %s AND model = %s AND snippet_hash = %s;"
)


def load_pr_summary(pr_key: str, model: str, snippet_hash: str) -> dict[str, Any] | None:
    """Return the persisted summary payload or None. DB failures never break the endpoint."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_SELECT, (pr_key, model, snippet_hash))
                row = cur.fetchone()
    except Exception as exc:  # pragma: no cover - defensive path
        logger.warning("ai_pr_summaries cache read failed: %s", type(exc).__name__)
        return None
    if not row:
        return None
    payload = row[0]
    if not isinstance(payload, dict):
        payload = json.loads(payload)
    return {
        **payload,
        "estimated_tokens": int(row[1]),
        "actual_input_tokens": int(row[2]),
        "actual_output_tokens": int(row[3]),
        "actual_total_tokens": int(row[4]),
        "saved_tokens": int(row[5]),
    }


def save_pr_summary(pr_key: str, model: str, snippet_hash: str, payload: dict[str, Any]) -> bool:
    """Upsert a successful summary. Returns False on DB failure instead of raising."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_pr_summaries (
                        pr_key, model, snippet_hash, payload,
                        estimated_tokens, actual_input_tokens, actual_output_tokens,
                        actual_total_tokens, saved_tokens
                    ) VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
                    ON CONFLICT (pr_key, model, snippet_hash) DO UPDATE SET
                        payload = EXCLUDED.payload,
                        estimated_tokens = EXCLUDED.estimated_tokens,
                        actual_input_tokens = EXCLUDED.actual_input_tokens,
                        actual_output_tokens = EXCLUDED.actual_output_tokens,
                        actual_total_tokens = EXCLUDED.actual_total_tokens,
                        saved_tokens = EXCLUDED.saved_tokens,
                        updated_at = NOW();
                    """,
                    (
                        pr_key,
                        model,
                        snippet_hash,
                        json.dumps(payload),
                        int(payload.get("estimated_tokens") or 0),
                        int(payload.get("actual_input_tokens") or 0),
                        int(payload.get("actual_output_tokens") or 0),
                        int(payload.get("actual_total_tokens") or 0),
                        int(payload.get("saved_tokens") or 0),
                    ),
                )
            conn.commit()
        return True
    except Exception as exc:  # pragma: no cover - defensive path
        logger.warning("ai_pr_summaries cache write failed: %s", type(exc).__name__)
        return False


def invalidate_pr_summary_cache(pr_key: str) -> bool:
    """Invalidate all cached summaries for a PR key (e.g. after findings triage changes)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM ai_pr_summaries WHERE pr_key = %s;", (pr_key,))
            conn.commit()
        return True
    except Exception as exc:  # pragma: no cover - defensive path
        logger.warning("ai_pr_summaries cache invalidation failed: %s", type(exc).__name__)
        return False
