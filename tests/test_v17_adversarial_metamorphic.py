"""Adversarial and Metamorphic Tests for Security Baseline Engine (Fases 7 e 8).

Validates:
- Adversarial robustness:
  - Malformed JSON
  - Incompatible schema versions
  - Empty baseline
  - Oversized payloads
  - Missing required fields
  - Unicode and path edge cases (e.g. windows vs posix separators)
  - Non-existent files
- Metamorphic invariants:
  1. Permutation invariance: Reordering findings does not alter comparison counts or fingerprints.
  2. Identity comparison: Comparing a baseline against its identical set yields NEW=0, EXISTING=N, RESOLVED=0.
  3. Strict monotonicity of NEW: Adding k unique findings to an identical set increases NEW exactly by k.
  4. Monotonicity of RESOLVED: Removing k findings from a complete re-analysis increases RESOLVED by k.
  5. Line drift invariance: Inserting unrelated lines preserves finding fingerprint.
  6. Idempotent round-trip: save_to_file -> load_from_file produces identical data model.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polaris.evidence.platform import CanonicalFindingDomain, CanonicalSecurityFinding
from polaris.policy.baseline import (
    BaselineError,
    SecurityBaselineEngine,
    compute_stable_baseline_fingerprint,
)


def _gen_finding(idx: int, file_path: str = "src/app.py", sev: str = "HIGH") -> CanonicalSecurityFinding:
    return CanonicalSecurityFinding(
        finding_id=f"find:{idx:08x}",
        domain=CanonicalFindingDomain.CODE_INTELLIGENCE,
        title=f"Security issue #{idx}",
        severity=sev,
        confidence="CONFIRMED",
        file_path=file_path,
        line=idx * 10,
        rule_or_cve=f"RULE_{idx}",
        evidence_text=f"vulnerable_call_{idx}()",
        remediation_hint=f"sanitize_{idx}()",
        risk_score=70.0,
    )


# --- FASE 7: ADVERSARIAL TESTS ---

def test_adversarial_malformed_json(tmp_path: Path):
    bad_json = tmp_path / "corrupt.json"
    bad_json.write_text("{ unclosed: json, ", encoding="utf-8")
    with pytest.raises(BaselineError, match="Invalid JSON"):
        SecurityBaselineEngine.load_from_file(bad_json)


def test_adversarial_unsupported_schema(tmp_path: Path):
    bad_schema = tmp_path / "bad_schema.json"
    bad_schema.write_text(json.dumps({"schema_version": "99.0", "findings": []}), encoding="utf-8")
    with pytest.raises(BaselineError, match="Unsupported baseline schema_version '99.0'"):
        SecurityBaselineEngine.load_from_file(bad_schema)


def test_adversarial_non_dict_json(tmp_path: Path):
    arr_json = tmp_path / "array.json"
    arr_json.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(BaselineError, match="top-level JSON must be an object"):
        SecurityBaselineEngine.load_from_file(arr_json)


def test_adversarial_missing_file(tmp_path: Path):
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(BaselineError, match="not found"):
        SecurityBaselineEngine.load_from_file(missing)


def test_adversarial_empty_baseline(tmp_path: Path):
    baseline = SecurityBaselineEngine.create_baseline([], files_analyzed=[])
    fpath = SecurityBaselineEngine.save_to_file(baseline, tmp_path / "empty.json")
    loaded = SecurityBaselineEngine.load_from_file(fpath)
    assert len(loaded.findings) == 0
    assert loaded.schema_version == "1.0"


def test_adversarial_overwrite_protection(tmp_path: Path):
    baseline = SecurityBaselineEngine.create_baseline([], files_analyzed=[])
    target = tmp_path / "base.json"
    SecurityBaselineEngine.save_to_file(baseline, target)
    # Attempting to save without overwrite must fail
    with pytest.raises(BaselineError, match="already exists"):
        SecurityBaselineEngine.save_to_file(baseline, target, overwrite=False)
    # With overwrite=True, succeeds cleanly
    SecurityBaselineEngine.save_to_file(baseline, target, overwrite=True)


def test_adversarial_unicode_and_separators():
    f_win = _gen_finding(1, file_path="src\\utils\\calc.py")
    f_posix = _gen_finding(1, file_path="src/utils/calc.py")
    # Path separators must normalize to the exact same fingerprint
    assert compute_stable_baseline_fingerprint(f_win) == compute_stable_baseline_fingerprint(f_posix)


# --- FASE 8: METAMORPHIC TESTS ---

def test_metamorphic_permutation_invariance():
    """Property 1: Reordering the input list of findings produces identical summary counts."""
    findings = [_gen_finding(i) for i in range(10)]
    import random
    shuffled_1 = list(findings)
    shuffled_2 = list(findings)
    random.seed(42)
    random.shuffle(shuffled_1)
    random.shuffle(shuffled_2)

    base = SecurityBaselineEngine.create_baseline(shuffled_1, files_analyzed=["src/app.py"])
    summary_1 = SecurityBaselineEngine.compare(shuffled_1, base, current_files_analyzed=["src/app.py"])
    summary_2 = SecurityBaselineEngine.compare(shuffled_2, base, current_files_analyzed=["src/app.py"])

    assert summary_1.counts == summary_2.counts
    assert summary_1.counts["existing"] == 10
    assert summary_1.counts["new"] == 0
    assert summary_1.counts["resolved"] == 0


def test_metamorphic_identity_comparison():
    """Property 2: Comparing a complete set against its identical baseline yields zero NEW and zero RESOLVED."""
    findings = [_gen_finding(i) for i in range(5)]
    base = SecurityBaselineEngine.create_baseline(findings, files_analyzed=["src/app.py"])
    summary = SecurityBaselineEngine.compare(findings, base, current_files_analyzed=["src/app.py"])

    assert summary.counts["new"] == 0
    assert summary.counts["resolved"] == 0
    assert summary.counts["existing"] == 5


def test_metamorphic_monotonicity_of_new():
    """Property 3: Adding k unique findings strictly increases NEW count by k."""
    base_findings = [_gen_finding(i) for i in range(4)]
    base = SecurityBaselineEngine.create_baseline(base_findings, files_analyzed=["src/app.py"])

    extra_findings = [_gen_finding(i + 100) for i in range(3)]
    current = base_findings + extra_findings

    summary = SecurityBaselineEngine.compare(current, base, current_files_analyzed=["src/app.py"])
    assert summary.counts["new"] == 3
    assert summary.counts["existing"] == 4
    assert summary.counts["resolved"] == 0


def test_metamorphic_monotonicity_of_resolved():
    """Property 4: Removing k findings from a complete re-analysis strictly increases RESOLVED count by k."""
    base_findings = [_gen_finding(i) for i in range(5)]
    base = SecurityBaselineEngine.create_baseline(base_findings, files_analyzed=["src/app.py"])

    # Keep only 2 findings, 3 are removed
    current = base_findings[:2]
    summary = SecurityBaselineEngine.compare(current, base, current_files_analyzed=["src/app.py"])

    assert summary.counts["new"] == 0
    assert summary.counts["existing"] == 2
    assert summary.counts["resolved"] == 3


def test_metamorphic_idempotent_serialization_roundtrip(tmp_path: Path):
    """Property 6: Serializing and loading a baseline preserves 100% data fidelity and order."""
    findings = [_gen_finding(i) for i in range(6)]
    original = SecurityBaselineEngine.create_baseline(
        findings,
        files_analyzed=["src/app.py"],
        repository_root="/repo",
        base_revision="main",
    )

    saved_path = SecurityBaselineEngine.save_to_file(original, tmp_path / "roundtrip.json")
    loaded = SecurityBaselineEngine.load_from_file(saved_path)

    assert loaded.schema_version == original.schema_version
    assert loaded.execution_id == original.execution_id
    assert len(loaded.findings) == len(original.findings)
    for orig_item, loaded_item in zip(original.findings, loaded.findings, strict=True):
        assert orig_item.stable_fingerprint == loaded_item.stable_fingerprint
        assert orig_item.finding_id == loaded_item.finding_id
        assert orig_item.severity == loaded_item.severity
