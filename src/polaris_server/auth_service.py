from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from polaris_server.db import get_connection

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "GLOBAL_ADMIN": {"ADMIN_USERS", "ADMIN_PROJECTS", "ANALYZE", "ISSUE_ADMIN", "VIEW"},
    "PROJECT_ADMIN": {"ADMIN_PROJECTS", "ANALYZE", "ISSUE_ADMIN", "VIEW"},
    "ANALYZER": {"ANALYZE", "VIEW"},
    "VIEWER": {"VIEW"},
}


def hash_password(password: str, salt: bytes | None = None) -> str:
    s = salt or secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=s, n=16384, r=8, p=1)
    return f"{s.hex()}:{dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt_hex, dk_hex = stored.split(":", 1)
    expected = hash_password(password, bytes.fromhex(salt_hex)).split(":", 1)[1]
    return hmac.compare_digest(expected, dk_hex)


@dataclass
class UserRecord:
    username: str
    password_hash: str
    role: str = "VIEWER"
    active: bool = True


@dataclass
class TokenRecord:
    token_id: str
    name: str
    username: str
    token_hash: str
    revoked: bool = False


def record_audit(action: str, actor: str, target: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO polaris_audit_log (action, actor, target) VALUES (%s, %s, %s);",
                (action, actor, target),
            )
        conn.commit()


def check_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role: str = "VIEWER"


class TokenCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    username: str


@router.post("/users", status_code=201)
def create_user(body: UserCreateRequest) -> dict[str, Any]:
    if body.role not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=400, detail="Invalid role")
    pw_hash = hash_password(body.password)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM polaris_users WHERE username = %s;", (body.username,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="User already exists")
            cur.execute(
                "INSERT INTO polaris_users (username, password_hash, role, active) VALUES (%s, %s, %s, TRUE);",
                (body.username, pw_hash, body.role),
            )
            cur.execute(
                "INSERT INTO polaris_audit_log (action, actor, target) VALUES (%s, %s, %s);",
                ("USER_CREATED", "system", body.username),
            )
        conn.commit()
    return {"username": body.username, "role": body.role, "active": True}


@router.post("/tokens", status_code=201)
def create_token(body: TokenCreateRequest) -> dict[str, Any]:
    raw = f"pol_{secrets.token_urlsafe(24)}"
    tid = f"tok-{secrets.token_hex(8)}"
    thash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM polaris_users WHERE username = %s AND active = TRUE;", (body.username,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="User not found or inactive")
            cur.execute(
                "INSERT INTO polaris_tokens (token_id, name, username, token_hash, revoked) VALUES (%s, %s, %s, %s, FALSE);",
                (tid, body.name, body.username, thash),
            )
            cur.execute(
                "INSERT INTO polaris_audit_log (action, actor, target) VALUES (%s, %s, %s);",
                ("TOKEN_CREATED", body.username, tid),
            )
        conn.commit()
    return {"token_id": tid, "name": body.name, "token": raw}


@router.post("/tokens/{token_id}/revoke")
def revoke_token(token_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT username FROM polaris_tokens WHERE token_id = %s;", (token_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Token not found")
            cur.execute("UPDATE polaris_tokens SET revoked = TRUE WHERE token_id = %s;", (token_id,))
            cur.execute(
                "INSERT INTO polaris_audit_log (action, actor, target) VALUES (%s, %s, %s);",
                ("TOKEN_REVOKED", row[0], token_id),
            )
        conn.commit()
    return {"token_id": token_id, "revoked": True}


@router.get("/audit")
def get_audit_log() -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT at, action, actor, target FROM polaris_audit_log ORDER BY id DESC LIMIT 200;")
            rows = cur.fetchall()
    items = [{"at": r[0].isoformat(), "action": r[1], "actor": r[2], "target": r[3]} for r in rows]
    return {"total": len(items), "items": items}


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


@router.post("/auth/login")
def login(body: LoginRequest) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash, role, active FROM users WHERE username = %s;", (body.username,))
            row = cur.fetchone()
            if not row or not bool(row[2]) or not verify_password(body.password, row[0]):
                raise HTTPException(status_code=401, detail="Credenciais inválidas ou usuário inativo")
            import hashlib as _hashlib
            import uuid as _uuid

            raw_token = secrets.token_urlsafe(24)
            token_id = f"sess-{_uuid.uuid4().hex[:10]}"
            cur.execute(
                "INSERT INTO api_tokens (token_id, username, token_hash, revoked) VALUES (%s, %s, %s, FALSE);",
                (token_id, body.username, _hashlib.sha256(raw_token.encode("utf-8")).hexdigest()),
            )
        conn.commit()
    return {"token": raw_token, "token_id": token_id, "username": body.username, "role": row[1]}


@router.post("/auth/logout")
def logout(token_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE api_tokens SET revoked = TRUE WHERE token_id = %s;", (token_id,))
        conn.commit()
    return {"revoked": True, "token_id": token_id}


@router.get("/auth/me")
def auth_me(request: Any) -> dict[str, Any]:
    import hashlib as _hashlib

    auth_header = request.headers.get("authorization", "") if hasattr(request, "headers") else ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token ausente")
    raw = auth_header[7:].strip()
    thash = _hashlib.sha256(raw.encode("utf-8")).hexdigest()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.username, u.role, u.active, t.revoked
                FROM api_tokens t
                JOIN users u ON u.username = t.username
                WHERE t.token_hash = %s;
                """,
                (thash,),
            )
            row = cur.fetchone()
            if not row or not bool(row[2]) or bool(row[3]):
                raise HTTPException(status_code=401, detail="Sessão inválida ou expirada")
    return {"username": row[0], "role": row[1]}


@router.get("/admin/users")
def list_users() -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT username, role, active, created_at FROM users ORDER BY username;")
            rows = cur.fetchall()
    return {
        "total": len(rows),
        "items": [
            {
                "username": r[0],
                "role": r[1],
                "active": bool(r[2]),
                "created_at": r[3].isoformat() if hasattr(r[3], "isoformat") else str(r[3]),
            }
            for r in rows
        ],
    }


@router.patch("/admin/users/{username}/status")
def set_user_status(username: str, active: bool) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET active = %s WHERE username = %s RETURNING username;", (active, username))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Usuário não encontrado")
        conn.commit()
    return {"username": username, "active": active}


@router.get("/admin/tokens")
def list_tokens() -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT token_id, username, revoked, expires_at, created_at FROM api_tokens ORDER BY created_at DESC;")
            rows = cur.fetchall()
    return {
        "total": len(rows),
        "items": [
            {
                "token_id": r[0],
                "username": r[1],
                "revoked": bool(r[2]),
                "expires_at": r[3].isoformat() if r[3] and hasattr(r[3], "isoformat") else (str(r[3]) if r[3] else None),
                "created_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
            }
            for r in rows
        ],
    }
