"""Deterministic PR review execution summary."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from deicide.core.models import Finding
from deicide.integrations.github.models import MappedComment, PublishOperation, ReviewSummary


def build_summary(
    files_analyzed: int,
    findings: Iterable[Finding],
    mapped: Iterable[MappedComment],
    operations: Iterable[PublishOperation],
) -> ReviewSummary:
    """Build a stable count-only outcome from immutable integration records."""
    finding_list = list(findings)
    mapped_list = list(mapped)
    operation_list = list(operations)
    severities = dict(sorted(Counter(finding.severity.value for finding in finding_list).items()))
    valid = sum(comment.position is not None for comment in mapped_list)
    new = sum(
        operation.status in {"dry_run", "published"} and operation.action in {"review_comment", "summary"}
        for operation in operation_list
    )
    duplicate = sum(operation.status == "duplicate" for operation in operation_list)
    errors = sorted(operation.detail for operation in operation_list if operation.status == "error")
    status = "failed" if errors else "dry_run" if any(op.status == "dry_run" for op in operation_list) else "completed"
    return ReviewSummary(
        files_analyzed=files_analyzed,
        findings=len(finding_list),
        severities=severities,
        findings_with_valid_location=valid,
        findings_without_valid_location=len(mapped_list) - valid,
        new_comments=new,
        duplicate_comments=duplicate,
        operational_errors=errors,
        status=status,
    )
