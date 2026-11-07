"""Comprehensive unit and integration tests for the POLARIS Behavioral Delta Analysis Engine."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from polaris.context.behavioral_delta import (
    BehavioralDelta,
    BehavioralDeltaResult,
    BehavioralDeltaType,
    analyze_behavioral_deltas,
    serialize_behavioral_deltas,
)
from polaris.context.context_models import ContextSelectionLimits, ContextSelectionResult
from polaris.context.pipeline import calculate_context_token_allowance, prepare_review_context
from polaris.core.config import PolarisConfig
from polaris.core.models import CandidateFinding, Confidence, ExecutionBudget, FindingCategory, LineRange, Severity
from polaris.evaluation.models import EvaluationFixture
from polaris.evaluation.runner import evaluate_case, load_fixtures_from_file
from polaris.git.analyzer import GitAnalyzer, parse_unified_diff
from polaris.git.models import ContextSnippet, DiffBundle, FileContext
from polaris.intelligence.pipeline import FindingIntelligenceEngine
from polaris.modules.code_review import CodeReviewModule
from polaris.providers.fake import FakeProvider
from tests.conftest import run_git_cmd

BENCHMARK_PATH = Path("evaluations/fixtures/bug_introduction_benchmark.json")


def _make_bundle_and_contexts(
    diff_text: str,
    file_contents: dict[str, str],
) -> tuple[DiffBundle, dict[str, FileContext]]:
    parsed_files = parse_unified_diff(diff_text)
    diff_bundle = DiffBundle(
        repository_root="/test/repo",
        base_revision="HEAD",
        target_description="test",
        files=parsed_files,
        truncated=False,
    )
    contexts: dict[str, FileContext] = {}
    for path, content in file_contents.items():
        lines = content.splitlines()
        line_map = {idx + 1: ln for idx, ln in enumerate(lines)}
        snippets = [ContextSnippet(start_line=1, end_line=len(lines), lines=line_map)] if line_map else []
        contexts[path] = FileContext(
            file_path=path,
            total_lines=len(lines),
            snippets=snippets,
            truncated=False,
        )
    return diff_bundle, contexts


def test_behavioral_delta_model_contracts_and_immutability() -> None:
    """Verify BehavioralDelta enforces strict typing, immutability, and separates observation from risk."""
    delta = BehavioralDelta(
        delta_id="delta-1234567890",
        delta_type=BehavioralDeltaType.GUARD_REMOVAL,
        file_path="pkg/math_utils.py",
        symbol_name="divide",
        qualified_name="Calculator.divide",
        line_range=LineRange(start_line=10, end_line=12),
        changed_lines=[10, 11, 12],
        before_evidence="if denom == 0:\n    return 0.0",
        after_evidence="return num / denom",
        related_callers=["pkg/caller.py:run (line 4)"],
        related_dependencies=[],
        confidence=Confidence.HIGH,
        observed_change="Removed early-exit guard `if denom == 0:` from `Calculator.divide`.",
        inferred_risk="Downstream division `num / denom` executes without zero check; verify caller guarantees.",
    )

    assert delta.affected_symbol == "Calculator.divide"
    assert delta.evidence_strength == Confidence.HIGH
    assert "Observed change:" in delta.impact_explanation
    assert "Potential impact:" in delta.impact_explanation

    serialized = serialize_behavioral_deltas([delta])
    assert "[DELTA 1] type=guard_removal" in serialized
    assert "Observed Change :" in serialized
    assert "Inferred Risk   :" in serialized
    assert "pkg/caller.py:run (line 4)" in serialized

    with pytest.raises(ValidationError):
        # Frozen model cannot be mutated
        delta.file_path = "other.py"  # type: ignore[misc]

    with pytest.raises(ValidationError):
        # Extra fields are forbidden
        BehavioralDeltaResult(deltas=[delta], files_analyzed=1, unknown_field="bad")  # type: ignore[call-arg]


def test_detect_guard_removal_and_modification_and_addition() -> None:
    """Verify detection of guard removal, guard condition modification, and guard addition."""
    # 1. Guard modification (`<=` changed to `<`)
    diff_mod = (
        "diff --git a/src/quota.py b/src/quota.py\n"
        "--- a/src/quota.py\n"
        "+++ b/src/quota.py\n"
        "@@ -1,4 +1,4 @@\n"
        " def is_allowed(remaining: int) -> bool:\n"
        "-    if remaining <= 0:\n"
        "+    if remaining < 0:\n"
        "         return False\n"
        "     return True\n"
    )
    contents_mod = {
        "src/quota.py": (
            "def is_allowed(remaining: int) -> bool:\n    if remaining < 0:\n        return False\n    return True\n"
        )
    }
    bundle_mod, ctx_mod = _make_bundle_and_contexts(diff_mod, contents_mod)
    res_mod = analyze_behavioral_deltas(bundle_mod, ctx_mod)

    assert len(res_mod.deltas) == 1
    d_mod = res_mod.deltas[0]
    assert d_mod.delta_type == BehavioralDeltaType.GUARD_MODIFICATION
    assert d_mod.qualified_name == "is_allowed"
    assert "if remaining <= 0:" in d_mod.before_evidence
    assert "if remaining < 0:" in d_mod.after_evidence

    # 2. Guard addition (defensive check added)
    diff_add = (
        "diff --git a/src/quota.py b/src/quota.py\n"
        "--- a/src/quota.py\n"
        "+++ b/src/quota.py\n"
        "@@ -1,2 +1,4 @@\n"
        " def compute_ratio(a: float, b: float) -> float:\n"
        "+    if b == 0:\n"
        "+        return 0.0\n"
        "     return a / b\n"
    )
    contents_add = {
        "src/quota.py": (
            "def compute_ratio(a: float, b: float) -> float:\n    if b == 0:\n        return 0.0\n    return a / b\n"
        )
    }
    bundle_add, ctx_add = _make_bundle_and_contexts(diff_add, contents_add)
    res_add = analyze_behavioral_deltas(bundle_add, ctx_add)

    assert len(res_add.deltas) == 1
    d_add = res_add.deltas[0]
    assert d_add.delta_type == BehavioralDeltaType.GUARD_ADDITION
    assert "legitimate bug fix" in d_add.inferred_risk


def test_detect_signature_contract_and_mutable_default_deltas() -> None:
    """Verify signature changes (added required param, removed param, reordered, mutable default)."""
    diff_sig = (
        "diff --git a/api/client.py b/api/client.py\n"
        "--- a/api/client.py\n"
        "+++ b/api/client.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-def send_request(url: str, timeout: int = 30, tags: list[str] | None = None) -> bool:\n"
        "+def send_request(url: str, timeout: int, tags: list[str] = []) -> bool:\n"
        "     return True\n"
    )
    contents_sig = {
        "api/client.py": ("def send_request(url: str, timeout: int, tags: list[str] = []) -> bool:\n    return True\n"),
        "api/consumer.py": (
            "from api.client import send_request\n\n"
            "def trigger() -> bool:\n"
            "    return send_request('https://example.com')\n"
        ),
    }
    bundle_sig, ctx_sig = _make_bundle_and_contexts(diff_sig, contents_sig)
    res_sig = analyze_behavioral_deltas(bundle_sig, ctx_sig)

    delta_types = {d.delta_type for d in res_sig.deltas}
    assert BehavioralDeltaType.SIGNATURE_CONTRACT_CHANGE in delta_types
    assert BehavioralDeltaType.STATE_MUTATION_CHANGE in delta_types

    sig_delta = next(d for d in res_sig.deltas if d.delta_type == BehavioralDeltaType.SIGNATURE_CONTRACT_CHANGE)
    assert any("api/consumer.py:trigger" in c for c in sig_delta.related_callers)
    assert "Detected 1 caller(s) passing fewer than 2 required argument(s)" in sig_delta.inferred_risk

    mut_delta = next(d for d in res_sig.deltas if d.delta_type == BehavioralDeltaType.STATE_MUTATION_CHANGE)
    assert "tags=[]" in mut_delta.observed_change


def test_detect_resource_lifecycle_and_return_behavior_deltas() -> None:
    """Verify detection of removed context managers/cleanup calls and new None return paths."""
    diff_res = (
        "diff --git a/storage/writer.py b/storage/writer.py\n"
        "--- a/storage/writer.py\n"
        "+++ b/storage/writer.py\n"
        "@@ -1,4 +1,5 @@\n"
        " def write_payload(path: str, data: str) -> int | None:\n"
        "-    with open(path, 'w') as fh:\n"
        "-        return fh.write(data)\n"
        "+    fh = open(path, 'w')\n"
        "+    if not data:\n"
        "+        return None\n"
        "+    return fh.write(data)\n"
    )
    contents_res = {
        "storage/writer.py": (
            "def write_payload(path: str, data: str) -> int | None:\n"
            "    fh = open(path, 'w')\n"
            "    if not data:\n"
            "        return None\n"
            "    return fh.write(data)\n"
        )
    }
    bundle_res, ctx_res = _make_bundle_and_contexts(diff_res, contents_res)
    res = analyze_behavioral_deltas(bundle_res, ctx_res)

    delta_types = {d.delta_type for d in res.deltas}
    assert BehavioralDeltaType.RESOURCE_LIFECYCLE_CHANGE in delta_types
    res_delta = next(d for d in res.deltas if d.delta_type == BehavioralDeltaType.RESOURCE_LIFECYCLE_CHANGE)
    assert "with" in res_delta.observed_change


def test_detect_conditional_binding_contract_change_without_flagging_safe_paths() -> None:
    """A former unconditional value made conditional before use is review-relevant evidence."""
    risky_diff = (
        "diff --git a/service.py b/service.py\n"
        "--- a/service.py\n"
        "+++ b/service.py\n"
        "@@ -1,3 +1,4 @@\n"
        " def render(enabled):\n"
        "-    value = build_value()\n"
        "+    if enabled:\n"
        "+        value = build_value()\n"
        "     return value.serialize()\n"
    )
    risky_contents = {
        "service.py": "def render(enabled):\n    if enabled:\n        value = build_value()\n    return value.serialize()\n"
    }
    risky_bundle, risky_contexts = _make_bundle_and_contexts(risky_diff, risky_contents)
    risky = analyze_behavioral_deltas(risky_bundle, risky_contexts)

    assert any(delta.delta_type == BehavioralDeltaType.DATA_FLOW_CONTRACT_CHANGE for delta in risky.deltas)
    delta = next(delta for delta in risky.deltas if delta.delta_type == BehavioralDeltaType.DATA_FLOW_CONTRACT_CHANGE)
    assert delta.line_range.start_line == 3
    assert "may be unbound" in delta.inferred_risk

    safe_diff = risky_diff.replace("+    if enabled:\n+        value = build_value()\n", "+    if enabled:\n+        value = build_value()\n+    else:\n+        value = build_value()\n")
    safe_contents = {
        "service.py": "def render(enabled):\n    if enabled:\n        value = build_value()\n    else:\n        value = build_value()\n    return value.serialize()\n"
    }
    safe_bundle, safe_contexts = _make_bundle_and_contexts(safe_diff, safe_contents)
    safe = analyze_behavioral_deltas(safe_bundle, safe_contexts)

    assert not any(delta.delta_type == BehavioralDeltaType.DATA_FLOW_CONTRACT_CHANGE for delta in safe.deltas)


def test_benchmark_corpus_behavioral_deltas_alignment() -> None:
    """Verify Behavioral Delta Analysis across all 8 MVP 1.4 benchmark fixtures."""
    fixtures = load_fixtures_from_file(BENCHMARK_PATH)
    by_id = {f.case_id: f for f in fixtures}

    # Case 1: tqdm division by zero (guard removal)
    f1 = by_id["bug-intro-01-tqdm-zerodiv"]
    b1, c1 = _make_bundle_and_contexts(f1.diff_text, f1.file_contents)
    r1 = analyze_behavioral_deltas(b1, c1)
    assert len(r1.deltas) == 1
    assert r1.deltas[0].delta_type == BehavioralDeltaType.GUARD_REMOVAL
    assert r1.deltas[0].qualified_name == "tqdm.compute_rate"
    assert r1.deltas[0].line_range == LineRange(start_line=3, end_line=4)

    # Case 2: budget underflow (clamping max(0, ...) removal)
    f2 = by_id["bug-intro-02-polaris-budget-underflow"]
    b2, c2 = _make_bundle_and_contexts(f2.diff_text, f2.file_contents)
    r2 = analyze_behavioral_deltas(b2, c2)
    assert len(r2.deltas) == 1
    assert r2.deltas[0].delta_type == BehavioralDeltaType.GUARD_REMOVAL
    assert r2.deltas[0].qualified_name == "CodeReviewModule.calculate_context_budget"
    assert "max(0, ...)" in r2.deltas[0].observed_change

    # Case 3: flask session null-byte crash (exception handler removal)
    f3 = by_id["bug-intro-03-flask-session-nullbyte-crash"]
    b3, c3 = _make_bundle_and_contexts(f3.diff_text, f3.file_contents)
    r3 = analyze_behavioral_deltas(b3, c3)
    assert len(r3.deltas) == 1
    assert r3.deltas[0].delta_type == BehavioralDeltaType.EXCEPTION_HANDLING_CHANGE
    assert "ValueError, KeyError" in r3.deltas[0].observed_change

    # Case 4: client state mutation (defensive copy dict(...) removed before .update())
    f4 = by_id["bug-intro-04-client-state-mutation"]
    b4, c4 = _make_bundle_and_contexts(f4.diff_text, f4.file_contents)
    r4 = analyze_behavioral_deltas(b4, c4)
    assert len(r4.deltas) == 1
    assert r4.deltas[0].delta_type == BehavioralDeltaType.STATE_MUTATION_CHANGE
    assert "headers.update(request_headers)" in r4.deltas[0].observed_change

    # Case 5: cross-file signature break (removed default parameter 'currency' + caller linked)
    f5 = by_id["bug-intro-05-cross-file-signature-break"]
    b5, c5 = _make_bundle_and_contexts(f5.diff_text, f5.file_contents)
    r5 = analyze_behavioral_deltas(b5, c5)
    assert len(r5.deltas) == 1
    assert r5.deltas[0].delta_type == BehavioralDeltaType.SIGNATURE_CONTRACT_CHANGE
    assert any("handlers/checkout.py:process_checkout" in caller for caller in r5.deltas[0].related_callers)

    # Case 6: clean bug fix (protective guard addition)
    f6 = by_id["clean-neg-01-tqdm-guarded-rate-fix"]
    b6, c6 = _make_bundle_and_contexts(f6.diff_text, f6.file_contents)
    r6 = analyze_behavioral_deltas(b6, c6)
    assert len(r6.deltas) == 1
    assert r6.deltas[0].delta_type == BehavioralDeltaType.GUARD_ADDITION

    # Case 7 & 8: clean helper refactor and docstring update produce 0 deltas
    f7 = by_id["clean-neg-02-safe-helper-refactor"]
    b7, c7 = _make_bundle_and_contexts(f7.diff_text, f7.file_contents)
    r7 = analyze_behavioral_deltas(b7, c7)
    assert len(r7.deltas) == 0

    f8 = by_id["clean-neg-03-docstring-and-typing-docs"]
    b8, c8 = _make_bundle_and_contexts(f8.diff_text, f8.file_contents)
    r8 = analyze_behavioral_deltas(b8, c8)
    assert len(r8.deltas) == 0


def test_pipeline_prompt_and_finding_intelligence_integration(tmp_path: Path) -> None:
    """Verify end-to-end integration with prepare_review_context, CodeReviewModule, and FindingIntelligenceEngine."""
    repo = tmp_path / "delta_repo"
    repo.mkdir(parents=True, exist_ok=True)
    run_git_cmd(repo, "init")
    run_git_cmd(repo, "config", "user.name", "Polaris Tester")
    run_git_cmd(repo, "config", "user.email", "tester@polaris.local")

    service_file = repo / "payment.py"
    service_file.write_text(
        "def charge_card(amount: int, currency: str = 'USD') -> dict:\n"
        "    return {'amount': amount, 'currency': currency}\n",
        encoding="utf-8",
    )
    caller_file = repo / "checkout.py"
    caller_file.write_text(
        "from payment import charge_card\n\ndef run_checkout(total: int) -> dict:\n    return charge_card(total)\n",
        encoding="utf-8",
    )
    run_git_cmd(repo, "add", ".")
    run_git_cmd(repo, "commit", "-m", "Initial commit")

    # Introduce breaking signature change in payment.py
    service_file.write_text(
        "def charge_card(amount: int, currency: str) -> dict:\n    return {'amount': amount, 'currency': currency}\n",
        encoding="utf-8",
    )

    git_analyzer = GitAnalyzer(repo)
    diff_bundle = git_analyzer.extract_diff()
    contexts = git_analyzer.retrieve_context(diff_bundle)
    budget = PolarisConfig(repo_path=repo).budget

    outcome = prepare_review_context(
        repo_root=repo,
        diff_bundle=diff_bundle,
        budget=budget,
        limits=ContextSelectionLimits(max_context_tokens=2000),
        context_enabled=True,
    )

    assert outcome.result is not None
    assert outcome.summary.behavioral_deltas == 1
    assert len(outcome.result.behavioral_deltas) == 1
    delta = outcome.result.behavioral_deltas[0]
    assert delta.delta_type == BehavioralDeltaType.SIGNATURE_CONTRACT_CHANGE
    assert any("checkout.py:run_checkout" in c for c in delta.related_callers)

    # Check CodeReviewModule prompt construction includes <BEHAVIORAL_DELTA_ANALYSIS>
    module = CodeReviewModule()
    prompt = module._build_user_prompt(
        diff_bundle.reviewable_files,
        contexts,
        context_result=outcome.result,
    )
    assert "<BEHAVIORAL_DELTA_ANALYSIS>" in prompt
    assert "type=signature_contract_change" in prompt
    assert "checkout.py:run_checkout" in prompt

    # Verify FindingIntelligenceEngine links validated finding to delta_id without bypassing validation
    valid_candidate = CandidateFinding(
        category=FindingCategory.CORRECTNESS,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="payment.py",
        start_line=1,
        end_line=1,
        title="Breaking signature change in charge_card",
        description="Removed default currency parameter breaking run_checkout caller.",
        evidence="def charge_card(amount: int, currency: str) -> dict:",
    )
    invalid_candidate = CandidateFinding(
        category=FindingCategory.CORRECTNESS,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="checkout.py",  # Unchanged file -> must still be rejected!
        start_line=4,
        end_line=4,
        title="Broken caller in checkout.py",
        description="Calls charge_card with 1 argument.",
        evidence="return charge_card(total)",
    )

    intel_res = FindingIntelligenceEngine().process_candidates(
        module_id="code_review",
        candidates=[valid_candidate, invalid_candidate],
        diff_bundle=diff_bundle,
        contexts=contexts,
        repo_root=repo,
        context_result=outcome.result,
    )

    assert len(intel_res.findings) == 1
    assert intel_res.rejected_count == 1
    kept_finding = intel_res.findings[0]
    assessment = intel_res.assessments[kept_finding.id]
    assert delta.delta_id in assessment.matched_delta_ids

    # Also verify evaluate_case works seamlessly with behavioral deltas
    fixtures = load_fixtures_from_file(BENCHMARK_PATH)
    case_res = evaluate_case(fixtures[0], provider=FakeProvider(), force_end_to_end=False)
    assert case_res.status == "completed"
    assert case_res.true_positives == 1
    assert case_res.false_positives == 0


def test_exception_hierarchy_broadening_and_interrupt_safety() -> None:
    """Verify that broadening to `except Exception` does not falsely report ValueError as removed,
    and verifies that `except Exception` is distinguished from BaseException / bare except.
    """
    # 1. Broadening from (ValueError, KeyError) to Exception: ValueError is NOT removed
    diff_broaden = (
        "diff --git a/service.py b/service.py\n"
        "--- a/service.py\n"
        "+++ b/service.py\n"
        "@@ -1,6 +1,6 @@\n"
        " def parse(data):\n"
        "     try:\n"
        "         return int(data)\n"
        "-    except (ValueError, KeyError):\n"
        "+    except Exception:\n"
        "         return 0\n"
    )
    bundle, ctxs = _make_bundle_and_contexts(
        diff_broaden,
        {
            "service.py": "def parse(data):\n    try:\n        return int(data)\n    except Exception:\n        return 0\n"
        },
    )
    res = analyze_behavioral_deltas(bundle, ctxs)
    # Must NOT contain a "Removed exception handler(s) for ValueError" delta because ValueError is a subclass of Exception
    assert not any(
        d.delta_type == BehavioralDeltaType.EXCEPTION_HANDLING_CHANGE
        and "Removed exception handler" in d.observed_change
        for d in res.deltas
    )
    # Must contain a broadening delta noting that KeyboardInterrupt / SystemExit are NOT intercepted
    broad_delta = next(
        d
        for d in res.deltas
        if d.delta_type == BehavioralDeltaType.EXCEPTION_HANDLING_CHANGE
        and "Broadened exception handler" in d.observed_change
    )
    assert "Exception" in broad_delta.observed_change
    assert "KeyboardInterrupt and SystemExit are not intercepted" in broad_delta.inferred_risk

    # 2. Dropping KeyboardInterrupt handling when changing to `except Exception`: MUST detect removal of KeyboardInterrupt!
    diff_drop_interrupt = (
        "diff --git a/worker.py b/worker.py\n"
        "--- a/worker.py\n"
        "+++ b/worker.py\n"
        "@@ -1,6 +1,6 @@\n"
        " def run():\n"
        "     try:\n"
        "         step()\n"
        "-    except KeyboardInterrupt:\n"
        "+    except Exception:\n"
        "         cleanup()\n"
    )
    bundle2, ctxs2 = _make_bundle_and_contexts(
        diff_drop_interrupt,
        {"worker.py": "def run():\n    try:\n        step()\n    except Exception:\n        cleanup()\n"},
    )
    res2 = analyze_behavioral_deltas(bundle2, ctxs2)
    # KeyboardInterrupt is NOT covered by Exception, so it must be flagged as removed
    removed_delta = next(
        d
        for d in res2.deltas
        if d.delta_type == BehavioralDeltaType.EXCEPTION_HANDLING_CHANGE
        and "Removed exception handler" in d.observed_change
    )
    assert "KeyboardInterrupt" in removed_delta.observed_change

    # 3. Broadening to BaseException or bare except: MUST mention system interrupts in inferred risk
    diff_bare = (
        "diff --git a/worker.py b/worker.py\n"
        "--- a/worker.py\n"
        "+++ b/worker.py\n"
        "@@ -1,6 +1,6 @@\n"
        " def run():\n"
        "     try:\n"
        "         step()\n"
        "-    except ValueError:\n"
        "+    except:\n"
        "         cleanup()\n"
    )
    bundle3, ctxs3 = _make_bundle_and_contexts(
        diff_bare,
        {"worker.py": "def run():\n    try:\n        step()\n    except:\n        cleanup()\n"},
    )
    res3 = analyze_behavioral_deltas(bundle3, ctxs3)
    bare_delta = next(
        d
        for d in res3.deltas
        if d.delta_type == BehavioralDeltaType.EXCEPTION_HANDLING_CHANGE
        and "Broadened exception handler" in d.observed_change
    )
    assert "intercept system interrupts" in bare_delta.inferred_risk


def test_dynamic_caller_handling_no_false_positive_broken_caller(tmp_path: Path) -> None:
    """Verify that callers using *args or **kwargs are not falsely flagged as broken callers."""
    repo = tmp_path / "repo_dynamic"
    repo.mkdir()
    run_git_cmd(repo, "init", "-b", "main")
    run_git_cmd(repo, "config", "user.name", "Tester")
    run_git_cmd(repo, "config", "user.email", "tester@polaris.ai")

    lib_file = repo / "lib.py"
    lib_file.write_text("def process(a: int) -> int:\n    return a * 2\n", encoding="utf-8")
    caller_file = repo / "caller.py"
    caller_file.write_text(
        "from lib import process\n\n"
        "def run_dynamic(params: list[int]) -> int:\n"
        "    return process(*params)\n\n"
        "def run_fixed() -> int:\n"
        "    return process(1)\n",
        encoding="utf-8",
    )
    run_git_cmd(repo, "add", ".")
    run_git_cmd(repo, "commit", "-m", "Initial commit")

    # Change signature of process to require 2 arguments (a, b)
    lib_file.write_text("def process(a: int, b: int) -> int:\n    return a * b\n", encoding="utf-8")

    git_analyzer = GitAnalyzer(repo)
    diff_bundle = git_analyzer.extract_diff()
    budget = PolarisConfig(repo_path=repo).budget

    outcome = prepare_review_context(
        repo_root=repo,
        diff_bundle=diff_bundle,
        budget=budget,
        context_enabled=True,
    )

    assert outcome.result is not None
    assert len(outcome.result.behavioral_deltas) == 1
    delta = outcome.result.behavioral_deltas[0]
    assert delta.delta_type == BehavioralDeltaType.SIGNATURE_CONTRACT_CHANGE

    # `run_fixed` passed only 1 argument statically, so it IS a broken caller
    assert "caller.py:run_fixed" in delta.inferred_risk
    # `run_dynamic` passes `*params`, so it must NOT be falsely flagged as passing fewer arguments
    assert "caller.py:run_dynamic" not in delta.inferred_risk


def test_resource_cleanup_method_name_cleanup() -> None:
    """Verify that removal of .cleanup() call is detected as a resource lifecycle change."""
    diff_text = (
        "diff --git a/conn.py b/conn.py\n"
        "--- a/conn.py\n"
        "+++ b/conn.py\n"
        "@@ -1,5 +1,4 @@\n"
        " def handle(session):\n"
        "     session.query()\n"
        "-    session.cleanup()\n"
    )
    bundle, ctxs = _make_bundle_and_contexts(
        diff_text,
        {"conn.py": "def handle(session):\n    session.query()\n"},
    )
    res = analyze_behavioral_deltas(bundle, ctxs)
    cleanup_delta = next(
        (d for d in res.deltas if d.delta_type == BehavioralDeltaType.RESOURCE_LIFECYCLE_CHANGE),
        None,
    )
    assert cleanup_delta is not None
    assert "cleanup" in cleanup_delta.observed_change


def test_multi_guard_modification_pairing() -> None:
    """Verify that multiple modified guards in the same function are both detected as GUARD_MODIFICATION."""
    diff_text = (
        "diff --git a/validator.py b/validator.py\n"
        "--- a/validator.py\n"
        "+++ b/validator.py\n"
        "@@ -1,8 +1,8 @@\n"
        " def check(x, y):\n"
        "-    if x <= 0:\n"
        "+    if x < 0:\n"
        "         return False\n"
        "-    if y <= 0:\n"
        "+    if y < 0:\n"
        "         return False\n"
        "     return True\n"
    )
    bundle, ctxs = _make_bundle_and_contexts(
        diff_text,
        {
            "validator.py": "def check(x, y):\n    if x < 0:\n        return False\n    if y < 0:\n        return False\n    return True\n"
        },
    )
    res = analyze_behavioral_deltas(bundle, ctxs)
    mod_deltas = [d for d in res.deltas if d.delta_type == BehavioralDeltaType.GUARD_MODIFICATION]
    assert len(mod_deltas) == 2
    obs_changes = [d.observed_change for d in mod_deltas]
    assert any("if x <= 0:" in obs and "if x < 0:" in obs for obs in obs_changes)
    assert any("if y <= 0:" in obs and "if y < 0:" in obs for obs in obs_changes)


def test_behavioral_delta_feature_toggle(tmp_path: Path) -> None:
    """Verify Behavioral Delta defaults off and supports explicit opt-in and opt-out."""
    # 1. Config default, env overrides, and explicit flags
    cfg_default = PolarisConfig.from_env_and_args()
    assert cfg_default.behavioral_delta_enabled is False

    cfg_enabled = PolarisConfig.from_env_and_args(
        environ={"POLARIS_BEHAVIORAL_DELTA_ENABLED": "1"},
    )
    assert cfg_enabled.behavioral_delta_enabled is True

    cfg_disabled = PolarisConfig.from_env_and_args(
        environ={"POLARIS_BEHAVIORAL_DELTA_ENABLED": "0"},
    )
    assert cfg_disabled.behavioral_delta_enabled is False

    cfg_flag_disabled = PolarisConfig.from_env_and_args(
        behavioral_delta_enabled=False,
    )
    assert cfg_flag_disabled.behavioral_delta_enabled is False

    # 2. Disabled in analyze_behavioral_deltas directly
    diff_text = (
        "diff --git a/m.py b/m.py\n"
        "--- a/m.py\n"
        "+++ b/m.py\n"
        "@@ -1,4 +1,3 @@\n"
        " def f(x):\n"
        "-    if x == 0:\n"
        "-        return 0\n"
        "     return 10 / x\n"
    )
    bundle, ctxs = _make_bundle_and_contexts(diff_text, {"m.py": "def f(x):\n    return 10 / x\n"})
    res_enabled = analyze_behavioral_deltas(bundle, ctxs, enabled=True)
    assert len(res_enabled.deltas) >= 1

    res_disabled = analyze_behavioral_deltas(bundle, ctxs, enabled=False)
    assert len(res_disabled.deltas) == 0
    assert res_disabled.serialized_summary == ""
    assert res_disabled.estimated_tokens == 0

    # 3. Disabled in prepare_review_context
    repo = tmp_path / "repo_toggle"
    repo.mkdir()
    run_git_cmd(repo, "init", "-b", "main")
    run_git_cmd(repo, "config", "user.name", "Tester")
    run_git_cmd(repo, "config", "user.email", "tester@polaris.ai")

    f_py = repo / "f.py"
    f_py.write_text("def f(x):\n    if x == 0:\n        return 0\n    return 10 / x\n", encoding="utf-8")
    run_git_cmd(repo, "add", ".")
    run_git_cmd(repo, "commit", "-m", "Initial commit")

    f_py.write_text("def f(x):\n    return 10 / x\n", encoding="utf-8")
    git_analyzer = GitAnalyzer(repo)
    diff_bundle = git_analyzer.extract_diff()
    budget = PolarisConfig(repo_path=repo).budget

    outcome_enabled = prepare_review_context(
        repo_root=repo,
        diff_bundle=diff_bundle,
        budget=budget,
        behavioral_delta_enabled=True,
    )
    assert outcome_enabled.summary.behavioral_deltas >= 1
    assert outcome_enabled.result is not None
    assert outcome_enabled.result.serialized_behavioral_deltas != ""

    outcome_disabled = prepare_review_context(
        repo_root=repo,
        diff_bundle=diff_bundle,
        budget=budget,
        behavioral_delta_enabled=False,
    )
    assert outcome_disabled.summary.behavioral_deltas == 0
    assert outcome_disabled.result is not None
    assert outcome_disabled.result.serialized_behavioral_deltas == ""
    assert outcome_disabled.result.behavioral_deltas == []

    # 4. Disabled in evaluate_case
    fixtures = load_fixtures_from_file(BENCHMARK_PATH)
    case_res = evaluate_case(
        fixtures[0],
        provider=FakeProvider(),
        force_end_to_end=False,
        behavioral_delta_enabled=False,
    )
    assert case_res.status == "completed"


def test_omitted_behavioral_delta_is_not_reintroduced_into_production_or_evaluation_prompt(tmp_path: Path) -> None:
    """A delta excluded by effective capacity must never reach either review prompt."""
    diff_text = (
        "diff --git a/math_utils.py b/math_utils.py\n"
        "--- a/math_utils.py\n"
        "+++ b/math_utils.py\n"
        "@@ -1,4 +1,2 @@\n"
        " def divide(value, denominator):\n"
        "-    if denominator == 0:\n"
        "-        return 0\n"
        "     return value / denominator\n"
    )
    file_contents = {"math_utils.py": "def divide(value, denominator):\n    return value / denominator\n"}
    bundle, contexts = _make_bundle_and_contexts(diff_text, file_contents)
    module = CodeReviewModule()
    baseline_tokens = module.estimate_baseline_tokens(bundle, contexts)
    budget = ExecutionBudget(max_total_tokens=baseline_tokens + 1150)

    assert calculate_context_token_allowance(
        budget,
        baseline_prompt_tokens=baseline_tokens,
        requested_context_tokens=2000,
    ) == 0

    repo = tmp_path / "zero_capacity_repo"
    repo.mkdir()
    (repo / "math_utils.py").write_text(file_contents["math_utils.py"], encoding="utf-8")
    outcome = prepare_review_context(
        repo_root=repo,
        diff_bundle=bundle,
        budget=budget,
        limits=ContextSelectionLimits(max_context_tokens=2000),
        baseline_prompt_tokens=baseline_tokens,
    )
    assert outcome.result is not None
    assert outcome.result.behavioral_deltas
    assert outcome.result.serialized_behavioral_deltas == ""
    production_prompt = module._build_user_prompt(bundle.reviewable_files, contexts, context_result=outcome.result)
    assert "<BEHAVIORAL_DELTA_ANALYSIS>" not in production_prompt

    direct_context = ContextSelectionResult(
        behavioral_deltas=outcome.result.behavioral_deltas,
        max_allowed_tokens=2000,
    )
    assert "<BEHAVIORAL_DELTA_ANALYSIS>" in module._build_user_prompt(
        bundle.reviewable_files,
        contexts,
        context_result=direct_context,
    )

    insufficient_budget = ExecutionBudget(max_total_tokens=baseline_tokens + 1151)
    assert calculate_context_token_allowance(
        insufficient_budget,
        baseline_prompt_tokens=baseline_tokens,
        requested_context_tokens=2000,
    ) == 1
    insufficient_outcome = prepare_review_context(
        repo_root=repo,
        diff_bundle=bundle,
        budget=insufficient_budget,
        limits=ContextSelectionLimits(max_context_tokens=2000),
        baseline_prompt_tokens=baseline_tokens,
    )
    assert insufficient_outcome.result is not None
    assert insufficient_outcome.result.behavioral_deltas
    assert insufficient_outcome.result.serialized_behavioral_deltas == ""
    assert "<BEHAVIORAL_DELTA_ANALYSIS>" not in module._build_user_prompt(
        bundle.reviewable_files,
        contexts,
        context_result=insufficient_outcome.result,
    )

    fixture = EvaluationFixture(
        case_id="zero-capacity-delta",
        description="Guard removal used to verify evaluation prompt budgeting.",
        diff_text=diff_text,
        file_contents=file_contents,
    )
    provider_on = FakeProvider()
    result_on = evaluate_case(
        fixture,
        provider=provider_on,
        budget=budget,
        force_end_to_end=True,
        behavioral_delta_enabled=True,
    )
    provider_off = FakeProvider()
    result_off = evaluate_case(
        fixture,
        provider=provider_off,
        budget=budget,
        force_end_to_end=True,
        behavioral_delta_enabled=False,
    )

    assert result_on.status == result_off.status == "completed"
    assert len(provider_on.requests) == len(provider_off.requests) == 1
    assert "<BEHAVIORAL_DELTA_ANALYSIS>" not in provider_on.requests[0].user_prompt
    assert provider_on.requests[0].user_prompt == provider_off.requests[0].user_prompt
    assert provider_on.requests[0].estimated_prompt_tokens == baseline_tokens
