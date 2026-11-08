"""Interprocedural Impact Analysis (GOAL 30 - Fase 30.4).

Calculates forward and reverse dependency impact across functions, modules,
and contract boundaries resulting from code changes.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polaris.context.semantic_graph import EdgeKind, GraphEntity, SemanticProjectGraph


class ImpactClassification(StrEnum):
    """Classification of how an entity is affected by a change."""

    DIRECT = "DIRECT"
    TRANSITIVE = "TRANSITIVE"
    POSSIBLE = "POSSIBLE"
    UNKNOWN = "UNKNOWN"


class ImpactedConsumer(BaseModel):
    """Consumer entity impacted by an upstream change."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    consumer_id: str = Field(..., min_length=1)
    consumer_name: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    classification: ImpactClassification
    dependency_path: list[str] = Field(default_factory=list)
    reason: str = Field(default="")


class InterproceduralImpactAnalysis:
    """Computes downstream impact on consumers given a set of modified symbols."""

    def __init__(self, graph: SemanticProjectGraph) -> None:
        self.graph = graph

    def analyze_impact(
        self,
        changed_entity_ids: list[str],
        max_depth: int = 5,
    ) -> list[ImpactedConsumer]:
        """Traverse incoming edges to identify all callers, importers, and consumers affected."""
        impacted: dict[str, ImpactedConsumer] = {}
        visited: set[str] = set()

        def traverse_reverse(current_id: str, current_path: list[str], depth: int) -> None:
            if depth > max_depth or current_id in visited:
                return
            visited.add(current_id)

            incoming_edges = self.graph.get_incoming_edges(current_id)
            for edge in incoming_edges:
                consumer = self.graph.get_entity(edge.source_id)
                if not consumer:
                    continue

                classification = (
                    ImpactClassification.DIRECT
                    if depth == 1
                    else ImpactClassification.TRANSITIVE
                )

                # Classify edge relationship
                reason = f"{edge.kind.value} from {consumer.name} -> {current_id}"
                path = current_path + [consumer.id]

                if consumer.id not in impacted or classification == ImpactClassification.DIRECT:
                    impacted[consumer.id] = ImpactedConsumer(
                        consumer_id=consumer.id,
                        consumer_name=consumer.name,
                        file_path=consumer.file_path,
                        classification=classification,
                        dependency_path=path,
                        reason=reason,
                    )

                traverse_reverse(consumer.id, path, depth + 1)

        for seed_id in changed_entity_ids:
            traverse_reverse(seed_id, [seed_id], depth=1)

        # Sort deterministically by file_path and consumer_name
        return sorted(impacted.values(), key=lambda x: (x.classification.value, x.file_path, x.consumer_name))
