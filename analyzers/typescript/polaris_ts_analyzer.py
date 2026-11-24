from __future__ import annotations

import re
from typing import Any

_TS_RULES: list[tuple[str, str, re.Pattern[str], str]] = [
    ("ts:TS-SEC-001", "CRITICAL", re.compile(r"dangerouslySetInnerHTML\s*=\s*\{\s*\{\s*__html\s*:\s*[A-Za-z_$][A-Za-z0-9_$.]*\s*\}\s*\}"), "Unsanitized variable in dangerouslySetInnerHTML"),
    ("ts:TS-SEC-002", "BLOCKER", re.compile(r"\b(?:eval|new\s+Function)\s*\("), "Dynamic code execution via eval/new Function"),
    ("ts:TS-SEC-003", "CRITICAL", re.compile(r"\.innerHTML\s*=\s*(?!['\"])"), "Dynamic assignment to innerHTML"),
    ("ts:TS-SEC-004", "BLOCKER", re.compile(r"child_process\.exec\s*\(\s*`[^`]*\$\{"), "Command injection via interpolated child_process.exec"),
    ("ts:TS-SEC-005", "CRITICAL", re.compile(r"""href\s*=\s*['"]javascript:"""), "XSS via javascript: URI in href"),
]


def analyze_ts_content(content: str, file_path: str = "app.tsx") -> list[dict[str, Any]]:
    """Lightweight deterministic TypeScript/React security analyzer."""
    issues: list[dict[str, Any]] = []
    for line_no, line in enumerate(content.splitlines(), start=1):
        for rule_id, severity, pattern, message in _TS_RULES:
            if pattern.search(line):
                issues.append(
                    {
                        "ruleId": rule_id,
                        "language": "typescript",
                        "severity": severity,
                        "confidence": "HIGH",
                        "location": {"file": file_path, "startLine": line_no},
                        "message": message,
                    }
                )
    return issues
