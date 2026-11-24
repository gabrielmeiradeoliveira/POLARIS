from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def compute_persistent_fingerprint(project_id: str, rule_id: str, normalized_path: str, normalized_code_line: str) -> str:
    raw = f"{project_id}:{rule_id}:{normalized_path}:{normalized_code_line.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class IssueRecord:
    fingerprint: str
    rule_id: str
    file_path: str
    line: int
    status: str = "OPEN"
    audit_log: list[dict[str, str]] = field(default_factory=list)

    def triage(self, new_status: str, comment: str, author: str) -> None:
        if new_status not in {"OPEN", "FALSE_POSITIVE", "ACCEPTED_RISK", "RESOLVED"}:
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
