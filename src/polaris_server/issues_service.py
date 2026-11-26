from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from polaris_server.domain_core import transition_issue_state

router = APIRouter(prefix="/api/v1", tags=["issues"])


@dataclass
class IssueRecord:
    issue_id: str
    project_key: str
    rule_id: str
    severity: str
    issue_type: str  # BUG | VULNERABILITY | CODE_SMELL | SECURITY_HOTSPOT
    file_path: str
    line: int
    message: str
    fingerprint: str
    status: str = "OPEN"
    assignee: str | None = None
    comments: list[dict[str, str]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    hotspot_status: str | None = None  # TO_REVIEW | SAFE | FIXED
    cwe: str | None = None
    flow_steps: list[dict[str, Any]] = field(default_factory=list)


import json
import re
from polaris_server.db import get_connection
from polaris_server.triage import compute_finding_fingerprint


def _parse_iso_utc(ts_str: str | None) -> datetime | None:
    if not ts_str:
        return None
    cleaned = ts_str.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    dt = datetime.fromisoformat(cleaned)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


class BatchTriageRequest(BaseModel):
    fingerprints: list[str] = Field(default_factory=list)
    issue_ids: list[str | int] = Field(default_factory=list)
    status: str
    justification: str
    actor: str = "local-user"
    expires_at: str | None = None


def apply_batch_triage(body: BatchTriageRequest) -> dict[str, Any]:
    norm_status = body.status.strip().upper()
    valid_statuses = {"OPEN", "ACCEPTED_RISK", "FALSE_POSITIVE", "FIXED"}
    if norm_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Status inválido: {body.status}. Valores permitidos: {sorted(valid_statuses)}",
        )

    clean_just = body.justification.strip() if body.justification else ""
    if len(clean_just) < 3:
        raise HTTPException(
            status_code=400,
            detail="A justificativa é obrigatória e deve conter no mínimo 3 caracteres.",
        )

    actor = body.actor.strip() if body.actor else "local-user"
    if not actor:
        actor = "local-user"

    expires_at_dt: datetime | None = None
    if body.expires_at is not None and body.expires_at != "":
        if norm_status != "ACCEPTED_RISK":
            raise HTTPException(
                status_code=400,
                detail="expires_at é permitido apenas quando status == 'ACCEPTED_RISK'.",
            )
        try:
            expires_at_dt = _parse_iso_utc(body.expires_at)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"expires_at deve ser uma data ISO-8601 UTC válida: {exc}",
            )
        now_utc = datetime.now(timezone.utc)
        if expires_at_dt <= now_utc:
            raise HTTPException(
                status_code=400,
                detail="expires_at deve ser uma data no futuro.",
            )

    combined_fps: set[str] = {str(fp).strip() for fp in body.fingerprints if str(fp).strip()}
    parsed_issue_ids: list[int] = []
    for raw_id in body.issue_ids:
        s = str(raw_id).strip()
        if s.isdigit():
            parsed_issue_ids.append(int(s))

    if not combined_fps and not parsed_issue_ids:
        raise HTTPException(
            status_code=400,
            detail="Informe ao menos 1 item em fingerprints ou issue_ids (limite: 500).",
        )

    with get_connection() as conn:
        with conn.cursor() as cur:
            if parsed_issue_ids:
                cur.execute(
                    "SELECT id, rule_id, file_path, flow_steps, fingerprint FROM issues WHERE id = ANY(%s);",
                    (parsed_issue_ids,),
                )
                for r in cur.fetchall():
                    fp = r[4]
                    if not fp:
                        fp = compute_finding_fingerprint(r[1], r[2], r[3])
                        cur.execute("UPDATE issues SET fingerprint = %s WHERE id = %s;", (fp, r[0]))
                    combined_fps.add(fp)

            if not combined_fps:
                raise HTTPException(status_code=404, detail="Nenhum achado correspondente encontrado.")

            if len(combined_fps) > 500:
                raise HTTPException(status_code=400, detail="Limite máximo de 500 itens por lote excedido.")

            # Descobre se há pr_key ou project_key associados para invalidação de cache
            cur.execute(
                """
                SELECT DISTINCT pr.pr_key
                FROM issues i
                JOIN project_pull_requests pr ON pr.project_key = i.project_key
                WHERE i.fingerprint = ANY(%s);
                """,
                (list(combined_fps),),
            )
            affected_pr_keys = [r[0] for r in cur.fetchall()]

            updated_items: list[dict[str, Any]] = []
            for fp in combined_fps:
                cur.execute(
                    """
                    INSERT INTO finding_triages (fingerprint, status, justification, actor, expires_at, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (fingerprint) DO UPDATE SET
                        status = EXCLUDED.status,
                        justification = EXCLUDED.justification,
                        actor = EXCLUDED.actor,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = NOW()
                    RETURNING fingerprint, status, justification, actor, expires_at, updated_at;
                    """,
                    (fp, norm_status, clean_just, actor, expires_at_dt),
                )
                row = cur.fetchone()
                cur.execute(
                    "UPDATE issues SET status = %s WHERE fingerprint = %s;",
                    (norm_status, fp),
                )
                cur.execute(
                    """
                    INSERT INTO finding_triage_audit (fingerprint, status, justification, actor, expires_at, recorded_at)
                    VALUES (%s, %s, %s, %s, %s, NOW());
                    """,
                    (fp, norm_status, clean_just, actor, expires_at_dt),
                )
                if row:
                    updated_items.append({
                        "fingerprint": row[0],
                        "status": row[1],
                        "justification": row[2],
                        "actor": row[3],
                        "expires_at": row[4].isoformat() if row[4] else None,
                        "updated_at": row[5].isoformat() if row[5] else None,
                    })

        conn.commit()

    # Invalidação FinOps de summaries cacheados para os PRs afetados
    if affected_pr_keys:
        from polaris_server.ai.summary_cache import invalidate_pr_summary_cache
        for pr_k in affected_pr_keys:
            invalidate_pr_summary_cache(pr_k)

    return {"updated_count": len(updated_items), "items": updated_items}


@router.patch("/findings/batch-triage")
def batch_triage_v1(body: BatchTriageRequest) -> dict[str, Any]:
    return apply_batch_triage(body)


@router.get("/findings/{fingerprint}/audit")
def get_finding_audit(fingerprint: str) -> dict[str, Any]:
    clean_fp = fingerprint.strip()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, fingerprint, status, justification, actor, expires_at, recorded_at
                FROM finding_triage_audit
                WHERE fingerprint = %s
                ORDER BY recorded_at DESC, id DESC;
                """,
                (clean_fp,),
            )
            rows = cur.fetchall()
    return {
        "fingerprint": clean_fp,
        "total": len(rows),
        "history": [
            {
                "id": r[0],
                "fingerprint": r[1],
                "status": r[2],
                "justification": r[3],
                "actor": r[4],
                "expires_at": r[5].isoformat() if r[5] else None,
                "recorded_at": r[6].isoformat() if r[6] else None,
            }
            for r in rows
        ],
    }


def upsert_issue_occurrence(
    project_key: str,
    rule_id: str,
    severity: str,
    issue_type: str,
    file_path: str,
    line: int,
    message: str,
    fingerprint: str,
    cwe: str | None = None,
    flow_steps: list[dict[str, Any]] | None = None,
    analysis_id: str = "manual",
) -> IssueRecord:
    """Create or update a persistent issue by project_key + rule_id + file_path + start_line."""
    issue_id = f"{project_key}:{fingerprint[:16]}"
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, status FROM issues WHERE project_key = %s AND rule_id = %s AND file_path = %s AND start_line = %s LIMIT 1;",
                (project_key, rule_id, file_path, line),
            )
            row = cur.fetchone()
            if row:
                db_id, cur_status = row
                new_status = transition_issue_state("RESOLVED", "REOPENED") if cur_status == "RESOLVED" else cur_status
                cur.execute(
                    "UPDATE issues SET message = %s, status = %s, cwe = %s, flow_steps = %s::jsonb WHERE id = %s;",
                    (message, new_status, cwe, json.dumps(flow_steps or []), db_id),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO issues (analysis_id, project_key, rule_id, language, severity, file_path, start_line, message, cwe, flow_steps, status, fingerprint)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'OPEN', %s);
                    """,
                    (analysis_id, project_key, rule_id, issue_type, severity, file_path, line, message, cwe, json.dumps(flow_steps or []), fingerprint),
                )
        conn.commit()
    return IssueRecord(
        issue_id=issue_id,
        project_key=project_key,
        rule_id=rule_id,
        severity=severity,
        issue_type=issue_type,
        file_path=file_path,
        line=line,
        message=message,
        fingerprint=fingerprint,
        cwe=cwe,
        flow_steps=flow_steps or [],
        history=[{"at": now, "action": "UPSERTED"}],
    )


class IssueTransitionRequest(BaseModel):
    target_status: str
    author: str = "local-user"
    comment: str | None = None


class IssueAssignRequest(BaseModel):
    assignee: str | None = None
    author: str = "local-user"


class IssueCommentRequest(BaseModel):
    author: str = "local-user"
    text: str = Field(min_length=1, max_length=2000)


class HotspotReviewRequest(BaseModel):
    status: str  # TO_REVIEW | SAFE | FIXED
    author: str = "local-user"


def _csv_safe_cell(val: Any) -> str:
    s = str(val if val is not None else "")
    if s and s[0] in ("=", "+", "-", "@"):
        s = "'" + s
    return '"' + s.replace('"', '""') + '"'


def build_sarif_report(items: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for it in items:
        sev = str(it.get("severity", "MAJOR")).upper()
        level = "error" if sev in ("BLOCKER", "CRITICAL") else "warning" if sev in ("HIGH", "MAJOR") else "note"
        results.append(
            {
                "ruleId": str(it.get("rule_id", "")),
                "level": level,
                "message": {"text": str(it.get("message", ""))},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": str(it.get("file_path", ""))},
                            "region": {"startLine": max(1, int(it.get("start_line") or 1))},
                        }
                    }
                ],
            }
        )
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "POLARIS", "version": "2.0.0"}}, "results": results}],
    }


@router.get("/issues/export")
def export_issues(project_key: str | None = None, format: str = "json") -> Any:
    from fastapi.responses import PlainTextResponse

    data = list_issues(project_key=project_key, limit=1000, offset=0)
    fmt = format.lower()
    if fmt == "sarif":
        return build_sarif_report(data["items"])
    if fmt == "csv":
        header = "issue_id,project_key,rule_id,severity,status,file_path,start_line,message"
        lines = [header]
        for it in data["items"]:
            lines.append(
                ",".join(
                    [
                        _csv_safe_cell(it["issue_id"]),
                        _csv_safe_cell(it["project_key"]),
                        _csv_safe_cell(it["rule_id"]),
                        _csv_safe_cell(it["severity"]),
                        _csv_safe_cell(it["status"]),
                        _csv_safe_cell(it["file_path"]),
                        _csv_safe_cell(it["start_line"]),
                        _csv_safe_cell(it["message"]),
                    ]
                )
            )
        return PlainTextResponse("\n".join(lines), media_type="text/csv")
    return data


@router.get("/issues/summary")
def issues_summary() -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM issues;")
            row = cur.fetchone()
            total_count = int(row[0]) if row else 0
            cur.execute("SELECT severity, COUNT(*) FROM issues GROUP BY severity;")
            by_severity = {str(r[0]): int(r[1]) for r in cur.fetchall()}
            cur.execute("SELECT language, COUNT(*) FROM issues GROUP BY language;")
            by_language = {str(r[0]): int(r[1]) for r in cur.fetchall()}
    return {"totalCount": total_count, "bySeverity": by_severity, "byLanguage": by_language}


@router.get("/issues")
def list_issues(
    project_key: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    issue_type: str | None = None,
    rule_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    clauses: list[str] = []
    params: list[Any] = []
    if project_key:
        clauses.append("project_key = %s")
        params.append(project_key)
    if severity:
        clauses.append("severity = %s")
        params.append(severity)
    if status:
        clauses.append("status = %s")
        params.append(status)
    if issue_type:
        clauses.append("language = %s")
        params.append(issue_type)
    if rule_id:
        clauses.append("rule_id = %s")
        params.append(rule_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    count_sql = "SELECT COUNT(*) FROM issues" + where + ";"
    select_sql = (
        """
        SELECT 
            i.id, i.project_key, i.rule_id, i.severity, i.language, 
            i.file_path, i.start_line, i.message, i.status, i.assignee, 
            i.cwe, i.flow_steps, i.fingerprint,
            ft.status AS triage_status,
            ft.justification AS triage_justification,
            ft.actor AS triage_actor,
            ft.expires_at AS triage_expires_at,
            ft.updated_at AS triage_updated_at
        FROM issues i
        LEFT JOIN finding_triages ft ON ft.fingerprint = i.fingerprint
        """
        + where
        + " ORDER BY i.id DESC LIMIT %s OFFSET %s;"
    )
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(count_sql, params)
            cnt_row = cur.fetchone()
            total = cnt_row[0] if cnt_row else 0
            cur.execute(select_sql, [*params, limit, offset])
            rows = cur.fetchall()

    now_utc = datetime.now(timezone.utc)
    items = []
    for r in rows:
        iss_id = str(r[0])
        proj_k = r[1]
        rule_k = r[2]
        sev = r[3]
        lang = r[4]
        fpath = r[5]
        sline = r[6]
        msg = r[7]
        raw_status = r[8] or "OPEN"
        assignee = r[9]
        cwe = r[10]
        flow_steps = r[11] or []
        fp = r[12] or compute_finding_fingerprint(rule_k, fpath, flow_steps)

        tr_status = r[13]
        tr_just = r[14]
        tr_actor = r[15]
        tr_expires = r[16]
        tr_updated = r[17]

        effective_status = tr_status or raw_status
        is_expired = False
        if effective_status == "ACCEPTED_RISK" and tr_expires:
            exp_dt = tr_expires if tr_expires.tzinfo else tr_expires.replace(tzinfo=timezone.utc)
            if exp_dt <= now_utc:
                effective_status = "OPEN"
                is_expired = True

        items.append({
            "issue_id": iss_id,
            "project_key": proj_k,
            "rule_id": rule_k,
            "severity": sev,
            "issue_type": lang,
            "file_path": fpath,
            "line": sline,
            "message": msg,
            "status": effective_status,
            "assignee": assignee,
            "cwe": cwe,
            "flow_steps": flow_steps,
            "fingerprint": fp,
            "justification": tr_just,
            "triage_actor": tr_actor,
            "expires_at": tr_expires.isoformat() if tr_expires else None,
            "triage_updated_at": tr_updated.isoformat() if tr_updated else None,
            "expired": is_expired,
        })
    return {"total": total, "items": items}


@router.post("/issues/{issue_id}/transition")
def transition_issue(issue_id: str, body: IssueTransitionRequest) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM issues WHERE id = %s;", (int(issue_id),))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Issue not found")
            try:
                new_status = transition_issue_state(row[0], body.target_status)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            cur.execute("UPDATE issues SET status = %s WHERE id = %s;", (new_status, int(issue_id)))
            if body.comment:
                cur.execute(
                    "INSERT INTO issue_comments (issue_id, author, body) VALUES (%s, %s, %s);",
                    (int(issue_id), body.author, body.comment),
                )
        conn.commit()
    return {"issue_id": issue_id, "status": new_status}


@router.post("/issues/{issue_id}/assign")
def assign_issue(issue_id: str, body: IssueAssignRequest) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE issues SET assignee = %s WHERE id = %s RETURNING id;", (body.assignee, int(issue_id)))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Issue not found")
        conn.commit()
    return {"issue_id": issue_id, "assignee": body.assignee}


@router.post("/issues/{issue_id}/comments")
def add_comment(issue_id: str, body: IssueCommentRequest) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM issues WHERE id = %s;", (int(issue_id),))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Issue not found")
            cur.execute(
                "INSERT INTO issue_comments (issue_id, author, body) VALUES (%s, %s, %s);",
                (int(issue_id), body.author, body.text),
            )
        conn.commit()
    return {"issue_id": issue_id, "author": body.author, "text": body.text}


@router.get("/issues/{issue_id}/flow")
def get_issue_flow(issue_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if issue_id.isdigit():
                cur.execute("SELECT id, rule_id, cwe, flow_steps FROM issues WHERE id = %s;", (int(issue_id),))
            elif ":" in issue_id:
                proj_key, _ = issue_id.split(":", 1)
                cur.execute(
                    "SELECT id, rule_id, cwe, flow_steps FROM issues WHERE project_key = %s ORDER BY id DESC LIMIT 1;",
                    (proj_key,),
                )
            else:
                raise HTTPException(status_code=400, detail="Invalid issue_id format")
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Issue not found")
    return {"issue_id": str(row[0]), "rule_id": row[1], "cwe": row[2], "flow_steps": row[3] or []}


@router.post("/hotspots/{issue_id}/review")
def review_hotspot(issue_id: str, body: HotspotReviewRequest) -> dict[str, Any]:
    if body.status not in ("TO_REVIEW", "SAFE", "FIXED"):
        raise HTTPException(status_code=400, detail="Invalid hotspot status")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE issues SET resolution = %s WHERE id = %s RETURNING id;", (body.status, int(issue_id)))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Security Hotspot not found")
        conn.commit()
    return {"issue_id": issue_id, "hotspot_status": body.status}
