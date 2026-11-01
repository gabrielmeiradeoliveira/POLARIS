"""Opt-in conservative relevance filtering for supplementary review context."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from deicide.context.change_impact import primary_prompt_source_lines, prove_exact_primary_overlap
from deicide.context.context_budget import serialize_context_bundle
from deicide.context.context_models import ContextRelationshipCategory, ContextSelectionResult, SelectedSnippet
from deicide.core.models import estimate_token_count
from deicide.git.models import FileContext


@dataclass(frozen=True)
class HybridContextSelection:
    """Prompt-local supplementary-context decision with auditable token accounting."""

    serialized_text: str
    retained_snippets: tuple[SelectedSnippet, ...]
    suppressed_snippet_ids: tuple[str, ...]
    fallback_reasons: tuple[str, ...]
    baseline_tokens: int
    optimized_tokens: int
    metadata_tokens: int = 0

    @property
    def saved_tokens(self) -> int:
        return max(0, self.baseline_tokens - self.optimized_tokens)


def select_hybrid_supplementary_context(
    context_result: ContextSelectionResult,
    contexts: Mapping[str, FileContext],
) -> HybridContextSelection:
    """Remove only proved duplicate ``changed_symbol`` supplementary snippets.

    The primary prompt is the authority.  If serialization is not the canonical
    rendering of the selected snippets, or if any overlap check is ambiguous,
    this function preserves the existing supplementary text unchanged.
    """
    baseline_text = context_result.serialized_text
    baseline_tokens = estimate_token_count(baseline_text) if baseline_text else 0
    selected = list(context_result.selected_snippets)

    if not context_result.hybrid_static_selection_enabled:
        return HybridContextSelection(
            baseline_text, tuple(selected), (), (), baseline_tokens, baseline_tokens
        )

    canonical_text = serialize_context_bundle(selected)
    if canonical_text != baseline_text:
        return HybridContextSelection(
            baseline_text,
            tuple(selected),
            (),
            ("supplementary serialization differs from canonical snippet rendering",),
            baseline_tokens,
            baseline_tokens,
        )

    primary_lines = primary_prompt_source_lines(contexts)
    retained: list[SelectedSnippet] = []
    suppressed: list[str] = []
    fallbacks: list[str] = []
    for snippet in selected:
        if snippet.relationship != ContextRelationshipCategory.CHANGED_SYMBOL:
            retained.append(snippet)
            continue

        evidence = prove_exact_primary_overlap(snippet, primary_lines)
        if evidence.is_exact:
            suppressed.append(snippet.snippet_id)
        else:
            retained.append(snippet)
            fallbacks.append(f"{snippet.snippet_id}: {evidence.reason}")

    optimized_text = serialize_context_bundle(retained)
    return HybridContextSelection(
        optimized_text,
        tuple(retained),
        tuple(suppressed),
        tuple(fallbacks),
        baseline_tokens,
        estimate_token_count(optimized_text) if optimized_text else 0,
    )
