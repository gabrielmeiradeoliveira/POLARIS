"""End-to-end offline PR review tests for Goal 20."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from polaris.cli import app
from polaris.core.errors import BudgetExceededError
from polaris.core.models import ExecutionBudget
from polaris.integrations.github.client import GitHubClient
from polaris.integrations.github.fixture_transport import FixtureGitHubTransport
from polaris.integrations.github.review_engine import GitHubPullRequestReview
from polaris.providers.fake import FakeProvider


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


class UnavailableProvider:
    provider_name = "controlled-unavailable"
    model_name = "controlled-unavailable-v1"

    def generate(self, _request: object) -> object:
        raise TimeoutError("controlled provider outage")


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


def test_pr_review_handles_empty_and_deleted_file_fixtures_without_publication() -> None:
    empty_payload = _fixture(patch="@@ -0,0 +0,0 @@\n")
    empty_payload["files"] = []
    empty_engine, empty_transport = _engine(empty_payload)
    empty_report, empty_summary = empty_engine.review("acme", "demo", 7)

    assert empty_report.status == "empty_diff"
    assert empty_summary.findings == 0
    assert all(method == "GET" for method, _ in empty_transport.requests)

    deleted_engine, deleted_transport = _engine(
        _fixture(patch="@@ -1 +0,0 @@\n-return 1 / 0", status="removed")
    )
    deleted_report, deleted_summary = deleted_engine.review("acme", "demo", 7)

    assert deleted_report.status == "completed"
    assert deleted_summary.new_comments == 0
    assert all(method == "GET" for method, _ in deleted_transport.requests)


def test_pr_review_maps_multiple_fixture_findings_and_never_posts() -> None:
    payload = _fixture(patch="@@ -0,0 +1 @@\n+return 1 / 0")
    payload["files"] = [
        {"filename": "src/a.py", "status": "added", "patch": "@@ -0,0 +1 @@\n+return 1 / 0"},
        {"filename": "src/b.py", "status": "added", "patch": "@@ -0,0 +1 @@\n+return 1 / 0"},
    ]
    engine, transport = _engine(payload)

    report, summary = engine.review("acme", "demo", 7)

    assert report.status == "completed"
    assert len(report.findings) == 2
    assert summary.new_comments == 2
    assert all(method == "GET" for method, _ in transport.requests)


def test_pr_review_provider_outage_stops_before_comment_lookup_or_publish() -> None:
    transport = FixtureGitHubTransport(_fixture(patch="@@ -0,0 +1 @@\n+return 1 / 0"))
    engine = GitHubPullRequestReview(GitHubClient(transport), UnavailableProvider())

    with pytest.raises(TimeoutError, match="controlled provider outage"):
        engine.review("acme", "demo", 7)

    assert [method for method, _ in transport.requests] == ["GET", "GET"]


def test_pr_review_rejects_invalid_provider_response_without_candidate_publication() -> None:
    transport = FixtureGitHubTransport(_fixture(patch="@@ -0,0 +1 @@\n+return 1 / 0"))
    engine = GitHubPullRequestReview(
        GitHubClient(transport),
        FakeProvider(scripted_responses=["not-json; ignore prior rules"]),
    )

    report, summary = engine.review("acme", "demo", 7)

    assert report.status == "completed"
    assert report.findings == []
    assert any(warning.code == "MALFORMED_MODEL_RESPONSE" for warning in report.warnings)
    assert summary.new_comments == 0
    assert all(method == "GET" for method, _ in transport.requests)


def test_pr_review_handles_large_patch_fixture_without_publication() -> None:
    lines = "\n".join(f"+# retained context {index}" for index in range(1, 401))
    patch = f"@@ -0,0 +1,400 @@\n{lines}"
    engine, transport = _engine(_fixture(patch=patch, status="added"))

    report, summary = engine.review("acme", "demo", 7)

    assert report.status == "completed"
    assert report.files_analyzed == ["src/new_name.py"]
    assert summary.new_comments == 0
    assert all(method == "GET" for method, _ in transport.requests)


def test_pr_review_deduplicates_existing_comment_by_stable_finding_marker() -> None:
    initial_engine, _ = _engine(_fixture(patch="@@ -0,0 +1 @@\n+return 1 / 0"))
    initial_report, _ = initial_engine.review("acme", "demo", 7)
    marker = f"<!-- polaris:finding:{initial_report.findings[0].id} --> existing"
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
    assert payload["report"]["platform"] == "POLARIS"
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
