"""Evidence-backed priority refinements supplied by the intraprocedural engine."""

from __future__ import annotations

from collections.abc import Mapping

from deicide.context.context_models import ContextCandidate, ContextRelationshipCategory
from deicide.context.models import ChangedSymbol
from deicide.context.static_analysis import ProcedureAnalysis, StaticAnalysisResult

_CONTROL_RELEVANT_SIGNALS = frozenset({"condition", "exception", "exception_handler", "return"})


def _procedure_for_change(result: StaticAnalysisResult, changed: ChangedSymbol) -> ProcedureAnalysis | None:
    for procedure in result.procedures:
        if procedure.start_line <= changed.location.start_line <= procedure.end_line:
            return procedure
    return None


def prioritize_static_relevance(
    candidates: list[ContextCandidate],
    changed_symbols: list[ChangedSymbol],
    analyses: Mapping[str, StaticAnalysisResult],
) -> tuple[list[ContextCandidate], list[str]]:
    """Promote, but never discard, evidence-connected callers and callees.

    A parse failure, complexity limit, unresolved relationship, or absence of a
    control/data-flow signal leaves legacy ranking untouched.  This makes the
    experimental path a safe fallback rather than a context-loss mechanism.
    """
    elevated: set[str] = set()
    diagnostics: list[str] = []
    for changed in changed_symbols:
        result = analyses.get(changed.location.file_path)
        if result is None:
            continue
        procedure = _procedure_for_change(result, changed)
        if procedure is None:
            continue
        signal_lines = {signal.line for signal in procedure.signals if signal.kind in _CONTROL_RELEVANT_SIGNALS}
        if signal_lines.intersection(changed.overlapping_lines):
            elevated.add(changed.symbol_id)
    if not elevated:
        diagnostics.append("Static relevance found no changed control-flow or error-handling signal; legacy ranking retained.")
        return candidates, diagnostics

    refined: list[ContextCandidate] = []
    for candidate in candidates:
        linked = any(provenance.target_id in elevated for provenance in candidate.provenance)
        promotable = candidate.relationship in {
            ContextRelationshipCategory.DIRECT_CALLER,
            ContextRelationshipCategory.DIRECT_CALLEE,
        }
        if linked and promotable:
            refined.append(
                candidate.model_copy(
                    update={
                        "priority": max(0, candidate.priority - 1),
                        "priority_explanation": f"{candidate.priority_explanation}; promoted by proven changed control-flow signal",
                    }
                )
            )
        else:
            refined.append(candidate)
    return refined, diagnostics
