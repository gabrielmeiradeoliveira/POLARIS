"""ContextRanker 3.0 (Consolidated into polaris.context.context_ranker).

Retained as a backwards-compatible entrypoint. All logic is now consolidated in
`polaris.context.context_ranker.ContextRanker`.
"""

from __future__ import annotations

from polaris.context.context_ranker import ContextRanker, ContextRanker3, RankedContextSnippet

__all__ = ["ContextRanker", "ContextRanker3", "RankedContextSnippet"]
