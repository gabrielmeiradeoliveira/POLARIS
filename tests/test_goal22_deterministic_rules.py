"""Provider-independent regression coverage for Goal 22 deterministic rules."""

from __future__ import annotations

import difflib
import json
from pathlib import Path

from deicide.git.analyzer import parse_unified_diff
from deicide.git.models import ContextSnippet, FileContext
from deicide.modules.deterministic_rules import deterministic_candidates

_CORPUS = Path(__file__).parents[1] / "evaluations" / "fixtures" / "goal21_adversarial" / "scenarios.json"


def _candidates(case: dict[str, object]) -> list[str]:
    path = str(case["file_path"])
    patch = "".join(
        difflib.unified_diff(
            str(case["before"]).splitlines(keepends=True),
            str(case["after"]).splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )
    files = parse_unified_diff(f"diff --git a/{path} b/{path}\n{patch}")
    after = str(case["after"]).splitlines()
    context = FileContext(
        file_path=path,
        total_lines=len(after),
        snippets=[ContextSnippet(start_line=1, end_line=len(after), lines=dict(enumerate(after, start=1)))],
    )
    return [candidate.title for candidate in deterministic_candidates(files, {path: context})]


def test_goal22_security_concurrency_and_state_rules_are_provider_independent() -> None:
    cases = {str(case["id"]): case for case in json.loads(_CORPUS.read_text(encoding="utf-8"))}
    expected = {
        "pos_auth_bypass": "DET-AUTH-GUARD-REMOVED",
        "pos_sql_interpolation": "DET-SQL-INTERPOLATION",
        "pos_path_traversal": "DET-PATH-CONTAINMENT-REMOVED",
        "pos_sensitive_logging": "DET-SENSITIVE-OUTPUT",
        "pos_race_lost_update": "DET-STALE-VERSION-GUARD-REMOVED",
        "pos_deadlock_order": "DET-LOCK-ORDER-REMOVED",
        "pos_masked_exception": "DET-BROAD-EXCEPT-DEFAULT",
        "pos_mutates_input": "DET-INPUT-MUTATION",
    }
    for case_id, rule_id in expected.items():
        assert any(rule_id in title for title in _candidates(cases[case_id]))


def test_goal22_clean_counterparts_do_not_trigger_deterministic_rules() -> None:
    cases = json.loads(_CORPUS.read_text(encoding="utf-8"))
    for case in cases:
        if case["kind"] == "negative":
            assert _candidates(case) == []
