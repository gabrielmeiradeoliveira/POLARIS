"""Runner for evaluating DEICIDE analysis modules against curated ground-truth fixtures."""

from __future__ import annotations

import json
import math
import re
import tempfile
import time
from pathlib import Path

from deicide.context.behavioral_delta import analyze_behavioral_deltas
from deicide.context.context_models import (
    ContextRelationshipCategory,
    ContextSelectionLimits,
    ContextSelectionResult,
    SelectedSnippet,
)
from deicide.context.pipeline import calculate_context_token_allowance, prepare_review_context
from deicide.core.errors import BudgetExceededError, QuotaExhaustedError
from deicide.core.models import (
    BudgetTracker,
    CandidateFinding,
    ExecutionBudget,
    LineRange,
    TokenUsage,
    estimate_token_count,
)
from deicide.core.registry import AnalysisModule
from deicide.evaluation.baseline import baseline_process_candidates
from deicide.evaluation.models import (
    CaseDiagnostics,
    CaseEvaluationResult,
    CaseObservability,
    CategoryMismatchDiagnostic,
    ChangeType,
    ContextSelectionDiagnostic,
    EvaluationFixture,
    EvaluationSummary,
    FindingMatchDiagnostic,
    RejectedCandidateDiagnostic,
    UnmatchedExpectedDiagnostic,
    UnmatchedFindingDiagnostic,
)
from deicide.git.analyzer import parse_unified_diff, retrieve_changed_file_context
from deicide.git.models import ContextSnippet, DiffBundle, FileContext
from deicide.intelligence.pipeline import FindingIntelligenceEngine
from deicide.modules.code_review import CodeReviewModule
from deicide.providers.base import LLMProvider


def _sanitize_error_message(msg: str, provider: LLMProvider | None = None) -> str:
    """Remove potential API keys or authorization secrets from error strings."""
    cleaned = msg
    api_key = getattr(provider, "_api_key", None)
    if api_key and hasattr(api_key, "get_secret_value"):
        secret_val = api_key.get_secret_value().strip()
        if secret_val:
            cleaned = cleaned.replace(secret_val, "[REDACTED]")
    cleaned = re.sub(r"nvapi-[A-Za-z0-9_-]+", "[REDACTED]", cleaned)
    cleaned = re.sub(r"Bearer\s+[A-Za-z0-9_.-]+", "Bearer [REDACTED]", cleaned, flags=re.IGNORECASE)
    return cleaned


def _categorize_error(
    exc: Exception | str,
    provider: LLMProvider | None = None,
) -> tuple[str, int | None, int]:
    """Extract error category, HTTP status code (if available), and retry count."""
    structured_category = getattr(exc, "failure_category", None)
    structured_status = getattr(exc, "http_status", None)
    structured_retries = getattr(exc, "retries_attempted", None)
    if isinstance(structured_category, str):
        return structured_category, structured_status if isinstance(structured_status, int) else None, int(structured_retries or 0)
    msg = str(exc)
    category = "unknown"
    http_status: int | None = None
    retries = 0

    # Extract retry count if mentioned in message
    retry_match = re.search(r"after\s+(\d+)\s+retries", msg, re.IGNORECASE)
    if retry_match:
        retries = int(retry_match.group(1))

    # Extract HTTP status from exception or error message
    if isinstance(exc, Exception) and hasattr(exc, "code") and isinstance(exc.code, int):
        http_status = exc.code
    else:
        status_match = re.search(r"\bHTTP\s+(\d{3})\b", msg, re.IGNORECASE)
        if status_match:
            http_status = int(status_match.group(1))

    # Check for budget / quota
    if isinstance(exc, (BudgetExceededError, QuotaExhaustedError)) or "budget" in msg.lower() or "quota" in msg.lower():
        category = "budget_exhausted"
    elif http_status == 429 or "rate limit" in msg.lower():
        category = "rate_limit"
        if http_status is None:
            http_status = 429
    elif isinstance(exc, TimeoutError) or "timeout" in msg.lower() or "timed out" in msg.lower():
        category = "timeout"
    elif http_status is not None and 500 <= http_status < 600:
        category = "server_error"
    elif http_status is not None and 400 <= http_status < 500:
        category = "client_error"
    elif (
        "json" in msg.lower()
        or "malformed" in msg.lower()
        or "missing 'choices'" in msg.lower()
        or "invalid response" in msg.lower()
    ):
        category = "invalid_response"
    elif "connection" in msg.lower() or "network" in msg.lower() or "name resolution" in msg.lower():
        category = "connection_error"

    return category, http_status, retries


def _operational_state(status: str, category: str | None) -> str:
    """Expose operational outcome without changing legacy evaluation status values."""
    if status == "budget_exhausted":
        return "budget_exhausted"
    return {
        "timeout": "provider_timeout",
        "rate_limit": "provider_rate_limited",
        "connection_error": "provider_connection_error",
        "invalid_response": "provider_invalid_response",
        "server_error": "provider_http_error",
        "client_error": "provider_http_error",
    }.get(category or "", "evaluation_error")


def _build_fixture_contexts(
    fixture: EvaluationFixture,
) -> dict[str, FileContext]:
    contexts: dict[str, FileContext] = {}
    for file_path, content in fixture.file_contents.items():
        lines = content.splitlines()
        line_map = {idx + 1: line for idx, line in enumerate(lines)}
        snippets = [ContextSnippet(start_line=1, end_line=len(lines), lines=line_map)] if line_map else []
        contexts[file_path] = FileContext(
            file_path=file_path,
            total_lines=len(lines),
            snippets=snippets,
            truncated=False,
        )
    return contexts


def _usage_delta(current: TokenUsage, previous: TokenUsage) -> TokenUsage:
    """Return usage attributable to one case when a tracker is shared by a corpus."""
    return TokenUsage(
        prompt_tokens=max(0, current.prompt_tokens - previous.prompt_tokens),
        completion_tokens=max(0, current.completion_tokens - previous.completion_tokens),
        total_tokens=max(0, current.total_tokens - previous.total_tokens),
        is_estimated=current.is_estimated,
        estimated_cost_usd=(
            max(0.0, (current.estimated_cost_usd or 0.0) - (previous.estimated_cost_usd or 0.0))
            if current.estimated_cost_usd is not None or previous.estimated_cost_usd is not None
            else None
        ),
    )


def _wilson_interval(successes: int, trials: int, *, minimum_trials: int = 20) -> tuple[float | None, float | None]:
    """Return a 95% Wilson interval only when the sample is large enough.

    Small fixture corpora should expose point estimates without implying a
    statistically meaningful confidence interval. The threshold is explicit so
    callers can distinguish unavailable uncertainty from a zero-width interval.
    """
    if trials < minimum_trials:
        return None, None
    z = 1.959963984540054
    proportion = successes / trials
    denominator = 1 + (z * z / trials)
    center = (proportion + z * z / (2 * trials)) / denominator
    margin = z * math.sqrt((proportion * (1 - proportion) + z * z / (4 * trials)) / trials) / denominator
    return round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)


def _observability_snapshot(
    provider: LLMProvider,
    context_result: ContextSelectionResult | None,
    enabled: bool,
) -> CaseObservability | None:
    """Create hash-only telemetry without retaining source or model response bodies."""
    if not enabled:
        return None
    context = None
    if context_result is not None:
        context = ContextSelectionDiagnostic(
            selected_files=context_result.selected_files_count,
            selected_snippets=context_result.selected_snippets_count,
            omitted_snippets=context_result.omitted_snippets_count,
            estimated_tokens=context_result.total_estimated_tokens,
            max_allowed_tokens=context_result.max_allowed_tokens,
            behavioral_deltas=len(context_result.behavioral_deltas),
            truncated=context_result.is_truncated,
            diagnostics=list(context_result.diagnostics),
        )
    return CaseObservability(
        provider=provider.provider_name,
        model=provider.model_name,
        attempts=list(getattr(provider, "last_attempts", [])) or None,
        context=context,
    )


def _prepare_production_parity_context(
    fixture: EvaluationFixture,
    diff_bundle: DiffBundle,
    budget: ExecutionBudget,
    module: AnalysisModule,
    behavioral_delta_enabled: bool,
    limits: ContextSelectionLimits,
) -> tuple[dict[str, FileContext], ContextSelectionResult | None]:
    """Materialize fixture AFTER sources and invoke the production context pipeline."""
    with tempfile.TemporaryDirectory(prefix="deicide-eval-") as directory:
        root = Path(directory)
        for relative_path, source in fixture.file_contents.items():
            destination = root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(source, encoding="utf-8")
        contexts = retrieve_changed_file_context(root, diff_bundle, budget)
        estimate = getattr(module, "estimate_baseline_tokens", None)
        baseline_tokens = estimate(diff_bundle, contexts) if callable(estimate) else 0
        outcome = prepare_review_context(
            repo_root=root,
            diff_bundle=diff_bundle,
            budget=budget,
            limits=limits,
            behavioral_delta_enabled=behavioral_delta_enabled,
            baseline_prompt_tokens=baseline_tokens,
        )
        return contexts, outcome.result


def evaluate_case(
    fixture: EvaluationFixture,
    provider: LLMProvider,
    module: AnalysisModule | None = None,
    budget: ExecutionBudget | None = None,
    use_baseline: bool = False,
    force_end_to_end: bool = False,
    strict_severity: bool = False,
    tracker: BudgetTracker | None = None,
    skip_unsuitable: bool = False,
    behavioral_delta_enabled: bool = True,
    hybrid_static_selection_enabled: bool = False,
    static_relevance_selection_enabled: bool = False,
    production_parity: bool = False,
    context_limits: ContextSelectionLimits | None = None,
    observability: bool = False,
) -> CaseEvaluationResult:
    """Run a single EvaluationFixture and compute TP, FP, FN, latency, and token consumption."""
    case_started = time.monotonic()
    active_module = module or CodeReviewModule()
    active_budget = budget or ExecutionBudget()
    active_tracker = tracker or BudgetTracker(
        active_budget,
        provider_name=provider.provider_name,
        model_name=provider.model_name,
    )
    usage_before = active_tracker.usage

    if skip_unsuitable and not fixture.is_suitable_for_live_benchmark:
        return CaseEvaluationResult(
            case_id=fixture.case_id,
            true_positives=0,
            false_positives=0,
            false_negatives=0,
            duplicates_reduced=0,
            legitimate_rejected=0,
            severity_mismatches=0,
            latency_ms=0,
            usage=_usage_delta(active_tracker.usage, usage_before),
            actual_findings=[],
            status="skipped",
            operational_state="skipped",
            error="Skipped fixture unsuitable for live benchmark",
            provenance=fixture.resolved_provenance,
            change_type=fixture.resolved_change_type,
            observability=_observability_snapshot(provider, None, observability),
        )

    start_ns = time.perf_counter_ns()
    parsed_files = parse_unified_diff(fixture.diff_text)
    diff_bundle = DiffBundle(
        repository_root="/evaluation/fixture",
        base_revision="HEAD",
        target_description=f"evaluation:{fixture.case_id}",
        files=parsed_files,
        truncated=False,
    )
    contexts = _build_fixture_contexts(fixture)

    context_result: ContextSelectionResult | None = None
    selected_snippets: list[SelectedSnippet] = []
    serialized_sections: list[str] = []
    if fixture.supplementary_snippets:
        for snip in fixture.supplementary_snippets:
            snippet_obj = SelectedSnippet(
                snippet_id=str(snip.get("snippet_id", "supp-1")),
                file_path=str(snip.get("file_path", "unknown.py")),
                start_line=int(snip.get("start_line", 1)),
                end_line=int(snip.get("end_line", 1)),
                content=str(snip.get("content", "")),
                relationship=ContextRelationshipCategory(snip.get("relationship", "direct_caller")),
            )
            selected_snippets.append(snippet_obj)
            serialized_sections.append(f"=== CONTEXT SNIPPET: {snippet_obj.file_path} ===\n{snippet_obj.content}")

    baseline_prompt_tokens = 0
    estimate_baseline = getattr(active_module, "estimate_baseline_tokens", None)
    if callable(estimate_baseline):
        baseline_prompt_tokens = estimate_baseline(diff_bundle, contexts)

    context_limits = (context_limits or ContextSelectionLimits()).model_copy(
        update={
            "hybrid_static_selection_enabled": hybrid_static_selection_enabled,
            "static_relevance_selection_enabled": static_relevance_selection_enabled,
        }
    )
    context_token_allowance = calculate_context_token_allowance(
        active_budget,
        baseline_prompt_tokens=baseline_prompt_tokens,
        requested_context_tokens=context_limits.max_context_tokens,
    )
    supplementary_context = "\n\n".join(serialized_sections)
    supplementary_tokens = estimate_token_count(supplementary_context)

    delta_result = analyze_behavioral_deltas(
        diff_bundle=diff_bundle,
        contexts=contexts,
        enabled=behavioral_delta_enabled,
    )
    available_delta_tokens = max(0, context_token_allowance - supplementary_tokens)
    include_serialized_deltas = (
        bool(delta_result.serialized_summary) and delta_result.estimated_tokens <= available_delta_tokens
    )
    delta_token_cost = delta_result.estimated_tokens if include_serialized_deltas else 0

    if selected_snippets or delta_result.deltas:
        context_result = ContextSelectionResult(
            selected_snippets=selected_snippets,
            serialized_text=supplementary_context,
            selected_snippets_count=len(selected_snippets),
            total_estimated_tokens=supplementary_tokens + delta_token_cost,
            max_allowed_tokens=context_token_allowance,
            behavioral_deltas=delta_result.deltas,
            serialized_behavioral_deltas=delta_result.serialized_summary if include_serialized_deltas else "",
            limits=context_limits.model_copy(update={"max_context_tokens": context_token_allowance}),
        )

    if production_parity:
        contexts, context_result = _prepare_production_parity_context(
            fixture,
            diff_bundle,
            active_budget,
            active_module,
            behavioral_delta_enabled,
            context_limits,
        )

    candidates: list[CandidateFinding] = []
    case_status = "completed"
    case_error: str | None = None
    error_category: str | None = None
    http_status: int | None = None
    retries_attempted: int = 0

    if not force_end_to_end and fixture.candidate_findings:
        candidates = list(fixture.candidate_findings)
    else:
        try:
            if active_budget.case_deadline_seconds is not None and time.monotonic() - case_started > active_budget.case_deadline_seconds:
                raise BudgetExceededError("Evaluation case deadline exceeded before provider request.")
            active_tracker.check_can_make_request()
            try:
                candidates = active_module.analyze(
                    diff_bundle=diff_bundle,
                    contexts=contexts,
                    provider=provider,
                    tracker=active_tracker,
                    context_result=context_result,
                )
            except TypeError:
                candidates = active_module.analyze(
                    diff_bundle=diff_bundle,
                    contexts=contexts,
                    provider=provider,
                    tracker=active_tracker,
                )
            # The synchronous urllib transport cannot be interrupted here beyond
            # its socket timeout; enforce the case deadline immediately on return.
            if active_budget.case_deadline_seconds is not None and time.monotonic() - case_started > active_budget.case_deadline_seconds:
                raise BudgetExceededError("Evaluation case deadline exceeded after provider request.")
        except (BudgetExceededError, QuotaExhaustedError) as exc:
            case_status = "budget_exhausted"
            case_error = _sanitize_error_message(str(exc), provider)
            error_category, http_status, retries_attempted = _categorize_error(exc, provider)
        except Exception as exc:
            case_status = "failed"
            case_error = _sanitize_error_message(str(exc), provider)
            error_category, http_status, retries_attempted = _categorize_error(exc, provider)

    if case_status != "completed":
        elapsed_ms = max(0, int((time.perf_counter_ns() - start_ns) / 1_000_000))
        return CaseEvaluationResult(
            case_id=fixture.case_id,
            true_positives=0,
            false_positives=0,
            false_negatives=0,
            duplicates_reduced=0,
            legitimate_rejected=0,
            severity_mismatches=0,
            latency_ms=elapsed_ms,
            usage=_usage_delta(active_tracker.usage, usage_before),
            actual_findings=[],
            status=case_status,
            operational_state=_operational_state(case_status, error_category),
            error=case_error,
            error_category=error_category,
            http_status=http_status,
            retries_attempted=retries_attempted,
            provenance=fixture.resolved_provenance,
            change_type=fixture.resolved_change_type,
            observability=_observability_snapshot(provider, context_result, observability),
        )

    warnings = []
    if use_baseline:
        actual_findings, rejected_count, deduped_count, warnings = baseline_process_candidates(
            module_id=active_module.module_id,
            candidates=candidates,
            diff_bundle=diff_bundle,
            contexts=contexts,
            repo_root=None,
        )
    else:
        intel_result = FindingIntelligenceEngine().process_candidates(
            module_id=active_module.module_id,
            candidates=candidates,
            diff_bundle=diff_bundle,
            contexts=contexts,
            repo_root=None,
            context_result=context_result,
        )
        actual_findings = intel_result.findings
        deduped_count = intel_result.deduplicated_count
        warnings = intel_result.warnings

    elapsed_ms = max(0, int((time.perf_counter_ns() - start_ns) / 1_000_000))

    # Reconstruct rejected candidate findings and rejection reasons
    rejection_warnings = [w for w in warnings if w.code.startswith("FINDING_REJECTED_")]
    rejected_diagnostics: list[RejectedCandidateDiagnostic] = []
    rej_warn_idx = 0
    for cand in candidates:
        cand_end_line = cand.end_line if cand.end_line is not None else cand.start_line
        cand_range = LineRange(start_line=cand.start_line, end_line=cand_end_line)
        is_validated = any(
            f.file_path == cand.file_path
            and f.line_range == cand_range
            and f.category == cand.category
            and f.title == cand.title
            for f in actual_findings
        )
        if not is_validated:
            matched_warn = None
            if rej_warn_idx < len(rejection_warnings):
                w = rejection_warnings[rej_warn_idx]
                if w.file_path == cand.file_path or cand.title in w.message or not w.file_path:
                    matched_warn = w
                    rej_warn_idx += 1
                else:
                    for idx_w in range(rej_warn_idx, len(rejection_warnings)):
                        candidate_w = rejection_warnings[idx_w]
                        if candidate_w.file_path == cand.file_path or cand.title in candidate_w.message:
                            matched_warn = candidate_w
                            break
            reason_msg = (
                matched_warn.message
                if matched_warn
                else "Candidate finding was rejected during evidence and policy validation."
            )
            rej_code = matched_warn.code if matched_warn else "FINDING_REJECTED"
            rejected_diagnostics.append(
                RejectedCandidateDiagnostic(
                    file_path=cand.file_path,
                    line_range=cand_range,
                    category=cand.category,
                    severity=cand.severity,
                    title=cand.title,
                    reason=reason_msg,
                    rejection_code=rej_code,
                )
            )

    effective_expected = fixture.expected_findings
    if force_end_to_end and fixture.resolved_change_type == ChangeType.CLEAN_BUG_FIX:
        effective_expected = []

    matched_expected_indices: set[int] = set()
    matched_actual_ids: set[str] = set()
    expected_claimed_by: dict[int, str] = {}
    matched_findings: list[FindingMatchDiagnostic] = []
    unmatched_findings: list[UnmatchedFindingDiagnostic] = []
    tp = 0
    fp = 0
    severity_mismatches = 0

    for actual in actual_findings:
        matched = False
        for idx, expected in enumerate(effective_expected):
            if idx not in matched_expected_indices and expected.matches(actual, strict_severity=strict_severity):
                matched_expected_indices.add(idx)
                matched_actual_ids.add(actual.id)
                expected_claimed_by[idx] = actual.id
                matched = True
                sev_match = expected.severity_matches(actual)
                if not sev_match:
                    severity_mismatches += 1

                allowed_cats = list(expected.acceptable_categories or [])
                matched_findings.append(
                    FindingMatchDiagnostic(
                        finding_id=actual.id,
                        file_path=actual.file_path,
                        line_range=actual.line_range,
                        category=actual.category,
                        severity=actual.severity,
                        title=actual.title,
                        expected_file_path=expected.file_path,
                        expected_line_range=expected.line_range,
                        expected_category=expected.category,
                        expected_allowed_categories=allowed_cats,
                        severity_match=sev_match,
                    )
                )
                break
        if matched:
            tp += 1
        else:
            fp += 1
            reasons: list[str] = []
            if not effective_expected:
                reasons.append("Fixture has no expected defects (clean change / false positive finding)")
            else:
                for idx, expected in enumerate(effective_expected):
                    exp_desc = (
                        f"expected defect #{idx + 1} "
                        f"({expected.file_path}:{expected.line_range.start_line}-{expected.line_range.end_line})"
                    )
                    if idx in matched_expected_indices and expected.matches(actual, strict_severity=strict_severity):
                        reasons.append(
                            f"Expected defect #{idx + 1} "
                            f"({expected.file_path}:{expected.line_range.start_line}-{expected.line_range.end_line}) "
                            f"already claimed by earlier finding '{expected_claimed_by.get(idx)}' (one-to-one constraint)"
                        )
                        continue

                    crit: list[str] = []
                    if actual.file_path != expected.file_path:
                        crit.append(f"file mismatch ('{actual.file_path}' != '{expected.file_path}')")
                    if not actual.line_range.overlaps_or_adjacent(expected.line_range, tolerance=2):
                        crit.append(
                            f"line range mismatch ({actual.line_range.start_line}-{actual.line_range.end_line} "
                            f"not overlapping or adjacent to {expected.line_range.start_line}-{expected.line_range.end_line} ± 2)"
                        )
                    if not expected.category_matches(actual.category):
                        exp_cats = sorted(c.value for c in (expected.acceptable_categories or set()))
                        crit.append(f"category mismatch ('{actual.category.value}' not in {exp_cats})")
                    if strict_severity and not expected.severity_matches(actual):
                        crit.append(
                            f"severity mismatch ('{actual.severity.value}' != '{expected.severity.value if expected.severity else 'any'}')"
                        )

                    if crit:
                        reasons.append(f"Against {exp_desc}: {'; '.join(crit)}")

            unmatched_findings.append(
                UnmatchedFindingDiagnostic(
                    finding_id=actual.id,
                    file_path=actual.file_path,
                    line_range=actual.line_range,
                    category=actual.category,
                    severity=actual.severity,
                    title=actual.title,
                    reasons=reasons,
                    reason=" | ".join(reasons),
                )
            )

    category_mismatches: list[CategoryMismatchDiagnostic] = []
    category_mismatch_expected_indices: set[int] = set()
    for actual in actual_findings:
        if actual.id in matched_actual_ids:
            continue
        for idx, expected in enumerate(effective_expected):
            if idx in matched_expected_indices or idx in category_mismatch_expected_indices:
                continue
            if expected.location_matches(actual) and not expected.category_matches(actual.category):
                category_mismatch_expected_indices.add(idx)
                category_mismatches.append(
                    CategoryMismatchDiagnostic(
                        finding_id=actual.id,
                        file_path=actual.file_path,
                        line_range=actual.line_range,
                        category=actual.category,
                        title=actual.title,
                        expected_file_path=expected.file_path,
                        expected_line_range=expected.line_range,
                        expected_category=expected.category,
                        expected_allowed_categories=list(expected.acceptable_categories or []),
                    )
                )
                break

    fn = len(effective_expected) - len(matched_expected_indices)
    undetected_expected_defects = len(effective_expected) - len(matched_expected_indices) - len(
        category_mismatch_expected_indices
    )

    unmatched_expected: list[UnmatchedExpectedDiagnostic] = []
    for idx, expected in enumerate(effective_expected):
        if idx not in matched_expected_indices:
            allowed_cats = list(expected.acceptable_categories or [])
            if not candidates:
                exp_reason = "No candidate findings generated by provider/module for this case."
            else:
                matching_rejected = [
                    r
                    for r in rejected_diagnostics
                    if r.file_path == expected.file_path
                    and r.line_range.overlaps_or_adjacent(expected.line_range, tolerance=2)
                    and expected.category_matches(r.category)
                ]
                if matching_rejected:
                    exp_reason = (
                        f"Candidate finding '{matching_rejected[0].title}' matched expected location and category, "
                        f"but was rejected during validation: {matching_rejected[0].reason}"
                    )
                elif not actual_findings:
                    exp_reason = (
                        f"All {len(candidates)} candidate findings were rejected during validation; "
                        "no validated findings available."
                    )
                else:
                    mismatches = []
                    for act in actual_findings:
                        crit = []
                        if act.file_path != expected.file_path:
                            crit.append(f"file '{act.file_path}' != '{expected.file_path}'")
                        if not act.line_range.overlaps_or_adjacent(expected.line_range, tolerance=2):
                            crit.append(
                                f"lines {act.line_range.start_line}-{act.line_range.end_line} not overlapping "
                                f"{expected.line_range.start_line}-{expected.line_range.end_line}"
                            )
                        if not expected.category_matches(act.category):
                            exp_cats = sorted(c.value for c in (expected.acceptable_categories or set()))
                            crit.append(f"category '{act.category.value}' not in {exp_cats}")
                        mismatches.append(f"finding '{act.id}' ({'; '.join(crit)})")
                    exp_reason = f"No validated finding matched this defect. Checked: {'; '.join(mismatches)}."

            unmatched_expected.append(
                UnmatchedExpectedDiagnostic(
                    file_path=expected.file_path,
                    line_range=expected.line_range,
                    category=expected.category,
                    allowed_categories=allowed_cats,
                    severity=expected.severity,
                    reason=exp_reason,
                )
            )

    # Calculate legitimate findings incorrectly rejected (ground truth in candidates but missing from actual)
    legitimate_rejected = 0
    for idx, expected in enumerate(effective_expected):
        if idx not in matched_expected_indices:
            candidate_present = any(
                c.file_path == expected.file_path
                and LineRange(start_line=c.start_line, end_line=c.end_line or c.start_line).overlaps_or_adjacent(
                    expected.line_range, tolerance=2
                )
                and expected.category_matches(c.category)
                for c in candidates
            )
            if candidate_present:
                legitimate_rejected += 1

    case_diagnostics = CaseDiagnostics(
        candidate_findings=list(candidates),
        validated_findings=actual_findings,
        rejected_candidates=rejected_diagnostics,
        matched_findings=matched_findings,
        category_mismatches=category_mismatches,
        unmatched_findings=unmatched_findings,
        unmatched_expected=unmatched_expected,
    )

    return CaseEvaluationResult(
        case_id=fixture.case_id,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        category_mismatch_detections=len(category_mismatches),
        undetected_expected_defects=undetected_expected_defects,
        duplicates_reduced=deduped_count,
        legitimate_rejected=legitimate_rejected,
        severity_mismatches=severity_mismatches,
        latency_ms=elapsed_ms,
        usage=_usage_delta(active_tracker.usage, usage_before),
        actual_findings=actual_findings,
        status="completed",
        error=None,
        provenance=fixture.resolved_provenance,
        change_type=fixture.resolved_change_type,
        diagnostics=case_diagnostics,
        observability=_observability_snapshot(provider, context_result, observability),
    )


def evaluate_corpus(
    fixtures: list[EvaluationFixture],
    provider: LLMProvider,
    module: AnalysisModule | None = None,
    budget: ExecutionBudget | None = None,
    use_baseline: bool = False,
    force_end_to_end: bool = False,
    strict_severity: bool = False,
    max_cases: int | None = None,
    shared_tracker: BudgetTracker | None = None,
    skip_unsuitable: bool = False,
    behavioral_delta_enabled: bool = True,
    hybrid_static_selection_enabled: bool = False,
    static_relevance_selection_enabled: bool = False,
    production_parity: bool = False,
    context_limits: ContextSelectionLimits | None = None,
    case_ids: list[str] | None = None,
    observability: bool = False,
) -> EvaluationSummary:
    """Evaluate a corpus of fixtures and aggregate precision, recall, latency, and tokens."""
    evaluated_fixtures = fixtures
    if case_ids is not None:
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Evaluation case IDs must be unique.")
        by_id = {fixture.case_id: fixture for fixture in fixtures}
        missing = [case_id for case_id in case_ids if case_id not in by_id]
        if missing:
            raise ValueError(f"Unknown evaluation case IDs: {', '.join(missing)}")
        evaluated_fixtures = [by_id[case_id] for case_id in case_ids]
    max_cases_applied: int | None = None
    if max_cases is not None and max_cases > 0:
        max_cases_applied = max_cases
        evaluated_fixtures = evaluated_fixtures[:max_cases]

    active_budget = budget or ExecutionBudget(
        max_requests=max(len(fixtures) * 2, 100),
        max_total_tokens=10_000_000,
    )
    active_tracker = shared_tracker or BudgetTracker(
        active_budget,
        provider_name=provider.provider_name,
        model_name=provider.model_name,
    )

    case_results: list[CaseEvaluationResult] = []
    total_tp = 0
    total_fp = 0
    total_fn = 0
    total_category_mismatch_detections = 0
    total_undetected_expected_defects = 0
    total_duplicates_reduced = 0
    total_legitimate_rejected = 0
    total_severity_mismatches = 0
    total_latency_ms = 0
    positive_cases = 0
    negative_cases = 0
    successful_negative_cases = 0
    negative_cases_with_fp = 0
    verified_cases = 0
    reference_modeled_cases = 0
    documented_verified_cases = 0
    unverified_cases = 0
    successful_cases = 0
    timeout_cases = 0
    error_cases = 0
    api_failed_cases = 0
    budget_exhausted_cases = 0
    skipped_cases = 0
    budget_exhausted = False

    for fixture in evaluated_fixtures:
        prov = fixture.resolved_provenance
        if prov == "fully_verified":
            verified_cases += 1
        elif prov == "documented_verified":
            documented_verified_cases += 1
        elif prov == "reference_modeled":
            reference_modeled_cases += 1
        else:
            unverified_cases += 1

        effective_is_positive = len(fixture.expected_findings) > 0
        if force_end_to_end and fixture.resolved_change_type == ChangeType.CLEAN_BUG_FIX:
            effective_is_positive = False

        if effective_is_positive:
            positive_cases += 1
        else:
            negative_cases += 1

        res = evaluate_case(
            fixture,
            provider=provider,
            module=module,
            budget=active_budget,
            use_baseline=use_baseline,
            force_end_to_end=force_end_to_end,
            strict_severity=strict_severity,
            tracker=active_tracker,
            skip_unsuitable=skip_unsuitable,
            behavioral_delta_enabled=behavioral_delta_enabled,
            hybrid_static_selection_enabled=hybrid_static_selection_enabled,
            static_relevance_selection_enabled=static_relevance_selection_enabled,
            production_parity=production_parity,
            context_limits=context_limits,
            observability=observability,
        )
        case_results.append(res)

        if res.status == "completed":
            successful_cases += 1
            total_tp += res.true_positives
            total_fp += res.false_positives
            total_fn += res.false_negatives
            total_category_mismatch_detections += res.category_mismatch_detections
            total_undetected_expected_defects += res.undetected_expected_defects
            total_duplicates_reduced += res.duplicates_reduced
            total_legitimate_rejected += res.legitimate_rejected
            total_severity_mismatches += res.severity_mismatches
            total_latency_ms += res.latency_ms
            if not effective_is_positive:
                successful_negative_cases += 1
                if res.false_positives > 0:
                    negative_cases_with_fp += 1
        elif res.status == "budget_exhausted":
            total_latency_ms += res.latency_ms
            budget_exhausted = True
            budget_exhausted_cases += 1
            remaining = evaluated_fixtures[len(case_results) :]
            for unattempted in remaining:
                case_results.append(
                    CaseEvaluationResult(
                        case_id=unattempted.case_id,
                        status="unassessed",
                        operational_state="not_attempted_budget_exhausted",
                        error=f"Not attempted because the evaluation budget was exhausted at case '{fixture.case_id}'.",
                        provenance=unattempted.resolved_provenance,
                        change_type=unattempted.resolved_change_type,
                    )
                )
            break
        elif res.status == "skipped":
            skipped_cases += 1
        else:
            total_latency_ms += res.latency_ms
            api_failed_cases += 1
            if res.error_category == "timeout":
                timeout_cases += 1
            else:
                error_cases += 1

    failed_cases = api_failed_cases + budget_exhausted_cases

    if successful_cases == 0:
        precision = None
        recall = None
        fp_rate = None
        detection_precision = None
        detection_recall = None
        f1_score = None
        detection_precision_ci_lower = detection_precision_ci_upper = None
        detection_recall_ci_lower = detection_recall_ci_upper = None
        precision_ci_lower = precision_ci_upper = None
        recall_ci_lower = recall_ci_upper = None
    else:
        precision = round(total_tp / (total_tp + total_fp), 4) if (total_tp + total_fp) > 0 else None
        recall = round(total_tp / (total_tp + total_fn), 4) if (total_tp + total_fn) > 0 else None
        fp_rate = (
            round(negative_cases_with_fp / successful_negative_cases, 4) if successful_negative_cases > 0 else None
        )
        detected_expected_defects = total_tp + total_category_mismatch_detections
        detection_precision = (
            round(detected_expected_defects / (total_tp + total_fp), 4) if (total_tp + total_fp) > 0 else None
        )
        detection_recall = (
            round(
                detected_expected_defects / (detected_expected_defects + total_undetected_expected_defects),
                4,
            )
            if (detected_expected_defects + total_undetected_expected_defects) > 0
            else None
        )
        if precision is None or recall is None:
            f1_score = None
        elif precision + recall == 0:
            f1_score = 0.0
        else:
            f1_score = round(2 * precision * recall / (precision + recall), 4)
        precision_ci_lower, precision_ci_upper = _wilson_interval(total_tp, total_tp + total_fp)
        recall_ci_lower, recall_ci_upper = _wilson_interval(total_tp, total_tp + total_fn)
        detection_precision_ci_lower, detection_precision_ci_upper = _wilson_interval(
            detected_expected_defects, total_tp + total_fp
        )
        detection_recall_ci_lower, detection_recall_ci_upper = _wilson_interval(
            detected_expected_defects, detected_expected_defects + total_undetected_expected_defects
        )

    avg_latency = (
        round(total_latency_ms / successful_cases, 2)
        if successful_cases > 0
        else (round(total_latency_ms / failed_cases, 2) if failed_cases > 0 else 0.0)
    )

    return EvaluationSummary(
        dataset_size=len(case_results),
        positive_cases=positive_cases,
        negative_cases=negative_cases,
        successful_cases=successful_cases,
        timeout_cases=timeout_cases,
        error_cases=error_cases,
        unassessed_cases=sum(result.status in {"failed", "budget_exhausted", "unassessed"} for result in case_results),
        failed_cases=failed_cases,
        api_failed_cases=api_failed_cases,
        budget_exhausted_cases=budget_exhausted_cases,
        skipped_cases=skipped_cases,
        true_positives=total_tp,
        false_positives=total_fp,
        false_negatives=total_fn,
        category_mismatch_detections=total_category_mismatch_detections,
        undetected_expected_defects=total_undetected_expected_defects,
        detection_precision=detection_precision,
        detection_recall=detection_recall,
        detection_precision_ci_lower=detection_precision_ci_lower,
        detection_precision_ci_upper=detection_precision_ci_upper,
        detection_recall_ci_lower=detection_recall_ci_lower,
        detection_recall_ci_upper=detection_recall_ci_upper,
        precision=precision,
        recall=recall,
        precision_ci_lower=precision_ci_lower,
        precision_ci_upper=precision_ci_upper,
        recall_ci_lower=recall_ci_lower,
        recall_ci_upper=recall_ci_upper,
        f1_score=f1_score,
        false_positive_rate=fp_rate,
        completion_rate=round(successful_cases / len(case_results), 4) if case_results else None,
        duplicates_reduced=total_duplicates_reduced,
        legitimate_rejected=total_legitimate_rejected,
        severity_mismatches=total_severity_mismatches,
        evaluation_mode="end_to_end" if force_end_to_end else "post_processing",
        total_latency_ms=total_latency_ms,
        average_latency_ms=round(avg_latency, 2),
        usage=active_tracker.usage,
        verified_cases=verified_cases,
        documented_verified_cases=documented_verified_cases,
        reference_modeled_cases=reference_modeled_cases,
        unverified_cases=unverified_cases,
        budget_exhausted=budget_exhausted,
        max_cases_applied=max_cases_applied,
        case_results=case_results,
    )


def load_fixtures_from_file(path: Path) -> list[EvaluationFixture]:
    """Load a list of EvaluationFixture objects from a JSON file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Evaluation fixture file must contain a JSON list of fixtures.")
    return [EvaluationFixture.model_validate(item) for item in raw]
