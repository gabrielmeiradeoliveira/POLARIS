from __future__ import annotations

import re
from typing import Any

_FE_RULES: list[tuple[str, str, str, re.Pattern[str], str]] = [
    ("FE-SEC-001", "CRITICAL", "SECURITY", re.compile(r"dangerouslySetInnerHTML"), "Unsanitized dangerouslySetInnerHTML"),
    ("FE-SEC-002", "CRITICAL", "SECURITY", re.compile(r"""href\s*=\s*["']javascript:"""), "XSS via javascript: URI"),
    ("FE-SEC-003", "MAJOR", "SECURITY", re.compile(r"""target\s*=\s*["']_blank["'](?![^>]*rel\s*=\s*["'][^"']*noopener)"""), "target=_blank without rel=noopener noreferrer"),
    ("FE-SEC-004", "BLOCKER", "SECURITY", re.compile(r"\b(?:eval|new\s+Function)\s*\("), "Dynamic code execution via eval/new Function"),
    ("FE-SEC-005", "CRITICAL", "SECURITY", re.compile(r"""(?:localStorage|sessionStorage)\.setItem\s*\(\s*["'][^"']*(?:token|secret|password)[^"']*["']""", re.I), "Sensitive credential stored in Web Storage"),
    ("FE-SEC-006", "MAJOR", "SECURITY", re.compile(r"""<script[^>]+src\s*=\s*["']https?://[^"']+["'](?![^>]*integrity\s*=)""", re.I), "External script missing SRI integrity attribute"),
    ("FE-SEC-007", "MAJOR", "SECURITY", re.compile(r"""<iframe(?![^>]*\bsandbox\b)""", re.I), "iframe missing sandbox attribute"),
    ("FE-REL-001", "MAJOR", "RELIABILITY", re.compile(r"useEffect\s*\(\s*\(\)\s*=>\s*\{[^}]*set[A-Z][A-Za-z0-9_]*\([^)]*\)[^}]*\}\s*\)"), "useEffect mutating state without dependency array"),
    ("FE-REL-002", "MINOR", "RELIABILITY", re.compile(r"\.map\s*\(\s*\([^,]+,\s*(\w+)\s*\)\s*=>[^)]*key=\{\1\}"), "Array index used as React key in .map()"),
    ("FE-REL-003", "MINOR", "RELIABILITY", re.compile(r"""<input[^>]+type\s*=\s*["']password["'](?![^>]*autocomplete\s*=\s*["'](?:new|current)-password["'])""", re.I), "Password input missing explicit autocomplete"),
]


def analyze_frontend_content(content: str, file_path: str = "app.tsx") -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    lang = "html" if file_path.endswith((".html", ".htm")) else "typescript"
    for idx, line in enumerate(content.splitlines(), start=1):
        for rule_id, severity, category, pat, message in _FE_RULES:
            if pat.search(line):
                issues.append({
                    "ruleId": f"{lang}:{rule_id}",
                    "language": lang,
                    "severity": severity,
                    "category": category,
                    "confidence": "HIGH",
                    "location": {"file": file_path, "startLine": idx},
                    "message": message,
                })
    return issues
