"""Safe, dry-run-first publication of a complete GitHub review batch."""

from __future__ import annotations

from collections.abc import Iterable

from polaris.integrations.github.client import GitHubClient
from polaris.integrations.github.mapping import finding_marker
from polaris.integrations.github.models import MappedComment, PublishOperation, PullRequestMetadata


class SafePublisher:
    """Publishes one atomic review request only when explicitly enabled."""

    def __init__(self, client: GitHubClient, *, dry_run: bool = True) -> None:
        self._client = client
        self.dry_run = dry_run

    @staticmethod
    def _duplicates(comments: Iterable[MappedComment], existing: Iterable[dict[str, object]]) -> set[str]:
        bodies = [str(item.get("body", "")) for item in existing]
        return {
            comment.finding_id
            for comment in comments
            if any(finding_marker(comment.finding_id) in body for body in bodies)
        }

    def publish(self, pr: PullRequestMetadata, comments: Iterable[MappedComment]) -> list[PublishOperation]:
        """Plan all comments first; a single review request prevents per-comment partial publication."""
        comment_list = list(comments)
        existing = self._client.list_review_comments(pr)
        duplicates = self._duplicates(comment_list, existing)
        operations: list[PublishOperation] = []
        publishable: list[MappedComment] = []
        summaries: list[MappedComment] = []
        for comment in comment_list:
            if comment.finding_id in duplicates:
                operations.append(
                    PublishOperation(finding_id=comment.finding_id, action="review_comment", status="duplicate")
                )
            elif comment.position is None:
                summaries.append(comment)
                operations.append(
                    PublishOperation(
                        finding_id=comment.finding_id,
                        action="summary",
                        status="dry_run" if self.dry_run else "planned",
                        detail=comment.reason or "No valid diff location.",
                    )
                )
            else:
                publishable.append(comment)

        if not publishable and not summaries:
            return operations
        review_body = "POLARIS automated review."
        if summaries:
            review_body += "\n\nFindings without a valid diff location:\n" + "\n".join(
                f"- {item.body}" for item in summaries
            )
        if self.dry_run:
            operations.extend(
                PublishOperation(finding_id=item.finding_id, action="review_comment", status="dry_run")
                for item in publishable
            )
            return operations
        payload = [
            {"path": item.position.path, "line": item.position.line, "side": item.position.side, "body": item.body}
            for item in publishable
            if item.position
        ]
        try:
            self._client.create_review(pr, review_body, payload)
        except Exception as exc:
            operations.append(
                PublishOperation(action="review", status="error", detail=f"Publication failed: {type(exc).__name__}")
            )
            return operations
        operations.extend(
            PublishOperation(finding_id=item.finding_id, action="review_comment", status="published")
            for item in publishable
        )
        return operations
