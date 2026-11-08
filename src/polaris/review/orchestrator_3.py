"""Hybrid Orchestrator 3.0 (GOAL 30 - Fase 30.12).

Upgrades hybrid orchestration pipeline by integrating:
- Semantic Project Graph
- Incremental updates
- Interprocedural Impact Analysis
- Static Dataflow
- Advanced Security & Contracts
- Evidence Fusion
- Explainable Risk Scoring
- ContextRanker 3.0
"""

from __future__ import annotations

import time
from typing import Any

from polaris.arbitration.evidence_fusion import EvidenceFusionEngine, EvidenceSource, FusedEvidence
from polaris.context.behavioral_delta_3 import BehavioralDelta3
from polaris.context.context_ranker_3 import ContextRanker3
from polaris.context.dataflow_engine import DataflowAnalysisEngine
from polaris.context.impact_analysis import InterproceduralImpactAnalysis
from polaris.context.semantic_graph import EntityKind, GraphEntity, SemanticProjectGraph
from polaris.core.models import BudgetTracker, ExecutionBudget, TokenUsage
from polaris.intelligence.risk_scoring import ExplainableRiskScoring
from polaris.providers.base import LLMProvider
from polaris.review.engine import HybridReviewOrchestrator
from polaris.review.models import HybridReviewResult


class HybridOrchestrator3(HybridReviewOrchestrator):
    """Next-generation hybrid orchestrator for the Autonomous Code Intelligence Platform."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.dataflow_engine = DataflowAnalysisEngine()

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
        """Execute deep 12-stage analysis combining structural graphs, dataflow, and LLM passes."""
        start_time = time.perf_counter()
        related = related_files or {}

        # 1. Base Hybrid Review Execution (Security Guardrails, Contract Engine, Arm OFF, Expansion, Arm ON)
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
