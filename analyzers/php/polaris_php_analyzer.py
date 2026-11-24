from __future__ import annotations

import re
from typing import Any

_PHP_RULES: list[tuple[str, str, str, re.Pattern[str], str]] = [
    ("PHP-SEC-001", "CRITICAL", "SECURITY", re.compile(r"->(?:query|prepare)\s*\([^)]*\$[A-Za-z_]\w*"), "SQL Injection via variable interpolation in query/prepare"),
    ("PHP-SEC-002", "CRITICAL", "SECURITY", re.compile(r"\b(?:echo|print)\b[^;]*\$_(?:GET|POST|REQUEST)\b"), "XSS via unescaped echo/print of superglobal"),
    ("PHP-SEC-003", "BLOCKER", "SECURITY", re.compile(r"\b(?:eval|exec|shell_exec|system|passthru)\s*\("), "Remote Code Execution via dangerous PHP function"),
    ("PHP-SEC-004", "BLOCKER", "SECURITY", re.compile(r"\bunserialize\s*\([^)]*\$_(?:GET|POST|REQUEST|COOKIE)"), "Unsafe unserialize on user input"),
    ("PHP-SEC-005", "CRITICAL", "SECURITY", re.compile(r"\b(?:include|require)(?:_once)?\s*\(?\s*\$[A-Za-z_]\w*"), "Local/Remote File Inclusion via variable path"),
    ("PHP-SEC-006", "MAJOR", "SECURITY", re.compile(r"\b(?:md5|sha1)\s*\([^)]*\$[A-Za-z_]*pass", re.I), "Weak password hashing with md5/sha1"),
    ("PHP-SEC-007", "CRITICAL", "SECURITY", re.compile(r"\bextract\s*\(\s*\$_(?:GET|POST|REQUEST)\s*\)"), "Variable injection via extract() on superglobal"),
    ("PHP-SEC-008", "CRITICAL", "SECURITY", re.compile(r"CURLOPT_SSL_VERIFYPEER\s*,\s*false", re.I), "TLS certificate verification disabled in cURL"),
    ("PHP-SEC-009", "BLOCKER", "SECURITY", re.compile(r"""\$(?:password|api_key|secret)\s*=\s*["'][^"']{6,}["']""", re.I), "Hardcoded credential in PHP"),
    ("PHP-REL-001", "MINOR", "RELIABILITY", re.compile(r"catch\s*\([^)]+\)\s*\{\s*\}"), "Empty catch block swallowing exception"),
]


def analyze_php_content(content: str, file_path: str = "index.php") -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for idx, line in enumerate(content.splitlines(), start=1):
        for rule_id, severity, category, pat, message in _PHP_RULES:
            if pat.search(line):
                issues.append({
                    "ruleId": f"php:{rule_id}",
                    "language": "php",
                    "severity": severity,
                    "category": category,
                    "confidence": "HIGH",
                    "location": {"file": file_path, "startLine": idx},
                    "message": message,
                })
    return issues
