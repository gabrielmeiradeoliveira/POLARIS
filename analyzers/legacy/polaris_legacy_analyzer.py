from __future__ import annotations

import re
from typing import Any

_LEGACY_RULES: list[tuple[str, str, str, re.Pattern[str], str]] = [
    ("LEG-SEC-001", "CRITICAL", "SECURITY", re.compile(r"\b(?:MD5|SHA1|DES|3DES|RC4|AES/ECB)\b"), "Weak or broken cryptographic algorithm"),
    ("LEG-SEC-002", "CRITICAL", "SECURITY", re.compile(r"\b(?:SSLv3|TLSv1(?:\.1)?|SecurityProtocolType\.Tls)\b"), "Insecure legacy TLS/SSL protocol"),
    ("LEG-SEC-003", "BLOCKER", "SECURITY", re.compile(r"\b(?:BinaryFormatter|ObjectInputStream|pickle\.loads|yaml\.load\s*\([^)]*\)|unserialize)\b"), "Unsafe legacy deserialization"),
    ("LEG-SEC-004", "CRITICAL", "SECURITY", re.compile(r"\b(?:XmlDocument|DocumentBuilderFactory|xml\.etree|lxml\.etree)\b"), "Potential XXE in XML parser"),
    ("LEG-SEC-005", "BLOCKER", "SECURITY", re.compile(r"""(?i)(?:connectionString|password|secret)\s*[:=]\s*["'][^"']{6,}["']"""), "Hardcoded secret or connection string in legacy config"),
    ("LEG-REL-001", "MAJOR", "RELIABILITY", re.compile(r"\b(?:SqlConnection|FileInputStream|open\s*\()"), "Potential unclosed resource stream"),
]


def analyze_legacy_content(content: str, file_path: str = "legacy.py") -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for idx, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line[:2000]
        for rule_id, severity, category, pat, message in _LEGACY_RULES:
            if pat.search(line):
                issues.append({
                    "ruleId": f"legacy:{rule_id}",
                    "language": "python",
                    "severity": severity,
                    "category": category,
                    "confidence": "HIGH",
                    "parseMode": "fallback",
                    "location": {"file": file_path, "startLine": idx},
                    "message": message,
                })
    return issues
