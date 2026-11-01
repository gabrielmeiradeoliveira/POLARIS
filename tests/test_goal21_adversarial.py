"""Integrity, oracle, and offline-evaluation checks for the GOAL 21 corpus."""

from __future__ import annotations

import ast
import builtins
import difflib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from deicide.core.models import FindingCategory, LineRange, Severity
from deicide.evaluation.models import EvaluationFixture, ExpectedFindingSpec
from deicide.evaluation.runner import evaluate_corpus
from deicide.providers.fake import FakeProvider

_CORPUS_PATH = Path(__file__).parents[1] / "evaluations" / "fixtures" / "goal21_adversarial" / "scenarios.json"


def _cases() -> list[dict[str, object]]:
    data = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    return data


def _namespace(source: str, fake_open: object | None = None) -> dict[str, object]:
    namespace: dict[str, object] = {"__builtins__": dict(vars(builtins))}
    if fake_open is not None:
        namespace["__builtins__"]["open"] = fake_open  # type: ignore[index]
    exec(compile(source, "<goal21>", "exec"), namespace)  # noqa: S102 -- corpus is local, static fixture data.
    return namespace


def _value(text: str) -> object:
    raw = text.removeprefix("returns:")
    try:
        return ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return raw


def _assert_outcome(namespace: dict[str, object], oracle: dict[str, object], phase: str, tmp_path: Path) -> None:
    oracle_type = oracle["type"]
    function = namespace.get(str(oracle.get("function", "")))
    if oracle_type == "manual":
        return
    assert callable(function)
    if oracle_type == "path_escape":
        root = tmp_path / phase / "root"
        root.mkdir(parents=True, exist_ok=True)
        if phase == "before" and "pos_" in str(oracle.get("case_id", "")):
            with pytest.raises(ValueError):
                function(root, "../outside.txt")
        elif phase == "before" or (phase == "after" and "pos_" in str(oracle.get("case_id", ""))):
            assert root.resolve() not in function(root, "../outside.txt").parents
        else:
            with pytest.raises(ValueError):
                function(root, "../outside.txt")
        return
    if oracle_type == "sql_shape":
        result = function("' OR 1=1 --")
        if phase == "after" and "pos_" in str(oracle.get("case_id", "")):
            assert isinstance(result, str)
        else:
            assert isinstance(result, tuple) and result[1] == ("' OR 1=1 --",)
        return
    if oracle_type == "stale_snapshot":
        if phase == "before":
            with pytest.raises(RuntimeError, match="stale"):
                function(100, 80, 1, 2)
        else:
            assert function(100, 80, 1, 2) == 20
        return
    if oracle_type == "mutation":
        values = [2, 1]
        assert function(values) == [1, 2]
        expect_mutation = phase == "after" and "pos_" in str(oracle.get("case_id", ""))
        assert (values == [1, 2]) is expect_mutation
        return
    if oracle_type == "default_leak":
        assert function("first") == ["first"]
        second = function("second")
        expect_leak = phase == "after" and "pos_" in str(oracle.get("case_id", ""))
        assert (second == ["first", "second"]) is expect_leak
        return
    args = list(oracle.get("args", []))
    if "__TEMPFILE__" in args:
        path = tmp_path / f"{phase}.txt"
        path.write_text("payload", encoding="utf-8")
        args[args.index("__TEMPFILE__")] = str(path)
    expected = str(oracle[phase])
    if expected.startswith("raises:"):
        error_type = getattr(builtins, expected.removeprefix("raises:"))
        with pytest.raises(error_type):
            function(*args)
    elif oracle_type == "stdout":
        captured = io.StringIO()
        with redirect_stdout(captured):
            function(*args)
        marker = expected.split(":", 1)[1]
        assert (marker in captured.getvalue()) is expected.startswith("contains:")
    else:
        assert function(*args) == _value(expected)


def test_goal21_corpus_integrity_and_coverage() -> None:
    cases = _cases()
    assert len(cases) == 30
    assert len({case["id"] for case in cases}) == len(cases)
    assert {case["kind"] for case in cases} == {"positive", "negative"}
    assert sum(case["kind"] == "positive" for case in cases) == 15
    assert sum(case["kind"] == "negative" for case in cases) == 15
    covered = {case["category"] for case in cases}
    assert {"logic_error", "concurrency", "resource_management", "error_handling", "null_handling", "type_mismatch", "state_mutation", "boundary_condition"} <= covered
    for case in cases:
        assert isinstance(case["before"], str) and isinstance(case["after"], str)
        assert isinstance(case["behavior"], str) and case["behavior"]
        assert int(case["expected_line"]) >= 1
        compile(case["before"], f"{case['id']}:before", "exec")
        compile(case["after"], f"{case['id']}:after", "exec")
        for related in (case.get("related_before", {}), case.get("related_after", {})):
            assert isinstance(related, dict)
            for path, source in related.items():
                assert isinstance(path, str) and isinstance(source, str)
                compile(source, f"{case['id']}:{path}", "exec")


def test_goal21_executable_oracles_demonstrate_expected_semantics(tmp_path: Path) -> None:
    cases = _cases()
    executable = 0
    for case in cases:
        oracle = dict(case["oracle"])
        oracle["case_id"] = case["id"]
        if oracle["type"] == "manual":
            continue
        executable += 1
        if case["id"] in {"pos_unclosed_resource", "neg_context_manager"}:
            continue  # Covered by the dedicated resource-lifetime oracle below.
        _assert_outcome(_namespace(str(case["before"])), oracle, "before", tmp_path)
        _assert_outcome(_namespace(str(case["after"])), oracle, "after", tmp_path)
    assert executable == 29


def test_goal21_resource_oracles_observe_closure_without_real_io() -> None:
    class Handle:
        def __init__(self) -> None:
            self.closed = False

        def read(self) -> str:
            return "payload"

        def __enter__(self) -> Handle:
            return self

        def __exit__(self, *_: object) -> None:
            self.closed = True

    for case_id, expected_closed in [("pos_unclosed_resource", False), ("neg_context_manager", True)]:
        case = next(item for item in _cases() if item["id"] == case_id)
        handles: list[Handle] = []

        def fake_open(*_: object, bucket: list[Handle] = handles, **__: object) -> Handle:
            handle = Handle()
            bucket.append(handle)
            return handle

        namespace = _namespace(str(case["after"]), fake_open)
        assert namespace["read"]("ignored") == "payload"
        assert handles[0].closed is expected_closed


def _fixture(case: dict[str, object]) -> EvaluationFixture:
    path = str(case["file_path"])
    before = str(case["before"]).splitlines(keepends=True)
    after = str(case["after"]).splitlines(keepends=True)
    patch = "".join(difflib.unified_diff(before, after, fromfile=f"a/{path}", tofile=f"b/{path}"))
    diff = f"diff --git a/{path} b/{path}\n{patch}"
    expected = []
    if case["kind"] == "positive":
        expected = [ExpectedFindingSpec(file_path=path, line_range=LineRange(start_line=int(case["expected_line"]), end_line=int(case["expected_line"])), category=FindingCategory(str(case["category"])), severity=Severity(str(case["severity"])))]
    return EvaluationFixture(case_id=str(case["id"]), description=str(case["behavior"]), diff_text=diff, file_contents={path: str(case["after"])}, expected_findings=expected, is_clean=case["kind"] == "negative", provenance="documented_verified")


def test_goal21_offline_evaluation_is_reproducible_and_never_uses_network() -> None:
    fixtures = [_fixture(case) for case in _cases()]
    first = evaluate_corpus(fixtures, provider=FakeProvider(), force_end_to_end=True, behavioral_delta_enabled=False)
    second = evaluate_corpus(fixtures, provider=FakeProvider(), force_end_to_end=True, behavioral_delta_enabled=False)
    assert first.dataset_size == second.dataset_size == 30
    assert first.positive_cases == second.positive_cases == 15
    assert first.negative_cases == second.negative_cases == 15
    assert (first.true_positives, first.false_positives, first.false_negatives) == (second.true_positives, second.false_positives, second.false_negatives)
    assert first.usage.is_estimated and second.usage.is_estimated
