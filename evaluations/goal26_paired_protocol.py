"""Offline execution controls for the GOAL 26 paired A/B protocol."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArmResult:
    case_id: str
    arm: str
    status: str
    tokens: int


@dataclass(frozen=True)
class ProtocolResult:
    attempted: tuple[ArmResult, ...]
    comparable_case_ids: tuple[str, ...]
    stopped_reason: str | None


def run_offline_protocol(results: list[ArmResult], *, token_limit: int, execution_limit: int = 40) -> ProtocolResult:
    """Admit complete OFF/ON pairs atomically under the global ceilings.

    Tokens are upper bounds reserved before either arm is attempted, not
    measurements observed after the request.
    """
    if token_limit < 0 or execution_limit < 0:
        raise ValueError("Limits must be non-negative.")
    if any(item.tokens < 0 for item in results):
        raise ValueError("Reserved tokens must be non-negative.")

    used = 0
    attempted: list[ArmResult] = []
    stopped_reason: str | None = None
    if len(results) % 2:
        raise ValueError("Protocol requires complete OFF/ON input pairs.")
    for index in range(0, len(results), 2):
        off, on = results[index:index + 2]
        if off.case_id != on.case_id or (off.arm, on.arm) != ("off", "on"):
            raise ValueError("Protocol requires adjacent OFF/ON arms of the same case.")
        if len(attempted) + 2 > execution_limit:
            stopped_reason = "execution_limit"
            break
        pair_tokens = off.tokens + on.tokens
        if used + pair_tokens > token_limit:
            stopped_reason = "token_limit"
            break
        attempted.extend((off, on))
        used += pair_tokens
    pairs = tuple(
        attempted[index].case_id
        for index in range(0, len(attempted), 2)
        if attempted[index].status == attempted[index + 1].status == "completed"
    )
    return ProtocolResult(tuple(attempted), pairs, stopped_reason)
