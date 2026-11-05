"""Core analysis orchestrator connecting Git diff/context, modules, validation, and reporting."""

from __future__ import annotations

import time

from polaris.context.pipeline import prepare_review_context
from polaris.core.config import PolarisConfig
from polaris.core.models import (
    AnalysisReport,
    BudgetTracker,
    CandidateFinding,
    ProviderInfo,
)
from polaris.core.registry import ModuleRegistry
from polaris.git.analyzer import GitAnalyzer
from polaris.intelligence.pipeline import FindingIntelligenceEngine
from polaris.providers.base import LLMProvider
from polaris.quota.store import UsageStore


class AnalysisOrchestrator:
    """Stateless orchestrator executing the end-to-end POLARIS analysis pipeline."""

    def __init__(
        self,
        config: PolarisConfig,
        provider: LLMProvider,
        registry: ModuleRegistry,
        usage_store: UsageStore | None = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.registry = registry
        self.usage_store = usage_store

    def _resolve_usage_store(self) -> UsageStore | None:
        if self.usage_store is not None:
            return self.usage_store
        provider_store = getattr(self.provider, "usage_store", None)
        if isinstance(provider_store, UsageStore):
            return provider_store
        if self.config.budget.quota_enabled and self.provider.provider_name.strip().lower() != "fake":
            return UsageStore(
                db_path=self.config.resolved_usage_db_path,
                reservation_ttl_seconds=self.config.budget.reservation_ttl_seconds,
            )
        return None

    def run(self, module_ids: list[str] | None = None) -> AnalysisReport:
        """Run the full analysis workflow and return a validated AnalysisReport."""
        start_time = time.monotonic()
        stage_timings_ms: dict[str, int] = {}

        def record_timing(stage: str, started_at: float) -> None:
            stage_timings_ms[stage] = max(0, int((time.monotonic() - started_at) * 1000))

        self.config.validate_provider_credentials()
        active_store = self._resolve_usage_store()

        tracker = BudgetTracker(
            self.config.budget,
            usage_store=active_store,
            provider_name=self.provider.provider_name,
            model_name=self.provider.model_name,
            quota_scope=self.config.resolved_quota_scope,
        )

        git_analyzer = GitAnalyzer(self.config.repo_path, budget=self.config.budget)
        diff_started = time.monotonic()
        diff_bundle = git_analyzer.extract_diff(
            base_revision=self.config.base_revision,
            tracker=tracker,
        )
        record_timing("diff_read", diff_started)

        selected_modules = (
            [self.registry.get(mid) for mid in module_ids] if module_ids is not None else self.registry.list_modules()
        )
        executed_module_ids = [m.module_id for m in selected_modules]

        reviewable = diff_bundle.reviewable_files
        if diff_bundle.is_empty or not reviewable:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return AnalysisReport(
                repository_root=diff_bundle.repository_root,
                base_revision=self.config.base_revision,
                target_description=diff_bundle.target_description,
                modules_executed=executed_module_ids,
                provider=ProviderInfo(
                    provider_name=self.provider.provider_name,
                    model_name=self.provider.model_name,
                    requests_made=tracker.requests_made,
                    retries_performed=tracker.retries_performed,
                ),
                usage=tracker.usage,
                duration_ms=duration_ms,
                stage_timings_ms=stage_timings_ms,
                files_analyzed=[f.new_path for f in diff_bundle.files],
                findings=[],
                rejected_findings_count=0,
                deduplicated_findings_count=0,
                warnings=tracker.warnings,
                status="empty_diff",
            )

        context_read_started = time.monotonic()
        contexts = git_analyzer.retrieve_context(diff_bundle, tracker=tracker)
        record_timing("diff_context_read", context_read_started)

        # Estimate baseline prompt tokens (system prompt + reviewable diff + diff context)
        baseline_prompt_tokens = 0
        review_module = next((m for m in selected_modules if hasattr(m, "estimate_baseline_tokens")), None)
        if review_module is not None:
            baseline_prompt_tokens = review_module.estimate_baseline_tokens(diff_bundle, contexts)

        context_prepare_started = time.monotonic()
        context_outcome = prepare_review_context(
            repo_root=git_analyzer.repo_root,
            diff_bundle=diff_bundle,
            budget=self.config.budget,
            limits=self.config.context_limits,
            context_enabled=self.config.context_enabled,
            behavioral_delta_enabled=self.config.behavioral_delta_enabled,
            baseline_prompt_tokens=baseline_prompt_tokens,
        )
        record_timing("context_preparation", context_prepare_started)
        for stage, elapsed_ms in context_outcome.summary.stage_timings_ms.items():
            stage_timings_ms[f"context.{stage}"] = elapsed_ms
        context_result = context_outcome.result
        context_summary = context_outcome.summary

        if context_summary.fallback and context_summary.fallback_reason:
            tracker.add_warning(
                code="CONTEXT_FALLBACK",
                message=f"Context Engine fallback: {context_summary.fallback_reason}",
            )

        candidates_by_module: list[tuple[str, list[CandidateFinding]]] = []

        for module in selected_modules:
            tracker.check_elapsed_time()
            module_started = time.monotonic()
            try:
                candidates: list[CandidateFinding] = module.analyze(
                    diff_bundle=diff_bundle,
                    contexts=contexts,
                    provider=self.provider,
                    tracker=tracker,
                    context_result=context_result,
                )
            except TypeError:
                candidates = module.analyze(
                    diff_bundle=diff_bundle,
                    contexts=contexts,
                    provider=self.provider,
                    tracker=tracker,
                )
            candidates_by_module.append((module.module_id, candidates))
            record_timing(f"module_analysis.{module.module_id}", module_started)

        intelligence_engine = FindingIntelligenceEngine()
        validation_started = time.monotonic()
        intelligence_result = intelligence_engine.process_multi_module_candidates(
            candidates_by_module=candidates_by_module,
            diff_bundle=diff_bundle,
            contexts=contexts,
            repo_root=git_analyzer.repo_root,
            context_result=context_result,
        )
        record_timing("finding_validation", validation_started)
        tracker.warnings.extend(intelligence_result.warnings)
        deduped_findings = intelligence_result.findings
        total_rejected = intelligence_result.rejected_count
        deduped_count = intelligence_result.deduplicated_count
        duration_ms = int((time.monotonic() - start_time) * 1000)

        incomplete_warning_codes = {
            "DIFF_TRUNCATED",
            "MAX_FILES_EXCEEDED",
            "CONTEXT_BUDGET_REACHED",
            "FILE_TOO_LARGE",
            "TOKEN_BUDGET_TRUNCATED",
            "BUDGET_EXCEEDED_INCOMPLETE",
            "PROVIDER_SKIPPED_BUDGET",
            "PROVIDER_STAGE_FAILED_STATIC_PRESERVED",
        }
        has_incomplete_warning = (
            diff_bundle.truncated
            or any(ctx.truncated for ctx in contexts.values())
            or any(w.code in incomplete_warning_codes for w in tracker.warnings)
        )

        return AnalysisReport(
            repository_root=diff_bundle.repository_root,
            base_revision=self.config.base_revision,
            target_description=diff_bundle.target_description,
            modules_executed=executed_module_ids,
            provider=ProviderInfo(
                provider_name=self.provider.provider_name,
                model_name=self.provider.model_name,
                requests_made=tracker.requests_made,
                retries_performed=tracker.retries_performed,
            ),
            usage=tracker.usage,
            duration_ms=duration_ms,
            stage_timings_ms=stage_timings_ms,
            files_analyzed=[f.new_path for f in reviewable],
            findings=deduped_findings,
            rejected_findings_count=total_rejected,
            deduplicated_findings_count=deduped_count,
            warnings=tracker.warnings,
            status="incomplete" if has_incomplete_warning else "completed",
            context_summary=context_summary,
        )
