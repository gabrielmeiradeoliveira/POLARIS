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
    """Apply global ceilings and retain only completed OFF/ON pairs for comparison."""
    used = 0
    attempted: list[ArmResult] = []
    stopped_reason: str | None = None
    for result in results:
        if len(attempted) == execution_limit:
            stopped_reason = "execution_limit"
            break
        if used + result.tokens > token_limit:
            stopped_reason = "token_limit"
            break
        attempted.append(result)
        used += result.tokens
    completed: dict[str, set[str]] = {}
    for result in attempted:
        if result.status == "completed":
            completed.setdefault(result.case_id, set()).add(result.arm)
    pairs = tuple(case_id for case_id, arms in completed.items() if arms == {"off", "on"})
    return ProtocolResult(tuple(attempted), pairs, stopped_reason)
