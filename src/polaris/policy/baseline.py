"""Security Baseline Engine (GOAL 47).

Provides reproducible generation, persistence, loading, and comparison of
canonical security baselines across Code, Container, and Supply Chain domains.
Enforces stable line-drift-tolerant identities, atomic writes, and coverage-aware
resolution tracking.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polaris import __version__
from polaris.core.errors import PolarisError
from polaris.evidence.platform import CanonicalFindingDomain, CanonicalSecurityFinding


class BaselineError(PolarisError):
    """Raised when baseline serialization, deserialization, or validation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class BaselineFindingClassification(StrEnum):
    """Classification of findings when compared against a security baseline."""

    NEW = "new"
    EXISTING = "existing"
    RESOLVED = "resolved"


def normalize_evidence_text(text: str) -> str:
    """Normalize code or manifest evidence string to be invariant under indentation and whitespace."""
    if not text:
        return ""
    # Strip leading/trailing and collapse multiple whitespace runs
    cleaned = re.sub(r"\s+", " ", text).strip().lower()
    return cleaned


def compute_stable_baseline_fingerprint(finding: CanonicalSecurityFinding) -> str:
    """Compute line-drift-tolerant deterministic fingerprint for canonical security findings.

    Does not depend on raw line numbers, ensuring insertion/deletion of unrelated lines
    in the same file does not invalidate the identity of existing findings.
    """
    domain_key = finding.domain.value.upper()
    norm_file = finding.file_path.replace("\\", "/").strip().lower().lstrip("./")
    norm_rule = finding.rule_or_cve.strip().upper()
    norm_evidence = normalize_evidence_text(finding.evidence_text)

    # Invariants per domain:
    # 1. SUPPLY_CHAIN: manifest_file + package/cve rule + ecosystem
    # 2. CONTAINER: dockerfile + defect_type + normalized instruction
    # 3. CODE_INTELLIGENCE: file_path + rule_category + normalized snippet evidence
    seed = f"{domain_key}|{norm_file}|{norm_rule}|{norm_evidence}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    return f"bl-{digest}"


class BaselineFindingItem(BaseModel):
    """Stable, serialized representation of a canonical finding within a baseline."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stable_fingerprint: str
    finding_id: str
    domain: CanonicalFindingDomain
    title: str
    severity: str
    confidence: str
    file_path: str
    line: int
    rule_or_cve: str
    evidence_text: str
    remediation_hint: str = ""
    risk_score: float = 50.0

    @classmethod
    def from_canonical(cls, finding: CanonicalSecurityFinding) -> BaselineFindingItem:
        fp = compute_stable_baseline_fingerprint(finding)
        return cls(
            stable_fingerprint=fp,
            finding_id=finding.finding_id,
            domain=finding.domain,
            title=finding.title,
            severity=finding.severity,
            confidence=finding.confidence,
            file_path=finding.file_path.replace("\\", "/").lstrip("./"),
            line=finding.line,
            rule_or_cve=finding.rule_or_cve,
            evidence_text=finding.evidence_text,
            remediation_hint=finding.remediation_hint,
            risk_score=finding.risk_score,
        )


class SecurityBaselinePayload(BaseModel):
    """Versioned, audit-ready baseline document schema."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default="1.0")
    polaris_version: str = Field(default=__version__)
    created_at_utc: str
    execution_id: str
    repository_root: str
    base_revision: str | None = None
    head_revision: str | None = None
    is_complete: bool = True
    incompleteness_reasons: list[str] = Field(default_factory=list)
    files_analyzed: list[str] = Field(default_factory=list)
    findings: list[BaselineFindingItem] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComparedBaselineFinding(BaseModel):
    """Result of classifying an active or baseline finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    classification: BaselineFindingClassification
    stable_fingerprint: str
    finding: CanonicalSecurityFinding
    matched_baseline_fingerprint: str | None = None
    reason: str = ""


class BaselineComparisonSummary(BaseModel):
    """Aggregated statistics and delta categorization from baseline evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    is_complete: bool
    incompleteness_reasons: list[str]
    counts: dict[str, int]
    new_findings: list[ComparedBaselineFinding] = Field(default_factory=list)
    existing_findings: list[ComparedBaselineFinding] = Field(default_factory=list)
    resolved_findings: list[ComparedBaselineFinding] = Field(default_factory=list)
    stats_by_severity: dict[str, dict[str, int]] = Field(default_factory=dict)
    stats_by_domain: dict[str, dict[str, int]] = Field(default_factory=dict)


class SecurityBaselineEngine:
    """Core engine for baseline construction, serialization, and regression comparison."""

    @classmethod
    def create_baseline(
        cls,
        findings: list[CanonicalSecurityFinding],
        *,
        files_analyzed: list[str],
        repository_root: str = ".",
        base_revision: str | None = None,
        head_revision: str | None = None,
        is_complete: bool = True,
        incompleteness_reasons: list[str] | None = None,
        execution_id: str | None = None,
    ) -> SecurityBaselinePayload:
        """Create a deterministic, ordered baseline document."""
        # Deduplicate and sort items deterministically by stable_fingerprint then file_path
        items_map: dict[str, BaselineFindingItem] = {}
        for f in findings:
            item = BaselineFindingItem.from_canonical(f)
            if item.stable_fingerprint not in items_map:
                items_map[item.stable_fingerprint] = item

        sorted_items = sorted(items_map.values(), key=lambda x: (x.stable_fingerprint, x.file_path, x.line))
        sorted_files = sorted(set(f.replace("\\", "/").lstrip("./") for f in files_analyzed))

        exec_id = execution_id or f"exec-{hashlib.sha256(str(sorted_files).encode()).hexdigest()[:12]}"
        now_utc = datetime.now(UTC).isoformat()

        return SecurityBaselinePayload(
            schema_version="1.0",
            polaris_version=__version__,
            created_at_utc=now_utc,
            execution_id=exec_id,
            repository_root=repository_root.replace("\\", "/"),
            base_revision=base_revision,
            head_revision=head_revision,
            is_complete=is_complete,
            incompleteness_reasons=sorted(incompleteness_reasons or []),
            files_analyzed=sorted_files,
            findings=sorted_items,
            metadata={"total_findings": len(sorted_items), "total_files_analyzed": len(sorted_files)},
        )

    @classmethod
    def save_to_file(
        cls,
        baseline: SecurityBaselinePayload,
        destination_path: str | Path,
        *,
        overwrite: bool = False,
    ) -> Path:
        """Save baseline JSON atomically using a temporary file in the same directory."""
        dest = Path(destination_path).resolve()
        if dest.exists() and not overwrite:
            raise BaselineError(f"Baseline destination '{dest}' already exists. Use overwrite flag to replace.")

        dest.parent.mkdir(parents=True, exist_ok=True)
        serialized_text = json.dumps(baseline.model_dump(), indent=2, sort_keys=True)

        # Atomic write pattern: write to tmp file in same directory, then atomic rename
        with tempfile.NamedTemporaryFile("w", dir=dest.parent, delete=False, encoding="utf-8") as temp_file:
            temp_name = temp_file.name
            try:
                temp_file.write(serialized_text)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            except Exception as exc:
                with contextlib.suppress(OSError):
                    os.remove(temp_name)
                raise BaselineError(f"Failed to write baseline atomically to '{dest}': {exc}") from exc

        try:
            os.replace(temp_name, str(dest))
        except Exception as exc:
            with contextlib.suppress(OSError):
                os.remove(temp_name)
            raise BaselineError(f"Failed to replace baseline atomically at '{dest}': {exc}") from exc

        return dest

    @classmethod
    def load_from_file(cls, source_path: str | Path) -> SecurityBaselinePayload:
        """Read and validate a baseline file against the schema."""
        src = Path(source_path).resolve()
        if not src.is_file():
            raise BaselineError(f"Baseline file '{src}' not found or is not a valid file.")

        try:
            content = src.read_text(encoding="utf-8")
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise BaselineError(f"Invalid JSON in baseline file '{src}': {exc}") from exc
        except Exception as exc:
            raise BaselineError(f"Cannot read baseline file '{src}': {exc}") from exc

        if not isinstance(data, dict):
            raise BaselineError(f"Invalid baseline format in '{src}': top-level JSON must be an object.")

        schema_ver = data.get("schema_version")
        if schema_ver != "1.0":
            raise BaselineError(f"Unsupported baseline schema_version '{schema_ver}'. Expected '1.0'.")

        try:
            return SecurityBaselinePayload(**data)
        except Exception as exc:
            raise BaselineError(f"Baseline schema validation failed for '{src}': {exc}") from exc

    @classmethod
    def compare(
        cls,
        current_findings: list[CanonicalSecurityFinding],
        baseline: SecurityBaselinePayload,
        *,
        current_files_analyzed: list[str],
        current_is_complete: bool = True,
        current_incompleteness_reasons: list[str] | None = None,
    ) -> BaselineComparisonSummary:
        """Compare current findings against baseline, enforcing coverage guarantees for RESOLVED.

        Safety Invariant:
        An incomplete current analysis or baseline NEVER marks findings as RESOLVED.
        Findings in files not analyzed in the current execution are NEVER marked as RESOLVED.
        """
        incompleteness: list[str] = []
        if not baseline.is_complete:
            incompleteness.append("Baseline execution was marked incomplete.")
            incompleteness.extend(baseline.incompleteness_reasons)
        if not current_is_complete:
            incompleteness.append("Current execution was marked incomplete.")
            if current_incompleteness_reasons:
                incompleteness.extend(current_incompleteness_reasons)

        is_fully_complete = len(incompleteness) == 0

        # Build baseline lookup maps
        baseline_by_fp: dict[str, BaselineFindingItem] = {b.stable_fingerprint: b for b in baseline.findings}
        matched_baseline_fps: set[str] = set()

        new_items: list[ComparedBaselineFinding] = []
        existing_items: list[ComparedBaselineFinding] = []
        resolved_items: list[ComparedBaselineFinding] = []

        # 1. Match current findings against baseline
        for f in current_findings:
            fp = compute_stable_baseline_fingerprint(f)
            if fp in baseline_by_fp:
                matched_baseline_fps.add(fp)
                existing_items.append(
                    ComparedBaselineFinding(
                        classification=BaselineFindingClassification.EXISTING,
                        stable_fingerprint=fp,
                        finding=f,
                        matched_baseline_fingerprint=fp,
                        reason="matched_stable_fingerprint",
                    )
                )
            else:
                new_items.append(
                    ComparedBaselineFinding(
                        classification=BaselineFindingClassification.NEW,
                        stable_fingerprint=fp,
                        finding=f,
                        matched_baseline_fingerprint=None,
                        reason="unmatched_in_baseline",
                    )
                )

        # 2. Check for RESOLVED findings (only if analysis is complete and file was analyzed)
        normalized_current_files = set(f.replace("\\", "/").lstrip("./") for f in current_files_analyzed)

        for b_item in baseline.findings:
            if b_item.stable_fingerprint in matched_baseline_fps:
                continue

            # Check coverage: was the file analyzed in current run?
            norm_b_file = b_item.file_path.replace("\\", "/").lstrip("./")
            file_was_analyzed = norm_b_file in normalized_current_files

            if is_fully_complete and file_was_analyzed:
                # Safe to declare resolved
                resolved_f = CanonicalSecurityFinding(
                    finding_id=b_item.finding_id,
                    domain=b_item.domain,
                    title=b_item.title,
                    severity=b_item.severity,
                    confidence=b_item.confidence,
                    file_path=b_item.file_path,
                    line=b_item.line,
                    rule_or_cve=b_item.rule_or_cve,
                    evidence_text=b_item.evidence_text,
                    remediation_hint=b_item.remediation_hint,
                    risk_score=b_item.risk_score,
                )
                resolved_items.append(
                    ComparedBaselineFinding(
                        classification=BaselineFindingClassification.RESOLVED,
                        stable_fingerprint=b_item.stable_fingerprint,
                        finding=resolved_f,
                        matched_baseline_fingerprint=b_item.stable_fingerprint,
                        reason="absent_in_reanalyzed_file",
                    )
                )

        counts = {
            "new": len(new_items),
            "existing": len(existing_items),
            "resolved": len(resolved_items),
            "baseline_total": len(baseline.findings),
            "current_total": len(current_findings),
        }

        # Build stats by severity and domain
        stats_by_sev: dict[str, dict[str, int]] = {}
        for category, items in [
            ("new", new_items),
            ("existing", existing_items),
            ("resolved", resolved_items),
        ]:
            for it in items:
                sev = it.finding.severity.upper()
                if sev not in stats_by_sev:
                    stats_by_sev[sev] = {"new": 0, "existing": 0, "resolved": 0}
                stats_by_sev[sev][category] += 1

        stats_by_dom: dict[str, dict[str, int]] = {}
        for category, items in [
            ("new", new_items),
            ("existing", existing_items),
            ("resolved", resolved_items),
        ]:
            for it in items:
                dom = it.finding.domain.value
                if dom not in stats_by_dom:
                    stats_by_dom[dom] = {"new": 0, "existing": 0, "resolved": 0}
                stats_by_dom[dom][category] += 1

        return BaselineComparisonSummary(
            is_complete=is_fully_complete,
            incompleteness_reasons=incompleteness,
            counts=counts,
            new_findings=new_items,
            existing_findings=existing_items,
            resolved_findings=resolved_items,
            stats_by_severity=stats_by_sev,
            stats_by_domain=stats_by_dom,
        )
