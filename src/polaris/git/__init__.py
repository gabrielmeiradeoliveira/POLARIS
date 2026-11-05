"""Git integration for change detection, diff extraction, and bounded context retrieval."""

from polaris.git.analyzer import GitAnalyzer, normalize_repo_relative_path, parse_unified_diff
from polaris.git.models import (
    ContextSnippet,
    DiffBundle,
    DiffHunk,
    FileChangeStatus,
    FileContext,
    FileDiff,
)

__all__ = [
    "ContextSnippet",
    "DiffBundle",
    "DiffHunk",
    "FileChangeStatus",
    "FileContext",
    "FileDiff",
    "GitAnalyzer",
    "normalize_repo_relative_path",
    "parse_unified_diff",
]
