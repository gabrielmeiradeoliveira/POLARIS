"""Deterministic Context Expansion Policy for the Hybrid Review Engine (GOAL 28.5).

Determines when to invoke Arm ON (behavioral context expansion) based on concrete evidence
from static analysis and Arm OFF findings, while enforcing budget and quota constraints.
"""

from __future__ import annotations

from polaris.contracts.models import ContractFinding
from polaris.core.models import BudgetTracker, CandidateFinding, FindingCategory
from polaris.guardrails.models import GuardrailConfidence, SecurityFinding
from polaris.review.models import ExpansionDecision


class ContextExpansionPolicy:
    """Evaluates concrete signals to decide if Arm ON is justified."""

    def __init__(self, min_tokens_for_on: int = 1500) -> None:
        self.min_tokens_for_on = min_tokens_for_on

    def evaluate(
        self,
        security_findings: list[SecurityFinding],
        contract_findings: list[ContractFinding],
        off_findings: list[CandidateFinding],
        tracker: BudgetTracker,
        related_files_available: bool,
    ) -> ExpansionDecision:
        """Evaluate deterministic criteria to decide if Arm ON is required."""
        reasons: list[str] = []
        target_files: set[str] = set()

        # Check budget availability using BudgetTracker
        remaining_tokens = tracker.budget.max_total_tokens - tracker.usage.total_tokens
        remaining_requests = tracker.budget.max_requests - tracker.requests_made

        budget_permitted = remaining_tokens >= self.min_tokens_for_on
        quota_permitted = remaining_requests >= 1

        if not budget_permitted:
            return ExpansionDecision(
                should_expand=False,
                reasons=["Budget constraint: insufficient remaining tokens for context expansion."],
                budget_permitted=False,
                quota_permitted=quota_permitted,
                context_files_targeted=[],
            )

        if not quota_permitted:
            return ExpansionDecision(
                should_expand=False,
                reasons=["Quota constraint: no remaining request slots in budget."],
                budget_permitted=budget_permitted,
                quota_permitted=False,
                context_files_targeted=[],
            )

        # Trigger 1: Cross-file contract violation detected (e.g. Case 9)
        if contract_findings and related_files_available:
            reasons.append("Cross-file contract inconsistency detected; requires semantic caller verification.")
            for cf in contract_findings:
                target_files.add(cf.evidence.consumer_file)

        # Trigger 2: Candidate finding in OFF has taxonomy that depends on caller context
        # e.g., Case 5: type_mismatch on function return or null_handling
        for off_f in off_findings:
            if off_f.category in (
                FindingCategory.TYPE_MISMATCH,
                FindingCategory.NULL_HANDLING,
                FindingCategory.BOUNDARY_CONDITION,
                FindingCategory.STATE_MUTATION,
            ):
                reasons.append(
                    f"Arm OFF emitted finding with context-sensitive category '{off_f.category.value}'; "
                    "requires caller context to refine diagnosis and eliminate false positives."
                )
                target_files.add(off_f.file_path)

        # Trigger 3: Suspected security finding that requires semantic disambiguation
        for sf in security_findings:
            if sf.evidence.confidence == GuardrailConfidence.SUSPECTED:
                reasons.append(
                    f"Security guardrail '{sf.rule_id}' has suspected confidence; requires semantic context."
                )
                target_files.add(sf.file_path)

        should_expand = len(reasons) > 0 and related_files_available

        if not related_files_available and len(reasons) > 0:
            reasons.append("Context expansion skipped: no related caller files available in repository.")
            should_expand = False

        if not should_expand and len(reasons) == 0:
            reasons.append("Trivial or self-contained change: no cross-file contract or contextual ambiguity detected.")

        return ExpansionDecision(
            should_expand=should_expand,
            reasons=reasons,
            budget_permitted=True,
            quota_permitted=True,
            context_files_targeted=sorted(target_files),
        )
