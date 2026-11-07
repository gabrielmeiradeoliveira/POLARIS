"""Bounded inter-file deterministic rule coverage."""

from __future__ import annotations

import difflib

from polaris.git.analyzer import parse_unified_diff
from polaris.git.models import ContextSnippet, FileContext
from polaris.modules.deterministic_rules import deterministic_candidates


def _titles(before: dict[str, str], after: dict[str, str]) -> list[str]:
    diff_text = ""
    for path in sorted(set(before) | set(after)):
        patch = "".join(
            difflib.unified_diff(
                before.get(path, "").splitlines(keepends=True),
                after.get(path, "").splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )
        if patch:
            diff_text += f"diff --git a/{path} b/{path}\n{patch}"
    diffs = parse_unified_diff(diff_text)
    contexts = {}
    for path, source in after.items():
        lines = source.splitlines()
        contexts[path] = FileContext(
            file_path=path,
            total_lines=len(lines),
            snippets=[ContextSnippet(start_line=1, end_line=len(lines), lines=dict(enumerate(lines, start=1)))],
        )
    return [finding.title for finding in deterministic_candidates(diffs, contexts)]


def test_cross_file_allowlist_widening_requires_changed_policy_and_caller() -> None:
    before = {
        "policy.py": "ALLOWED = {'admin'}\n",
        "routes.py": "def export(role):\n    if role not in ALLOWED: raise PermissionError()\n    return 'ok'\n",
    }
    after = {
        "policy.py": "ALLOWED = {'admin', 'viewer'}\n",
        "routes.py": "def export(role):\n    if role not in ALLOWED: raise PermissionError('export')\n    return 'ok'\n",
    }
    assert any("DET-CROSSFILE-ALLOWLIST-WIDENED" in title for title in _titles(before, after))


def test_cross_file_allowlist_requires_changed_caller_and_permission_guard() -> None:
    before = {
        "policy.py": "ALLOWED = {'admin'}\n",
        "routes.py": "def export(role):\n    if role not in ALLOWED: raise PermissionError()\n    return 'ok'\n",
    }
    unchanged_caller = {"policy.py": "ALLOWED = {'admin', 'viewer'}\n", "routes.py": before["routes.py"]}
    non_permission = {
        "policy.py": "ALLOWED = {'admin', 'viewer'}\n",
        "routes.py": "def export(role):\n    if role not in ALLOWED: return 'blocked'\n    return 'ok'\n",
    }
    assert not any("DET-CROSSFILE-ALLOWLIST-WIDENED" in title for title in _titles(before, unchanged_caller))
    assert not any("DET-CROSSFILE-ALLOWLIST-WIDENED" in title for title in _titles(before, non_permission))


def test_cross_file_filter_bypass_requires_unambiguous_raw_helper() -> None:
    before = {
        "query.py": "def query(rows, tenant):\n    return [row for row in rows if row['tenant'] == tenant]\n",
        "format.py": "def format_rows(rows):\n    return list(rows)\n",
    }
    after = {
        "query.py": "def query(rows, tenant):\n    return format_rows(rows)\n",
        "format.py": before["format.py"],
    }
    assert any("DET-CROSSFILE-COLLECTION-FILTER-BYPASSED" in title for title in _titles(before, after))

    ambiguous = {
        **after,
        "other.py": "def format_rows(rows):\n    return list(rows)\n",
    }
    assert not any("DET-CROSSFILE-COLLECTION-FILTER-BYPASSED" in title for title in _titles(before, ambiguous))


def test_cross_file_filter_equivalent_refactor_is_clean() -> None:
    before = {
        "query.py": "def query(rows, tenant):\n    return [row for row in rows if row['tenant'] == tenant]\n",
        "format.py": "def format_rows(rows):\n    return list(rows)\n",
    }
    after = {
        "query.py": "def query(rows, tenant):\n    return [row for row in rows if tenant == row['tenant']]\n",
        "format.py": before["format.py"],
    }
    assert not any("DET-CROSSFILE-COLLECTION-FILTER-BYPASSED" in title for title in _titles(before, after))
