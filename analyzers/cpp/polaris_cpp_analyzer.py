from __future__ import annotations

import re
from typing import Any


def analyze_cpp_content(content: str, file_path: str = "main.c") -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    lines = content.splitlines()
    for idx, line in enumerate(lines, start=1):
        if re.search(r"\b(?:gets|strcpy|strcat|sprintf)\s*\(", line):
            issues.append({"ruleId": "cpp:CPP-SEC-001", "language": "cpp", "severity": "BLOCKER", "category": "SECURITY", "confidence": "HIGH", "location": {"file": file_path, "startLine": idx}, "message": "Banned unsafe buffer function"})
        if re.search(r'\b(?:system|popen)\s*\(\s*(?!")', line):
            issues.append({"ruleId": "cpp:CPP-SEC-002", "language": "cpp", "severity": "BLOCKER", "category": "SECURITY", "confidence": "HIGH", "location": {"file": file_path, "startLine": idx}, "message": "Command injection via system/popen with non-literal arg"})
        if re.search(r'\b(?:printf\s*\(\s*[A-Za-z_]\w*\s*\)|fprintf\s*\([^,]+,\s*[A-Za-z_]\w*\s*\))', line):
            issues.append({"ruleId": "cpp:CPP-SEC-003", "language": "cpp", "severity": "CRITICAL", "category": "SECURITY", "confidence": "HIGH", "location": {"file": file_path, "startLine": idx}, "message": "Format string vulnerability"})
        if re.search(r"\b(?:rand|srand)\s*\(", line):
            issues.append({"ruleId": "cpp:CPP-SEC-004", "language": "cpp", "severity": "MAJOR", "category": "SECURITY", "confidence": "HIGH", "location": {"file": file_path, "startLine": idx}, "message": "Weak PRNG rand()/srand()"})
    if re.search(r"\b(?:malloc|calloc)\s*\(", content) and "free(" not in content:
        issues.append({"ruleId": "cpp:CPP-REL-001", "language": "cpp", "severity": "MAJOR", "category": "RELIABILITY", "confidence": "HIGH", "location": {"file": file_path, "startLine": 1}, "message": "malloc/calloc without matching free()"})
    return issues
