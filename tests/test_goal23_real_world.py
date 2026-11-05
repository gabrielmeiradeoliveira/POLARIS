"""Independent integrity and offline reproducibility checks for GOAL 23."""

from __future__ import annotations

import ast
import builtins
import difflib
import json
from pathlib import Path

import pytest

from polaris.core.models import FindingCategory, LineRange, Severity
from polaris.evaluation.models import EvaluationFixture, ExpectedFindingSpec
from polaris.evaluation.runner import evaluate_corpus
from polaris.providers.fake import FakeProvider

_PATH = Path(__file__).parents[1] / "evaluations" / "fixtures" / "goal23_real_world" / "cases.json"


def _cases() -> list[dict[str, object]]:
    data = json.loads(_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    return data


def _run(source: str) -> dict[str, object]:
    scope: dict[str, object] = {"__builtins__": dict(vars(builtins))}
    exec(compile(source, "<goal23-local-fixture>", "exec"), scope)  # noqa: S102 -- only static local corpus code is executed.
    return scope


def _expected(value: str) -> object:
    raw = value.removeprefix("returns:")
    try:
        return ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return raw


def _assert_oracle(case: dict[str, object], phase: str) -> None:
    oracle = dict(case["oracle"])
    fn = _run(str(case[phase]))[str(oracle["function"])]
    assert callable(fn)
    oracle_type = oracle.get("type", "returns")
    if oracle_type == "idempotency":
        seen: set[str] = set()
        assert fn(seen, "payment-1", 50) == 50
        expected_retry = 50 if case["kind"] == "positive" and phase == "after" else 0
        assert fn(seen, "payment-1", 50) == expected_retry
        return
    if oracle_type == "cache_invalidation":
        cache = {"name": "old"}
        assert fn(cache, "name", "new") == "new"
        expected_absent = case["kind"] == "negative" or phase == "before"
        assert ("name" not in cache) is expected_absent
        return
    if oracle_type == "default_leak":
        assert fn("first") == ["first"]
        second = fn("second")
        leak = case["kind"] == "positive" and phase == "after"
        assert (second == ["first", "second"]) is leak
        return
    if oracle_type == "close_called":
        class Session:
            closed = False

            def close(self) -> None:
                self.closed = True

        session = Session()
        assert fn(session) == "ok"
        expected_closed = case["kind"] == "negative" or phase == "before"
        assert session.closed is expected_closed
        return
    args = list(oracle["args"])
    expected = str(oracle[phase])
    if expected.startswith("raises:"):
        with pytest.raises(getattr(builtins, expected.removeprefix("raises:"))):
            fn(*args)
    else:
        assert fn(*args) == _expected(expected)


def test_goal23_corpus_integrity_and_distribution() -> None:
    cases = _cases()
    assert len(cases) == 40
    assert len({case["id"] for case in cases}) == 40
    assert sum(case["kind"] == "positive" for case in cases) == 20
    assert sum(case["kind"] == "negative" for case in cases) == 20
    domains = {case["domain"] for case in cases}
    assert {"api_validation", "business_rules", "persistence", "authorization", "error_handling", "cache", "concurrency_state", "async_processing", "module_contract", "serialization", "api_pagination", "resource_cleanup"} <= domains
    assert sum(bool(case.get("related_before")) for case in cases) >= 4
    for case in cases:
        assert isinstance(case["impact"], str) and isinstance(case["repro"], str)
        assert int(case["line"]) >= 1
        assert "candidate_findings" not in case
        compile(str(case["before"]), f"{case['id']}:before", "exec")
        compile(str(case["after"]), f"{case['id']}:after", "exec")
        for related in (case.get("related_before", {}), case.get("related_after", {})):
            assert isinstance(related, dict)
            for name, code in related.items():
                assert isinstance(name, str) and isinstance(code, str)
                compile(code, f"{case['id']}:{name}", "exec")


def test_goal23_oracles_show_regression_or_contract_preservation() -> None:
    for case in _cases():
        _assert_oracle(case, "before")
        _assert_oracle(case, "after")


def _fixture(case: dict[str, object]) -> EvaluationFixture:
    path = str(case["path"])
    before = str(case["before"]).splitlines(keepends=True)
    after = str(case["after"]).splitlines(keepends=True)
    diff = f"diff --git a/{path} b/{path}\n" + "".join(difflib.unified_diff(before, after, fromfile=f"a/{path}", tofile=f"b/{path}"))
    expected = []
    if case["kind"] == "positive":
        expected = [ExpectedFindingSpec(file_path=path, line_range=LineRange(start_line=int(case["line"]), end_line=int(case["line"])), category=FindingCategory(str(case["category"])), severity=Severity(str(case["severity"])))]
    return EvaluationFixture(case_id=str(case["id"]), description=str(case["impact"]), diff_text=diff, file_contents={path: str(case["after"])}, expected_findings=expected, is_clean=case["kind"] == "negative", provenance="documented_verified")


def test_goal23_offline_public_interface_is_reproducible() -> None:
    fixtures = [_fixture(case) for case in _cases()]
    one = evaluate_corpus(fixtures, provider=FakeProvider(), force_end_to_end=True, behavioral_delta_enabled=False)
    two = evaluate_corpus(fixtures, provider=FakeProvider(), force_end_to_end=True, behavioral_delta_enabled=False)
    assert one.dataset_size == two.dataset_size == 40
    assert one.positive_cases == two.positive_cases == 20
    assert one.negative_cases == two.negative_cases == 20
    assert (one.true_positives, one.false_positives, one.false_negatives) == (two.true_positives, two.false_positives, two.false_negatives)
    assert one.usage.is_estimated and two.usage.is_estimated
