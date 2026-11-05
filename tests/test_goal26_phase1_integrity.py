"""Frozen integrity controls for the GOAL 26 Phase 1 evaluation baseline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from polaris.evaluation.runner import load_fixtures_from_file
from polaris.git.analyzer import parse_unified_diff

MANIFEST_PATH = Path("evaluations/manifests/goal26-phase1-evaluation.json")
E2E_PATH = Path("evaluations/fixtures/end_to_end_context_benchmark.json")
VERIFIED_PATH = Path("evaluations/fixtures/real_world_verified_benchmark.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_goal26_manifest_freezes_corpora_hashes_runner_and_e2e_order() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 1
    assert manifest["runner"] == {
        "command": ".\\.venv\\Scripts\\python.exe -m polaris evaluate --provider fake --fixtures evaluations/fixtures/end_to_end_context_benchmark.json --end-to-end --format json",
        "provider": "fake",
        "mode": "end_to_end",
        "behavioral_delta_enabled": True,
        "external_network_authorized": False,
    }
    assert _sha256(E2E_PATH) == manifest["corpora"]["end_to_end_context"]["sha256"]
    assert _sha256(VERIFIED_PATH) == manifest["corpora"]["real_world_verified"]["sha256"]
    assert [fixture.case_id for fixture in load_fixtures_from_file(E2E_PATH)] == manifest["case_order"]


def test_e2e_expected_locations_are_exact_added_lines() -> None:
    for fixture in load_fixtures_from_file(E2E_PATH):
        diffs = {file_diff.new_path: file_diff for file_diff in parse_unified_diff(fixture.diff_text)}
        for expected in fixture.expected_findings:
            changed = diffs[expected.file_path].added_lines
            assert expected.line_range.start_line in changed
            assert expected.line_range.end_line in changed


def test_proxy_redirect_ground_truth_covers_the_changed_location_envelope() -> None:
    fixture = next(
        item
        for item in load_fixtures_from_file(VERIFIED_PATH)
        if item.case_id == "rw-urllib3-proxy-redirect-origin"
    )
    expected = fixture.expected_findings[0]
    changed = parse_unified_diff(fixture.diff_text)[0].added_lines

    assert (expected.line_range.start_line, expected.line_range.end_line) == (2, 5)
    assert {expected.line_range.start_line, expected.line_range.end_line} <= changed
