from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/quality-profiles", tags=["quality-profiles"])


@dataclass
class ProfileRecord:
    profile_id: str
    name: str
    language: str
    is_default: bool = False
    active_rules: dict[str, dict[str, Any]] = field(default_factory=dict)
    projects: set[str] = field(default_factory=set)
    history: list[dict[str, Any]] = field(default_factory=list)


import json
from polaris_server.db import get_connection


class ProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    language: str
    is_default: bool = False


class RuleActivationRequest(BaseModel):
    rule_id: str
    severity: str = "MAJOR"
    params: dict[str, Any] = Field(default_factory=dict)


@router.get("")
def list_profiles(language: str | None = None) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if language:
                cur.execute("SELECT profile_id, name, language, is_default, active_rules FROM quality_profiles WHERE language = %s ORDER BY created_at;", (language,))
            else:
                cur.execute("SELECT profile_id, name, language, is_default, active_rules FROM quality_profiles ORDER BY created_at;")
            rows = cur.fetchall()
    items = [{"profile_id": r[0], "name": r[1], "language": r[2], "is_default": r[3], "active_rules": r[4] or {}, "projects": []} for r in rows]
    return {"total": len(items), "items": items}


@router.post("", status_code=201)
def create_profile(body: ProfileCreateRequest) -> dict[str, Any]:
    pid = f"{body.language}-{body.name.lower().replace(' ', '-')}"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM quality_profiles WHERE profile_id = %s;", (pid,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Profile already exists")
            cur.execute(
                "INSERT INTO quality_profiles (profile_id, name, language, is_default, active_rules) VALUES (%s, %s, %s, %s, '{}'::jsonb);",
                (pid, body.name, body.language, body.is_default),
            )
        conn.commit()
    return {"profile_id": pid, "name": body.name, "language": body.language, "is_default": body.is_default}


@router.post("/{profile_id}/rules/activate")
def activate_rule(profile_id: str, body: RuleActivationRequest) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT active_rules FROM quality_profiles WHERE profile_id = %s;", (profile_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Profile not found")
            rules = dict(row[0] or {})
            rules[body.rule_id] = {"severity": body.severity, "params": body.params}
            cur.execute("UPDATE quality_profiles SET active_rules = %s::jsonb WHERE profile_id = %s;", (json.dumps(rules), profile_id))
        conn.commit()
    return {"profile_id": profile_id, "active_rules": rules}


@router.post("/{profile_id}/rules/{rule_id}/deactivate")
def deactivate_rule(profile_id: str, rule_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT active_rules FROM quality_profiles WHERE profile_id = %s;", (profile_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Profile not found")
            rules = dict(row[0] or {})
            rules.pop(rule_id, None)
            cur.execute("UPDATE quality_profiles SET active_rules = %s::jsonb WHERE profile_id = %s;", (json.dumps(rules), profile_id))
        conn.commit()
    return {"profile_id": profile_id, "active_rules": rules}


@router.post("/{profile_id}/projects/{project_key}")
def associate_project(profile_id: str, project_key: str) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM quality_profiles WHERE profile_id = %s;", (profile_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Profile not found")
    return {"profile_id": profile_id, "projects": [project_key]}


@router.get("/projects/{project_key}/effective-profile")
def get_effective_profile(project_key: str) -> dict[str, Any]:
    import hashlib
    import json as _json

    from polaris_server.config import ServerConfig

    with get_connection(ServerConfig()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT qp.profile_id, qp.name, qp.language
                FROM quality_profiles qp
                JOIN project_quality_profiles pqp ON pqp.profile_id = qp.profile_id
                WHERE pqp.project_key = %s
                ORDER BY qp.profile_id;
                """,
                (project_key,),
            )
            profiles = cur.fetchall()
            profile_ids = [p[0] for p in profiles]
            enabled: list[str] = []
            disabled: list[str] = []
            params: dict[str, Any] = {}
            if profile_ids:
                cur.execute(
                    "SELECT rule_id, enabled, params_json FROM profile_rules WHERE profile_id = ANY(%s) ORDER BY rule_id;",
                    (profile_ids,),
                )
                for rid, is_enabled, pjson in cur.fetchall():
                    if is_enabled:
                        enabled.append(rid)
                        if pjson:
                            params[rid] = pjson if isinstance(pjson, dict) else _json.loads(pjson)
                    else:
                        disabled.append(rid)
    payload = {"enabledRules": sorted(set(enabled)), "disabledRules": sorted(set(disabled)), "parameters": params}
    digest = hashlib.sha256(_json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return {"projectKey": project_key, "profileHash": digest, **payload}
