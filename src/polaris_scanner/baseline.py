from __future__ import annotations

import re
from typing import Any

_SUPPRESS_RE = re.compile(r"(?:#|//|/\*|<!--)\s*polaris-ignore:\s*([A-Za-z0-9:_-]+)\s*--\s*(.+?)(?:\*/|-->)?$")


def extract_suppression(line: str) -> tuple[str, str] | None:
    m = _SUPPRESS_RE.search(line.strip())
    if not m:
        return None
    return m.group(1).strip(), m.group(2).strip()


def filter_new_debt(
    issues: list[dict[str, Any]],
    baseline_fingerprints: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separate newly introduced issues from legacy baseline issues."""
    new_debt: list[dict[str, Any]] = []
    legacy: list[dict[str, Any]] = []
    for issue in issues:
        if issue.get("fingerprint") in baseline_fingerprints:
            legacy.append(issue)
        else:
            new_debt.append(issue)
    return new_debt, legacy
