from __future__ import annotations

import math
import re
from dataclasses import dataclass

_PROVIDER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS_ACCESS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GITHUB_PAT", re.compile(r"\b(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("POLARIS_TOKEN", re.compile(r"\bpls_[A-Za-z0-9_\-]{16,}\b")),
    ("PEM_PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("DB_CONN_PASSWORD", re.compile(r"(?:postgres|postgresql|mysql|mongodb)://[^:\s]+:[^@\s]+@")),
]


@dataclass(frozen=True)
class SecretFinding:
    rule_id: str
    kind: str
    file_path: str
    line: int
    masked_value: str
    confidence: str = "HIGH"


def shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    if len(text) > 256:
        return max(shannon_entropy(text[i : i + 256]) for i in range(0, len(text), 256))
    freq = {ch: text.count(ch) / len(text) for ch in set(text)}
    return -sum(p * math.log2(p) for p in freq.values())


def mask_secret(value: str) -> str:
    if len(value) <= 6:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 4)


def scan_secrets(file_path: str, content: str) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for line_no, line in enumerate(content.splitlines(), start=1):
        if "polaris:ignore" in line or "NOSONAR" in line:
            continue
        for kind, pat in _PROVIDER_PATTERNS:
            for m in pat.finditer(line):
                findings.append(
                    SecretFinding(
                        rule_id="security:SECRET_EXPOSED",
                        kind=kind,
                        file_path=file_path,
                        line=line_no,
                        masked_value=mask_secret(m.group(0)),
                    )
                )
    return findings
