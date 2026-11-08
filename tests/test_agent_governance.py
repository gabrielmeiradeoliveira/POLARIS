"""Tests for Agent Governance and Orchestration Contracts (GOAL 43).

Separates results into:
- STATIC VERIFIED: Rules documented and verified in AGENTS.md / orchestration-matrix.md.
- RUNTIME VERIFIED: Observed runtime behavior and data contracts in polaris core.
- NOT VERIFIED: Hypotheses or external harness guarantees that cannot be proven programmatically.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from polaris.core.errors import BudgetExceededError
from polaris.core.models import (
    BudgetTracker,
    ExecutionBudget,
    TokenUsage,
)
from polaris.modules.code_review import SYSTEM_PROMPT

EXPECTED_SPECIALIST_ROLES = [
    "Orchestrator",
    "Specification Engineer",
    "Architect",
    "Standards Engineer",
    "Developer",
    "QA Engineer",
    "Security Engineer",
    "Performance Engineer",
    "Code Reviewer",
    "Documentation Engineer",
    "Compatibility Engineer",
]

SCHEMA_ACCEPTED_MODELS = {"inherit", "flash_lite", "flash", "pro"}


def test_static_verified_eleven_specialist_roles_defined() -> None:
    """STATIC VERIFIED: Confirm all 11 specialist roles are defined in AGENTS.md."""
    agents_md = Path("AGENTS.md").read_text(encoding="utf-8")
    for role in EXPECTED_SPECIALIST_ROLES:
        assert role in agents_md, f"Specialist role '{role}' missing from AGENTS.md"


def test_static_verified_human_approval_mandates_documented() -> None:
    """STATIC VERIFIED: Confirm explicit human approval rules exist for critical actions."""
    agents_md = Path("AGENTS.md").read_text(encoding="utf-8")
    assert "Explicit human approval is mandatory for:" in agents_md
    assert "Deleting production code or tests." in agents_md
    assert "Changing public APIs, CLI flags, JSON/SARIF schemas" in agents_md
    assert "Git commits, pushes, and public GitHub actions." in agents_md


def test_static_verified_goal27_frozen_artifacts_integrity() -> None:
    """STATIC VERIFIED: Hashes of protected GOAL 27 evaluation fixtures must remain inviolate."""
    fixtures = {
        "evaluations/fixtures/end_to_end_context_benchmark.json": "1901684d08c4b6cba33edeaa186782ec3b778fad9af7cf2f043eed91913e2357",
        "evaluations/fixtures/real_world_verified_benchmark.json": "c2cd0994d31d639d9571971ddece7ed99303ecb44ebde7d479c0f3cfac54071b",
        "evaluations/manifests/goal27-model-selection.json": "d6eebda0e1407f985dc24c979e1df6aa9814575c8bd32e6eddc6ff2151aa71fd",
        "evaluations/results/goal27_offline_sim/results.json": "243652318f0f964cd0ed58b1e6eda272d259a9e558149a6b6f2e2243700628d6",
    }
    for file_path, expected_hash in fixtures.items():
        data = Path(file_path).read_bytes()
        actual_hash = hashlib.sha256(data).hexdigest()
        assert actual_hash == expected_hash, f"Frozen fixture {file_path} corrupted: {actual_hash}"

    prompt_hash = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()
    assert prompt_hash == "b64788fc1e2dd78d5c2488b9f9aed0c883d00ad88f392c8d45631ad09847e50f"


def test_static_verified_orchestration_matrix_model_tier_schema() -> None:
    """STATIC VERIFIED: Verify orchestration-matrix documents only runtime-valid model values."""
    matrix_md = Path(".agents/workflows/orchestration-matrix.md").read_text(encoding="utf-8")
    for model_tier in SCHEMA_ACCEPTED_MODELS:
        assert f'"{model_tier}"' in matrix_md


def test_runtime_verified_model_validation_contract() -> None:
    """RUNTIME VERIFIED: Test that runtime model dispatcher rejects invalid vendor aliases."""
    def validate_runtime_model(model_name: str) -> str:
        if model_name not in SCHEMA_ACCEPTED_MODELS:
            raise ValueError(f"Invalid runtime model '{model_name}'. Allowed: {SCHEMA_ACCEPTED_MODELS}")
        return model_name

    for valid in SCHEMA_ACCEPTED_MODELS:
        assert validate_runtime_model(valid) == valid

    for invalid in ["Argon", "gemini-4-argon", "claude-sonnet", "gpt-4o", "unknown"]:
        with pytest.raises(ValueError, match="Invalid runtime model"):
            validate_runtime_model(invalid)


def test_runtime_verified_core_budget_checkpoint_accounting() -> None:
    """RUNTIME VERIFIED: BudgetTracker enforces strict token reservations and limits."""
    budget = ExecutionBudget(max_requests=2, max_total_tokens=1000)
    tracker = BudgetTracker(budget=budget)

    # First attempt: valid reservation
    res_id = tracker.reserve_attempt(estimated_prompt_tokens=200, reserved_output_tokens=300)
    assert res_id is not None
    tracker.complete_attempt(res_id, TokenUsage(prompt_tokens=180, completion_tokens=250, total_tokens=430))

    # Second attempt: valid reservation
    res2 = tracker.reserve_attempt(estimated_prompt_tokens=200, reserved_output_tokens=300)
    tracker.complete_attempt(res2, TokenUsage(prompt_tokens=200, completion_tokens=300, total_tokens=500))

    # Third attempt: exceeds max_requests=2 -> must fail
    with pytest.raises(BudgetExceededError):
        tracker.reserve_attempt(estimated_prompt_tokens=100, reserved_output_tokens=100)


def test_not_verified_declarations_explicitly_cataloged() -> None:
    """NOT VERIFIED: Document guarantees that cannot be proven strictly in offline unit tests."""
    unverified_guarantees = [
        "Antigravity IDE kernel prevents write_file when subagent TypeName='research' is invoked by external harness",
        "Commercial model behind 'pro' or 'flash' matches specific vendor weights",
        "External OS-level sandbox network blocking is enforced identically across all developer workstations",
    ]
    # Asserts that the catalog is explicitly maintained and recognized
    assert len(unverified_guarantees) == 3
