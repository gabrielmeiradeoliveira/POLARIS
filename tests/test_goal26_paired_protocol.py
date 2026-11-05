import pytest

from evaluations.goal26_paired_protocol import ArmResult, run_offline_protocol


def test_protocol_retains_only_completed_pairs() -> None:
    outcome = run_offline_protocol(
        [ArmResult("a", "off", "completed", 10), ArmResult("a", "on", "timeout", 10)], token_limit=100
    )
    assert outcome.comparable_case_ids == ()


def test_protocol_stops_before_exceeding_global_token_limit() -> None:
    outcome = run_offline_protocol(
        [ArmResult("a", "off", "completed", 60), ArmResult("a", "on", "completed", 60)], token_limit=100
    )
    assert len(outcome.attempted) == 0
    assert outcome.stopped_reason == "token_limit"
    assert outcome.comparable_case_ids == ()


def test_protocol_allows_forty_initial_executions() -> None:
    results = [ArmResult(str(index // 2), "off" if index % 2 == 0 else "on", "completed", 1) for index in range(40)]
    outcome = run_offline_protocol(results, token_limit=100)
    assert len(outcome.attempted) == 40
    assert len(outcome.comparable_case_ids) == 20


def test_protocol_does_not_start_pair_with_one_request_remaining() -> None:
    result = run_offline_protocol(
        [ArmResult("a", "off", "completed", 1), ArmResult("a", "on", "completed", 1)],
        token_limit=100,
        execution_limit=1,
    )
    assert result.attempted == ()
    assert result.stopped_reason == "execution_limit"


def test_protocol_rejects_unpaired_or_reordered_input() -> None:
    with pytest.raises(ValueError, match="complete"):
        run_offline_protocol([ArmResult("a", "off", "completed", 1)], token_limit=100)
    with pytest.raises(ValueError, match="adjacent"):
        run_offline_protocol(
            [ArmResult("a", "on", "completed", 1), ArmResult("a", "off", "completed", 1)],
            token_limit=100,
        )
