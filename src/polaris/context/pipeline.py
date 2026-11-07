"""Context Engine pipeline integration connecting Git diffs, AST analysis, and review prompts."""

from __future__ import annotations

import time
from pathlib import Path
from typing import NamedTuple

from polaris.context.behavioral_delta import (
    BehavioralDeltaResult,
    analyze_behavioral_deltas,
)
from polaris.context.changed_symbols import identify_changed_symbols
from polaris.context.context_models import (
    ContextSelectionLimits,
    ContextSelectionResult,
)
from polaris.context.dependency_graph import build_dependency_graph
from polaris.context.models import ChangedSymbol, FileAnalysisStatus
from polaris.context.project_index import IndexLimits, build_project_index
from polaris.context.python_ast import PythonAstAnalyzer
from polaris.context.snippet_selector import select_context
from polaris.context.static_analysis import PythonStaticAnalyzer, StaticAnalysisResult
from polaris.core.errors import SecurityViolationError
from polaris.core.models import ContextSummary, ExecutionBudget
from polaris.git.analyzer import ensure_safe_repo_file
from polaris.git.models import DiffBundle, FileChangeStatus


class ContextPreparationOutcome(NamedTuple):
    """Result of context preparation containing selection result and observable summary."""

    result: ContextSelectionResult | None
    summary: ContextSummary


def calculate_context_token_allowance(
    budget: ExecutionBudget,
    *,
    baseline_prompt_tokens: int,
    requested_context_tokens: int,
) -> int:
    """Return the context capacity remaining after prompt, output, and safety reservations."""
    output_reservation = 1000
    safety_margin = 150
    remaining_capacity = max(
        0,
        budget.max_total_tokens - baseline_prompt_tokens - output_reservation - safety_margin,
    )
    return min(max(0, requested_context_tokens), remaining_capacity)


def prepare_review_context(
    repo_root: Path,
    diff_bundle: DiffBundle,
    budget: ExecutionBudget,
    limits: ContextSelectionLimits | None = None,
    context_enabled: bool = True,
    behavioral_delta_enabled: bool = True,
    baseline_prompt_tokens: int = 0,
) -> ContextPreparationOutcome:
    """Safely prepare budgeted supplementary cross-file context for code review."""
    pipeline_started = time.perf_counter_ns()
    stage_timings_ms: dict[str, int] = {}

    def record_timing(stage: str, started_ns: int) -> None:
        stage_timings_ms[stage] = stage_timings_ms.get(stage, 0) + max(
            0, int((time.perf_counter_ns() - started_ns) / 1_000_000)
        )

    def complete_timings() -> dict[str, int]:
        result = dict(stage_timings_ms)
        result["context_preparation_total"] = max(0, int((time.perf_counter_ns() - pipeline_started) / 1_000_000))
        return result

    if not context_enabled:
        return ContextPreparationOutcome(
            result=None,
            summary=ContextSummary(status="disabled", fallback=False, stage_timings_ms=complete_timings()),
        )

    python_files = [
        f for f in diff_bundle.reviewable_files if f.new_path.endswith(".py") and f.status != FileChangeStatus.DELETED
    ]
    if not python_files:
        return ContextPreparationOutcome(
            result=None,
            summary=ContextSummary(status="no_python_changes", fallback=False, stage_timings_ms=complete_timings()),
        )

    active_limits = limits or ContextSelectionLimits()
    ast_analyzer = PythonAstAnalyzer()
    static_analyzer = PythonStaticAnalyzer()
    all_changed_symbols: list[ChangedSymbol] = []
    static_analyses: dict[str, StaticAnalysisResult] = {}

    for fdiff in python_files:
        try:
            ast_started = time.perf_counter_ns()
            analysis = ast_analyzer.analyze_file(repo_root, fdiff.new_path)
            record_timing("ast_parse", ast_started)
            if analysis.status == FileAnalysisStatus.PARSED:
                changed_res = identify_changed_symbols(fdiff, analysis)
                all_changed_symbols.extend(changed_res.changed_symbols)
                if active_limits.static_relevance_selection_enabled:
                    source_path = ensure_safe_repo_file(repo_root, fdiff.new_path)
                    static_started = time.perf_counter_ns()
                    static_analyses[fdiff.new_path] = static_analyzer.analyze_source(
                        source_path.read_text(encoding="utf-8"), fdiff.new_path
                    )
                    record_timing("cfg_data_flow", static_started)
        except SecurityViolationError:
            raise
        except Exception:  # noqa: S112
            continue

    if not all_changed_symbols:
        return ContextPreparationOutcome(
            result=None,
            summary=ContextSummary(status="no_changed_symbols", fallback=False, stage_timings_ms=complete_timings()),
        )

    try:
        index_limits = IndexLimits(
            max_files=min(500, active_limits.max_context_files * 20),
            max_file_size_bytes=budget.max_file_bytes,
            max_total_bytes=budget.max_total_context_bytes,
        )
        index_started = time.perf_counter_ns()
        index = build_project_index(repo_root, limits=index_limits, analyzer=ast_analyzer)
        record_timing("project_index", index_started)
        graph_started = time.perf_counter_ns()
        graph = build_dependency_graph(index)
        record_timing("dependency_graph", graph_started)

        context_token_allowance = calculate_context_token_allowance(
            budget,
            baseline_prompt_tokens=baseline_prompt_tokens,
            requested_context_tokens=active_limits.max_context_tokens,
        )

        delta_started = time.perf_counter_ns()
        delta_result = (
            analyze_behavioral_deltas(
                diff_bundle=diff_bundle,
                repo_root=repo_root,
                project_index=index,
                dependency_graph=graph,
                enabled=behavioral_delta_enabled,
            )
            if behavioral_delta_enabled
            else BehavioralDeltaResult()
        )
        record_timing("behavioral_delta", delta_started)
        delta_allowance = (
            min(active_limits.behavioral_delta_reserved_tokens, context_token_allowance)
            if active_limits.behavioral_delta_reserved_tokens
            else context_token_allowance
        )
        include_serialized_deltas = bool(delta_result.serialized_summary) and delta_result.estimated_tokens <= delta_allowance
        delta_token_cost = delta_result.estimated_tokens if include_serialized_deltas else 0
        snippet_token_allowance = (
            max(0, context_token_allowance - delta_allowance)
            if active_limits.behavioral_delta_reserved_tokens
            else max(0, context_token_allowance - delta_token_cost)
        )

        selection_started = time.perf_counter_ns()
        context_result = select_context(
            repo_root=repo_root,
            changed_symbols=all_changed_symbols,
            dependency_graph=graph,
            project_index=index,
            limits=active_limits,
            max_context_tokens=snippet_token_allowance,
            static_analyses=static_analyses if active_limits.static_relevance_selection_enabled else None,
        )
        record_timing("context_selection", selection_started)
        context_result = context_result.model_copy(
            update={
                "behavioral_deltas": delta_result.deltas,
                "serialized_behavioral_deltas": delta_result.serialized_summary if include_serialized_deltas else "",
                "total_estimated_tokens": context_result.total_estimated_tokens + delta_token_cost,
                "max_allowed_tokens": context_token_allowance,
            }
        )

        summary = ContextSummary(
            status="ready",
            indexed_files=len(index.file_analyses),
            selected_snippets=context_result.selected_snippets_count,
            related_files=context_result.selected_files_count,
            estimated_tokens=context_result.total_estimated_tokens,
            omitted_candidates=context_result.omitted_snippets_count,
            behavioral_deltas=len(delta_result.deltas),
            fallback=False,
            stage_timings_ms=complete_timings(),
        )
        return ContextPreparationOutcome(result=context_result, summary=summary)

    except SecurityViolationError:
        raise
    except Exception as exc:
        summary = ContextSummary(
            status="fallback",
            fallback=True,
            fallback_reason=f"Recoverable context failure: {exc}",
            stage_timings_ms=complete_timings(),
        )
        return ContextPreparationOutcome(result=None, summary=summary)
