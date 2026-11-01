"""Unit contracts for conservative primary-prompt overlap proofs."""

from deicide.context.change_impact import primary_prompt_source_lines, prove_exact_primary_overlap
from deicide.context.context_models import ContextRelationshipCategory, SelectedSnippet
from deicide.git.models import ContextSnippet, FileContext


def _changed_symbol(content: str = "10 | return value\n11 | raise ValueError(value)") -> SelectedSnippet:
    return SelectedSnippet(
        snippet_id="changed",
        file_path="service.py",
        start_line=10,
        end_line=11,
        content=content,
        relationship=ContextRelationshipCategory.CHANGED_SYMBOL,
    )


def test_exact_overlap_requires_every_numbered_primary_line_and_content() -> None:
    contexts = {
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

    proof = prove_exact_primary_overlap(_changed_symbol(), primary_prompt_source_lines(contexts))

    assert proof.is_exact
    assert proof.covered_lines == 2


def test_exact_overlap_rejects_missing_mismatched_or_noncanonical_snippets() -> None:
    contexts = {
        "service.py": FileContext(
            file_path="service.py",
            total_lines=20,
            snippets=[ContextSnippet(start_line=10, end_line=10, lines={10: "return value"})],
        )
    }
    primary = primary_prompt_source_lines(contexts)

    missing = prove_exact_primary_overlap(_changed_symbol(), primary)
    mismatch = prove_exact_primary_overlap(_changed_symbol("10 | return other\n11 | raise ValueError(value)"), primary)
    unnumbered = prove_exact_primary_overlap(_changed_symbol("return value\nraise ValueError(value)"), primary)

    assert not missing.is_exact
    assert not mismatch.is_exact
    assert not unnumbered.is_exact
