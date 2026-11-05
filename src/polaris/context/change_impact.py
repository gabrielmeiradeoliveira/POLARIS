"""Conservative, local evidence checks for change-impact context decisions.

This module does not classify bugs.  It only proves whether a numbered
supplementary snippet is already present, byte-for-byte at each source line,
in the primary changed-file context that will be sent to the model.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from deicide.context.context_models import SelectedSnippet
from deicide.git.models import FileContext


@dataclass(frozen=True)
class ExactOverlapEvidence:
    """Outcome of an exact primary-prompt coverage check."""

    is_exact: bool
    covered_lines: int
    reason: str


def primary_prompt_source_lines(contexts: Mapping[str, FileContext]) -> dict[str, dict[int, str]]:
    """Return the exact numbered source values serialized in the primary prompt."""
    return {
        path: {line_no: line for snippet in context.snippets for line_no, line in snippet.lines.items()}
        for path, context in contexts.items()
    }


def prove_exact_primary_overlap(
    snippet: SelectedSnippet,
    primary_source_lines: Mapping[str, Mapping[int, str]],
) -> ExactOverlapEvidence:
    """Prove that every exact numbered line of ``snippet`` is in primary prompt data.

    Any malformed numbered line, a missing primary line, or a textual mismatch is
    deliberately treated as non-overlap.  Callers must retain supplementary
    context in those cases.
    """
    primary_lines = primary_source_lines.get(snippet.file_path)
    if primary_lines is None:
        return ExactOverlapEvidence(False, 0, "changed file has no primary prompt context")

    parsed: list[tuple[int, str]] = []
    for raw_line in snippet.content.splitlines():
        line_number, separator, source = raw_line.partition(" | ")
        if not separator or not line_number.strip().isdigit():
            return ExactOverlapEvidence(False, 0, "supplementary snippet is not an exact numbered source slice")
        parsed.append((int(line_number.strip()), source))

    expected_lines = list(range(snippet.start_line, snippet.end_line + 1))
    if not parsed or [line for line, _ in parsed] != expected_lines:
        return ExactOverlapEvidence(False, 0, "supplementary snippet line span is incomplete or non-contiguous")

    for line_no, source in parsed:
        if primary_lines.get(line_no) != source:
            return ExactOverlapEvidence(False, 0, f"primary prompt does not exactly contain line {line_no}")

    return ExactOverlapEvidence(True, len(parsed), "all numbered source lines are exactly present in primary prompt")
