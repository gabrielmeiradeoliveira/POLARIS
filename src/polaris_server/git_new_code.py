from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any


def _run_safe_git(repo_dir: Path, args: list[str]) -> str:
    """Run read-only git command with hooks disabled."""
    cmd = ["git", "-C", str(repo_dir), "-c", "core.hooksPath=/dev/null", *args]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=True)
    return res.stdout


def parse_git_diff_added_lines(diff_text: str) -> dict[str, set[int]]:
    """Parse unified=0 git diff output into {file_path: {added_line_numbers}}."""
    changed: dict[str, set[int]] = {}
    current_file: str | None = None
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            changed.setdefault(current_file, set())
        elif line.startswith("@@ ") and current_file:
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2)) if m.group(2) is not None else 1
                for ln in range(start, start + count):
                    changed[current_file].add(ln)
    return changed


def compute_new_code_issues(
    issues: list[dict[str, Any]],
    changed_lines_by_file: dict[str, set[int]],
) -> dict[str, Any]:
    """Separate issues into new_code_issues and overall_only_issues."""
    new_issues: list[dict[str, Any]] = []
    historical_issues: list[dict[str, Any]] = []
    for iss in issues:
        fpath = iss.get("file_path") or iss.get("location", {}).get("file", "")
        line = int(iss.get("line") or iss.get("location", {}).get("startLine", 0))
        if fpath in changed_lines_by_file and line in changed_lines_by_file[fpath]:
            new_issues.append(iss)
        else:
            historical_issues.append(iss)
    return {
        "new_issues_count": len(new_issues),
        "historical_issues_count": len(historical_issues),
        "new_issues": new_issues,
        "historical_issues": historical_issues,
    }
