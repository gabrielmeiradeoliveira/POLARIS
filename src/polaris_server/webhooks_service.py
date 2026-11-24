from __future__ import annotations

import hashlib
import hmac
import ipaddress
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


def validate_webhook_url(url: str) -> str:
    """Validate webhook URL and block SSRF targets (loopback, private, link-local)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Invalid webhook URL scheme or host")
    host = parsed.hostname.lower()
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise ValueError("Loopback webhook targets are forbidden (SSRF protection)")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("Private or reserved IP webhook targets are forbidden")
    except ValueError as exc:
        if "forbidden" in str(exc):
            raise
    return url


def sign_webhook_payload(secret: str, payload: bytes) -> str:
    """Compute HMAC-SHA256 signature for webhook delivery."""
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


from polaris_server.db import get_connection


@dataclass
class WebhookRecord:
    webhook_id: str
    name: str
    url: str
    project_key: str | None = None


class WebhookCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str
    project_key: str | None = None


@router.post("", status_code=201)
def create_webhook(body: WebhookCreateRequest) -> dict[str, Any]:
    try:
        safe_url = validate_webhook_url(body.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    import secrets
    wid = f"wh-{secrets.token_hex(6)}"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO project_webhooks (webhook_id, project_key, url, secret, active) VALUES (%s, %s, %s, %s, TRUE);",
                (wid, body.project_key, safe_url, body.name),
            )
        conn.commit()
    return {"webhook_id": wid, "name": body.name, "url": safe_url, "project_key": body.project_key}


@router.get("")
def list_webhooks() -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT webhook_id, secret, url, project_key FROM project_webhooks WHERE active = TRUE ORDER BY created_at DESC;")
            rows = cur.fetchall()
    items = [{"webhook_id": r[0], "name": r[1], "url": r[2], "project_key": r[3]} for r in rows]
    return {"total": len(items), "items": items}
