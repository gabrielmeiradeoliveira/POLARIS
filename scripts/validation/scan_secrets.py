from __future__ import annotations

import re
import sys
from pathlib import Path

SECRET_PATTERNS = (
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("generic_token", re.compile(r"(?i)(api_key|secret_key|password)\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]")),
)

SKIP_DIRS = {".git", ".venv", "node_modules", "bin", "obj", "target", "dist", "__pycache__"}


def scan_text(text: str) -> list[str]:
    findings: list[str] = []
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(name)
    return findings


def scan_repository(root: Path) -> list[tuple[str, list[str]]]:
    results: list[tuple[str, list[str]]] = []
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jar", ".dll", ".exe", ".pyc"}:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        hits = scan_text(content)
        if hits:
            results.append((path.relative_to(root).as_posix(), hits))
    return results


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    findings = scan_repository(root)
    if findings:
        for rel, hits in findings:
            print(f"SECRET_DETECTED {rel}: {hits}", file=sys.stderr)
        return 1
    print("SECRETS_SCAN_OK=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
