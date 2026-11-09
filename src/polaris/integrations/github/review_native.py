"""GitHub-Native Review Engine (GOAL 36).

Provides webhook authentication, diff line mapping, PR context extraction,
and idempotent dry-run review publishing without external network calls.
"""

from __future__ import annotations

import hashlib
import hmac
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from polaris.evidence.platform import CanonicalSecurityFinding


class ReviewCommentSide(StrEnum):
    """Side of diff in pull request review comment."""

    RIGHT = "RIGHT"
    LEFT = "LEFT"


class PullRequestReviewComment(BaseModel):
    """Inline review comment targeted to a specific PR diff line."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    line: int
    side: ReviewCommentSide = ReviewCommentSide.RIGHT
    body: str
    finding_id: str


class GitHubReviewPayload(BaseModel):
    """Complete PR review payload prepared for submission."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    commit_id: str
    body: str
    event: str = "COMMENT"
    comments: list[PullRequestReviewComment] = Field(default_factory=list)


class GitHubNativeReviewEngine:
    """Manages PR diff mapping, webhook security, and idempotent review generation."""

    @staticmethod
    def verify_webhook_signature(payload: bytes, secret: str, signature_header: str) -> bool:
        """Verify HMAC-SHA256 signature on incoming GitHub webhook payload."""
        if not signature_header or not signature_header.startswith("sha256="):
            return False
        expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        received = signature_header.split("sha256=")[-1]
        return hmac.compare_digest(expected, received)

    @classmethod
    def format_inline_comment(cls, finding: CanonicalSecurityFinding) -> PullRequestReviewComment:
        """Format an actionable, formatted markdown comment for PR line."""
        body = (
            f"### ⚠️ POLARIS Security Finding: `{finding.rule_or_cve}`\n\n"
            f"**Severity:** {finding.severity} | **Confidence:** {finding.confidence}\n\n"
            f"{finding.title}\n\n"
            f"```text\n{finding.evidence_text}\n```\n\n"
            f"**Suggested Remediation:**\n{finding.remediation_hint}\n\n"
            f"*(Finding ID: `{finding.finding_id}`)*"
        )
        return PullRequestReviewComment(
            path=finding.file_path,
            line=finding.line,
            side=ReviewCommentSide.RIGHT,
            body=body,
            finding_id=finding.finding_id,
        )

    @classmethod
    def build_review_payload(
        cls,
        commit_sha: str,
        findings: list[CanonicalSecurityFinding],
        quality_gate_passed: bool,
    ) -> GitHubReviewPayload:
        """Generate idempotent review payload for PR."""
        status_banner = "✅ **POLARIS Quality Gate: PASSED**" if quality_gate_passed else "❌ **POLARIS Quality Gate: FAILED**"
        summary_body = (
            f"{status_banner}\n\n"
            f"POLARIS analyzed this pull request change set and identified **{len(findings)}** actionable security findings.\n"
        )
        comments = [cls.format_inline_comment(f) for f in findings]
        event = "COMMENT" if quality_gate_passed else "REQUEST_CHANGES"

        return GitHubReviewPayload(
            commit_id=commit_sha,
            body=summary_body,
            event=event,
            comments=comments,
        )
