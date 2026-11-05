"""Integrity checks for the frozen post-slice causal holdout."""

import builtins

from evaluations.fixtures.goal24_post_slice_holdout.catalog import CASES, PostSliceScenario
from evaluations.goal24_post_slice_holdout_runner import corpus_sha256, fixture_for, run_post_slice_holdout

from polaris.evaluation.models import ChangeType


def _entrypoint(files: dict[str, str], name: str):
    scope = {"__builtins__": dict(vars(builtins))}
    for source in files.values():
        exec(compile(source, "<goal24-post-slice>", "exec"), scope)  # noqa: S102 -- local static corpus.
    return scope[name]


def _oracle_holds(case: PostSliceScenario, files: dict[str, str]) -> bool:
    subject = _entrypoint(files, case.entrypoint)
    if case.oracle == "page_bound":
        return subject([1, 2, 3], 2) == [1, 2]
    if case.oracle == "authorization":
        try:
            subject("viewer")
        except PermissionError:
            return True
        return False
    if case.oracle == "replay":
        seen: set[str] = set()
        return subject(seen, "payment") == "charged" and subject(seen, "payment") == "duplicate"
    if case.oracle == "required_id":
        try:
            subject({})
        except KeyError:
            return True
        return False
    if case.oracle == "cache":
        cache = {"derived:order": "old"}
        subject(cache, "order", "new")
        return "derived:order" not in cache
    if case.oracle == "lock_order":
        return subject("z", "a") == ("a", "z")
    if case.oracle == "numeric_contract":
        return subject("4") == 4 and isinstance(subject("4"), int)
    if case.oracle == "exception":
        try:
            subject("not-a-number")
        except ValueError:
            return True
        return False
    if case.oracle == "tenant_flow":
        return subject([{"tenant": "a"}, {"tenant": "b"}], "a") == [{"tenant": "a"}]
    raise AssertionError(f"Unknown oracle {case.oracle}")


def test_post_slice_holdout_is_balanced_direction_labeled_and_causal() -> None:
    assert len(CASES) == 18
    assert sum(case.kind == "positive" for case in CASES) == 9
    assert sum(case.kind == "negative" for case in CASES) == 9
    assert sum(len(case.after_files) > 1 for case in CASES) >= 4
    for case in CASES:
        assert _oracle_holds(case, case.before_files)
        assert _oracle_holds(case, case.after_files) is (case.kind == "negative")


def test_post_slice_holdout_has_explicit_direction_and_frozen_digest() -> None:
    result = run_post_slice_holdout()

    assert result.sha256 == corpus_sha256()
    assert len(result.sha256) == 64
    assert result.summary.dataset_size == 18
    assert result.summary.positive_cases == 9
    assert result.summary.negative_cases == 9
    assert all(
        fixture_for(case).change_type
        == (ChangeType.DEFECT_INTRODUCTION if case.kind == "positive" else ChangeType.CLEAN_UNRELATED)
        for case in CASES
    )
