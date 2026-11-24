from __future__ import annotations

import re
from typing import Any


def analyze_rust_content(content: str, file_path: str = "lib.rs") -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    is_test = "test" in file_path.lower()
    lines = content.splitlines()
    for idx, line in enumerate(lines, start=1):
        if re.search(r"\bunsafe\s*\{", line):
            prev = lines[idx - 2] if idx >= 2 else ""
            if "// SAFETY:" not in prev and "// SAFETY:" not in line:
                issues.append({"ruleId": "rust:RS-SEC-001", "language": "rust", "severity": "CRITICAL", "category": "SECURITY", "confidence": "HIGH", "location": {"file": file_path, "startLine": idx}, "message": "unsafe block without // SAFETY: comment"})
        if "std::mem::transmute" in line:
            issues.append({"ruleId": "rust:RS-SEC-002", "language": "rust", "severity": "CRITICAL", "category": "SECURITY", "confidence": "HIGH", "location": {"file": file_path, "startLine": idx}, "message": "Unsafe std::mem::transmute usage"})
        if re.search(r'Command::new\("sh"\)\.arg\("-c"\)', line):
            issues.append({"ruleId": "rust:RS-SEC-003", "language": "rust", "severity": "BLOCKER", "category": "SECURITY", "confidence": "HIGH", "location": {"file": file_path, "startLine": idx}, "message": "Dynamic shell execution via Command::new(\"sh\").arg(\"-c\")"})
        if not is_test and ".unwrap()" in line:
            issues.append({"ruleId": "rust:RS-REL-001", "language": "rust", "severity": "MAJOR", "category": "RELIABILITY", "confidence": "HIGH", "location": {"file": file_path, "startLine": idx}, "message": ".unwrap() in non-test code"})
        if not is_test and ".expect(" in line:
            issues.append({"ruleId": "rust:RS-REL-002", "language": "rust", "severity": "MINOR", "category": "RELIABILITY", "confidence": "HIGH", "location": {"file": file_path, "startLine": idx}, "message": ".expect() in non-test code"})
    return issues
