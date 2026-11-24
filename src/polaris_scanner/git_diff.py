from __future__ import annotations

import re
import subprocess
from pathlib import Path

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_unified_diff(diff_text: str) -> dict[str, set[int]]:
    """Parse `git diff --unified=0` output into {relative_path: {added_or_modified_lines}}."""
    changed: dict[str, set[int]] = {}
    current_file: str | None = None
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            changed.setdefault(current_file, set())
        elif line.startswith("+++ /dev/null"):
            current_file = None
        elif line.startswith("@@ ") and current_file is not None:
            m = _HUNK_RE.match(line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2)) if m.group(2) is not None else 1
                if count > 0:
                    changed[current_file].update(range(start, start + count))
    return changed


class GitDiffResolver:
    """Resolve added/modified line numbers per file against a base git ref."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def resolve(self, base_ref: str) -> dict[str, set[int]]:
        try:
            res = subprocess.run(
                ["git", "diff", "--unified=0", f"{base_ref}...HEAD"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if res.returncode != 0:
                return {}
            return parse_unified_diff(res.stdout)
        except Exception:
            return {}
