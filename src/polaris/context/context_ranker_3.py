"""ContextRanker 3.0 (GOAL 30 - Fase 30.9).

Deterministic budget-aware context ranker incorporating diff proximity,
semantic graph distance, behavioral deltas, and contract breakages.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polaris.context.behavioral_delta_3 import BehavioralChange
from polaris.context.impact_analysis import ImpactedConsumer
from polaris.context.semantic_graph import SemanticProjectGraph


class RankedContextSnippet(BaseModel):
    """Ranked snippet for LLM Arm ON prompting."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: str
    symbol_name: str
    score: float
    token_cost: int
    reason: str
    snippet_content: str


class ContextRanker3:
    """Ranks context snippets under strict token budgets."""

    def __init__(self, graph: SemanticProjectGraph | None = None) -> None:
        self.graph = graph

    @classmethod
    def rank_context(
        cls,
        changed_files: list[str],
        impacted_consumers: list[ImpactedConsumer],
        behavioral_changes: list[BehavioralChange],
        file_contents: dict[str, str],
        max_tokens: int = 1500,
    ) -> list[RankedContextSnippet]:
        """Produce deterministically sorted snippets fitting within max_tokens."""
        candidates: list[RankedContextSnippet] = []

        # 1. Primary changed files (highest baseline score)
        for cf in sorted(set(changed_files)):
            if cf in file_contents:
                content = file_contents[cf]
                cost = max(1, len(content) // 4)
                candidates.append(
                    RankedContextSnippet(
                        file_path=cf,
                        symbol_name=cf.split("/")[-1],
                        score=100.0,
                        token_cost=cost,
                        reason="Primary changed file",
                        snippet_content=content,
                    )
                )

        # 2. Files with behavioral alterations
        for bc in behavioral_changes:
            if bc.file_path in file_contents and bc.file_path not in [c.file_path for c in candidates]:
                content = file_contents[bc.file_path]
                cost = max(1, len(content) // 4)
                candidates.append(
                    RankedContextSnippet(
                        file_path=bc.file_path,
                        symbol_name=bc.symbol_name,
                        score=85.0,
                        token_cost=cost,
                        reason=f"Behavioral change: {bc.category.value}",
                        snippet_content=content,
                    )
                )

        # 3. Direct and transitive consumers
        for ic in impacted_consumers:
            if ic.file_path in file_contents and ic.file_path not in [c.file_path for c in candidates]:
                content = file_contents[ic.file_path]
                cost = max(1, len(content) // 4)
                score = 70.0 if ic.classification.value == "DIRECT" else 40.0
                candidates.append(
                    RankedContextSnippet(
                        file_path=ic.file_path,
                        symbol_name=ic.consumer_name,
                        score=score,
                        token_cost=cost,
                        reason=f"Impacted consumer: {ic.classification.value}",
                        snippet_content=content,
                    )
                )

        # Sort deterministically: highest score first, then lowest cost, then file_path
        sorted_candidates = sorted(
            candidates,
            key=lambda x: (-x.score, x.token_cost, x.file_path, x.symbol_name),
        )

        # Select under token budget
        selected: list[RankedContextSnippet] = []
        accumulated_tokens = 0
        for cand in sorted_candidates:
            if accumulated_tokens + cand.token_cost <= max_tokens:
                selected.append(cand)
                accumulated_tokens += cand.token_cost

        return selected
