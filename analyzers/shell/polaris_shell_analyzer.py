from __future__ import annotations

import re
from typing import Any

_SH_RULES: list[tuple[str, str, str, re.Pattern[str], str]] = [
    ("SH-SEC-001", "BLOCKER", "SECURITY", re.compile(r"\b(?:curl|wget)\b[^|]*\|\s*(?:sh|bash)\b"), "Piping remote script directly into sh/bash"),
    ("SH-SEC-002", "CRITICAL", "SECURITY", re.compile(r"\bchmod\s+(?:-R\s+)?777\b"), "Overly permissive chmod 777"),
    ("SH-SEC-003", "CRITICAL", "SECURITY", re.compile(r"\beval\s+.*\$"), "Dynamic eval with variable expansion"),
    ("SH-SEC-004", "BLOCKER", "SECURITY", re.compile(r"""(?:export\s+)?(?:PASSWORD|SECRET|TOKEN|API_KEY)=["']?[A-Za-z0-9_\-]{8,}"""), "Hardcoded secret in shell script"),
    ("SH-SEC-005", "CRITICAL", "SECURITY", re.compile(r"\becho\b[^|]*\|\s*sudo\s+-S\b"), "Passing password via echo | sudo -S"),
    ("SH-REL-001", "CRITICAL", "RELIABILITY", re.compile(r"\brm\s+-rf\s+\$[A-Za-z_]\w*(?!/|\")"), "Unquoted variable in rm -rf"),
    ("SH-REL-002", "MAJOR", "RELIABILITY", re.compile(r">/tmp/[A-Za-z0-9_.-]+"), "Predictable /tmp/ file without mktemp"),
]


def analyze_shell_content(content: str, file_path: str = "deploy.sh") -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    lines = content.splitlines()
    for idx, line in enumerate(lines, start=1):
        for rule_id, severity, category, pat, message in _SH_RULES:
            if pat.search(line):
                issues.append({
                    "ruleId": f"shell:{rule_id}",
                    "language": "shell",
                    "severity": severity,
                    "category": category,
                    "confidence": "HIGH",
                    "location": {"file": file_path, "startLine": idx},
                    "message": message,
                })
    if lines and lines[0].startswith("#!") and "set -e" not in content and "set -euo pipefail" not in content:
        issues.append({
            "ruleId": "shell:SH-REL-003",
            "language": "shell",
            "severity": "MINOR",
            "category": "RELIABILITY",
            "confidence": "HIGH",
            "location": {"file": file_path, "startLine": 1},
            "message": "Executable script missing set -e / set -euo pipefail",
        })
    return issues
