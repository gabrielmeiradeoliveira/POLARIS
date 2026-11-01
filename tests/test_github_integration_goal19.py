"""Offline contract tests for the GitHub PR integration."""

from __future__ import annotations

import json

import pytest

from deicide.core.models import (
    AnalysisReport,
    Confidence,
    Finding,
    FindingCategory,
    LineRange,
    ProviderInfo,
    Severity,
    TokenUsage,
)
from deicide.integrations.github.adapter import GitHubReviewAdapter
from deicide.integrations.github.client import GitHubClient
from deicide.integrations.github.mapping import map_finding, map_findings
from deicide.integrations.github.models import (
    ChangedFile,
    GitHubErrorCategory,
    GitHubIntegrationError,
    HttpResponse,
    MappedComment,
    PublishOperation,
    PullRequestMetadata,
)
from deicide.integrations.github.publishing import SafePublisher
from deicide.integrations.github.summary import build_summary


class ScriptedTransport:
    def __init__(self, responses: list[HttpResponse | Exception]) -> None:
        self.responses = responses
        self.requests: list[tuple[str, str, dict[str, str], str | None]] = []

    def request(self, method: str, path: str, *, headers: dict[str, str], body: str | None, timeout_seconds: float) -> HttpResponse:
        self.requests.append((method, path, headers, body))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def response(status: int, payload: object, headers: dict[str, str] | None = None) -> HttpResponse:
    return HttpResponse(status_code=status, body=json.dumps(payload), headers=headers or {})


def pr() -> PullRequestMetadata:
    return PullRequestMetadata(owner="acme", repository="demo", number=7, head_sha="head", base_sha="base")


def finding(path: str = "src/app.py", line: int = 4, finding_id: str = "finding-001") -> Finding:
    return Finding(id=finding_id, module_id="code_review", category=FindingCategory.CORRECTNESS, severity=Severity.HIGH, confidence=Confidence.HIGH, file_path=path, line_range=LineRange(start_line=line, end_line=line), title="Unsafe calculation", description="A concrete defect was detected in changed code.", evidence="return 1 / 0")


def test_pagination_and_file_payload_validation() -> None:
    link = '<https://api.github.com/repos/acme/demo/pulls/7/files?per_page=100&page=2>; rel="next"'
    transport = ScriptedTransport([response(200, [{"filename": "src/a.py", "status": "modified", "patch": "@@ -1 +1 @@\n-a\n+b"}], {"Link": link}), response(200, [{"filename": "src/b.py", "status": "added", "patch": "@@ -0,0 +1 @@\n+x"}])])
    files = GitHubClient(transport).list_changed_files(pr())
    assert [item.path for item in files] == ["src/a.py", "src/b.py"]


@pytest.mark.parametrize(("status", "category", "headers"), [(401, GitHubErrorCategory.AUTHENTICATION, {}), (403, GitHubErrorCategory.AUTHORIZATION, {}), (404, GitHubErrorCategory.NOT_FOUND, {}), (429, GitHubErrorCategory.RATE_LIMIT, {}), (500, GitHubErrorCategory.SERVER, {}), (403, GitHubErrorCategory.RATE_LIMIT, {"X-RateLimit-Remaining": "0"})])
def test_http_errors_are_classified_offline(status: int, category: GitHubErrorCategory, headers: dict[str, str]) -> None:
    with pytest.raises(GitHubIntegrationError) as raised:
        GitHubClient(ScriptedTransport([response(status, {}, headers)]), max_retries=0).get_pull_request("acme", "demo", 7)
    assert raised.value.category == category


def test_timeout_network_and_invalid_payload_are_classified() -> None:
    for failure, expected in [(TimeoutError(), GitHubErrorCategory.TIMEOUT), (OSError(), GitHubErrorCategory.NETWORK)]:
        with pytest.raises(GitHubIntegrationError) as raised:
            GitHubClient(ScriptedTransport([failure]), max_retries=0).get_pull_request("acme", "demo", 7)
        assert raised.value.category == expected
    with pytest.raises(GitHubIntegrationError) as raised:
        GitHubClient(ScriptedTransport([HttpResponse(status_code=200, body="not-json")])).get_pull_request("acme", "demo", 7)
    assert raised.value.category == GitHubErrorCategory.INVALID_RESPONSE


def test_mapping_multiple_hunks_renames_removed_and_outside_diff() -> None:
    changed = ChangedFile(path="src/new.py", previous_path="src/old.py", status="renamed", patch="@@ -2,2 +2,2 @@\n-old\n+new\n keep\n@@ -10 +10 @@\n-old2\n+new2")
    assert map_finding(finding("src/new.py", 10), [changed]).position is not None
    removed = map_finding(finding("src/old.py", 2), [changed])
    assert removed.position is not None and removed.position.side == "LEFT"
    assert map_finding(finding("src/new.py", 3), [changed]).position is None


def test_dry_run_deduplicates_and_never_posts_or_exposes_token() -> None:
    transport = ScriptedTransport([response(200, [{"body": "<!-- deicide:finding:finding-001 --> prior"}])])
    publisher = SafePublisher(GitHubClient(transport, token="secret-token"), dry_run=True)
    operations = publisher.publish(pr(), [MappedComment(finding_id="finding-001", body="same"), MappedComment(finding_id="finding-002", body="next")])
    assert [operation.status for operation in operations] == ["duplicate", "dry_run"]
    assert len(transport.requests) == 1
    assert "secret-token" not in str(operations)


def test_real_publish_is_explicit_and_uses_one_batch_request() -> None:
    transport = ScriptedTransport([response(200, []), response(200, {})])
    publisher = SafePublisher(GitHubClient(transport), dry_run=False)
    comment = MappedComment(finding_id="finding-001", body="body", position={"path": "src/a.py", "line": 2, "side": "RIGHT"})
    operations = publisher.publish(pr(), [comment])
    assert [operation.status for operation in operations] == ["published"]
    assert [request[0] for request in transport.requests] == ["GET", "POST"]
    assert json.loads(transport.requests[1][3] or "{}") ["comments"][0]["line"] == 2


def test_publish_failure_is_recorded_without_individual_retry_or_partial_claim() -> None:
    transport = ScriptedTransport([response(200, []), response(500, {})])
    publisher = SafePublisher(GitHubClient(transport, max_retries=0), dry_run=False)
    comment = MappedComment(finding_id="finding-001", body="body", position={"path": "src/a.py", "line": 2, "side": "RIGHT"})
    operations = publisher.publish(pr(), [comment])
    assert operations[-1].status == "error"
    assert all(operation.status != "published" for operation in operations)


def test_mapping_is_deterministic_and_finding_without_location_becomes_summary() -> None:
    changed = ChangedFile(path="src/app.py", status="added", patch="@@ -0,0 +1,4 @@\n+a\n+b\n+c\n+d")
    mapped = map_findings([finding(line=40, finding_id="zzzzz"), finding(line=4, finding_id="aaaaa")], [changed])
    assert [item.finding_id for item in mapped] == ["aaaaa", "zzzzz"]
    assert mapped[0].position is not None and mapped[1].position is None


def test_review_summary_is_deterministic_and_counts_all_required_outcomes() -> None:
    located = MappedComment(finding_id="finding-001", body="body", position={"path": "src/a.py", "line": 2, "side": "RIGHT"})
    unlocated = MappedComment(finding_id="finding-002", body="body", reason="outside diff")
    operations = [
        PublishOperation(finding_id="finding-001", action="review_comment", status="dry_run"),
        PublishOperation(finding_id="finding-003", action="review_comment", status="duplicate"),
    ]
    summary = build_summary(3, [finding(), finding(finding_id="finding-002")], [located, unlocated], operations)
    assert summary.model_dump() == {
        "files_analyzed": 3,
        "findings": 2,
        "severities": {"high": 2},
        "findings_with_valid_location": 1,
        "findings_without_valid_location": 1,
        "new_comments": 1,
        "duplicate_comments": 1,
        "operational_errors": [],
        "status": "dry_run",
    }


def test_public_analysis_report_adapter_runs_offline_end_to_end() -> None:
    transport = ScriptedTransport(
        [
            response(200, [{"filename": "src/app.py", "status": "modified", "patch": "@@ -4 +4 @@\n-old\n+new"}]),
            response(200, []),
        ]
    )
    report = AnalysisReport(
        repository_root="C:/repo",
        target_description="test",
        modules_executed=["code_review"],
        provider=ProviderInfo(provider_name="fake", model_name="fake"),
        usage=TokenUsage(),
        files_analyzed=["src/app.py"],
        findings=[finding()],
    )
    adapter = GitHubReviewAdapter(GitHubClient(transport), SafePublisher(GitHubClient(transport)))
    summary = adapter.review(pr(), report)
    assert summary.status == "dry_run"
    assert summary.findings_with_valid_location == 1
    assert summary.new_comments == 1
