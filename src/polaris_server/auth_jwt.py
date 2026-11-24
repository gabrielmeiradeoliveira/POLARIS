from __future__ import annotations

import hashlib
import hmac
import json
import base64
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key(prefix: str = "pls_live_") -> tuple[str, str, str]:
    token = secrets.token_hex(16)
    raw = f"{prefix}{token}"
    return raw, raw[:12], hash_api_key(raw)


def create_jwt(payload: dict[str, Any], secret: str | None = None, ttl_seconds: int = 3600) -> str:
    sec = secret or os.environ.get("POLARIS_JWT_SECRET", "polaris-dev-secret")
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    body_dict = {**payload, "exp": int(time.time()) + ttl_seconds}
    body = base64.urlsafe_b64encode(json.dumps(body_dict).encode()).rstrip(b"=").decode()
    sig_raw = hmac.new(sec.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    sig = base64.urlsafe_b64encode(sig_raw).rstrip(b"=").decode()
    return f"{header}.{body}.{sig}"


def verify_jwt(token: str, secret: str | None = None) -> dict[str, Any] | None:
    try:
        sec = secret or os.environ.get("POLARIS_JWT_SECRET", "polaris-dev-secret")
        header, body, sig = token.split(".")
        expected_raw = hmac.new(sec.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
        expected = base64.urlsafe_b64encode(expected_raw).rstrip(b"=").decode()
        if not hmac.compare_digest(sig, expected):
            return None
        padded = body + "=" * (-len(body) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded).decode())
        if int(data.get("exp", 0)) < int(time.time()):
            return None
        return data
    except Exception:
        return None
