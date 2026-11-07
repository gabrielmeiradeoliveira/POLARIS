"""Synthetic-secret regression tests for the provider prompt boundary."""

from polaris.context.context_models import (
    ContextRelationshipCategory,
    ContextSelectionResult,
    SelectedSnippet,
)
from polaris.git.models import ContextSnippet, DiffHunk, FileChangeStatus, FileContext, FileDiff
from polaris.modules.code_review import CodeReviewModule


def test_prompt_redacts_synthetic_secret_literals_but_preserves_code_structure() -> None:
    secret = "synthetic-secret-value-123"
    file_diff = FileDiff(
        new_path="settings.py",
        status=FileChangeStatus.MODIFIED,
        hunks=[
            DiffHunk(
                old_start=1,
                old_count=1,
                new_start=1,
                new_count=2,
                lines=['-API_TOKEN = "old"', f'+API_TOKEN = "{secret}"', '+timeout = 30'],
                added_line_numbers=frozenset({1, 2}),
            )
        ],
    )
    context = FileContext(
        file_path="settings.py",
        total_lines=2,
        snippets=[ContextSnippet(start_line=1, end_line=2, lines={1: f'API_TOKEN = "{secret}"', 2: "timeout = 30"})],
    )

    prompt = CodeReviewModule()._build_user_prompt([file_diff], {"settings.py": context})

    assert secret not in prompt
    assert "[REDACTED]" in prompt
    assert "timeout = 30" in prompt


def test_prompt_redacts_synthetic_secrets_in_supplementary_and_delta_channels() -> None:
    secret = "synthetic-secret-value-456"
    selection = ContextSelectionResult(
        selected_snippets=[
            SelectedSnippet(
                snippet_id="support",
                file_path="support.py",
                start_line=1,
                end_line=1,
                content=f'PASSWORD = "{secret}"',
                relationship=ContextRelationshipCategory.DIRECT_CALLEE,
            )
        ],
        serialized_text=f'PASSWORD = "{secret}"',
        selected_snippets_count=1,
        serialized_behavioral_deltas=f'Observed: config["api_key"] = "{secret}"',
        max_allowed_tokens=500,
    )
    file_diff = FileDiff(new_path="service.py", status=FileChangeStatus.MODIFIED)

    prompt = CodeReviewModule()._build_user_prompt([file_diff], {}, context_result=selection)

    assert secret not in prompt
    assert prompt.count("[REDACTED]") >= 2
