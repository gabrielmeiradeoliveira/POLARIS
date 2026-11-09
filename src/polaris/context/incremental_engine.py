"""Incremental Analysis Engine (GOAL 30 - Fase 30.3).

Provides selective invalidation, content hash tracking, and incremental
updating of repository graph and analysis caches.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from polaris.context.semantic_graph import GraphEdge, GraphEntity, SemanticProjectGraph


class FileChangeKind(StrEnum):
    """Classification of a file status in an incremental update."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    UNCHANGED = "unchanged"


class IncrementalFileState(BaseModel):
    """Tracked hash and entity manifest for a single file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: str = Field(..., min_length=1)
    content_hash: str = Field(..., min_length=1)
    entity_ids: list[str] = Field(default_factory=list)


class IncrementalAnalysisEngine:
    """Manages incremental graph synchronization and dependency invalidation."""

    def __init__(self, graph: SemanticProjectGraph | None = None) -> None:
        self.graph = graph or SemanticProjectGraph()
        self.file_states: dict[str, IncrementalFileState] = {}

    @staticmethod
    def compute_hash(content: str | bytes) -> str:
        """Compute stable SHA-256 hash for file content."""
        if isinstance(content, str):
            content = content.encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    def detect_changes(self, current_files: dict[str, str]) -> dict[str, FileChangeKind]:
        """Compare current file contents against tracked file states."""
        changes: dict[str, FileChangeKind] = {}

        # Check existing tracked files for deletion or modification
        for tracked_path, state in self.file_states.items():
            if tracked_path not in current_files:
                changes[tracked_path] = FileChangeKind.DELETED
            else:
                curr_hash = self.compute_hash(current_files[tracked_path])
                if curr_hash != state.content_hash:
                    changes[tracked_path] = FileChangeKind.MODIFIED
                else:
                    changes[tracked_path] = FileChangeKind.UNCHANGED

        # Check for newly added files
        for curr_path in current_files:
            if curr_path not in self.file_states:
                changes[curr_path] = FileChangeKind.ADDED

        return changes

    def invalidate_file(self, file_path: str) -> set[str]:
        """Remove entities and outgoing/incoming edges for a specific file, returning invalidated IDs."""
        norm_p = file_path.replace("\\", "/")
        state = self.file_states.pop(norm_p, None)
        invalidated_ids: set[str] = set()

        if state:
            invalidated_ids.update(state.entity_ids)

        # Also find any entities pointing to this file path
        for ent_id, ent in list(self.graph.entities.items()):
            if ent.file_path == norm_p:
                invalidated_ids.add(ent_id)

        # Remove entities from graph
        for ent_id in invalidated_ids:
            self.graph.entities.pop(ent_id, None)

        # Re-filter edges to drop invalidated connections
        self.graph.edges = [
            e
            for e in self.graph.edges
            if e.source_id not in invalidated_ids and e.target_id not in invalidated_ids
        ]
        # Rebuild graph adjacency
        self.graph._adj_out = {k: [] for k in self.graph.entities}
        self.graph._adj_in = {k: [] for k in self.graph.entities}
        for edge in self.graph.edges:
            self.graph._adj_out.setdefault(edge.source_id, []).append(edge)
            self.graph._adj_in.setdefault(edge.target_id, []).append(edge)

        return invalidated_ids

    def sync_file(self, file_path: str, content: str, entities: list[GraphEntity], edges: list[GraphEdge]) -> None:
        """Incrementally sync a single file, replacing previous entities and edges cleanly."""
        norm_p = file_path.replace("\\", "/")
        self.invalidate_file(norm_p)

        c_hash = self.compute_hash(content)
        ent_ids = []
        for ent in entities:
            self.graph.add_entity(ent)
            ent_ids.append(ent.id)

        for edge in edges:
            self.graph.add_edge(edge)

        self.file_states[norm_p] = IncrementalFileState(
            file_path=norm_p,
            content_hash=c_hash,
            entity_ids=sorted(ent_ids),
        )
