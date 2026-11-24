from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class RelocatableIssue:
    issue_id: str
    file_path: str
    rule_id: str
    line: int
    enclosing_symbol: str | None = None
    line_hash: str | None = None
    code_line: str = ""
    state: str = "OPEN"


def compute_line_hash(code_line: str) -> str:
    return hashlib.sha256(code_line.strip().encode("utf-8")).hexdigest()


def _levenshtein_ratio(a: str, b: str) -> float:
    if a == b:
        return 0.0
    if not a or not b:
        return 1.0
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            cur = dp[j]
            dp[j] = prev if a[i - 1] == b[j - 1] else 1 + min(prev, dp[j], dp[j - 1])
            prev = cur
    return dp[n] / max(m, n)


def build_relocation_index(
    previous_issues: list[RelocatableIssue],
) -> tuple[dict[tuple[str, str], list[RelocatableIssue]], dict[str, list[RelocatableIssue]]]:
    """Pre-index previous issues by (file_path, rule_id) and rule_id to avoid O(N*M) scans."""
    by_file_rule: dict[tuple[str, str], list[RelocatableIssue]] = {}
    by_rule: dict[str, list[RelocatableIssue]] = {}
    for prev in previous_issues:
        by_file_rule.setdefault((prev.file_path, prev.rule_id), []).append(prev)
        by_rule.setdefault(prev.rule_id, []).append(prev)
    return by_file_rule, by_rule


def relocate_issue(
    candidate: RelocatableIssue,
    previous_issues: list[RelocatableIssue],
    renames: dict[str, str] | None = None,
    *,
    index: tuple[dict[tuple[str, str], list[RelocatableIssue]], dict[str, list[RelocatableIssue]]] | None = None,
) -> RelocatableIssue | None:
    """4-stage deterministic issue relocation."""
    renames = renames or {}
    by_file_rule, by_rule = index if index is not None else build_relocation_index(previous_issues)
    same_file_candidates = by_file_rule.get((candidate.file_path, candidate.rule_id), [])

    # Stage 1: Exact match (file_path + rule_id + line_hash)
    for prev in same_file_candidates:
        if prev.line_hash and prev.line_hash == candidate.line_hash:
            return prev

    # Stage 2: Intra-file displacement (file_path + rule_id + enclosing_symbol + line_hash)
    for prev in same_file_candidates:
        if prev.enclosing_symbol == candidate.enclosing_symbol and prev.line_hash == candidate.line_hash:
            return prev

    # Stage 3: Git rename (old_path -> new_path)
    for prev in previous_issues:
        if renames.get(prev.file_path) == candidate.file_path and prev.rule_id == candidate.rule_id and prev.line_hash == candidate.line_hash:
            return prev

    # Stage 4: Local structural similarity (<= 15% Levenshtein within +-25 lines)
    for prev in previous_issues:
        if (
            prev.file_path == candidate.file_path
            and prev.rule_id == candidate.rule_id
            and prev.enclosing_symbol == candidate.enclosing_symbol
            and abs(prev.line - candidate.line) <= 25
            and _levenshtein_ratio(prev.code_line.strip(), candidate.code_line.strip()) <= 0.15
        ):
            return prev

    return None
