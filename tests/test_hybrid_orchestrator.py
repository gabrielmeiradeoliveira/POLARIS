"""End-to-end tests for POLARIS Hybrid Review Orchestrator (GOAL 28.5)."""

from __future__ import annotations

import pytest

from polaris.core.models import (
    BudgetTracker,
    CandidateFinding,
    Confidence,
    ExecutionBudget,
    FindingCategory,
    Severity,
    TokenUsage,
)
from polaris.intelligence.arbitration import ArbitrationStatus, ExecutionState
from polaris.providers.base import ProviderRequest, ProviderResponse
from polaris.providers.fake import FakeProvider
from polaris.review.engine import HybridReviewOrchestrator
from polaris.review.models import ReviewStrategy


class ScriptedProvider(FakeProvider):
    """Fake provider allowing customized candidate findings for testing hybrid review."""

    def __init__(
        self,
        off_findings: list[CandidateFinding] | None = None,
        on_findings: list[CandidateFinding] | None = None,
        tokens_per_call: int = 500,
        fail_on: bool = False,
        fail_off: bool = False,
    ) -> None:
        super().__init__()
        self.off_findings = off_findings or []
        self.on_findings = on_findings or []
        self.tokens_per_call = tokens_per_call
        self.fail_on = fail_on
        self.fail_off = fail_off
        self.call_count = 0

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        self.call_count += 1
        prompt = request.user_prompt
        is_on_prompt = "CALLER CONTEXT" in prompt

        if is_on_prompt and self.fail_on:
            raise RuntimeError("Simulated network failure on Arm ON")
        if not is_on_prompt and self.fail_off:
            raise RuntimeError("Simulated timeout on Arm OFF")

        findings_to_return = self.on_findings if is_on_prompt else self.off_findings
        self.last_candidates = findings_to_return
        return ProviderResponse(
            content="Simulated review text",
            model_name="fake-model",
            usage=TokenUsage(
                prompt_tokens=self.tokens_per_call // 2,
                completion_tokens=self.tokens_per_call // 2,
                total_tokens=self.tokens_per_call,
            ),
        )


def test_case_05_hybrid_end_to_end_taxonomic_refinement():
    """Case 05: OFF emits type_mismatch -> policy expands context to ON -> ON emits null_handling -> arbitrated without duplication."""
    off_candidate = CandidateFinding(
        category=FindingCategory.TYPE_MISMATCH,
        severity=Severity.MEDIUM,
        confidence=Confidence.MEDIUM,
        file_path="plugins/loader.py",
        start_line=1,
        end_line=1,
        title="Plugin returns None unexpectedly",
        description="Return type is incompatible with expected caller object",
        evidence="plugin.execute() returns None",
    )

    on_candidate = CandidateFinding(
        category=FindingCategory.NULL_HANDLING,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="plugins/loader.py",
        start_line=1,
        end_line=1,
        title="Unhandled null in plugin execution",
        description="Callers do not guard against None return from plugin execute()",
        evidence="Caller app.py crashes with AttributeError on None",
    )

    provider = ScriptedProvider(off_findings=[off_candidate], on_findings=[on_candidate])
    budget = ExecutionBudget(max_total_tokens=10_000, max_requests=10)
    tracker = BudgetTracker(budget)
    orchestrator = HybridReviewOrchestrator()

    result = orchestrator.run_review(
        changed_file="plugins/loader.py",
        before_content="def execute(): return {'status': 'ok'}\n",
        after_content="def execute(): return None\n",
        diff_text="@@ -1 +1 @@\n-def execute(): return {'status': 'ok'}\n+def execute(): return None\n",
        provider=provider,
        tracker=tracker,
        related_files={"app.py": "from plugins.loader import execute\ndef run(): return execute()['status']\n"},
    )

    # 1. Telemetry verifies both OFF and ON were executed
    assert result.telemetry.off_arm_state == ExecutionState.SUCCESS
    assert result.telemetry.on_arm_state == ExecutionState.SUCCESS
    assert result.telemetry.expansion_decision.should_expand is True
    assert provider.call_count == 2

    # 2. Case 5 acceptance: single consolidated finding, refined to null_handling with HIGH severity
    arb = result.arbitration
    assert arb.total_consolidated == 1
    consolidated = arb.findings[0]
    assert consolidated.category == FindingCategory.NULL_HANDLING
    assert consolidated.severity == Severity.HIGH
    assert consolidated.status == ArbitrationStatus.CORROBORATED


def test_case_11_hybrid_end_to_end_security_preservation():
    """Case 11: Static guardrail detects CONFIRMED authorization relaxation, OFF agrees, ON returns empty -> finding preserved!"""
    off_candidate = CandidateFinding(
        category=FindingCategory.LOGIC_ERROR,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="auth/roles.py",
        start_line=1,
        end_line=1,
        title="Authorization check relaxed to accept None",
        description="Allows unauthenticated caller access",
        evidence="role is None in return condition",
    )

    # ON returns empty list (simulating the Case 11 attention dilution suppression)
    provider = ScriptedProvider(off_findings=[off_candidate], on_findings=[])
    budget = ExecutionBudget(max_total_tokens=10_000, max_requests=10)
    tracker = BudgetTracker(budget)
    orchestrator = HybridReviewOrchestrator()

    before_code = "def allowed(role=None):\n    return role == 'admin'\n"
    after_code = "def allowed(role=None):\n    return role is None or role == 'admin'\n"
    diff = "@@ -1 +1 @@\n-def allowed(role=None): return role == 'admin'\n+def allowed(role=None): return role is None or role == 'admin'\n"

    result = orchestrator.run_review(
        changed_file="auth/roles.py",
        before_content=before_code,
        after_content=after_code,
        diff_text=diff,
        provider=provider,
        tracker=tracker,
        related_files={"client.py": "from auth.roles import allowed\ndef check(): return allowed()\n"},
    )

    # Acceptance: finding must NOT be suppressed!
    arb = result.arbitration
    assert arb.total_consolidated == 1
    f = arb.findings[0]
    assert f.category == FindingCategory.LOGIC_ERROR
    assert f.severity == Severity.HIGH
    assert f.status == ArbitrationStatus.CONFIRMED
    assert any("disputed by context" in note for note in f.arbitration_notes)


def test_case_09_hybrid_end_to_end_contract_preserves_suspected():
    """Case 09: Cross-file contract engine identifies violation between 3 files, LLMs return empty -> SUSPECTED finding preserved."""
    provider = ScriptedProvider(off_findings=[], on_findings=[])
    budget = ExecutionBudget(max_total_tokens=10_000, max_requests=10)
    tracker = BudgetTracker(budget)
    orchestrator = HybridReviewOrchestrator()

    before_code = "def encode(x): return {'value': x}\n"
    after_code = "def encode(x): return x\n"
    diff = "@@ -1 +1 @@\n-def encode(x): return {'value': x}\n+def encode(x): return x\n"

    related = {
        "mapping/user.py": "from adapters.id import encode\ndef map_user(x): return encode(x)\n",
        "messaging/publish.py": "from mapping.user import map_user\ndef publish(x): return map_user(x)['value']\n",
    }

    result = orchestrator.run_review(
        changed_file="adapters/id.py",
        before_content=before_code,
        after_content=after_code,
        diff_text=diff,
        provider=provider,
        tracker=tracker,
        related_files=related,
    )

    arb = result.arbitration
    assert arb.total_consolidated == 1
    f = arb.findings[0]
    assert f.category == FindingCategory.TYPE_MISMATCH
    assert f.severity == Severity.HIGH
    assert f.status == ArbitrationStatus.SUSPECTED
    assert "cannot be proven statically" in f.limitations[0]


def test_trivial_change_does_not_expand_to_on():
    """When the change is purely local and trivial, Arm ON must be skipped to save tokens and latency."""
    provider = ScriptedProvider(off_findings=[])
    budget = ExecutionBudget(max_total_tokens=10_000, max_requests=10)
    tracker = BudgetTracker(budget)
    orchestrator = HybridReviewOrchestrator()

    before = "def add(a, b): return a + b\n"
    after = "def add(a, b): return a + b + 0\n"
    diff = "@@ -1 +1 @@\n-def add(a, b): return a + b\n+def add(a, b): return a + b + 0\n"

    result = orchestrator.run_review(
        changed_file="math_util.py",
        before_content=before,
        after_content=after,
        diff_text=diff,
        provider=provider,
        tracker=tracker,
        related_files={},
    )

    # Arm ON was skipped!
    assert result.telemetry.expansion_decision.should_expand is False
    assert result.telemetry.on_arm_state == ExecutionState.SKIPPED
    assert provider.call_count == 1  # Only Arm OFF was called!


def test_budget_exhaustion_prevents_on_safely():
    """If budget does not permit Arm ON, it is skipped cleanly without crashing."""
    off_candidate = CandidateFinding(
        category=FindingCategory.TYPE_MISMATCH,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="service.py",
        start_line=1,
        end_line=1,
        title="Mismatch requiring context",
        description="Detailed description for mismatch requiring context",
        evidence="Evidence line",
    )

    provider = ScriptedProvider(off_findings=[off_candidate], tokens_per_call=800)
    # Budget has only 1 request permitted total
    budget = ExecutionBudget(max_total_tokens=10_000, max_requests=1)
    tracker = BudgetTracker(budget)
    orchestrator = HybridReviewOrchestrator()

    result = orchestrator.run_review(
        changed_file="service.py",
        before_content="def f(): return 1\n",
        after_content="def f(): return None\n",
        diff_text="diff",
        provider=provider,
        tracker=tracker,
        related_files={"other.py": "from service import f\n"},
    )

    assert result.telemetry.off_arm_state == ExecutionState.SUCCESS
    assert result.telemetry.on_arm_state == ExecutionState.SKIPPED
    assert result.telemetry.expansion_decision.should_expand is False
    assert "Quota constraint" in result.telemetry.expansion_decision.reasons[0]


def test_on_arm_failure_preserves_off_and_static_findings():
    """If Arm ON encounters an operational exception, OFF and static findings remain intact."""
    off_candidate = CandidateFinding(
        category=FindingCategory.LOGIC_ERROR,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="service.py",
        start_line=1,
        end_line=1,
        title="Logic defect in diff",
        description="Detailed description for logic defect in diff",
        evidence="Evidence line",
    )

    provider = ScriptedProvider(off_findings=[off_candidate], fail_on=True)
    budget = ExecutionBudget(max_total_tokens=10_000, max_requests=10)
    tracker = BudgetTracker(budget)
    orchestrator = HybridReviewOrchestrator()

    # Trigger expansion with contract finding
    before = "def encode(x): return {'val': x}\n"
    after = "def encode(x): return x\n"

    result = orchestrator.run_review(
        changed_file="service.py",
        before_content=before,
        after_content=after,
        diff_text="diff",
        provider=provider,
        tracker=tracker,
        related_files={"client.py": "from service import encode\ndef run(x): return encode(x)['val']\n"},
    )

    assert result.telemetry.on_arm_state == ExecutionState.FAILED
    assert result.telemetry.partial_failure is True
    # Findings from OFF and static are preserved!
    assert result.arbitration.total_consolidated >= 1
    assert any("failed operationally" in note for f in result.arbitration.findings for note in f.arbitration_notes)
