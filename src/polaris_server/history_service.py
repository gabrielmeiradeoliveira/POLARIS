from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1", tags=["history"])


@dataclass
class AnalysisSnapshot:
    analysis_id: str
    project_key: str
    branch: str
    created_at: str
    quality_gate_status: str
    metrics: dict[str, Any] = field(default_factory=dict)
    issue_fingerprints: set[str] = field(default_factory=set)


from polaris_server.db import get_connection


def record_snapshot(
    project_key: str,
    analysis_id: str,
    branch: str = "main",
    quality_gate_status: str = "PASSED",
    metrics: dict[str, Any] | None = None,
    issue_fingerprints: set[str] | None = None,
) -> AnalysisSnapshot:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analyses (analysis_id, project_key, branch, status, total_files)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (analysis_id) DO NOTHING;
                """,
                (analysis_id, project_key, branch, quality_gate_status, int((metrics or {}).get("total_files", 0))),
            )
        conn.commit()
    return AnalysisSnapshot(
        analysis_id=analysis_id,
        project_key=project_key,
        branch=branch,
        created_at=now,
        quality_gate_status=quality_gate_status,
        metrics=metrics or {},
        issue_fingerprints=issue_fingerprints or set(),
    )


@router.get("/projects/{project_key}/history")
def get_project_history(project_key: str, branch: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if branch:
                cur.execute(
                    "SELECT analysis_id, project_key, branch, status, total_files, created_at FROM analyses WHERE project_key = %s AND branch = %s ORDER BY created_at DESC LIMIT %s OFFSET %s;",
                    (project_key, branch, limit, offset),
                )
            else:
                cur.execute(
                    "SELECT analysis_id, project_key, branch, status, total_files, created_at FROM analyses WHERE project_key = %s ORDER BY created_at DESC LIMIT %s OFFSET %s;",
                    (project_key, limit, offset),
                )
            rows = cur.fetchall()
    items = [
        {"analysis_id": r[0], "project_key": r[1], "branch": r[2], "quality_gate_status": r[3], "total_files": r[4], "created_at": r[5].isoformat()}
        for r in rows
    ]
    return {"total": len(items), "items": items}


@router.get("/projects/{project_key}/compare")
def compare_analyses(project_key: str, base_id: str, target_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT analysis_id, total_files FROM analyses WHERE project_key = %s AND analysis_id IN (%s, %s);",
                (project_key, base_id, target_id),
            )
            rows = {r[0]: r[1] for r in cur.fetchall()}
            if base_id not in rows or target_id not in rows:
                raise HTTPException(status_code=404, detail="Analysis snapshot not found")
            cur.execute("SELECT rule_id || ':' || file_path || ':' || start_line FROM issues WHERE project_key = %s AND analysis_id = %s;", (project_key, base_id))
            base_fps = {r[0] for r in cur.fetchall()}
            cur.execute("SELECT rule_id || ':' || file_path || ':' || start_line FROM issues WHERE project_key = %s AND analysis_id = %s;", (project_key, target_id))
            target_fps = {r[0] for r in cur.fetchall()}
    return {
        "base_id": base_id,
        "target_id": target_id,
        "new_issues": sorted(target_fps - base_fps),
        "resolved_issues": sorted(base_fps - target_fps),
        "persistent_issues": sorted(base_fps & target_fps),
        "metrics_delta": {"total_files": rows[target_id] - rows[base_id]},
    }
