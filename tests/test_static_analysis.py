"""Contracts for the bounded GOAL 10 static-analysis engine."""

from pathlib import Path

from deicide.context.context_models import ContextCandidate, ContextRelationshipCategory, ProvenanceRecord
from deicide.context.dependency_graph import EdgeResolutionStatus
from deicide.context.models import ChangedSymbol, OverlapClassification, SourceLocation, SymbolKind
from deicide.context.static_analysis import DataFlowCertainty, PythonStaticAnalyzer, StaticAnalysisStatus
from deicide.context.static_relevance import prioritize_static_relevance
from deicide.core.config import DeicideConfig


def test_static_engine_extracts_structures_cfg_and_def_use_evidence() -> None:
    source = '''\
class Service(Base):
    def run(self, value):
        result = value
        if result:
            return helper(result)
        try:
            for item in items:
                if item is None:
                    continue
                result = item
                if result:
                    break
                cleanup(item)
        except ValueError as exc:
            raise RuntimeError(exc)
        finally:
            cleanup(result)
        return result
'''
    result = PythonStaticAnalyzer().analyze_source(source)
    procedure = next(item for item in result.procedures if item.qualified_name == "run")

    assert result.status == StaticAnalysisStatus.PARSED
    assert any(item.kind == "class" and item.name == "Service" for item in result.structures)
    assert {node.kind.value for node in procedure.cfg_nodes} >= {"entry", "condition", "loop", "exception", "finally", "exit"}
    assert any(edge.kind == "loop_back" for edge in procedure.cfg_edges)
    assert {edge.kind for edge in procedure.cfg_edges} >= {"continue", "loop_back"}
    assert any(fact.name == "value" and fact.certainty == DataFlowCertainty.PROVEN for fact in procedure.data_flow)
    assert {signal.kind for signal in procedure.signals} >= {
        "assignment",
        "break",
        "condition",
        "continue",
        "loop",
        "return",
        "exception_handler",
    }


def test_static_engine_preserves_unknown_and_limits_conservatively() -> None:
    result = PythonStaticAnalyzer(max_nodes_per_procedure=2).analyze_source("def f():\n    a = missing\n    b = a\n    return b\n")
    assert result.status == StaticAnalysisStatus.COMPLEXITY_LIMIT
    procedure = result.procedures[0]
    assert procedure.incomplete
    assert any(fact.name == "missing" and fact.certainty == DataFlowCertainty.POSSIBLE for fact in procedure.data_flow)

    invalid = PythonStaticAnalyzer().analyze_source("def broken(:\n")
    assert invalid.status == StaticAnalysisStatus.SYNTAX_ERROR


def test_static_engine_marks_possible_local_use_before_assignment() -> None:
    result = PythonStaticAnalyzer().analyze_source("def f(flag):\n    if flag:\n        return value\n    value = 1\n")
    procedure = result.procedures[0]

    assert any(
        fact.name == "value" and fact.certainty == DataFlowCertainty.POSSIBLE and fact.kind == "possible_use_before_assignment"
        for fact in procedure.data_flow
    )


def test_static_engine_marks_statements_after_terminal_flow_as_potentially_unreachable() -> None:
    result = PythonStaticAnalyzer().analyze_source("def f():\n    return 1\n    after_return = 2\n")

    assert result.procedures[0].unreachable_lines == (3,)


def test_static_relevance_selection_is_opt_in_and_propagates_to_context_limits() -> None:
    default = DeicideConfig.from_env_and_args(repo_path=Path("."), provider="fake", environ={})
    enabled = DeicideConfig.from_env_and_args(
        repo_path=Path("."), provider="fake", static_relevance_selection_enabled=True, environ={}
    )

    assert default.static_relevance_selection_enabled is False
    assert default.context_limits.static_relevance_selection_enabled is False
    assert enabled.static_relevance_selection_enabled is True
    assert enabled.context_limits.static_relevance_selection_enabled is True


def test_static_relevance_promotes_proven_direct_context_and_preserves_safe_fallback() -> None:
    changed = ChangedSymbol(
        symbol_id="changed",
        symbol_name="check",
        qualified_name="check",
        kind=SymbolKind.FUNCTION,
        location=SourceLocation(file_path="service.py", start_line=1, end_line=3),
        overlapping_lines=[2],
        classification=OverlapClassification.BODY,
    )
    candidate = ContextCandidate(
        candidate_id="caller",
        file_path="caller.py",
        start_line=1,
        end_line=4,
        relationship=ContextRelationshipCategory.DIRECT_CALLER,
        priority=1,
        provenance=[
            ProvenanceRecord(
                source_id="caller",
                target_id="changed",
                relationship=ContextRelationshipCategory.DIRECT_CALLER,
                resolution_status=EdgeResolutionStatus.RESOLVED,
            )
        ],
    )
    analysis = PythonStaticAnalyzer().analyze_source("def check(value):\n    if value:\n        return value\n", "service.py")

    promoted, diagnostics = prioritize_static_relevance([candidate], [changed], {"service.py": analysis})
    fallback, fallback_diagnostics = prioritize_static_relevance([candidate], [changed], {})

    assert promoted[0].priority == 0
    assert not diagnostics
    assert fallback == [candidate]
    assert fallback_diagnostics
