from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from polaris_server.domain_core import evaluate_quality_gate

router = APIRouter(prefix="/api/v1/quality-gates", tags=["quality-gates"])


@dataclass
class GateRecord:
    gate_id: str
    name: str
    is_default: bool = False
    conditions: list[dict[str, Any]] = field(default_factory=list)
    projects: set[str] = field(default_factory=set)


import json
from polaris_server.db import get_connection


class GateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    is_default: bool = False


class GateEvaluateRequest(BaseModel):
    metrics: dict[str, float]
    issues: list[dict[str, Any]] | None = None


@router.get("")
def list_gates() -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT gate_id, name, is_default, conditions FROM quality_gates ORDER BY created_at;")
            rows = cur.fetchall()
    items = [
        {"gate_id": r[0], "name": r[1], "is_default": r[2], "conditions": r[3] or [], "projects": []}
        for r in rows
    ]
    return {"total": len(items), "items": items}


@router.post("", status_code=201)
def create_gate(body: GateCreateRequest) -> dict[str, Any]:
    gid = body.name.lower().replace(" ", "-")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM quality_gates WHERE gate_id = %s;", (gid,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Quality Gate already exists")
            cur.execute(
                "INSERT INTO quality_gates (gate_id, name, is_default, conditions) VALUES (%s, %s, %s, %s::jsonb);",
                (gid, body.name, body.is_default, json.dumps(body.conditions)),
            )
        conn.commit()
    return {"gate_id": gid, "name": body.name, "conditions": body.conditions}


@router.post("/{gate_id}/evaluate")
def evaluate_gate_endpoint(gate_id: str, body: GateEvaluateRequest) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT conditions FROM quality_gates WHERE gate_id = %s;", (gate_id,))
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Quality Gate not found")
    return evaluate_quality_gate(body.metrics, row[0] or [], issues=body.issues)


@router.post("/{gate_id}/projects/{project_key}")
def assign_gate_to_project(gate_id: str, project_key: str) -> dict[str, str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM quality_gates WHERE gate_id = %s;", (gate_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Quality gate não encontrado")
            cur.execute(
                """
                INSERT INTO project_quality_gates (project_key, gate_id)
                VALUES (%s, %s)
                ON CONFLICT (project_key) DO UPDATE SET gate_id = EXCLUDED.gate_id;
                """,
                (project_key, gate_id),
            )
        conn.commit()
    return {"projectKey": project_key, "gateId": gate_id}


def evaluate_project_gate(
    conn: Any,
    project_key: str,
    analysis_id: str,
    metrics: dict[str, Any],
    analysis_status: str = "COMPLETED",
    issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if analysis_status != "COMPLETED":
        return {"status": "NOT_COMPUTED", "conditions": [], "analysisId": analysis_id}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT qg.gate_id, qg.conditions_json
            FROM quality_gates qg
            LEFT JOIN project_quality_gates pqg ON pqg.gate_id = qg.gate_id AND pqg.project_key = %s
            WHERE pqg.project_key IS NOT NULL OR qg.is_default = TRUE
            ORDER BY (pqg.project_key IS NOT NULL) DESC, qg.gate_id
            LIMIT 1;
            """,
            (project_key,),
        )
        row = cur.fetchone()
    if not row:
        return {"status": "PASSED", "conditions": [], "analysisId": analysis_id}
    res = evaluate_quality_gate(metrics, row[1] or [], issues=issues)
    return {**res, "gateId": row[0], "analysisId": analysis_id}


@router.put("/{gate_id}")
def update_gate(gate_id: str, body: GateCreateRequest) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE quality_gates SET name = %s, conditions_json = %s::jsonb WHERE gate_id = %s RETURNING gate_id;",
                (body.name, json.dumps(body.conditions), gate_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Quality gate não encontrado")
        conn.commit()
    return {"gate_id": gate_id, "name": body.name, "conditions": body.conditions}
