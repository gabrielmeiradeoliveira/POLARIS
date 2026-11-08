"""Semantic Project Graph (GOAL 30 - Fase 30.2).

Persistent, deterministic, offline-capable code graph capturing entities,
interprocedural relations, and code contracts.
"""

from __future__ import annotations

import hashlib
import json
import logging
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "3.0.0"
logger = logging.getLogger(__name__)


class EntityKind(StrEnum):
    """Types of structural entities in the semantic project graph."""

    FILE = "file"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    SYMBOL = "symbol"
    IMPORT = "import"
    CALL = "call"
    CONTRACT = "contract"
    ENDPOINT = "endpoint"


class EdgeKind(StrEnum):
    """Types of semantic relations connecting entities."""

    IMPORTS = "IMPORTS"
    DEFINES = "DEFINES"
    CALLS = "CALLS"
    REFERENCES = "REFERENCES"
    INHERITS = "INHERITS"
    CONSUMES = "CONSUMES"
    RETURNS = "RETURNS"
    DEPENDS_ON = "DEPENDS_ON"


class EdgeCertainty(StrEnum):
    """Certainty level of a graph relationship."""

    CONFIRMED = "confirmed"
    POSSIBLE = "possible"
    INFERRED = "inferred"


class GraphEntity(BaseModel):
    """A node in the semantic graph representing a code construct."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Deterministic node identifier.")
    kind: EntityKind
    name: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1, description="Normalized POSIX path.")
    start_line: int = Field(default=1, ge=1)
    end_line: int = Field(default=1, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create_id(cls, kind: EntityKind, file_path: str, name: str, line: int = 1) -> str:
        """Create a deterministic unique ID based on entity properties."""
        norm_path = file_path.replace("\\", "/").strip("/")
        seed = f"{kind.value}::{norm_path}::{name}::{line}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        return f"{kind.value}:{digest}:{name.split('.')[-1]}"


class GraphEdge(BaseModel):
    """A directed edge in the semantic graph."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str = Field(..., min_length=1)
    target_id: str = Field(..., min_length=1)
    kind: EdgeKind
    certainty: EdgeCertainty = EdgeCertainty.CONFIRMED
    evidence: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticProjectGraph:
    """In-memory and persistent graph containing code entities and their dependencies."""

    def __init__(self, repo_root: Path | str = ".", schema_version: str = SCHEMA_VERSION) -> None:
        self.repo_root = Path(repo_root)
        self.schema_version = schema_version
        self.entities: dict[str, GraphEntity] = {}
        self.edges: list[GraphEdge] = []
        self._adj_out: dict[str, list[GraphEdge]] = {}
        self._adj_in: dict[str, list[GraphEdge]] = {}

    def add_entity(self, entity: GraphEntity) -> None:
        """Add or update an entity in the graph."""
        self.entities[entity.id] = entity
        self._adj_out.setdefault(entity.id, [])
        self._adj_in.setdefault(entity.id, [])

    def add_edge(self, edge: GraphEdge) -> None:
        """Add a directed edge between entities, ensuring deterministic deduplication."""
        for existing in self._adj_out.get(edge.source_id, []):
            if existing.target_id == edge.target_id and existing.kind == edge.kind:
                return
        self.edges.append(edge)
        self._adj_out.setdefault(edge.source_id, []).append(edge)
        self._adj_in.setdefault(edge.target_id, []).append(edge)

    def get_entity(self, entity_id: str) -> GraphEntity | None:
        """Retrieve an entity by its ID."""
        return self.entities.get(entity_id)

    def get_outgoing_edges(self, entity_id: str, kind: EdgeKind | None = None) -> list[GraphEdge]:
        """Get outgoing edges from an entity."""
        edges = self._adj_out.get(entity_id, [])
        if kind is not None:
            return [e for e in edges if e.kind == kind]
        return list(edges)

    def get_incoming_edges(self, entity_id: str, kind: EdgeKind | None = None) -> list[GraphEdge]:
        """Get incoming edges to an entity (reverse dependencies)."""
        edges = self._adj_in.get(entity_id, [])
        if kind is not None:
            return [e for e in edges if e.kind == kind]
        return list(edges)

    def detect_cycles(self, max_depth: int = 50) -> list[list[str]]:
        """Detect direct and transitive dependency cycles in the graph."""
        visited: set[str] = set()
        rec_stack: list[str] = []
        cycles: list[list[str]] = []

        def dfs(node_id: str, depth: int) -> None:
            if depth > max_depth:
                return
            visited.add(node_id)
            rec_stack.append(node_id)

            for edge in self._adj_out.get(node_id, []):
                target = edge.target_id
                if target not in visited:
                    dfs(target, depth + 1)
                elif target in rec_stack:
                    # Cycle detected
                    idx = rec_stack.index(target)
                    cycles.append(rec_stack[idx:] + [target])

            rec_stack.pop()

        for entity_id in sorted(self.entities.keys()):
            if entity_id not in visited:
                dfs(entity_id, 1)

        return cycles

    def to_dict(self) -> dict[str, Any]:
        """Serialize graph to a deterministic JSON-serializable dictionary."""
        return {
            "schema_version": self.schema_version,
            "entities": [self.entities[k].model_dump() for k in sorted(self.entities.keys())],
            "edges": [
                e.model_dump()
                for e in sorted(self.edges, key=lambda x: (x.source_id, x.target_id, x.kind.value))
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], repo_root: Path | str = ".") -> SemanticProjectGraph:
        """Deserialize graph with schema validation and error recovery."""
        if data.get("schema_version") != SCHEMA_VERSION:
            # Corrupted / incompatible schema -> return fresh graph
            return cls(repo_root=repo_root)

        graph = cls(repo_root=repo_root, schema_version=data["schema_version"])
        for ent_data in data.get("entities", []):
            try:
                ent = GraphEntity.model_validate(ent_data)
                graph.add_entity(ent)
            except Exception as exc:
                logger.debug("Falha ao desserializar entidade do grafo: %s", type(exc).__name__)
                continue

        for edge_data in data.get("edges", []):
            try:
                edge = GraphEdge.model_validate(edge_data)
                if edge.source_id in graph.entities and edge.target_id in graph.entities:
                    graph.add_edge(edge)
            except Exception as exc:
                logger.debug("Falha ao desserializar aresta do grafo: %s", type(exc).__name__)
                continue

        return graph

    def save(self, file_path: Path | str) -> None:
        """Persist graph to file atomically."""
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp_p = p.with_suffix(".tmp")
        tmp_p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        tmp_p.replace(p)

    @classmethod
    def load(cls, file_path: Path | str, repo_root: Path | str = ".") -> SemanticProjectGraph:
        """Load graph from file with corrupted-state recovery."""
        p = Path(file_path)
        if not p.is_file():
            return cls(repo_root=repo_root)
        try:
            content = json.loads(p.read_text(encoding="utf-8"))
            return cls.from_dict(content, repo_root=repo_root)
        except Exception:
            return cls(repo_root=repo_root)
