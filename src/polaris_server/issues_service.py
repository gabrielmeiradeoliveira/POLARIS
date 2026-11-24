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
from polaris_server.db import get_connection


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
                    INSERT INTO issues (analysis_id, project_key, rule_id, language, severity, file_path, start_line, message, cwe, flow_steps, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'OPEN');
                    """,
                    (analysis_id, project_key, rule_id, issue_type, severity, file_path, line, message, cwe, json.dumps(flow_steps or [])),
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
        "SELECT id, project_key, rule_id, severity, language, file_path, start_line, message, status, assignee, cwe, flow_steps FROM issues"
        + where
        + " ORDER BY id DESC LIMIT %s OFFSET %s;"
    )
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(count_sql, params)
            cnt_row = cur.fetchone()
            total = cnt_row[0] if cnt_row else 0
            cur.execute(select_sql, [*params, limit, offset])
            rows = cur.fetchall()
    items = [
        {
            "issue_id": str(r[0]),
            "project_key": r[1],
            "rule_id": r[2],
            "severity": r[3],
            "issue_type": r[4],
            "file_path": r[5],
            "line": r[6],
            "message": r[7],
            "status": r[8],
            "assignee": r[9],
            "cwe": r[10],
            "flow_steps": r[11] or [],
        }
        for r in rows
    ]
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
