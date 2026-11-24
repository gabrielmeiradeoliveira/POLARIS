from __future__ import annotations

import os
from typing import Any


def get_retention_keep_last() -> int:
    """Return configured number of raw analysis snapshots to retain per project."""
    try:
        return max(1, int(os.environ.get("POLARIS_RETENTION_KEEP_LAST", "30")))
    except ValueError:
        return 30


def prune_old_snapshots(conn: Any, project_key: str, keep_last: int | None = None) -> int:
    """Delete raw analysis snapshots older than keep_last while preserving aggregated metrics and issue_states."""
    limit = keep_last if keep_last is not None else get_retention_keep_last()
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM analyses
            WHERE project_key = %s
              AND analysis_id NOT IN (
                  SELECT analysis_id FROM analyses
                  WHERE project_key = %s
                  ORDER BY created_at DESC
                  LIMIT %s
              );
            """,
            (project_key, project_key, limit),
        )
        deleted = cur.rowcount or 0
    conn.commit()
    return deleted
