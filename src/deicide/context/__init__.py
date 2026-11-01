"""Context Engine package for DEICIDE: AST analysis, indexing, dependency graphs, and context selection."""

from __future__ import annotations

from deicide.context.behavioral_delta import (
    BehavioralDelta,
    BehavioralDeltaResult,
    BehavioralDeltaType,
    analyze_behavioral_deltas,
    serialize_behavioral_deltas,
)
from deicide.context.changed_symbols import identify_changed_symbols
from deicide.context.change_impact import ExactOverlapEvidence, primary_prompt_source_lines, prove_exact_primary_overlap
from deicide.context.context_relevance import HybridContextSelection, select_hybrid_supplementary_context
from deicide.context.context_budget import (
    enforce_context_budget,
    estimate_snippet_tokens,
    serialize_context_bundle,
    serialize_snippet_block,
)
from deicide.context.context_models import (
    ContextCandidate,
    ContextRelationshipCategory,
    ContextSelectionLimits,
    ContextSelectionResult,
    OmissionReason,
    OmittedCandidate,
    ProvenanceRecord,
    SelectedSnippet,
)
from deicide.context.context_ranker import ContextRanker
from deicide.context.dependency_graph import (
    CallerEvidence,
    ChangedSymbolImpact,
    DependencyGraph,
    EdgeResolutionStatus,
    GraphEdge,
    GraphEdgeKind,
    GraphNode,
    GraphNodeKind,
    build_dependency_graph,
)
from deicide.context.import_resolver import (
    FileImportMap,
    ImportResolver,
    ResolvedImport,
    resolve_relative_module,
)
from deicide.context.models import (
    CallReference,
    ChangedSymbol,
    ChangedSymbolsResult,
    FileAnalysis,
    FileAnalysisStatus,
    ImportKind,
    ImportReference,
    ModuleLevelChange,
    OverlapClassification,
    SourceLocation,
    Symbol,
    SymbolKind,
)
from deicide.context.project_index import (
    IndexLimits,
    ProjectIndex,
    build_project_index,
    file_path_to_module_name,
)
from deicide.context.python_ast import PythonAstAnalyzer
from deicide.context.snippet_selector import (
    SnippetExtractor,
    select_context,
)
from deicide.context.static_analysis import (
    BehavioralSignal,
    ControlFlowEdge,
    ControlFlowNode,
    DataFlowFact,
    PythonStaticAnalyzer,
    StaticAnalysisResult,
)

__all__ = [
    "BehavioralDelta",
    "BehavioralDeltaResult",
    "BehavioralDeltaType",
    "BehavioralSignal",
    "CallReference",
    "CallerEvidence",
    "ChangedSymbol",
    "ChangedSymbolImpact",
    "ChangedSymbolsResult",
    "ContextCandidate",
    "ExactOverlapEvidence",
    "HybridContextSelection",
    "ContextRanker",
    "ContextRelationshipCategory",
    "ContextSelectionLimits",
    "ContextSelectionResult",
    "ControlFlowEdge",
    "ControlFlowNode",
    "DataFlowFact",
    "DependencyGraph",
    "EdgeResolutionStatus",
    "FileAnalysis",
    "FileAnalysisStatus",
    "FileImportMap",
    "GraphEdge",
    "GraphEdgeKind",
    "GraphNode",
    "GraphNodeKind",
    "ImportKind",
    "ImportReference",
    "ImportResolver",
    "IndexLimits",
    "ModuleLevelChange",
    "OmissionReason",
    "OmittedCandidate",
    "OverlapClassification",
    "ProjectIndex",
    "ProvenanceRecord",
    "PythonAstAnalyzer",
    "PythonStaticAnalyzer",
    "StaticAnalysisResult",
    "ResolvedImport",
    "SelectedSnippet",
    "SnippetExtractor",
    "SourceLocation",
    "Symbol",
    "SymbolKind",
    "analyze_behavioral_deltas",
    "build_dependency_graph",
    "build_project_index",
    "enforce_context_budget",
    "estimate_snippet_tokens",
    "file_path_to_module_name",
    "identify_changed_symbols",
    "primary_prompt_source_lines",
    "prove_exact_primary_overlap",
    "resolve_relative_module",
    "select_context",
    "select_hybrid_supplementary_context",
    "serialize_behavioral_deltas",
    "serialize_context_bundle",
    "serialize_snippet_block",
]
