"""Deterministic Finding Arbitration Engine (GOAL 28.4).

Consolidates, deduplicates, and resolves conflicts between static security guardrails,
cross-file contract analysis, Arm OFF (diff only), and Arm ON (behavioral delta) findings.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from polaris.contracts.models import ContractFinding
from polaris.core.models import CandidateFinding, FindingCategory, LineRange, Severity
from polaris.guardrails.models import GuardrailConfidence, SecurityFinding
from polaris.intelligence.evidence_registry import EvidenceRecord, EvidenceSource


class ArbitrationStatus(StrEnum):
    """Consolidated status of an arbitrated finding."""

    CONFIRMED = "confirmed"          # Formally proven by static guardrail or verified by corroboration
    CORROBORATED = "corroborated"    # Both OFF and ON (or static + LLM) independently identified the defect
    DISPUTED = "disputed"            # Divergence between sources (e.g. OFF found defect, ON returned empty)
    SUSPECTED = "suspected"          # Static or heuristic finding with unproven dynamic assumptions
    UNRESOLVED = "unresolved"        # Conflicting classifications without sufficient evidence to arbitrate


class ExecutionState(StrEnum):
    """Execution health state of an analysis arm or source."""

    SUCCESS = "success"
    EMPTY = "empty"
    TIMEOUT = "timeout"
    FAILED = "failed"
    SKIPPED = "skipped"


class SourceProvenance(BaseModel):
    """Detailed provenance tracking for a source contributing to a finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: EvidenceSource
    original_category: FindingCategory
    original_severity: Severity
    original_title: str
    original_description: str
    evidence_id: str


class ConsolidatedFinding(BaseModel):
    """Final arbitrated finding with rich provenance, evidence links, and resolution status."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str = Field(..., description="Deterministic stable identifier across sources.")
    category: FindingCategory = Field(..., description="Consolidated category.")
    severity: Severity = Field(..., description="Consolidated severity.")
    status: ArbitrationStatus = Field(..., description="Arbitration verdict.")
    file_path: str = Field(...)
    line_range: LineRange = Field(...)
    symbol: str | None = Field(default=None)
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=4000)
    primary_evidence: str = Field(...)
    provenance: list[SourceProvenance] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    arbitration_notes: list[str] = Field(default_factory=list)


class ArbitrationResult(BaseModel):
    """Output of the finding arbitration process."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    findings: list[ConsolidatedFinding] = Field(default_factory=list)
    evidence_registry: list[EvidenceRecord] = Field(default_factory=list)
    arm_execution_states: dict[str, ExecutionState] = Field(default_factory=dict)
    total_received: int
    total_consolidated: int
    has_partial_failures: bool
    warnings: list[str] = Field(default_factory=list)


def _compute_stable_id(file_path: str, start_line: int, symbol: str | None, category: str) -> str:
    norm_p = file_path.replace("\\", "/")
    raw = f"{norm_p}:{start_line}:{symbol or ''}:{category}".encode()
    return f"polaris-arb-{hashlib.sha256(raw).hexdigest()[:16]}"


class FindingArbitrationEngine:
    """Engine implementing the 6 deterministic arbitration rules."""

    def arbitrate(
        self,
        security_findings: list[SecurityFinding] | None = None,
        contract_findings: list[ContractFinding] | None = None,
        off_findings: list[CandidateFinding] | None = None,
        on_findings: list[CandidateFinding] | None = None,
        execution_states: dict[str, ExecutionState] | None = None,
    ) -> ArbitrationResult:
        """Arbitrate findings from all sources into a single coherent set of consolidated findings."""
        sec_list = security_findings or []
        con_list = contract_findings or []
        off_list = off_findings or []
        on_list = on_findings or []
        states = execution_states or {
            "security": ExecutionState.SUCCESS,
            "contract": ExecutionState.SUCCESS,
            "off": ExecutionState.SUCCESS if off_list else ExecutionState.EMPTY,
            "on": ExecutionState.SUCCESS if on_list else ExecutionState.EMPTY,
        }

        evidence_registry: list[EvidenceRecord] = []
        warnings: list[str] = []

        has_partial_failures = any(
            st in (ExecutionState.TIMEOUT, ExecutionState.FAILED)
            for st in states.values()
        )
        if has_partial_failures:
            warnings.append("One or more analysis sources experienced operational failures or timeouts.")

        # Step 1: Ingest and register all evidence
        # Internal item: (source, category, severity, file_path, line_range, symbol, title, desc, ev_rec)
        raw_items: list[tuple[EvidenceSource, FindingCategory, Severity, str, LineRange, str | None, str, str, EvidenceRecord]] = []

        # From Security Guardrail
        for sf in sec_list:
            ev = EvidenceRecord.create(
                source=EvidenceSource.STATIC_SECURITY,
                file_path=sf.file_path,
                line_range=sf.line_range,
                property_or_contract=sf.rule_id,
                confidence=sf.evidence.confidence,
                description=sf.evidence.reason,
                symbol=sf.evidence.symbol,
                metadata={"after_predicate": sf.evidence.after_predicate},
            )
            evidence_registry.append(ev)
            raw_items.append((
                EvidenceSource.STATIC_SECURITY,
                sf.category,
                sf.severity,
                sf.file_path,
                sf.line_range,
                sf.evidence.symbol,
                sf.title,
                sf.description,
                ev,
            ))

        # From Contract Analysis
        for cf in con_list:
            ev = EvidenceRecord.create(
                source=EvidenceSource.STATIC_CONTRACT,
                file_path=cf.file_path,
                line_range=cf.line_range,
                property_or_contract=cf.rule_id,
                confidence=cf.evidence.confidence,
                description=cf.evidence.reason,
                symbol=cf.evidence.origin_symbol,
                limitations=cf.evidence.limitations,
                metadata={"consumer": f"{cf.evidence.consumer_file}:{cf.evidence.consumer_line}"},
            )
            evidence_registry.append(ev)
            raw_items.append((
                EvidenceSource.STATIC_CONTRACT,
                cf.category,
                cf.severity,
                cf.file_path,
                cf.line_range,
                cf.evidence.origin_symbol,
                cf.title,
                cf.description,
                ev,
            ))

        # From Arm OFF
        for off_c in off_list:
            ev = EvidenceRecord.create(
                source=EvidenceSource.OFF_DIFF_ONLY,
                file_path=off_c.file_path,
                line_range=LineRange(start_line=off_c.start_line, end_line=off_c.end_line or off_c.start_line),
                property_or_contract="diff_defect",
                confidence=GuardrailConfidence.SUSPECTED,
                description=off_c.evidence,
            )
            evidence_registry.append(ev)
            raw_items.append((
                EvidenceSource.OFF_DIFF_ONLY,
                off_c.category,
                off_c.severity,
                off_c.file_path,
                LineRange(start_line=off_c.start_line, end_line=off_c.end_line or off_c.start_line),
                None,
                off_c.title,
                off_c.description,
                ev,
            ))

        # From Arm ON
        for on_c in on_list:
            ev = EvidenceRecord.create(
                source=EvidenceSource.ON_BEHAVIORAL_DELTA,
                file_path=on_c.file_path,
                line_range=LineRange(start_line=on_c.start_line, end_line=on_c.end_line or on_c.start_line),
                property_or_contract="behavioral_context_defect",
                confidence=GuardrailConfidence.SUSPECTED,
                description=on_c.evidence,
            )
            evidence_registry.append(ev)
            raw_items.append((
                EvidenceSource.ON_BEHAVIORAL_DELTA,
                on_c.category,
                on_c.severity,
                on_c.file_path,
                LineRange(start_line=on_c.start_line, end_line=on_c.end_line or on_c.start_line),
                None,
                on_c.title,
                on_c.description,
                ev,
            ))

        # Step 2: Semantic Grouping
        # Group items that refer to the same file and overlapping or within 1 line
        clusters: list[list[tuple[EvidenceSource, FindingCategory, Severity, str, LineRange, str | None, str, str, EvidenceRecord]]] = []

        # Sort raw_items deterministically before grouping to guarantee order independence
        sorted_items = sorted(
            raw_items,
            key=lambda x: (x[3].replace("\\", "/"), x[4].start_line, x[4].end_line, x[0].value, x[1].value)
        )

        for item in sorted_items:
            _, _, _, file_p, line_r, sym, _, _, _ = item
            norm_p = file_p.replace("\\", "/")

            matched_cluster = None
            for cl in clusters:
                c_file = cl[0][3].replace("\\", "/")
                c_line = cl[0][4]
                c_sym = cl[0][5]
                if (
                    c_file == norm_p
                    and c_line.overlaps_or_adjacent(line_r, tolerance=1)
                    and (sym is None or c_sym is None or sym == c_sym)
                ):
                    matched_cluster = cl
                    break

            if matched_cluster is not None:
                matched_cluster.append(item)
            else:
                clusters.append([item])

        # Step 3: Arbitrate Each Cluster
        consolidated_findings: list[ConsolidatedFinding] = []

        for cluster in clusters:
            sources_present = {item[0] for item in cluster}
            all_provenance: list[SourceProvenance] = []
            ev_ids: list[str] = []
            all_limits: list[str] = []
            notes: list[str] = []

            for item in cluster:
                src, cat, sev, _, _, _, tit, desc, ev_rec = item
                all_provenance.append(
                    SourceProvenance(
                        source=src,
                        original_category=cat,
                        original_severity=sev,
                        original_title=tit,
                        original_description=desc,
                        evidence_id=ev_rec.evidence_id,
                    )
                )
                ev_ids.append(ev_rec.evidence_id)
                all_limits.extend(ev_rec.limitations)

            base_file = cluster[0][3]
            base_lines = cluster[0][4]
            base_sym = next((item[5] for item in cluster if item[5]), None)

            # Determine Arbitration Status, Category, and Severity via the 6 Rules

            # Rule A & Rule 1: Static Security Guardrail CONFIRMED
            has_confirmed_sec = any(
                item[0] == EvidenceSource.STATIC_SECURITY and item[8].confidence == GuardrailConfidence.CONFIRMED
                for item in cluster
            )
            has_contract = any(item[0] == EvidenceSource.STATIC_CONTRACT for item in cluster)
            has_off = EvidenceSource.OFF_DIFF_ONLY in sources_present
            has_on = EvidenceSource.ON_BEHAVIORAL_DELTA in sources_present

            final_category = cluster[0][1]
            final_severity = cluster[0][2]
            final_title = cluster[0][6]
            final_desc = cluster[0][7]
            status = ArbitrationStatus.SUSPECTED

            if has_confirmed_sec:
                # Security is inviolable
                status = ArbitrationStatus.CONFIRMED
                sec_item = next(it for it in cluster if it[0] == EvidenceSource.STATIC_SECURITY)
                final_category = sec_item[1]
                final_severity = sec_item[2]
                final_title = sec_item[6]
                final_desc = sec_item[7]
                if has_off and not has_on and states.get("on") != ExecutionState.FAILED:
                    notes.append("Rule A & Rule B: Static security confirmed and corroborated by Arm OFF; Arm ON omitted finding (disputed by context).")
                else:
                    notes.append("Rule A: Proven static security guardrail preserved.")

            elif has_off and has_on:
                # Both LLM arms emitted findings on this cluster
                off_item = next(it for it in cluster if it[0] == EvidenceSource.OFF_DIFF_ONLY)
                on_item = next(it for it in cluster if it[0] == EvidenceSource.ON_BEHAVIORAL_DELTA)

                if off_item[1] == on_item[1]:
                    # Exact taxonomic agreement (Rule E)
                    status = ArbitrationStatus.CORROBORATED
                    final_category = on_item[1]
                    final_severity = max(off_item[2], on_item[2], key=lambda s: s.rank)
                    final_title = on_item[6]
                    final_desc = on_item[7]
                    notes.append("Rule E: Agreement between Arm OFF and Arm ON.")
                else:
                    # Taxonomic discrepancy (Rule C - Case 5)
                    # If ON has null_handling and OFF has type_mismatch, ON's context resolution is superior
                    if off_item[1] == FindingCategory.TYPE_MISMATCH and on_item[1] == FindingCategory.NULL_HANDLING:
                        final_category = FindingCategory.NULL_HANDLING
                        final_severity = on_item[2]
                        final_title = on_item[6]
                        final_desc = on_item[7]
                        status = ArbitrationStatus.CORROBORATED
                        notes.append(
                            f"Rule C: Taxonomic discrepancy resolved in favor of Arm ON's contextual finding "
                            f"'{final_category}' over Arm OFF's '{off_item[1]}' without duplicate findings."
                        )
                    else:
                        # Ambiguous mismatch without specific domain override
                        status = ArbitrationStatus.UNRESOLVED
                        final_category = on_item[1]
                        final_severity = max(off_item[2], on_item[2], key=lambda s: s.rank)
                        final_title = on_item[6]
                        final_desc = on_item[7]
                        notes.append(f"Rule C: Disputed taxonomy between OFF ({off_item[1]}) and ON ({on_item[1]}).")

            elif has_off and not has_on:
                # Rule B: OFF reported, ON was empty or failed (Case 11 without guardrail or with guardrail)
                off_item = next(it for it in cluster if it[0] == EvidenceSource.OFF_DIFF_ONLY)
                final_category = off_item[1]
                final_severity = off_item[2]
                final_title = off_item[6]
                final_desc = off_item[7]

                if states.get("on") in (ExecutionState.FAILED, ExecutionState.TIMEOUT):
                    status = ArbitrationStatus.SUSPECTED
                    notes.append("Rule F: Arm ON failed operationally; Arm OFF finding preserved unconditionally.")
                else:
                    status = ArbitrationStatus.DISPUTED
                    notes.append("Rule B: Arm OFF reported finding, but Arm ON omitted it. Preserved with disputed status.")

            elif has_on and not has_off:
                # ON reported, OFF was empty
                on_item = next(it for it in cluster if it[0] == EvidenceSource.ON_BEHAVIORAL_DELTA)
                final_category = on_item[1]
                final_severity = on_item[2]
                final_title = on_item[6]
                final_desc = on_item[7]
                status = ArbitrationStatus.SUSPECTED
                notes.append("Finding emerged exclusively from expanded behavioral context (Arm ON).")

            elif has_contract:
                # Static contract only (Rule D - Case 9)
                con_item = next(it for it in cluster if it[0] == EvidenceSource.STATIC_CONTRACT)
                final_category = con_item[1]
                final_severity = con_item[2]
                final_title = con_item[6]
                final_desc = con_item[7]
                if con_item[8].confidence == GuardrailConfidence.CONFIRMED:
                    status = ArbitrationStatus.CONFIRMED
                else:
                    # Incerteza estática preservada
                    status = ArbitrationStatus.SUSPECTED
                    notes.append("Rule D: Static contract violation detected with unproven parameter type; uncertainty preserved as SUSPECTED.")

            primary_ev = cluster[0][8].description
            stable_id = _compute_stable_id(base_file, base_lines.start_line, base_sym, final_category.value)

            consolidated_findings.append(
                ConsolidatedFinding(
                    finding_id=stable_id,
                    category=final_category,
                    severity=final_severity,
                    status=status,
                    file_path=base_file,
                    line_range=base_lines,
                    symbol=base_sym,
                    title=final_title,
                    description=final_desc,
                    primary_evidence=primary_ev,
                    provenance=all_provenance,
                    evidence_ids=ev_ids,
                    limitations=all_limits,
                    arbitration_notes=notes,
                )
            )

        return ArbitrationResult(
            findings=consolidated_findings,
            evidence_registry=evidence_registry,
            arm_execution_states=states,
            total_received=len(raw_items),
            total_consolidated=len(consolidated_findings),
            has_partial_failures=has_partial_failures,
            warnings=warnings,
        )
