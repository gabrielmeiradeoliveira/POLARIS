"""Tests for DEICIDE MVP 1.4.2 Reproducible Behavioral Regression Benchmark.

Verifies:
1. Benchmark corpus integrity, schema conformity, and category coverage.
2. Ground-truth line range validity and diff hunk overlap.
3. Offline post-processing evaluation precision and recall.
4. Behavioral Delta flag compatibility (both enabled and disabled).
5. CLI evaluation command execution.
6. Executable Python reproduction tests for all 8 positive regression cases.
7. Executable Python verification tests for all 4 clean negative cases.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from deicide.cli import app
from deicide.core.errors import ExitCode
from deicide.core.models import FindingCategory
from deicide.evaluation.models import ChangeType, EvaluationSummary
from deicide.evaluation.runner import evaluate_corpus, load_fixtures_from_file
from deicide.git.analyzer import parse_unified_diff
from deicide.providers.fake import FakeProvider

BENCHMARK_PATH = Path("evaluations/fixtures/behavioral_regression_benchmark.json")
BASELINE_BENCHMARK_PATH = Path("evaluations/fixtures/bug_introduction_benchmark.json")


def test_behavioral_regression_benchmark_corpus_integrity() -> None:
    """Validate structure, composition, category coverage, and provenance of the 12-case benchmark."""
    assert BENCHMARK_PATH.exists(), f"Benchmark fixture file missing: {BENCHMARK_PATH}"
    fixtures = load_fixtures_from_file(BENCHMARK_PATH)

    assert len(fixtures) == 12, f"Expected 12 benchmark cases, found {len(fixtures)}"

    # Ensure all case IDs are unique within this suite and distinct from the 8 baseline cases
    case_ids = [f.case_id for f in fixtures]
    assert len(case_ids) == len(set(case_ids)), "Benchmark contains duplicate case IDs"

    if BASELINE_BENCHMARK_PATH.exists():
        baseline_fixtures = load_fixtures_from_file(BASELINE_BENCHMARK_PATH)
        baseline_ids = {bf.case_id for bf in baseline_fixtures}
        overlap = set(case_ids).intersection(baseline_ids)
        assert not overlap, f"New benchmark IDs must not collide with baseline IDs: {overlap}"

    positive_cases = [f for f in fixtures if not f.is_clean]
    negative_cases = [f for f in fixtures if f.is_clean]

    assert len(positive_cases) == 8, f"Expected 8 positive cases, got {len(positive_cases)}"
    assert len(negative_cases) == 4, f"Expected 4 negative cases, got {len(negative_cases)}"

    # Check common fields across all 12 cases
    for f in fixtures:
        assert f.case_id.strip()
        assert f.description.strip()
        assert f.diff_text.strip()
        assert f.file_contents
        assert f.fix_reference
        assert f.provenance == "synthetic_benchmark", f"Expected synthetic provenance for {f.case_id}"
        assert f.commit_id is None, "Synthetic benchmarks must not fabricate commit IDs"
        assert f.is_suitable_for_live_benchmark is True, f"Case {f.case_id} must be suitable for live benchmark"

    # Verify positive cases have exactly 1 expected finding and candidate findings
    for f in positive_cases:
        assert f.resolved_change_type == ChangeType.DEFECT_INTRODUCTION
        assert len(f.expected_findings) == 1, f"Expected 1 finding for {f.case_id}"
        assert len(f.candidate_findings) >= 1, f"Expected candidates for {f.case_id}"

    # Verify negative cases have 0 expected findings and clean change types
    for f in negative_cases:
        assert len(f.expected_findings) == 0, f"Clean case {f.case_id} must have no expected findings"
        assert len(f.candidate_findings) == 0, f"Clean case {f.case_id} must have no candidate findings"
        assert f.resolved_change_type in (ChangeType.CLEAN_BUG_FIX, ChangeType.CLEAN_UNRELATED)

    # Verify category coverage across positive cases
    categories = {f.expected_findings[0].category for f in positive_cases}
    assert FindingCategory.CORRECTNESS in categories
    assert FindingCategory.BOUNDARY_CONDITION in categories
    assert FindingCategory.STATE_MUTATION in categories
    assert FindingCategory.ERROR_HANDLING in categories
    assert FindingCategory.RESOURCE_MANAGEMENT in categories
    assert FindingCategory.LOGIC_ERROR in categories

    expected_by_case = {fixture.case_id: fixture.expected_findings[0] for fixture in positive_cases}
    assert FindingCategory.TYPE_MISMATCH in expected_by_case[
        "beh-regress-01-cross-file-return-contract"
    ].acceptable_categories
    assert FindingCategory.TYPE_MISMATCH in expected_by_case[
        "beh-regress-02-removed-parameter-default"
    ].acceptable_categories
    assert FindingCategory.LOGIC_ERROR in expected_by_case["beh-regress-08-lru-recency-logic-flaw"].acceptable_categories


def test_behavioral_regression_benchmark_ground_truth_consistency() -> None:
    """Verify ground-truth line ranges and file coordinates strictly overlap modified diff hunks."""
    fixtures = load_fixtures_from_file(BENCHMARK_PATH)

    for f in fixtures:
        parsed_files = parse_unified_diff(f.diff_text)
        assert parsed_files, f"Failed parsing unified diff in {f.case_id}"

        for expected in f.expected_findings:
            assert expected.file_path in f.file_contents, (
                f"{expected.file_path} missing in file_contents for {f.case_id}"
            )
            file_lines = len(f.file_contents[expected.file_path].splitlines())
            assert expected.line_range.start_line <= file_lines, (
                f"Start line {expected.line_range.start_line} exceeds file length {file_lines} in {f.case_id}"
            )
            assert expected.line_range.end_line <= file_lines, (
                f"End line {expected.line_range.end_line} exceeds file length {file_lines} in {f.case_id}"
            )

            diff_file = next(
                (d for d in parsed_files if d.new_path == expected.file_path or d.old_path == expected.file_path),
                None,
            )
            assert diff_file is not None, f"File {expected.file_path} not found in diff for {f.case_id}"
            assert diff_file.has_changed_overlap(expected.line_range), (
                f"Diff in {f.case_id} does not overlap expected range {expected.line_range}"
            )


def test_behavioral_regression_benchmark_post_processing_metrics() -> None:
    """Verify FindingIntelligenceEngine achieves 100% precision and recall on candidate findings."""
    fixtures = load_fixtures_from_file(BENCHMARK_PATH)
    provider = FakeProvider()

    summary: EvaluationSummary = evaluate_corpus(
        fixtures,
        provider=provider,
        use_baseline=False,
        force_end_to_end=False,
    )

    assert summary.dataset_size == 12
    assert summary.positive_cases == 8
    assert summary.negative_cases == 4
    assert summary.successful_cases == 12
    assert summary.failed_cases == 0
    assert summary.true_positives == 8
    assert summary.false_positives == 0
    assert summary.false_negatives == 0
    assert summary.precision == 1.0
    assert summary.recall == 1.0
    assert summary.false_positive_rate == 0.0


def test_behavioral_regression_benchmark_behavioral_delta_flag_compatibility() -> None:
    """Verify evaluation runs identically with both behavioral_delta enabled and disabled."""
    fixtures = load_fixtures_from_file(BENCHMARK_PATH)
    provider = FakeProvider()

    summary_on = evaluate_corpus(
        fixtures,
        provider=provider,
        use_baseline=False,
        force_end_to_end=False,
        behavioral_delta_enabled=True,
    )
    summary_off = evaluate_corpus(
        fixtures,
        provider=provider,
        use_baseline=False,
        force_end_to_end=False,
        behavioral_delta_enabled=False,
    )

    assert summary_on.true_positives == summary_off.true_positives == 8
    assert summary_on.false_positives == summary_off.false_positives == 0
    assert summary_on.false_negatives == summary_off.false_negatives == 0
    assert summary_on.successful_cases == summary_off.successful_cases == 12


def test_behavioral_regression_benchmark_cli_invocation() -> None:
    """Verify CLI evaluate command correctly loads and executes the benchmark offline."""
    runner = CliRunner()

    res_default = runner.invoke(
        app,
        ["evaluate", "--provider", "fake", "--fixtures", str(BENCHMARK_PATH)],
    )
    assert res_default.exit_code == int(ExitCode.SUCCESS)
    assert "Dataset Size        : 12 (positive=8, negative=4)" in res_default.stdout
    assert "TP=8, FP=0, FN=0" in res_default.stdout
    assert "Precision           : 100.00%" in res_default.stdout
    assert "Recall              : 100.00%" in res_default.stdout

    res_delta_on = runner.invoke(
        app,
        ["evaluate", "--provider", "fake", "--fixtures", str(BENCHMARK_PATH), "--behavioral-delta"],
    )
    assert res_delta_on.exit_code == int(ExitCode.SUCCESS)
    assert "TP=8, FP=0, FN=0" in res_delta_on.stdout

    res_delta_off = runner.invoke(
        app,
        ["evaluate", "--provider", "fake", "--fixtures", str(BENCHMARK_PATH), "--no-behavioral-delta"],
    )
    assert res_delta_off.exit_code == int(ExitCode.SUCCESS)
    assert "TP=8, FP=0, FN=0" in res_delta_off.stdout


# =========================================================================
# Phase 3: Independent Reproducibility Tests for Positive Cases
# =========================================================================


def test_reproduction_case_01_cross_file_return_contract() -> None:
    """Case 1: decode_auth_token return contract changed from dict to str breaking caller."""

    def decode_before(token: str) -> dict[str, str]:
        if not token.startswith("tok_"):
            raise ValueError("Invalid token prefix")
        parts = token.split(".")
        return {"sub": parts[1], "tenant_id": parts[2] if len(parts) > 2 else "default"}

    def decode_after(token: str) -> str:
        if not token.startswith("tok_"):
            raise ValueError("Invalid token prefix")
        parts = token.split(".")
        return parts[1]

    def authenticate_request(decode_fn: Any, headers: dict[str, str]) -> str:
        token = headers.get("Authorization", "")
        payload = decode_fn(token)
        return str(payload["sub"])

    headers = {"Authorization": "tok_header.alice.corp"}

    # Before: caller unpacks sub claim successfully
    assert authenticate_request(decode_before, headers) == "alice"

    # After: decode_fn returns string, causing TypeError on subscription
    with pytest.raises(TypeError, match="string indices must be integers"):
        authenticate_request(decode_after, headers)


def test_reproduction_case_02_removed_parameter_default() -> None:
    """Case 2: build_cache_key removed default version argument breaking existing caller."""

    def build_cache_key_before(namespace: str, item_id: str, version: int = 1) -> str:
        return f"{namespace}:v{version}:{item_id}"

    def build_cache_key_after(namespace: str, item_id: str, version: int) -> str:
        return f"{namespace}:v{version}:{item_id}"

    def get_user_cache_key(build_fn: Any, user_id: str) -> str:
        return str(build_fn("users", user_id))

    # Before: 1-argument call succeeds using default version=1
    assert get_user_cache_key(build_cache_key_before, "u100") == "users:v1:u100"

    # After: missing required positional argument raises TypeError
    with pytest.raises(TypeError, match="missing 1 required positional argument"):
        get_user_cache_key(build_cache_key_after, "u100")


def test_reproduction_case_03_incorrect_boundary_condition() -> None:
    """Case 3: compute_chunk_indices omits upper bound clamp causing last chunk overflow."""

    def compute_chunk_indices_before(total_length: int, chunk_size: int) -> list[tuple[int, int]]:
        if chunk_size <= 0 or total_length <= 0:
            return []
        chunks = []
        for start in range(0, total_length, chunk_size):
            end = min(start + chunk_size, total_length)
            chunks.append((start, end))
        return chunks

    def compute_chunk_indices_after(total_length: int, chunk_size: int) -> list[tuple[int, int]]:
        if chunk_size <= 0 or total_length <= 0:
            return []
        chunks = []
        for start in range(0, total_length, chunk_size):
            end = start + chunk_size
            chunks.append((start, end))
        return chunks

    # Before: length 10 with chunk 4 clamps final chunk to 10
    before_result = compute_chunk_indices_before(10, 4)
    assert before_result == [(0, 4), (4, 8), (8, 10)]
    assert before_result[-1][1] == 10

    # After: unclamped end index overshoots total_length
    after_result = compute_chunk_indices_after(10, 4)
    assert after_result == [(0, 4), (4, 8), (8, 12)]
    assert after_result[-1][1] == 12
    assert after_result[-1][1] > 10, "Final chunk end must not exceed total length"


def test_reproduction_case_04_shared_mutable_state() -> None:
    """Case 4: register_pipeline_step uses mutable default list contaminating calls."""

    def register_step_before(step_name: str, options: list[str] | None = None) -> list[str]:
        applied = list(options) if options is not None else []
        applied.append(f"step:{step_name}")
        return applied

    def register_step_after(step_name: str, options: list[str] = []) -> list[str]:  # noqa: B006 - Intentionally testing mutable default regression
        options.append(f"step:{step_name}")
        return options

    # Before: multiple calls with default argument remain isolated
    assert register_step_before("build") == ["step:build"]
    assert register_step_before("test") == ["step:test"]

    # After: first call mutates default list in-place, contaminating second call
    res1 = register_step_after("build")
    assert res1 == ["step:build"]
    res2 = register_step_after("test")
    assert res2 == ["step:build", "step:test"]
    assert "step:build" in res2, "Default list mutated across invocations"


def test_reproduction_case_05_exception_handling_regression() -> None:
    """Case 5: parse_json_payload removed UnicodeDecodeError handler causing unhandled crash."""

    def parse_payload_before(raw_bytes: bytes) -> dict[str, Any] | None:
        try:
            decoded = raw_bytes.decode("utf-8")
            return json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    def parse_payload_after(raw_bytes: bytes) -> dict[str, Any] | None:
        try:
            decoded = raw_bytes.decode("utf-8")
            return json.loads(decoded)
        except json.JSONDecodeError:
            return None

    valid_bytes = b'{"status": "ok"}'
    invalid_bytes = b"\xff\xfe\xfd"

    # Valid payload succeeds in both
    assert parse_payload_before(valid_bytes) == {"status": "ok"}
    assert parse_payload_after(valid_bytes) == {"status": "ok"}

    # Malformed byte sequence: before falls back safely, after crashes with UnicodeDecodeError
    assert parse_payload_before(invalid_bytes) is None
    with pytest.raises(UnicodeDecodeError):
        parse_payload_after(invalid_bytes)


def test_reproduction_case_06_resource_lifecycle_regression() -> None:
    """Case 6: execute_transaction removed finally block leaking open connection on error."""

    class Connection:
        def __init__(self) -> None:
            self.is_open: bool = False

        def open(self) -> None:
            self.is_open = True

        def close(self) -> None:
            self.is_open = False

    def exec_before(conn: Connection, query: str) -> str:
        conn.open()
        try:
            if "FAIL" in query:
                raise RuntimeError("Query execution failed")
            return f"RECORD:{query}"
        finally:
            conn.close()

    def exec_after(conn: Connection, query: str) -> str:
        conn.open()
        if "FAIL" in query:
            raise RuntimeError("Query execution failed")
        result = f"RECORD:{query}"
        conn.close()
        return result

    # Before: query failure cleans up and closes connection
    conn_before = Connection()
    with pytest.raises(RuntimeError):
        exec_before(conn_before, "FAIL_QUERY")
    assert conn_before.is_open is False, "Connection must be closed on error via finally"

    # After: query failure bypasses close, leaking the open connection
    conn_after = Connection()
    with pytest.raises(RuntimeError):
        exec_after(conn_after, "FAIL_QUERY")
    assert conn_after.is_open is True, "Connection remained open after exception"


def test_reproduction_case_07_auth_validation_bypass() -> None:
    """Case 7: check_resource_access condition changed from 'and' to 'or' bypassing ownership."""

    def check_access_before(role: str, action: str, is_owner: bool) -> bool:
        if role == "admin":
            return True
        if action == "view":
            return True
        return is_owner and action in ("edit", "delete")

    def check_access_after(role: str, action: str, is_owner: bool) -> bool:
        if role == "admin":
            return True
        if action == "view":
            return True
        return is_owner or action in ("edit", "delete")

    # Legitimate owner can edit and delete in both
    assert check_access_before("user", "delete", is_owner=True) is True
    assert check_access_after("user", "delete", is_owner=True) is True

    # Non-owner attempting to delete:
    # Before: denied (False)
    assert check_access_before("user", "delete", is_owner=False) is False
    # After: authorized erroneously (True)
    assert check_access_after("user", "delete", is_owner=False) is True, "Non-owner authorized to delete"


def test_reproduction_case_08_lru_recency_logic_flaw() -> None:
    """Case 8: LRUCache get misses recency refresh causing accessed items to be evicted."""

    class LRUCacheBefore:
        def __init__(self, capacity: int) -> None:
            self.capacity = capacity
            self.store: dict[str, str] = {}
            self.order: list[str] = []

        def get(self, key: str) -> str | None:
            if key not in self.store:
                return None
            self.order.remove(key)
            self.order.append(key)
            return self.store[key]

        def put(self, key: str, value: str) -> None:
            if key in self.store:
                self.order.remove(key)
            elif len(self.store) >= self.capacity:
                oldest = self.order.pop(0)
                del self.store[oldest]
            self.store[key] = value
            self.order.append(key)

    class LRUCacheAfter:
        def __init__(self, capacity: int) -> None:
            self.capacity = capacity
            self.store: dict[str, str] = {}
            self.order: list[str] = []

        def get(self, key: str) -> str | None:
            if key not in self.store:
                return None
            return self.store[key]

        def put(self, key: str, value: str) -> None:
            if key in self.store:
                self.order.remove(key)
            elif len(self.store) >= self.capacity:
                oldest = self.order.pop(0)
                del self.store[oldest]
            self.store[key] = value
            self.order.append(key)

    # Before: accessing key 'a' refreshes it; inserting 'c' evicts 'b'
    cache1 = LRUCacheBefore(2)
    cache1.put("a", "1")
    cache1.put("b", "2")
    assert cache1.get("a") == "1"
    cache1.put("c", "3")
    assert cache1.get("a") == "1", "Recently read key 'a' must remain in cache"
    assert cache1.get("b") is None, "Oldest key 'b' must be evicted"

    # After: accessing key 'a' fails to refresh order; inserting 'c' evicts 'a'
    cache2 = LRUCacheAfter(2)
    cache2.put("a", "1")
    cache2.put("b", "2")
    assert cache2.get("a") == "1"
    cache2.put("c", "3")
    assert cache2.get("a") is None, "Key 'a' was prematurely evicted due to missing recency refresh"
    assert cache2.get("b") == "2", "Key 'b' was erroneously retained"


# =========================================================================
# Phase 3: Independent Verification Tests for Clean Negative Cases
# =========================================================================


def test_verification_case_09_defensive_query_guard() -> None:
    """Case 9: parse_query_param defensive guard prevents ValueError on malformed inputs."""

    def parse_query_before(query_string: str, param_name: str) -> str | None:
        pairs = query_string.split("&")
        for pair in pairs:
            key, val = pair.split("=", 1)
            if key == param_name:
                return val
        return None

    def parse_query_after(query_string: str, param_name: str) -> str | None:
        if not query_string or "=" not in query_string:
            return None
        pairs = query_string.split("&")
        for pair in pairs:
            if "=" in pair:
                key, val = pair.split("=", 1)
                if key == param_name:
                    return val
        return None

    # Valid inputs work identically
    assert parse_query_before("user=alice&action=login", "user") == "alice"
    assert parse_query_after("user=alice&action=login", "user") == "alice"

    # Malformed / empty inputs: before crashes with ValueError, after safely returns None
    with pytest.raises(ValueError, match="not enough values to unpack"):
        parse_query_before("invalid_token_without_delimiter", "user")

    assert parse_query_after("invalid_token_without_delimiter", "user") is None
    assert parse_query_after("", "user") is None


def test_verification_case_10_safe_signature_migration() -> None:
    """Case 10: Function signature migration with default argument and updated callers."""

    def gen_invoice_before(customer_id: str, amount_due: float) -> dict[str, Any]:
        return {"customer": customer_id, "amount": amount_due, "status": "unpaid"}

    def create_invoice_before(cid: str, total: float) -> dict[str, Any]:
        return gen_invoice_before(cid, total)

    def gen_invoice_after(customer_id: str, amount_due: float, currency: str = "USD") -> dict[str, Any]:
        return {"customer": customer_id, "amount": amount_due, "currency": currency, "status": "unpaid"}

    def create_invoice_after(cid: str, total: float, currency: str = "USD") -> dict[str, Any]:
        return gen_invoice_after(cid, total, currency=currency)

    # Before call
    inv1 = create_invoice_before("cust_100", 99.95)
    assert inv1 == {"customer": "cust_100", "amount": 99.95, "status": "unpaid"}

    # After call with default
    inv2 = create_invoice_after("cust_100", 99.95)
    assert inv2 == {"customer": "cust_100", "amount": 99.95, "currency": "USD", "status": "unpaid"}

    # After call with custom currency
    inv3 = create_invoice_after("cust_100", 99.95, currency="EUR")
    assert inv3["currency"] == "EUR"


def test_verification_case_11_resource_cleanup_context_manager() -> None:
    """Case 11: Modernizing try...finally into context manager protocol preserves cleanup."""

    class BufferHandleBefore:
        def __init__(self, data: bytes) -> None:
            self.data: bytes = data
            self.is_closed: bool = False

        def close(self) -> None:
            self.is_closed = True

    def write_payload_before(handle: BufferHandleBefore, extra: bytes) -> int:
        try:
            handle.data = handle.data + extra
            return len(handle.data)
        finally:
            handle.close()

    class BufferHandleAfter:
        def __init__(self, data: bytes) -> None:
            self.data: bytes = data
            self.is_closed: bool = False

        def __enter__(self) -> BufferHandleAfter:
            return self

        def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
            self.close()

        def close(self) -> None:
            self.is_closed = True

    def write_payload_after(handle: BufferHandleAfter, extra: bytes) -> int:
        with handle:
            handle.data = handle.data + extra
            return len(handle.data)

    # Successful execution closes handle in both
    h_before = BufferHandleBefore(b"abc")
    assert write_payload_before(h_before, b"def") == 6
    assert h_before.is_closed is True

    h_after = BufferHandleAfter(b"abc")
    assert write_payload_after(h_after, b"def") == 6
    assert h_after.is_closed is True


def test_verification_case_12_specific_exception_narrowing() -> None:
    """Case 12: Exception narrowing preserves transient error handling without masking bugs."""

    def query_service_before(endpoint: str, timeout: float = 5.0) -> str:
        try:
            if not endpoint:
                raise ValueError("Endpoint must not be empty")
            if "timeout" in endpoint:
                raise TimeoutError("Network connection timed out")
            return f"RESPONSE:{endpoint}"
        except Exception:
            return "FALLBACK"

    def query_service_after(endpoint: str, timeout: float = 5.0) -> str:
        try:
            if not endpoint:
                raise ValueError("Endpoint must not be empty")
            if "timeout" in endpoint:
                raise TimeoutError("Network connection timed out")
            return f"RESPONSE:{endpoint}"
        except (TimeoutError, ConnectionError):
            return "FALLBACK"

    # Transient timeout errors return fallback in both
    assert query_service_before("timeout_endpoint") == "FALLBACK"
    assert query_service_after("timeout_endpoint") == "FALLBACK"

    # Programming bug (empty endpoint raising ValueError):
    # Before: silently swallowed into "FALLBACK"
    assert query_service_before("") == "FALLBACK"

    # After: raised appropriately to avoid masking bugs
    with pytest.raises(ValueError, match="Endpoint must not be empty"):
        query_service_after("")
