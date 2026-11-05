"""Provider-independent regression coverage for Goal 22 deterministic rules."""

from __future__ import annotations

import difflib
import json
from pathlib import Path

from polaris.git.analyzer import parse_unified_diff
from polaris.git.models import ContextSnippet, FileContext
from polaris.modules.deterministic_rules import deterministic_candidates

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


def test_redirect_host_stripping_requires_removed_host_set_and_pop() -> None:
    before = """def redirect(headers):
    new_headers = headers.copy()
    headers_to_remove = {\"authorization\", 'host'}
    for header in headers:
        if header.lower() in headers_to_remove:
            new_headers.pop(header, None)
    return new_headers
"""
    multiline_before = before.replace(
        "headers_to_remove = {\"authorization\", 'host'}",
        "headers_to_remove = (\n        {\"Host\", \"authorization\"}\n    )",
    )
    after = """def redirect(headers):
    new_headers = headers.copy()
    for header in headers:
        if header.lower() in {\"authorization\"}:
            new_headers.pop(header, None)
    return new_headers
"""
    for source in (before, multiline_before):
        titles = _candidates({"file_path": "redirect.py", "before": source, "after": after})
        assert any("DET-REDIRECT-HOST-STRIPPING-REMOVED" in title for title in titles)

    retained = before.replace("headers_to_remove = {\"authorization\", 'host'}", "headers_to_remove = {\"host\"}")
    no_host = before.replace("{\"authorization\", 'host'}", "{\"authorization\"}")
    non_set_host = before.replace("{\"authorization\", 'host'}", "make_policy(\"host\")")
    no_pop = after.replace("new_headers.pop(header, None)", "continue")
    assert _candidates({"file_path": "redirect.py", "before": retained, "after": retained}) == []
    assert _candidates({"file_path": "redirect.py", "before": no_host, "after": after}) == []
    assert _candidates({"file_path": "redirect.py", "before": non_set_host, "after": after}) == []
    no_pop_titles = _candidates({"file_path": "redirect.py", "before": before, "after": no_pop})
    assert not any("DET-REDIRECT-HOST-STRIPPING-REMOVED" in title for title in no_pop_titles)


def test_validation_after_resource_acquisition_requires_proven_local_linear_lifecycle() -> None:
    before = """def check(value):
    if not isinstance(value, int):
        raise ValueError("invalid")
    return value

def process(value):
    checked = check(value)
    try:
        resource = open_resource()
        return use(resource, checked)
    finally:
        resource.close()
"""
    after = """def check(value):
    if not isinstance(value, int):
        raise ValueError("invalid")
    return value

def process(value):
    try:
        resource = open_resource()
        checked = check(value)
        return use(resource, checked)
    finally:
        resource.close()
"""
    titles = _candidates({"file_path": "lifecycle.py", "before": before, "after": after})
    assert any("DET-VALIDATION-AFTER-RESOURCE-ACQUISITION" in title for title in titles)

    reordered_safely = after.replace("resource = open_resource()\n        checked = check(value)", "checked = check(value)\n        resource = open_resource()")
    external_validator = after.replace("def check(value):", "def _check(value):").replace("check(value)", "validate(value)")
    handled = after.replace("    finally:", "    except ValueError:\n        return None\n    finally:")
    no_cleanup = after.replace("        resource.close()\n", "")
    duplicated_validation = after.replace("    try:\n", "    checked = check(value)\n    try:\n")
    for source in (reordered_safely, external_validator, handled, no_cleanup, duplicated_validation):
        case_titles = _candidates({"file_path": "lifecycle.py", "before": before, "after": source})
        assert not any("DET-VALIDATION-AFTER-RESOURCE-ACQUISITION" in title for title in case_titles)
