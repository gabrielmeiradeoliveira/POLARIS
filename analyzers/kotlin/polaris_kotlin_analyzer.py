from __future__ import annotations

import re
from typing import Any

_KT_RULES: list[tuple[str, str, str, re.Pattern[str], str]] = [
    ("KT-SEC-001", "CRITICAL", "SECURITY", re.compile(r'"[^"]*\b(?:SELECT|INSERT|UPDATE|DELETE)\b[^"]*\$[A-Za-z_]\w*'), "SQL Injection via string template"),
    ("KT-SEC-002", "BLOCKER", "SECURITY", re.compile(r"(?:X509TrustManager|HostnameVerifier\s*\{\s*_\s*,\s*_\s*->\s*true)"), "Permissive TLS trust manager or hostname verifier"),
    ("KT-SEC-003", "BLOCKER", "SECURITY", re.compile(r"""(?:val|var|const\s+val)\s+(?:password|secret|apiKey|token)\s*=\s*"[^"]{6,}" """.strip(), re.I), "Hardcoded secret in Kotlin"),
    ("KT-SEC-004", "BLOCKER", "SECURITY", re.compile(r"ObjectInputStream\s*\([^)]*\)\.readObject\s*\("), "Untrusted deserialization via ObjectInputStream.readObject"),
    ("KT-REL-001", "MAJOR", "RELIABILITY", re.compile(r"[A-Za-z0-9_)\]]!!"), "Unsafe non-null assertion (!!)"),
    ("KT-REL-002", "MAJOR", "RELIABILITY", re.compile(r"\brunBlocking\s*\{"), "Blocking coroutine runBlocking usage"),
    ("KT-REL-003", "MAJOR", "RELIABILITY", re.compile(r"\bGlobalScope\.launch\b"), "Unstructured concurrency via GlobalScope.launch"),
    ("KT-REL-004", "MINOR", "RELIABILITY", re.compile(r"catch\s*\([^)]+\)\s*\{\s*\}"), "Empty catch block"),
]


def analyze_kotlin_content(content: str, file_path: str = "Main.kt") -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for idx, line in enumerate(content.splitlines(), start=1):
        for rule_id, severity, category, pat, message in _KT_RULES:
            if pat.search(line):
                issues.append({
                    "ruleId": f"kotlin:{rule_id}",
                    "language": "kotlin",
                    "severity": severity,
                    "category": category,
                    "confidence": "HIGH",
                    "location": {"file": file_path, "startLine": idx},
                    "message": message,
                })
    return issues
