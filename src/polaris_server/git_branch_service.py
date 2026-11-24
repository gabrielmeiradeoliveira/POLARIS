from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["branches"])


@dataclass
class BranchRecord:
    project_key: str
    name: str
    is_main: bool = False
    last_commit: str | None = None
    quality_gate_status: str = "NOT_COMPUTED"
    new_code_issues: int = 0


@dataclass
class PullRequestRecord:
    project_key: str
    pr_id: str
    head_branch: str
    base_branch: str
    commit: str
    quality_gate_status: str = "NOT_COMPUTED"
    new_issues: list[dict[str, Any]] = field(default_factory=list)


from polaris_server.db import get_connection


def register_branch(project_key: str, name: str, is_main: bool = False, last_commit: str | None = None, quality_gate_status: str = "PASSED", new_code_issues: int = 0) -> BranchRecord:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO project_branches (project_key, name, is_main, last_analysis_id, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (project_key, name) DO UPDATE
                SET is_main = EXCLUDED.is_main, last_analysis_id = EXCLUDED.last_analysis_id, updated_at = NOW();
                """,
                (project_key, name, is_main, last_commit),
            )
        conn.commit()
    return BranchRecord(project_key, name, is_main, last_commit, quality_gate_status, new_code_issues)


def register_pull_request(project_key: str, pr_id: str, head_branch: str, base_branch: str, commit: str, quality_gate_status: str = "PASSED", new_issues: list[dict[str, Any]] | None = None) -> PullRequestRecord:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO project_pull_requests (project_key, pr_key, title, source_branch, target_branch, status, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (project_key, pr_key) DO UPDATE
                SET source_branch = EXCLUDED.source_branch, target_branch = EXCLUDED.target_branch, status = EXCLUDED.status, updated_at = NOW();
                """,
                (project_key, pr_id, commit, head_branch, base_branch, quality_gate_status),
            )
        conn.commit()
    return PullRequestRecord(project_key, pr_id, head_branch, base_branch, commit, quality_gate_status, new_issues or [])


@router.get("/projects/{project_key}/branches")
def list_branches(project_key: str) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT project_key, name, is_main, last_analysis_id FROM project_branches WHERE project_key = %s ORDER BY name;", (project_key,))
            rows = cur.fetchall()
    items = [{"project_key": r[0], "name": r[1], "is_main": r[2], "last_commit": r[3]} for r in rows]
    return {"total": len(items), "items": items}


@router.get("/projects/{project_key}/pull-requests")
def list_pull_requests(project_key: str) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT project_key, pr_key, source_branch, target_branch, title, status FROM project_pull_requests WHERE project_key = %s ORDER BY updated_at DESC;", (project_key,))
            rows = cur.fetchall()
    items = [{"project_key": r[0], "pr_id": r[1], "head_branch": r[2], "base_branch": r[3], "commit": r[4], "quality_gate_status": r[5]} for r in rows]
    return {"total": len(items), "items": items}
