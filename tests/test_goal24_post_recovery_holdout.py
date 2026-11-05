"""Causal validity and frozen execution checks for the post-recovery holdout."""

import builtins

from evaluations.fixtures.goal24_holdout.catalog import CASES, HoldoutScenario
from evaluations.goal24_holdout_runner import fixture_for, holdout_sha256, run_holdout


def _subject(source: str):
    scope = {"__builtins__": dict(vars(builtins))}
    exec(compile(source, "<goal24-holdout>", "exec"), scope)  # noqa: S102 -- static local benchmark corpus.
    return scope["subject"]


def _oracle_holds(case: HoldoutScenario, source: str) -> bool:
    subject = _subject(source)
    if case.oracle == "negative_quota":
        try:
            subject(-1)
        except ValueError:
            return True
        return False
    elif case.oracle == "account_filter":
        return subject([{"account": "a"}, {"account": "b"}], "a") == [{"account": "a"}]
    elif case.oracle == "replay":
        processed: set[str] = set()
        return subject(processed, "evt") == "applied" and subject(processed, "evt") == "ignored"
    elif case.oracle == "close":
        class Lease:
            closed = False

            def close(self) -> None:
                self.closed = True

        lease = Lease()
        return subject(lease) == "done" and lease.closed
    elif case.oracle == "page":
        return subject([1, 2, 3], 2) == [1, 2]
    elif case.oracle == "discount":
        return subject(100, True) == 80.0
    raise AssertionError(f"Unknown oracle {case.oracle}")


def test_post_recovery_holdout_is_balanced_direction_labeled_and_causal() -> None:
    assert len(CASES) == 12
    assert sum(case.kind == "positive" for case in CASES) == 6
    assert sum(case.kind == "negative" for case in CASES) == 6
    for case in CASES:
        assert _oracle_holds(case, case.before)
        if case.kind == "negative":
            assert _oracle_holds(case, case.after)
        else:
            assert not _oracle_holds(case, case.after)


def test_post_recovery_holdout_runs_end_to_end_with_frozen_digest() -> None:
    result = run_holdout()

    assert len(result.sha256) == 64
    assert result.sha256 == holdout_sha256()
    assert result.summary.dataset_size == 12
    assert result.summary.positive_cases == 6
    assert result.summary.negative_cases == 6
    assert result.summary.true_positives == 6
    assert result.summary.false_positives == 0
    assert result.summary.false_negatives == 0
    assert all(fixture_for(case).change_type is not None for case in CASES)
