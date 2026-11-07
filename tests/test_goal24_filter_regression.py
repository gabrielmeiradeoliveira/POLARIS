"""Regression coverage for generic collection-visibility filter removal."""

from __future__ import annotations

import difflib

from polaris.git.analyzer import parse_unified_diff
from polaris.git.models import ContextSnippet, FileContext
from polaris.modules.deterministic_rules import deterministic_candidates


def test_removed_collection_filter_is_detected_but_equivalent_filter_is_not() -> None:
    path = "repo.py"
    before = "def rows(items, tenant):\n    return [item for item in items if item['tenant'] == tenant]\n"
    after = "def rows(items, tenant):\n    return list(items)\n"
    patch = "".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile=f"a/{path}", tofile=f"b/{path}"))
    diff = parse_unified_diff(f"diff --git a/{path} b/{path}\n{patch}")[0]
    context = FileContext(file_path=path, total_lines=2, snippets=[ContextSnippet(start_line=1, end_line=2, lines={1: "def rows(items, tenant):", 2: "    return list(items)"})])
    titles = [candidate.title for candidate in deterministic_candidates([diff], {path: context})]
    assert any("DET-COLLECTION-FILTER-REMOVED" in title for title in titles)


def test_role_allowlist_widening_is_reported_without_flagging_a_guard_refactor() -> None:
    path = "roles.py"
    before = "def export(role):\n    if role != 'admin': raise PermissionError()\n    return 'export'\n"
    widened_after = "def export(role):\n    if role not in ('admin', 'viewer'): raise PermissionError()\n    return 'export'\n"
    refactor_after = "def export(role):\n    if role == 'admin': return 'export'\n    raise PermissionError()\n"

    def titles_for(after: str) -> list[str]:
        patch = "".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile=f"a/{path}", tofile=f"b/{path}"))
        diff = parse_unified_diff(f"diff --git a/{path} b/{path}\n{patch}")[0]
        lines = after.splitlines()
        context = FileContext(file_path=path, total_lines=len(lines), snippets=[ContextSnippet(start_line=1, end_line=len(lines), lines=dict(enumerate(lines, start=1)))])
        return [candidate.title for candidate in deterministic_candidates([diff], {path: context})]

    assert any("DET-ROLE-ALLOWLIST-WIDENED" in title for title in titles_for(widened_after))
    assert not any("DET-AUTH-GUARD-REMOVED" in title for title in titles_for(refactor_after))


def test_removed_idempotency_and_cache_guards_are_detected() -> None:
    cases = [
        (
            "payments.py",
            "def charge(seen, key, amount):\n    if key in seen: return 0\n    seen.add(key); return amount\n",
            "def charge(seen, key, amount):\n    seen.add(key); return amount\n",
            "DET-IDEMPOTENCY-GUARD-REMOVED",
        ),
        (
            "cache.py",
            "def update(cache, key, value):\n    cache.pop(key, None)\n    return value\n",
            "def update(cache, key, value):\n    return value\n",
            "DET-CACHE-EVICTION-REMOVED",
        ),
        (
            "session.py",
            "def finish(session):\n    session.close(); return 'ok'\n",
            "def finish(session):\n    return 'ok'\n",
            "DET-CALLER-RESOURCE-CLOSE-REMOVED",
        ),
    ]
    for path, before, after, rule_id in cases:
        patch = "".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile=f"a/{path}", tofile=f"b/{path}"))
        diff = parse_unified_diff(f"diff --git a/{path} b/{path}\n{patch}")[0]
        lines = after.splitlines()
        context = FileContext(file_path=path, total_lines=len(lines), snippets=[ContextSnippet(start_line=1, end_line=len(lines), lines=dict(enumerate(lines, start=1)))])
        titles = [candidate.title for candidate in deterministic_candidates([diff], {path: context})]
        assert any(rule_id in title for title in titles)


def test_removed_validation_guard_is_detected_but_a_replacement_guard_is_not() -> None:
    path = "api.py"
    before = "def create_age(age):\n    if age < 0: raise ValueError('age')\n    return {'age': age}\n"
    removed_after = "def create_age(age):\n    return {'age': age}\n"
    replacement_after = "def create_age(age):\n    if age <= -1: raise ValueError('age')\n    return {'age': age}\n"

    def titles_for(after: str) -> list[str]:
        patch = "".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile=f"a/{path}", tofile=f"b/{path}"))
        diff = parse_unified_diff(f"diff --git a/{path} b/{path}\n{patch}")[0]
        lines = after.splitlines()
        context = FileContext(file_path=path, total_lines=len(lines), snippets=[ContextSnippet(start_line=1, end_line=len(lines), lines=dict(enumerate(lines, start=1)))])
        return [candidate.title for candidate in deterministic_candidates([diff], {path: context})]

    assert any("DET-VALIDATION-GUARD-REMOVED" in title for title in titles_for(removed_after))
    assert not any("DET-VALIDATION-GUARD-REMOVED" in title for title in titles_for(replacement_after))


def test_removed_validation_guard_through_a_local_helper_alias_is_detected() -> None:
    path = "service.py"
    before = (
        "def normalize(value):\n    return int(value)\n\n"
        "def create(value):\n    normalized = normalize(value)\n"
        "    if normalized < 0: raise ValueError('invalid')\n    return normalized\n"
    )
    after = (
        "def normalize(value):\n    return int(value)\n\n"
        "def create(value):\n    normalized = normalize(value)\n    return normalized\n"
    )
    patch = "".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile=f"a/{path}", tofile=f"b/{path}"))
    diff = parse_unified_diff(f"diff --git a/{path} b/{path}\n{patch}")[0]
    lines = after.splitlines()
    context = FileContext(file_path=path, total_lines=len(lines), snippets=[ContextSnippet(start_line=1, end_line=len(lines), lines=dict(enumerate(lines, start=1)))])
    titles = [candidate.title for candidate in deterministic_candidates([diff], {path: context})]

    assert any("DET-VALIDATION-GUARD-REMOVED" in title for title in titles)


def test_slice_bound_retry_bound_and_mapping_schema_regressions_are_detected() -> None:
    cases = [
        (
            "feed.py",
            "def page(items, limit):\n    return items[:min(limit, 100)]\n",
            "def page(items, limit):\n    return items[:limit + 1]\n",
            "DET-SLICE-LIMIT-WIDENED",
        ),
        (
            "retry.py",
            "def retry(attempt):\n    return attempt < 3\n",
            "def retry(attempt):\n    return attempt <= 3\n",
            "DET-STRICT-BOUND-MADE-INCLUSIVE",
        ),
        (
            "schema.py",
            "def dump(event):\n    return {'id': event['id'], 'version': event['version']}\n",
            "def dump(event):\n    return {'id': event['id']}\n",
            "DET-SERIALIZED-FIELD-REMOVED",
        ),
    ]
    for path, before, after, rule_id in cases:
        patch = "".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile=f"a/{path}", tofile=f"b/{path}"))
        diff = parse_unified_diff(f"diff --git a/{path} b/{path}\n{patch}")[0]
        lines = after.splitlines()
        context = FileContext(file_path=path, total_lines=len(lines), snippets=[ContextSnippet(start_line=1, end_line=len(lines), lines=dict(enumerate(lines, start=1)))])
        titles = [candidate.title for candidate in deterministic_candidates([diff], {path: context})]
        assert any(rule_id in title for title in titles)


def test_conditional_parameter_polarity_inversion_is_detected_without_equivalence_false_positives() -> None:
    path = "pricing.py"
    before = "def discount(amount, eligible):\n    return amount * 0.8 if eligible else amount\n"

    def titles_for(after: str) -> list[str]:
        patch = "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile=f"a/{path}", tofile=f"b/{path}"
            )
        )
        diff = parse_unified_diff(f"diff --git a/{path} b/{path}\n{patch}")[0]
        lines = after.splitlines()
        context = FileContext(
            file_path=path,
            total_lines=len(lines),
            snippets=[ContextSnippet(start_line=1, end_line=len(lines), lines=dict(enumerate(lines, start=1)))],
        )
        return [candidate.title for candidate in deterministic_candidates([diff], {path: context})]

    inverted = "def discount(amount, eligible):\n    return amount * 0.8 if not eligible else amount\n"
    changed_branch = "def discount(amount, eligible):\n    return amount * 0.7 if not eligible else amount\n"
    non_parameter_predicate = "def discount(amount, eligible):\n    return amount * 0.8 if not customer.eligible else amount\n"
    double_negation = "def discount(amount, eligible):\n    return amount * 0.8 if not not eligible else amount\n"

    assert any("DET-CONDITIONAL-POLARITY-INVERTED" in title for title in titles_for(inverted))
    assert not any("DET-CONDITIONAL-POLARITY-INVERTED" in title for title in titles_for(changed_branch))
    assert not any("DET-CONDITIONAL-POLARITY-INVERTED" in title for title in titles_for(non_parameter_predicate))
    assert not any("DET-CONDITIONAL-POLARITY-INVERTED" in title for title in titles_for(double_negation))


def test_idempotency_guard_removal_distinguishes_a_multiline_refactor() -> None:
    path = "payments.py"
    before = "def charge(seen, key):\n    if key in seen: return 'duplicate'\n    seen.add(key)\n    return 'charged'\n"

    def titles_for(after: str) -> list[str]:
        patch = "".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile=f"a/{path}", tofile=f"b/{path}"))
        diff = parse_unified_diff(f"diff --git a/{path} b/{path}\n{patch}")[0]
        lines = after.splitlines()
        context = FileContext(file_path=path, total_lines=len(lines), snippets=[ContextSnippet(start_line=1, end_line=len(lines), lines=dict(enumerate(lines, start=1)))])
        return [candidate.title for candidate in deterministic_candidates([diff], {path: context})]

    removed_guard = "def charge(seen, key):\n    seen.add(key)\n    return 'charged'\n"
    multiline_refactor = "def charge(seen, key):\n    if key in seen:\n        return 'duplicate'\n    seen.add(key)\n    return 'charged'\n"

    assert any("DET-IDEMPOTENCY-GUARD-REMOVED" in title for title in titles_for(removed_guard))
    assert not any("DET-IDEMPOTENCY-GUARD-REMOVED" in title for title in titles_for(multiline_refactor))


def test_typed_exception_fallback_is_detected_without_broad_or_propagating_false_positives() -> None:
    path = "importer.py"
    before = "def parse(value):\n    try:\n        return int(value)\n    except ValueError:\n        raise\n"

    def titles_for(after: str) -> list[str]:
        patch = "".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile=f"a/{path}", tofile=f"b/{path}"))
        diff = parse_unified_diff(f"diff --git a/{path} b/{path}\n{patch}")[0]
        lines = after.splitlines()
        context = FileContext(file_path=path, total_lines=len(lines), snippets=[ContextSnippet(start_line=1, end_line=len(lines), lines=dict(enumerate(lines, start=1)))])
        return [candidate.title for candidate in deterministic_candidates([diff], {path: context})]

    swallowed = "def parse(value):\n    try:\n        return int(value)\n    except ValueError:\n        return 0\n"
    chained = "def parse(value):\n    try:\n        return int(value)\n    except ValueError as exc:\n        raise ValueError('invalid') from exc\n"
    broad = "def parse(value):\n    try:\n        return int(value)\n    except Exception:\n        return 0\n"

    assert any("DET-TYPED-EXCEPTION-SWALLOWED" in title for title in titles_for(swallowed))
    assert not any("DET-TYPED-EXCEPTION-SWALLOWED" in title for title in titles_for(chained))
    assert not any("DET-TYPED-EXCEPTION-SWALLOWED" in title for title in titles_for(broad))
