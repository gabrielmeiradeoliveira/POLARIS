"""Context Engine pipeline integration connecting Git diffs, AST analysis, and review prompts."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from deicide.context.behavioral_delta import (
    BehavioralDeltaResult,
    analyze_behavioral_deltas,
)
from deicide.context.changed_symbols import identify_changed_symbols
from deicide.context.context_models import (
    ContextSelectionLimits,
    ContextSelectionResult,
)
from deicide.context.dependency_graph import build_dependency_graph
from deicide.context.models import ChangedSymbol, FileAnalysisStatus
from deicide.context.project_index import IndexLimits, build_project_index
from deicide.context.python_ast import PythonAstAnalyzer
from deicide.context.snippet_selector import select_context
from deicide.core.errors import SecurityViolationError
from deicide.core.models import ContextSummary, ExecutionBudget
from deicide.git.models import DiffBundle, FileChangeStatus


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
    if not context_enabled:
        return ContextPreparationOutcome(
            result=None,
            summary=ContextSummary(status="disabled", fallback=False),
        )

    python_files = [
        f for f in diff_bundle.reviewable_files if f.new_path.endswith(".py") and f.status != FileChangeStatus.DELETED
    ]
    if not python_files:
        return ContextPreparationOutcome(
            result=None,
            summary=ContextSummary(status="no_python_changes", fallback=False),
        )

    active_limits = limits or ContextSelectionLimits()
    ast_analyzer = PythonAstAnalyzer()
    all_changed_symbols: list[ChangedSymbol] = []

    for fdiff in python_files:
        try:
            analysis = ast_analyzer.analyze_file(repo_root, fdiff.new_path)
            if analysis.status == FileAnalysisStatus.PARSED:
                changed_res = identify_changed_symbols(fdiff, analysis)
                all_changed_symbols.extend(changed_res.changed_symbols)
        except SecurityViolationError:
            raise
        except Exception:  # noqa: S112
            continue

    if not all_changed_symbols:
        return ContextPreparationOutcome(
            result=None,
            summary=ContextSummary(status="no_changed_symbols", fallback=False),
        )

    try:
        index_limits = IndexLimits(
            max_files=min(500, active_limits.max_context_files * 20),
            max_file_size_bytes=budget.max_file_bytes,
            max_total_bytes=budget.max_total_context_bytes,
        )
        index = build_project_index(repo_root, limits=index_limits, analyzer=ast_analyzer)
        graph = build_dependency_graph(index)

        context_token_allowance = calculate_context_token_allowance(
            budget,
            baseline_prompt_tokens=baseline_prompt_tokens,
            requested_context_tokens=active_limits.max_context_tokens,
        )

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

        context_result = select_context(
            repo_root=repo_root,
            changed_symbols=all_changed_symbols,
            dependency_graph=graph,
            project_index=index,
            limits=active_limits,
            max_context_tokens=snippet_token_allowance,
        )
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
        )
        return ContextPreparationOutcome(result=context_result, summary=summary)

    except SecurityViolationError:
        raise
    except Exception as exc:
        summary = ContextSummary(
            status="fallback",
            fallback=True,
            fallback_reason=f"Recoverable context failure: {exc}",
        )
        return ContextPreparationOutcome(result=None, summary=summary)
