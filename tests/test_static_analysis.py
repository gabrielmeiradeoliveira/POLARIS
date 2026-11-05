"""Contracts for the bounded GOAL 10 static-analysis engine."""

from pathlib import Path

from polaris.context.context_models import ContextCandidate, ContextRelationshipCategory, ProvenanceRecord
from polaris.context.dependency_graph import EdgeResolutionStatus
from polaris.context.models import ChangedSymbol, OverlapClassification, SourceLocation, SymbolKind
from polaris.context.static_analysis import DataFlowCertainty, PythonStaticAnalyzer, StaticAnalysisStatus
from polaris.context.static_relevance import prioritize_static_relevance
from polaris.core.config import PolarisConfig
from polaris.core.models import BudgetTracker, ExecutionBudget
from polaris.evaluation.runner import evaluate_corpus, load_fixtures_from_file
from polaris.git.analyzer import parse_unified_diff
from polaris.git.models import ContextSnippet, DiffBundle, FileContext
from polaris.modules.code_review import CodeReviewModule
from polaris.providers.fake import FakeProvider


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


def test_static_engine_keeps_branch_only_bindings_possible_and_merges_complete_branches() -> None:
    """Branch assignments must not hide an UnboundLocalError path after the branch."""
    partial = PythonStaticAnalyzer().analyze_source(
        "def partial(flag):\n    if flag:\n        value = 1\n    return value\n"
    ).procedures[0]
    complete = PythonStaticAnalyzer().analyze_source(
        "def complete(flag):\n    if flag:\n        value = 1\n    else:\n        value = 2\n    return value\n"
    ).procedures[0]

    assert any(fact.name == "value" and fact.kind == "possible_unbound_local" for fact in partial.data_flow)
    assert any(
        fact.name == "value" and fact.kind == "return" and fact.certainty == DataFlowCertainty.PROVEN
        for fact in complete.data_flow
    )


def test_static_engine_models_try_else_and_does_not_promote_handler_only_bindings() -> None:
    """Try-else is reachable only after the try body; handler-local names remain conditional."""
    procedure = PythonStaticAnalyzer().analyze_source(
        "def parse(raw):\n"
        "    try:\n"
        "        value = int(raw)\n"
        "    except ValueError as exc:\n"
        "        fallback = str(exc)\n"
        "    else:\n"
        "        value += 1\n"
        "    return fallback\n"
    ).procedures[0]

    assert any(signal.kind == "exception_else" and signal.line == 7 for signal in procedure.signals)
    assert any(fact.name == "fallback" and fact.kind == "possible_unbound_local" for fact in procedure.data_flow)


def test_code_review_emits_changed_conditional_binding_as_deterministic_candidate() -> None:
    """A proven new unbound-local path is reported without requiring an LLM guess."""
    diff_text = (
        "diff --git a/service.py b/service.py\n"
        "--- a/service.py\n"
        "+++ b/service.py\n"
        "@@ -1,3 +1,4 @@\n"
        " def render(enabled):\n"
        "-    value = build_value()\n"
        "+    if enabled:\n"
        "+        value = build_value()\n"
        "     return value.serialize()\n"
    )
    contents = "def render(enabled):\n    if enabled:\n        value = build_value()\n    return value.serialize()\n"
    file_diff = parse_unified_diff(diff_text)[0]
    bundle = DiffBundle(repository_root="/test", base_revision="HEAD", target_description="test", files=[file_diff])
    context = FileContext(
        file_path="service.py",
        total_lines=4,
        snippets=[ContextSnippet(start_line=1, end_line=4, lines=dict(enumerate(contents.splitlines(), start=1)))],
    )
    candidates = CodeReviewModule().analyze(
        bundle,
        {"service.py": context},
        FakeProvider(scripted_responses=['{"findings": []}']),
        BudgetTracker(ExecutionBudget(max_total_tokens=10_000)),
    )

    assert len(candidates) == 1
    assert candidates[0].category.value == "logic_error"
    assert candidates[0].start_line == 3
    assert "may be unbound" in candidates[0].title


def test_goal18_data_flow_contract_corpus_has_positive_and_negative_end_to_end_coverage() -> None:
    """The GOAL 18 corpus proves detection without creating a safe-path false positive."""
    fixtures = load_fixtures_from_file(Path("evaluations/fixtures/goal18_data_flow_contract_corpus.json"))
    summary = evaluate_corpus(fixtures, FakeProvider(), force_end_to_end=True, strict_severity=True)

    assert (summary.true_positives, summary.false_positives, summary.false_negatives) == (1, 0, 0)
    assert summary.successful_cases == 2


def test_goal18_engine_improves_over_the_pre_data_flow_module_behavior() -> None:
    """The new deterministic pass recovers the previously missed executable defect."""
    fixtures = load_fixtures_from_file(Path("evaluations/fixtures/goal18_data_flow_contract_corpus.json"))

    class PreGoal18CodeReviewModule(CodeReviewModule):
        @staticmethod
        def _static_data_flow_candidates(_files: object, _contexts: object) -> list[object]:
            return []

    before = evaluate_corpus(
        fixtures, FakeProvider(), module=PreGoal18CodeReviewModule(), force_end_to_end=True, strict_severity=True
    )
    after = evaluate_corpus(fixtures, FakeProvider(), module=CodeReviewModule(), force_end_to_end=True, strict_severity=True)

    assert (before.true_positives, before.false_negatives) == (0, 1)
    assert (after.true_positives, after.false_negatives) == (1, 0)
    assert after.false_positives == 0


def test_static_relevance_selection_is_opt_in_and_propagates_to_context_limits() -> None:
    default = PolarisConfig.from_env_and_args(repo_path=Path("."), provider="fake", environ={})
    enabled = PolarisConfig.from_env_and_args(
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
