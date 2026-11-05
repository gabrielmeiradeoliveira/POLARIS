"""Compatibility adapter from the stable public analysis report to GitHub contracts."""

from __future__ import annotations

from deicide.core.models import AnalysisReport
from deicide.integrations.github.client import GitHubClient
from deicide.integrations.github.mapping import map_findings
from deicide.integrations.github.models import ChangedFile, PullRequestMetadata, ReviewSummary
from deicide.integrations.github.publishing import SafePublisher
from deicide.integrations.github.summary import build_summary


class GitHubReviewAdapter:
    """Connect an `AnalysisReport` to GitHub without importing engine internals."""

    def __init__(self, client: GitHubClient, publisher: SafePublisher) -> None:
        self._client = client
        self._publisher = publisher

    def review(self, pr: PullRequestMetadata, report: AnalysisReport) -> ReviewSummary:
        files = self._client.list_changed_files(pr)
        return self.review_with_files(pr, report, files)

    def review_with_files(
        self,
        pr: PullRequestMetadata,
        report: AnalysisReport,
        files: list[ChangedFile],
    ) -> ReviewSummary:
        """Map and publish using already fetched PR files to avoid duplicate fetches."""
        mapped = map_findings(report.findings, files)
        operations = self._publisher.publish(pr, mapped)
        return build_summary(len(report.files_analyzed), report.findings, mapped, operations)
