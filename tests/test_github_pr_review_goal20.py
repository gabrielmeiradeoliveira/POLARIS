"""End-to-end offline PR review tests for Goal 20."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from deicide.cli import app
from deicide.core.errors import BudgetExceededError
from deicide.core.models import ExecutionBudget
from deicide.integrations.github.client import GitHubClient
from deicide.integrations.github.fixture_transport import FixtureGitHubTransport
from deicide.integrations.github.review_engine import GitHubPullRequestReview
from deicide.providers.fake import FakeProvider


def _fixture(
    *, patch: str | None, comments: list[dict[str, str]] | None = None, status: str = "modified"
) -> dict[str, object]:
    return {
        "pull_request": {"title": "Offline PR", "state": "open", "head": {"sha": "head"}, "base": {"sha": "base"}},
        "files": [
            {"filename": "src/new_name.py", "previous_filename": "src/old_name.py", "status": status, "patch": patch}
        ],
        "comments": comments or [],
    }


def _engine(payload: dict[str, object]) -> tuple[GitHubPullRequestReview, FixtureGitHubTransport]:
    transport = FixtureGitHubTransport(payload)
    return GitHubPullRequestReview(GitHubClient(transport), FakeProvider()), transport


def test_pr_review_connects_fixture_patch_to_engine_mapping_and_dry_run() -> None:
    engine, transport = _engine(_fixture(patch="@@ -0,0 +1 @@\n+return 1 / 0", status="renamed"))

    report, summary = engine.review("acme", "demo", 7)

    assert report.status == "completed"
    assert len(report.findings) == 1
    assert report.findings[0].file_path == "src/new_name.py"
    assert report.findings[0].line_range.start_line == 1
    assert summary.status == "dry_run"
    assert summary.findings_with_valid_location == 1
    assert summary.new_comments == 1
    assert all(method == "GET" for method, _ in transport.requests)
    assert [path for _, path in transport.requests][-1].endswith("/comments?per_page=100&page=1")


def test_pr_review_marks_missing_patch_incomplete_without_inventing_context() -> None:
    engine, transport = _engine(_fixture(patch=None))

    report, summary = engine.review("acme", "demo", 7)

    assert report.status == "incomplete"
    assert report.findings == []
    assert summary.findings == 0
    assert all(method == "GET" for method, _ in transport.requests)


def test_pr_review_clean_change_has_no_false_positive_comment() -> None:
    engine, transport = _engine(_fixture(patch="@@ -0,0 +1 @@\n+return 3"))

    report, summary = engine.review("acme", "demo", 7)

    assert report.status == "completed"
    assert report.findings == []
    assert summary.findings == 0
    assert summary.new_comments == 0
    assert all(method == "GET" for method, _ in transport.requests)


def test_pr_review_deduplicates_existing_comment_by_stable_finding_marker() -> None:
    initial_engine, _ = _engine(_fixture(patch="@@ -0,0 +1 @@\n+return 1 / 0"))
    initial_report, _ = initial_engine.review("acme", "demo", 7)
    marker = f"<!-- deicide:finding:{initial_report.findings[0].id} --> existing"
    engine, transport = _engine(_fixture(patch="@@ -0,0 +1 @@\n+return 1 / 0", comments=[{"body": marker}]))

    _, summary = engine.review("acme", "demo", 7)

    assert summary.duplicate_comments == 1
    assert summary.new_comments == 0
    assert all(method == "GET" for method, _ in transport.requests)


def test_pr_review_stops_before_publication_when_provider_budget_is_exhausted() -> None:
    transport = FixtureGitHubTransport(_fixture(patch="@@ -0,0 +1 @@\n+return 1 / 0"))
    engine = GitHubPullRequestReview(
        GitHubClient(transport),
        FakeProvider(),
        budget=ExecutionBudget(max_requests=1, max_total_tokens=100),
    )

    with pytest.raises(BudgetExceededError):
        engine.review("acme", "demo", 7)

    assert [method for method, _ in transport.requests] == ["GET", "GET"]


def test_github_cli_runs_fixture_only_and_emits_structured_json(tmp_path) -> None:
    fixture = tmp_path / "pr.json"
    fixture.write_text(json.dumps(_fixture(patch="@@ -0,0 +1 @@\n+return 1 / 0")), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "github",
            "review",
            "--repo",
            "acme/demo",
            "--pr",
            "7",
            "--fixture",
            str(fixture),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["report"]["platform"] == "DEICIDE"
    assert payload["summary"]["status"] == "dry_run"
    assert payload["summary"]["new_comments"] == 1


def test_github_cli_rejects_external_provider(tmp_path) -> None:
    fixture = tmp_path / "pr.json"
    fixture.write_text(json.dumps(_fixture(patch="@@ -0,0 +1 @@\n+return 1 / 0")), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        ["github", "review", "--repo", "acme/demo", "--pr", "7", "--fixture", str(fixture), "--provider", "nvidia"],
    )

    assert result.exit_code == 2
    assert "offline 'fake' provider" in result.output
