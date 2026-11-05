"""Independent structural validation for reconstructed unified-diff fixtures."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HUNK = re.compile(r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@")


class FixtureIntegrityError(ValueError):
    """Raised when a fixture diff cannot be structurally reconstructed."""


@dataclass(frozen=True)
class ValidatedFixtureDiff:
    """A fixture file whose diff was independently round-tripped."""

    file_path: str
    before: str
    after: str
    hunk_count: int


def validate_fixture_diff(diff_text: str, file_contents: dict[str, str]) -> list[ValidatedFixtureDiff]:
    """Validate unified-diff syntax and independently reverse/apply every file hunk."""
    lines = diff_text.splitlines()
    files: list[ValidatedFixtureDiff] = []
    index = 0
    while index < len(lines):
        if not lines[index].startswith("diff --git "):
            index += 1
            continue
        index += 1
        path: str | None = None
        hunks: list[tuple[int, int, int, int, list[str], list[str]]] = []
        while index < len(lines) and not lines[index].startswith("diff --git "):
            line = lines[index]
            if line.startswith("+++ b/"):
                path = line[6:]
                index += 1
                continue
            match = _HUNK.match(line)
            if not match:
                index += 1
                continue
            old_start = int(match["old_start"])
            old_count = int(match["old_count"] or "1")
            new_start = int(match["new_start"])
            new_count = int(match["new_count"] or "1")
            index += 1
            old_body: list[str] = []
            new_body: list[str] = []
            while index < len(lines) and not lines[index].startswith(("diff --git ", "@@ ")):
                body = lines[index]
                if body.startswith("-") and not body.startswith("---"):
                    old_body.append(body[1:])
                elif body.startswith("+") and not body.startswith("+++"):
                    new_body.append(body[1:])
                elif body.startswith(" "):
                    old_body.append(body[1:])
                    new_body.append(body[1:])
                elif body.startswith("\\ No newline"):
                    pass
                else:
                    raise FixtureIntegrityError(f"Unexpected hunk line: {body!r}")
                index += 1
            if len(old_body) != old_count or len(new_body) != new_count:
                raise FixtureIntegrityError(
                    f"Hunk counts differ from body: declared {old_count}/{new_count}, actual {len(old_body)}/{len(new_body)}"
                )
            hunks.append((old_start, old_count, new_start, new_count, old_body, new_body))
        if path is None or path not in file_contents:
            raise FixtureIntegrityError(f"Diff path is not materialized: {path!r}")
        after_lines = file_contents[path].splitlines()
        source = list(after_lines)
        for _old_start, _old_count, new_start, new_count, old_body, new_body in reversed(hunks):
            at = new_start - 1
            if at < 0 or source[at : at + new_count] != new_body:
                raise FixtureIntegrityError(f"New-side lines do not match materialized AFTER for {path}:{new_start}")
            source[at : at + new_count] = old_body
        before = source
        rebuilt = list(before)
        offset = 0
        for old_start, old_count, _new_start, new_count, old_body, new_body in hunks:
            at = old_start - 1 + offset
            if at < 0 or rebuilt[at : at + old_count] != old_body:
                raise FixtureIntegrityError(f"Old-side lines do not match reconstructed BEFORE for {path}:{old_start}")
            rebuilt[at : at + old_count] = new_body
            offset += new_count - old_count
        if rebuilt != after_lines:
            raise FixtureIntegrityError(f"Forward application does not reconstruct AFTER for {path}")
        newline = "\n" if file_contents[path].endswith("\n") else ""
        files.append(ValidatedFixtureDiff(path, "\n".join(before) + newline, file_contents[path], len(hunks)))
    if not files:
        raise FixtureIntegrityError("Diff contains no files")
    return files
