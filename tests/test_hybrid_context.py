"""Regression coverage for opt-in hybrid supplementary-context selection."""

from deicide.context.context_budget import serialize_context_bundle
from deicide.context.context_models import (
    ContextRelationshipCategory,
    ContextSelectionLimits,
    ContextSelectionResult,
    SelectedSnippet,
)
from deicide.context.context_relevance import select_hybrid_supplementary_context
from deicide.core.config import DeicideConfig
from deicide.git.models import ContextSnippet, DiffHunk, FileChangeStatus, FileContext, FileDiff
from deicide.modules.code_review import CodeReviewModule


def _snippet(
    snippet_id: str,
    relationship: ContextRelationshipCategory,
    *,
    path: str = "service.py",
    start: int = 10,
    end: int = 11,
    content: str = "10 | return value\n11 | raise ValueError(value)",
) -> SelectedSnippet:
    return SelectedSnippet(
        snippet_id=snippet_id,
        file_path=path,
        start_line=start,
        end_line=end,
        content=content,
        relationship=relationship,
    )


def _contexts() -> dict[str, FileContext]:
    return {
        "service.py": FileContext(
            file_path="service.py",
            total_lines=20,
            snippets=[
                ContextSnippet(
                    start_line=10,
                    end_line=11,
                    lines={10: "return value", 11: "raise ValueError(value)"},
                )
            ],
        )
    }


def _result(*snippets: SelectedSnippet, enabled: bool = True, serialized_text: str | None = None) -> ContextSelectionResult:
    return ContextSelectionResult(
        selected_snippets=list(snippets),
        selected_snippets_count=len(snippets),
        serialized_text=serialized_text if serialized_text is not None else serialize_context_bundle(list(snippets)),
        limits=ContextSelectionLimits(hybrid_static_selection_enabled=enabled),
    )


def test_hybrid_selection_is_disabled_by_default() -> None:
    changed = _snippet("changed", ContextRelationshipCategory.CHANGED_SYMBOL)
    result = _result(changed, enabled=False)

    selection = select_hybrid_supplementary_context(result, _contexts())

    assert selection.suppressed_snippet_ids == ()
    assert selection.serialized_text == result.serialized_text
    assert selection.saved_tokens == 0
    assert DeicideConfig(repo_path=".", provider="fake").hybrid_static_selection_enabled is False


def test_hybrid_selection_removes_only_proved_changed_symbol_duplicate_and_keeps_indirect_context() -> None:
    changed = _snippet("changed", ContextRelationshipCategory.CHANGED_SYMBOL)
    caller = _snippet(
        "caller",
        ContextRelationshipCategory.DIRECT_CALLER,
        path="caller.py",
        start=3,
        end=3,
        content="3 | return service(value)",
    )

    selection = select_hybrid_supplementary_context(_result(changed, caller), _contexts())

    assert selection.suppressed_snippet_ids == ("changed",)
    assert [snippet.snippet_id for snippet in selection.retained_snippets] == ["caller"]
    assert "caller.py" in selection.serialized_text
    assert "service.py" not in selection.serialized_text
    assert selection.saved_tokens > 0
    assert selection.metadata_tokens == 0


def test_hybrid_selection_falls_back_for_content_or_serialization_ambiguity() -> None:
    mismatch = _snippet(
        "changed",
        ContextRelationshipCategory.CHANGED_SYMBOL,
        content="10 | return altered\n11 | raise ValueError(value)",
    )
    mismatched = _result(mismatch)
    mismatch_selection = select_hybrid_supplementary_context(mismatched, _contexts())
    assert mismatch_selection.suppressed_snippet_ids == ()
    assert mismatch_selection.serialized_text == mismatched.serialized_text
    assert mismatch_selection.fallback_reasons

    exact = _snippet("changed", ContextRelationshipCategory.CHANGED_SYMBOL)
    noncanonical = _result(exact, serialized_text="manual supplementary serialization")
    noncanonical_selection = select_hybrid_supplementary_context(noncanonical, _contexts())
    assert noncanonical_selection.suppressed_snippet_ids == ()
    assert noncanonical_selection.serialized_text == noncanonical.serialized_text
    assert noncanonical_selection.fallback_reasons == (
        "supplementary serialization differs from canonical snippet rendering",
    )


def test_prompt_keeps_changed_diff_and_locations_when_duplicate_context_is_suppressed() -> None:
    changed = _snippet("changed", ContextRelationshipCategory.CHANGED_SYMBOL)
    context_result = _result(changed)
    file_diff = FileDiff(
        new_path="service.py",
        status=FileChangeStatus.MODIFIED,
        hunks=[
            DiffHunk(
                old_start=10,
                old_count=2,
                new_start=10,
                new_count=2,
                lines=["-return old", "+return value", "+raise ValueError(value)"],
                added_line_numbers=frozenset({10, 11}),
            )
        ],
    )

    prompt = CodeReviewModule()._build_user_prompt([file_diff], _contexts(), context_result=context_result)

    assert '"file_path": "service.py"' in prompt
    assert '"added_lines": [' in prompt
    assert '"10": "return value"' in prompt
    assert "SUPPLEMENTARY_REPOSITORY_CONTEXT" not in prompt
