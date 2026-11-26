from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from polaris_server.db import get_connection


def _normalize_flow_signature(flow_steps: list[dict[str, Any]] | None) -> str:
    """Normalize flow steps into a deterministic string representation without line numbers."""
    if not flow_steps:
        return "NOFLOW:"
    normalized_parts: list[str] = []
    for step in flow_steps:
        if not isinstance(step, dict):
            continue
        kind = str(step.get("kind") or "").strip().upper()
        msg = str(step.get("message") or step.get("msg") or step.get("label") or "").strip()
        loc = str(step.get("location") or step.get("loc") or step.get("file") or step.get("file_path") or "").strip()
        # strip line numbers like :12, :123:4
        loc = re.sub(r":\d+(?::\d+)?$", "", loc).strip()
        msg = " ".join(msg.split())
        normalized_parts.append(f"{kind}:{loc}:{msg}")
    return ";".join(normalized_parts) if normalized_parts else "NOFLOW:"


def compute_finding_fingerprint(
    rule_id: str,
    file_path: str,
    flow_steps: list[dict[str, Any]] | None = None,
    fallback_signature: str = "",
) -> str:
    """Generate SHA-256 (64 hex) deterministic fingerprint immune to line moves.

    Format: norm_rule|norm_path|flow_sig
    Line numbers (:12, start_line, step['line']) are stripped and whitespace normalized.
    """
    norm_rule = " ".join(str(rule_id or "").strip().split())
    clean_path = str(file_path or "").strip().replace("\\", "/")
    # strip trailing :line or :line:col if present in file_path
    clean_path = re.sub(r":\d+(?::\d+)?$", "", clean_path).strip()
    norm_path = " ".join(clean_path.split())

    flow_sig = _normalize_flow_signature(flow_steps)
    if flow_sig == "NOFLOW:" and fallback_signature:
        norm_fallback = " ".join(re.sub(r":\d+(?::\d+)?$", "", str(fallback_signature).strip()).split())
        flow_sig = f"NOFLOW:{norm_fallback}"

    raw = f"{norm_rule}|{norm_path}|{flow_sig}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_persistent_fingerprint(project_id: str, rule_id: str, normalized_path: str, normalized_code_line: str) -> str:
    """Backward compatibility helper."""
    raw = f"{project_id}:{rule_id}:{normalized_path}:{normalized_code_line.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def backfill_missing_fingerprints() -> int:
    """Backfill issues.fingerprint for existing records in the database."""
    updated = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, rule_id, file_path, flow_steps FROM issues WHERE fingerprint IS NULL OR fingerprint = '';")
            rows = cur.fetchall()
            for row in rows:
                iss_id, rule_id, file_path, flow_steps = row
                fp = compute_finding_fingerprint(rule_id=rule_id, file_path=file_path, flow_steps=flow_steps)
                cur.execute("UPDATE issues SET fingerprint = %s WHERE id = %s;", (fp, iss_id))
                updated += 1
        conn.commit()
    return updated


@dataclass
class IssueRecord:
    fingerprint: str
    rule_id: str
    file_path: str
    line: int
    status: str = "OPEN"
    audit_log: list[dict[str, str]] = field(default_factory=list)

    def triage(self, new_status: str, comment: str, author: str) -> None:
        if new_status not in {"OPEN", "FALSE_POSITIVE", "ACCEPTED_RISK", "FIXED", "RESOLVED"}:
            raise ValueError(f"Invalid triage status: {new_status}")
        if not comment.strip():
            raise ValueError("Justification comment is required")
        self.status = new_status
        self.audit_log.append({
            "status": new_status,
            "comment": comment.strip(),
            "author": author,
            "at": datetime.now(timezone.utc).isoformat(),
        })
