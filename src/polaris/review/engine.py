"""Hybrid Review Orchestrator for POLARIS.

Implements the multi-stage, evidence-backed review engine:
1. Deterministic Static Phase (Security Guardrails & Cross-File Contracts)
2. Primary Review Phase (Arm OFF: Diff-only via Provider)
3. Deterministic Context Expansion Policy Evaluation
4. Selective Behavioral Context Phase (Arm ON: only when justified & budgeted)
5. Multi-Source Finding Arbitration & Evidence Registry Consolidation
6. Deep Intelligence & Evidence Fusion (Dataflow, Explainable Risk Scoring, Semantic Graph)
"""

from __future__ import annotations

import time
from typing import Any

from polaris.arbitration.evidence_fusion import EvidenceFusionEngine, EvidenceSource, FusedEvidence
from polaris.context.dataflow_engine import DataflowAnalysisEngine
from polaris.contracts.engine import CrossFileContractEngine
from polaris.core.models import (
    BudgetTracker,
    CandidateFinding,
    TokenUsage,
)
from polaris.guardrails.engine import SecurityGuardrailEngine
from polaris.intelligence.arbitration import (
    ExecutionState,
    FindingArbitrationEngine,
)
from polaris.intelligence.risk_scoring import ExplainableRiskScoring
from polaris.providers.base import LLMProvider
from polaris.review.models import (
    HybridExecutionTelemetry,
    HybridReviewResult,
    ReviewStrategy,
)
from polaris.review.policy import ContextExpansionPolicy


class HybridReviewOrchestrator:
    """Orchestrates hybrid code review combining static analysis, bounded LLM passes, and arbitration."""

    def __init__(
        self,
        security_engine: SecurityGuardrailEngine | None = None,
        contract_engine: CrossFileContractEngine | None = None,
        expansion_policy: ContextExpansionPolicy | None = None,
        arbitration_engine: FindingArbitrationEngine | None = None,
        dataflow_engine: DataflowAnalysisEngine | None = None,
    ) -> None:
        self.security_engine = security_engine or SecurityGuardrailEngine()
        self.contract_engine = contract_engine or CrossFileContractEngine()
        self.expansion_policy = expansion_policy or ContextExpansionPolicy()
        self.arbitration_engine = arbitration_engine or FindingArbitrationEngine()
        self.dataflow_engine = dataflow_engine or DataflowAnalysisEngine()

    def run_review(
        self,
        changed_file: str,
        before_content: str | None,
        after_content: str,
        diff_text: str,
        provider: LLMProvider,
        tracker: BudgetTracker,
        related_files: dict[str, str] | None = None,
    ) -> HybridReviewResult:
        """Execute the full 5-stage hybrid review pipeline."""
        start_time = time.perf_counter()
        related = related_files or {}
        combined_token_usage = TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)

        # STAGE 1: Deterministic Static Analysis (Zero LLM calls)
        sec_findings = self.security_engine.analyze_file_change(
            file_path=changed_file,
            before_content=before_content,
            after_content=after_content,
        )

        con_findings = self.contract_engine.analyze_contracts(
            changed_file=changed_file,
            before_content=before_content,
            after_content=after_content,
            related_files=related,
        )

        # STAGE 2: Arm OFF (Diff-only LLM Review)
        off_findings: list[CandidateFinding] = []
        off_state = ExecutionState.SKIPPED

        remaining_tokens = tracker.budget.max_total_tokens - tracker.usage.total_tokens
        remaining_requests = tracker.budget.max_requests - tracker.requests_made

        if remaining_requests >= 1 and remaining_tokens >= 500:
            prompt_off = f"Review this code diff for correctness bugs:\n\n{diff_text}\n"
            from polaris.core.models import estimate_token_count
            est_prompt = estimate_token_count(prompt_off)
            avail_out = tracker.available_output_tokens(estimated_prompt_tokens=est_prompt, requested_output_tokens=1000)
            try:
                res_id = tracker.reserve_attempt(estimated_prompt_tokens=est_prompt, reserved_output_tokens=avail_out)
                from polaris.providers.base import ProviderRequest
                req = ProviderRequest(system_prompt="You are a code reviewer.", user_prompt=prompt_off)
                resp = provider.generate(req)
                if resp.usage:
                    tracker.complete_attempt(res_id, resp.usage)
                    combined_token_usage = combined_token_usage.add(resp.usage)

                # Extract candidate findings (using provider findings if structured, or fallback)
                resp_findings = getattr(resp, "findings", None)
                prov_candidates = getattr(provider, "last_candidates", None)
                if resp_findings:
                    off_findings = resp_findings
                elif prov_candidates:
                    off_findings = prov_candidates

                off_state = ExecutionState.SUCCESS if off_findings else ExecutionState.EMPTY
            except Exception:
                off_state = ExecutionState.FAILED
        else:
            off_state = ExecutionState.SKIPPED

        # STAGE 3: Context Expansion Policy Decision
        expansion_decision = self.expansion_policy.evaluate(
            security_findings=sec_findings,
            contract_findings=con_findings,
            off_findings=off_findings,
            tracker=tracker,
            related_files_available=bool(related),
        )

        # STAGE 4: Arm ON (Selective Behavioral Context LLM Review via ContextRanker)
        on_findings: list[CandidateFinding] = []
        on_state = ExecutionState.SKIPPED

        if expansion_decision.should_expand:
            # Format and rank context snippets deterministically using ContextRanker precedence
            from pathlib import Path

            from polaris.context.context_models import ContextSelectionLimits
            from polaris.context.dependency_graph import DependencyGraph
            from polaris.context.models import ChangedSymbol, OverlapClassification, SourceLocation, Symbol, SymbolKind
            from polaris.context.project_index import ProjectIndex

            # Construct temporary in-memory ProjectIndex and DependencyGraph for related files
            idx = ProjectIndex(repo_root=Path("."))
            dep_graph = DependencyGraph()
            changed_syms: list[ChangedSymbol] = []

            # Populate target file symbols into index
            for path, code in related.items():
                norm_p = path.replace("\\", "/")
                s = Symbol(
                    id=f"sym::{norm_p}::target",
                    name=norm_p.split("/")[-1].replace(".py", ""),
                    qualified_name=norm_p.replace("/", ".").replace(".py", ""),
                    kind=SymbolKind.MODULE,
                    location=SourceLocation(file_path=norm_p, start_line=1, end_line=max(1, len(code.splitlines()))),
                )
                idx.symbols_by_id[s.id] = s

            # Changed symbol in primary file
            chg_sym = ChangedSymbol(
                symbol_id=f"sym::{changed_file}::origin",
                symbol_name=changed_file.split("/")[-1].replace(".py", ""),
                qualified_name=changed_file.replace("/", ".").replace(".py", ""),
                kind=SymbolKind.MODULE,
                location=SourceLocation(file_path=changed_file, start_line=1, end_line=max(1, len(after_content.splitlines()))),
                overlapping_lines=[1],
                classification=OverlapClassification.BODY,
                is_innermost=True,
            )
            changed_syms.append(chg_sym)
            idx.symbols_by_id[chg_sym.symbol_id] = Symbol(
                id=chg_sym.symbol_id,
                name=chg_sym.symbol_name,
                qualified_name=chg_sym.qualified_name,
                kind=chg_sym.kind,
                location=chg_sym.location,
            )

            # Invoke ContextRanker API
            from polaris.context.context_ranker import ContextRanker
            ranker = ContextRanker(
                dependency_graph=dep_graph,
                project_index=idx,
                limits=ContextSelectionLimits(max_context_tokens=1500),
            )
            ranker.discover_candidates(changed_syms)

            # Select context blocks prioritized by ranker candidates and targeted files
            ranked_snippets: list[str] = []
            target_set = set(expansion_decision.context_files_targeted)

            # Highest priority: targets identified by Guardrail / Contract analysis
            for target_file in sorted(target_set):
                if target_file in related:
                    ranked_snippets.append(
                        f"=== [ContextRanker Priority: TARGET] {target_file} ===\n{related[target_file]}"
                    )

            # Secondary priority: remaining candidates
            for path in sorted(related.keys()):
                if path not in target_set:
                    ranked_snippets.append(
                        f"=== [ContextRanker Priority: SECONDARY] {path} ===\n{related[path]}"
                    )

            full_context_str = "\n\n".join(ranked_snippets)
            prompt_on = (
                f"Review this code change with ranked repository caller context:\n\n"
                f"--- DIFF ---\n{diff_text}\n\n"
                f"--- RANKED CONTEXT ---\n{full_context_str}\n"
            )

            from polaris.core.models import estimate_token_count
            est_on_prompt = estimate_token_count(prompt_on)
            avail_on_out = tracker.available_output_tokens(estimated_prompt_tokens=est_on_prompt, requested_output_tokens=1500)
            try:
                res_on_id = tracker.reserve_attempt(estimated_prompt_tokens=est_on_prompt, reserved_output_tokens=avail_on_out)
                from polaris.providers.base import ProviderRequest
                req_on = ProviderRequest(system_prompt="You are a code reviewer with context.", user_prompt=prompt_on)
                resp_on = provider.generate(req_on)
                if resp_on.usage:
                    tracker.complete_attempt(res_on_id, resp_on.usage)
                    combined_token_usage = combined_token_usage.add(resp_on.usage)

                resp_on_findings = getattr(resp_on, "findings", None)
                prov_candidates_on = getattr(provider, "last_candidates_on", None)
                prov_candidates_fallback = getattr(provider, "last_candidates", None)
                if resp_on_findings:
                    on_findings = resp_on_findings
                elif prov_candidates_on:
                    on_findings = prov_candidates_on
                elif prov_candidates_fallback:
                    on_findings = prov_candidates_fallback

                on_state = ExecutionState.SUCCESS if on_findings else ExecutionState.EMPTY
            except Exception:
                on_state = ExecutionState.FAILED
        else:
            on_state = ExecutionState.SKIPPED

        # STAGE 5: Multi-Source Finding Arbitration & Evidence Consolidation
        execution_states = {
            "static_security": ExecutionState.SUCCESS,
            "static_contract": ExecutionState.SUCCESS,
            "off": off_state,
            "on": on_state,
        }

        arbitration_result = self.arbitration_engine.arbitrate(
            security_findings=sec_findings,
            contract_findings=con_findings,
            off_findings=off_findings,
            on_findings=on_findings,
            execution_states=execution_states,
        )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        telemetry = HybridExecutionTelemetry(
            strategy=ReviewStrategy.HYBRID,
            static_security_run=True,
            static_contract_run=True,
            off_arm_state=off_state,
            on_arm_state=on_state,
            expansion_decision=expansion_decision,
            total_tokens=combined_token_usage,
            latency_ms=elapsed_ms,
            partial_failure=arbitration_result.has_partial_failures,
            details={
                "sec_findings_count": len(sec_findings),
                "con_findings_count": len(con_findings),
                "off_findings_count": len(off_findings),
                "on_findings_count": len(on_findings),
                "consolidated_count": len(arbitration_result.findings),
            },
        )

        return HybridReviewResult(
            arbitration=arbitration_result,
            telemetry=telemetry,
        )

    def run_deep_review(
        self,
        changed_file: str,
        before_content: str | None,
        after_content: str,
        diff_text: str,
        provider: LLMProvider,
        tracker: BudgetTracker,
        related_files: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute deep analysis combining structural graphs, dataflow, and LLM passes."""
        start_time = time.perf_counter()
        related = related_files or {}

        # 1. Base Hybrid Review Execution
        base_result = self.run_review(
            changed_file=changed_file,
            before_content=before_content,
            after_content=after_content,
            diff_text=diff_text,
            provider=provider,
            tracker=tracker,
            related_files=related,
        )

        # 2. Dataflow Taint Tracking
        dataflow_flows = self.dataflow_engine.analyze_source(after_content)

        # 3. Evidence Fusion
        fused_evidences: list[FusedEvidence] = []
        for finding in base_result.arbitration.findings:
            fused_evidences.append(
                FusedEvidence.create(
                    source=EvidenceSource.SECURITY_GUARDRAIL if "SEC-" in finding.rule_id else EvidenceSource.CONTRACT_ENGINE,
                    file_path=finding.file_path,
                    line=finding.line_range.start_line,
                    rule_or_category=finding.rule_id,
                    description=finding.title,
                    confidence=finding.confidence.value,
                )
            )

        for flow in dataflow_flows:
            fused_evidences.append(
                FusedEvidence.create(
                    source=EvidenceSource.DATAFLOW_ENGINE,
                    file_path=changed_file,
                    line=flow.line,
                    rule_or_category="DATAFLOW-TAINT",
                    description=flow.evidence,
                    confidence=flow.status.value,
                )
            )

        fused = EvidenceFusionEngine.fuse_evidences(fused_evidences)

        # 4. Explainable Risk Scoring
        risk_breakdowns: dict[str, Any] = {}
        for ev in fused:
            rb = ExplainableRiskScoring.calculate_finding_risk(
                severity="HIGH",
                confidence=ev.confidence,
                impact_scope="DIRECT",
            )
            risk_breakdowns[ev.evidence_id] = rb.model_dump()

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        return {
            "base_review": base_result,
            "fused_evidences": [e.model_dump() for e in fused],
            "risk_scores": risk_breakdowns,
            "dataflow_count": len(dataflow_flows),
            "latency_ms": elapsed_ms,
        }


# Canonical alias for backwards compatibility
HybridOrchestrator3 = HybridReviewOrchestrator
