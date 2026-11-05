"""Map DEICIDE findings to only explicit, valid unified-diff locations."""

from __future__ import annotations

import re
from collections.abc import Iterable

from deicide.core.models import Finding
from deicide.integrations.github.models import ChangedFile, DiffPosition, MappedComment

_HUNK = re.compile(r"^@@ -(?P<old>\d+)(?:,(?P<old_count>\d+))? \+(?P<new>\d+)(?:,(?P<new_count>\d+))? @@")
_MARKER = "<!-- deicide:finding:{finding_id} -->"


def finding_marker(finding_id: str) -> str:
    """Return the stable hidden marker used for idempotent publication."""
    return _MARKER.format(finding_id=finding_id)


def format_finding(finding: Finding) -> str:
    """Use stable content that never asks GitHub to infer a line location."""
    remediation = f"\n\nSuggested remediation: {finding.suggested_remediation}" if finding.suggested_remediation else ""
    return f"{finding_marker(finding.id)}\n**{finding.severity.value.upper()}** — {finding.title}\n\n{finding.description}\n\nEvidence: {finding.evidence}{remediation}"


def _diff_lines(file: ChangedFile) -> tuple[set[int], set[int]]:
    """Return (old_removed, new_added), excluding context-only lines and malformed hunks."""
    old_removed: set[int] = set()
    new_added: set[int] = set()
    old_line = new_line = None
    for raw in (file.patch or "").splitlines():
        match = _HUNK.match(raw)
        if match:
            old_line = int(match.group("old"))
            new_line = int(match.group("new"))
            continue
        if old_line is None or new_line is None or raw.startswith("\\ No newline"):
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            new_added.add(new_line)
            new_line += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            old_removed.add(old_line)
            old_line += 1
        elif raw.startswith(" "):
            old_line += 1
            new_line += 1
    return old_removed, new_added


def map_finding(finding: Finding, files: Iterable[ChangedFile]) -> MappedComment:
    """Map a finding only when its exact finding line is an added or removed diff line."""
    normalized = finding.file_path.replace("\\", "/").lstrip("./")
    body = format_finding(finding)
    for changed in files:
        removed, added = _diff_lines(changed)
        if normalized == changed.path and finding.line_range.start_line in added:
            return MappedComment(
                finding_id=finding.id,
                body=body,
                position=DiffPosition(path=changed.path, line=finding.line_range.start_line, side="RIGHT"),
            )
        if changed.previous_path and normalized == changed.previous_path and finding.line_range.start_line in removed:
            return MappedComment(
                finding_id=finding.id,
                body=body,
                position=DiffPosition(path=changed.path, line=finding.line_range.start_line, side="LEFT"),
            )
    return MappedComment(finding_id=finding.id, body=body, reason="Finding does not have an exact changed diff line.")


def map_findings(findings: Iterable[Finding], files: Iterable[ChangedFile]) -> list[MappedComment]:
    """Deterministically map findings, retaining unlocatable ones for summary reporting."""
    file_list = list(files)
    return [map_finding(finding, file_list) for finding in sorted(findings, key=lambda item: item.id)]
