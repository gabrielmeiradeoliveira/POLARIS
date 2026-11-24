from __future__ import annotations

import ast
from typing import Any

from fastapi import APIRouter

from polaris_server.domain_core import compute_rating

router = APIRouter(prefix="/api/v1", tags=["metrics"])


def compute_python_complexity(source: str) -> dict[str, int]:
    """Compute cyclomatic and cognitive complexity for Python source."""
    tree = ast.parse(source)
    cyclomatic = 1
    cognitive = 0

    def walk(node: ast.AST, depth: int) -> None:
        nonlocal cyclomatic, cognitive
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler)):
                cyclomatic += 1
                cognitive += 1 + depth
                walk(child, depth + 1)
            elif isinstance(child, ast.BoolOp):
                ops = max(1, len(child.values) - 1)
                cyclomatic += ops
                cognitive += ops
                walk(child, depth)
            else:
                walk(child, depth)

    walk(tree, 0)
    return {"cyclomatic": cyclomatic, "cognitive": cognitive}


def compute_code_metrics(
    files_count: int,
    lines: int,
    ncloc: int,
    comment_lines: int,
    issues: list[dict[str, Any]],
    cyclomatic_complexity: int = 0,
    cognitive_complexity: int = 0,
) -> dict[str, Any]:
    """Aggregate fundamental metrics, technical debt, and ratings."""
    comment_density = round((comment_lines / max(1, ncloc + comment_lines)) * 100.0, 2)
    by_severity: dict[str, int] = {}
    by_type: dict[str, int] = {}
    debt_minutes = 0
    for iss in issues:
        sev = iss.get("severity", "MAJOR")
        itype = iss.get("issue_type", "CODE_SMELL")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        by_type[itype] = by_type.get(itype, 0) + 1
        debt_minutes += int(iss.get("effort_minutes", 10))

    rel_sevs = {i.get("severity", "MAJOR"): 1 for i in issues if i.get("issue_type") == "BUG"}
    sec_sevs = {i.get("severity", "MAJOR"): 1 for i in issues if i.get("issue_type") == "VULNERABILITY"}
    maint_sevs = {i.get("severity", "MAJOR"): 1 for i in issues if i.get("issue_type") == "CODE_SMELL"}

    return {
        "files": files_count,
        "lines": lines,
        "ncloc": ncloc,
        "comment_lines": comment_lines,
        "comment_density": comment_density,
        "cyclomatic_complexity": cyclomatic_complexity,
        "cognitive_complexity": cognitive_complexity,
        "technical_debt_minutes": debt_minutes,
        "issues_total": len(issues),
        "issues_by_severity": by_severity,
        "issues_by_type": by_type,
        "ratings": {
            "reliability": compute_rating(rel_sevs),
            "security": compute_rating(sec_sevs),
            "maintainability": compute_rating(maint_sevs),
        },
    }


import json
from polaris_server.db import get_connection


def store_project_metrics(project_key: str, metrics: dict[str, Any], analysis_id: str | None = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO project_metrics (project_key, analysis_id, metrics) VALUES (%s, %s, %s::jsonb);",
                (project_key, analysis_id, json.dumps(metrics)),
            )
        conn.commit()


@router.get("/projects/{project_key}/metrics")
def get_project_metrics(project_key: str) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT metrics FROM project_metrics WHERE project_key = %s ORDER BY recorded_at DESC LIMIT 1;",
                (project_key,),
            )
            row = cur.fetchone()
    if not row:
        return {"project_key": project_key, "status": "NOT_COMPUTED"}
    return row[0]
