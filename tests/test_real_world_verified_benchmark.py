"""Integrity tests for the scored, provenance-backed real-world pilot corpus."""

from pathlib import Path

from polaris.core.models import CandidateFinding
from polaris.evaluation.models import GroundTruthVerificationStatus
from polaris.evaluation.runner import evaluate_case, evaluate_corpus, load_fixtures_from_file
from polaris.git.analyzer import parse_unified_diff
from polaris.git.models import DiffBundle, FileContext
from polaris.modules.code_review import CodeReviewModule
from polaris.providers.fake import FakeProvider


def test_real_world_port_zero_captured_candidate_survives_production_validation() -> None:
    """The reconstructed hunk must map the captured line-6 candidate to its changed source line."""
    fixtures = load_fixtures_from_file(Path("evaluations/fixtures/real_world_verified_benchmark.json"))
    fixture = next(fixture for fixture in fixtures if fixture.case_id == "rw-urllib3-port-zero")
    candidate = CandidateFinding(
        category="boundary_condition",
        severity="medium",
        confidence="high",
        file_path="src/urllib3/util/url.py",
        start_line=6,
        end_line=6,
        title="Explicit port 0 is omitted from the netloc",
        description="A truthiness check treats an explicit port 0 as absent.",
        evidence="if self.port:",
        suggested_remediation="Restore the explicit-None check.",
    )

    result = evaluate_case(
        fixture.model_copy(update={"candidate_findings": [candidate]}),
        FakeProvider(),
    )

    assert result.true_positives == 1
    assert result.legitimate_rejected == 0
    assert len(result.actual_findings) == 1
    assert result.diagnostics is not None
    assert result.diagnostics.rejected_candidates == []


def test_real_world_verified_corpus_contains_only_scored_documented_cases() -> None:
    fixtures = load_fixtures_from_file(Path("evaluations/fixtures/real_world_verified_benchmark.json"))
    assert len(fixtures) == 8
    assert len({fixture.case_id for fixture in fixtures}) == len(fixtures)
    assert len({fixture.repository for fixture in fixtures}) >= 2

    for fixture in fixtures:
        assert fixture.suitable_for_live_benchmark
        assert fixture.expected_findings
        assert fixture.commit_id and fixture.fix_commit_id
        assert fixture.verification_status in {
            GroundTruthVerificationStatus.EXECUTABLE_VERIFIED,
            GroundTruthVerificationStatus.DOCUMENTED_VERIFIED,
        }
        assert fixture.independent_evidence
        assert fixture.reproduction_instructions
        assert fixture.known_limitations
        parsed = parse_unified_diff(fixture.diff_text)
        assert parsed
        for expected in fixture.expected_findings:
            assert expected.file_path in fixture.file_contents
            assert expected.line_range.end_line <= len(fixture.file_contents[expected.file_path].splitlines())


def test_real_world_metadata_is_not_in_model_prompt() -> None:
    fixtures = load_fixtures_from_file(Path("evaluations/fixtures/real_world_verified_benchmark.json"))
    # Fixture provenance must remain evaluation metadata; CodeReviewModule serializes only diff/context.
    for fixture in fixtures:
        assert fixture.fix_commit_id not in fixture.diff_text
        assert all(evidence not in "\n".join(fixture.file_contents.values()) for evidence in fixture.independent_evidence)

    fixture = fixtures[0]
    diff_bundle = DiffBundle(
        repository_root="/fixture",
        base_revision="HEAD",
        target_description="fixture",
        files=parse_unified_diff(fixture.diff_text),
    )
    contexts = {
        path: FileContext(file_path=path, total_lines=len(source.splitlines()))
        for path, source in fixture.file_contents.items()
    }
    prompt = CodeReviewModule()._build_user_prompt(diff_bundle.reviewable_files, contexts)
    assert fixture.fix_commit_id not in prompt
    assert fixture.reproduction_instructions not in prompt
    assert all(evidence not in prompt for evidence in fixture.independent_evidence)


def test_real_world_corpus_materializes_with_production_parity() -> None:
    fixtures = load_fixtures_from_file(Path("evaluations/fixtures/real_world_verified_benchmark.json"))
    summary = evaluate_corpus(
        fixtures,
        FakeProvider(),
        force_end_to_end=True,
        production_parity=True,
        behavioral_delta_enabled=False,
        observability=True,
    )
    assert summary.successful_cases == 8
    assert summary.documented_verified_cases == 8
    assert summary.unverified_cases == 0
    for result in summary.case_results:
        assert result.observability is not None
        context = result.observability.context
        assert context is not None
        assert context.estimated_tokens <= context.max_allowed_tokens
