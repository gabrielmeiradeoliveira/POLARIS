"""Hardening tests for BudgetTracker and quota control under adversarial conditions (GOAL 29.2)."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from polaris.core.errors import BudgetExceededError
from polaris.core.models import (
    BudgetTracker,
    ExecutionBudget,
    TokenUsage,
)
from polaris.quota.store import RequestStatus


def test_concurrent_reservations_thread_safety():
    """Verify that multiple concurrent threads reserving attempts do not exceed request limits."""
    max_requests = 10
    budget = ExecutionBudget(max_total_tokens=100_000, max_requests=max_requests)
    tracker = BudgetTracker(budget)

    successful_reservations = []
    rejected_count = 0
    lock = threading.Lock()

    def attempt_reservation(thread_idx: int):
        nonlocal rejected_count
        try:
            res_id = tracker.reserve_attempt(estimated_prompt_tokens=100, reserved_output_tokens=100)
            with lock:
                successful_reservations.append(res_id)
        except BudgetExceededError:
            with lock:
                rejected_count += 1

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(attempt_reservation, i) for i in range(25)]
        for f in futures:
            f.result()

    # Requests made must equal exactly max_requests, and excess threads must be rejected cleanly
    assert tracker.requests_made == max_requests
    assert len(successful_reservations) == max_requests
    assert rejected_count == 15


def test_timeout_and_uncertain_usage_conservative_accounting():
    """Verify that a timeout or network cut after dispatch records conservative usage rather than zero."""
    budget = ExecutionBudget(max_total_tokens=10_000, max_requests=5)
    tracker = BudgetTracker(budget)

    res_id = tracker.reserve_attempt(estimated_prompt_tokens=500, reserved_output_tokens=500)
    assert tracker.usage.total_tokens == 0  # Not yet completed

    # Simulate timeout: marked UNCERTAIN
    tracker.fail_attempt(res_id, status=RequestStatus.UNCERTAIN, estimated_prompt_tokens=500)

    # Conservative accounting must NOT treat it as 0! Prompt tokens must be accounted
    assert tracker.usage.total_tokens >= 500
    assert tracker.usage.is_estimated is True


def test_response_missing_usage_reconciles_conservatively():
    """When provider returns a response with null or zero usage, tracker reconciles with estimated prompt tokens."""
    budget = ExecutionBudget(max_total_tokens=10_000, max_requests=5)
    tracker = BudgetTracker(budget)

    res_id = tracker.reserve_attempt(estimated_prompt_tokens=350, reserved_output_tokens=350)
    # Simulate missing usage
    fallback_usage = TokenUsage(prompt_tokens=350, completion_tokens=50, total_tokens=400, is_estimated=True)
    tracker.complete_attempt(res_id, fallback_usage)

    assert tracker.usage.total_tokens == 400
    assert tracker.usage.is_estimated is True


def test_completion_overage_triggers_budget_exceeded():
    """Completion exceeding allocated reservation raises BudgetExceededError and prevents further calls."""
    budget = ExecutionBudget(max_total_tokens=1000, max_requests=5)
    tracker = BudgetTracker(budget)

    res_id = tracker.reserve_attempt(estimated_prompt_tokens=200, reserved_output_tokens=200)
    actual_huge_usage = TokenUsage(prompt_tokens=200, completion_tokens=900, total_tokens=1100)

    with pytest.raises(BudgetExceededError) as exc_info:
        tracker.complete_attempt(res_id, actual_huge_usage)

    assert "Token budget exceeded" in str(exc_info.value)
    # Ensure tracker records the overage to prevent any subsequent request
    assert tracker.usage.total_tokens == 1100
    with pytest.raises(BudgetExceededError):
        tracker.reserve_attempt(estimated_prompt_tokens=100, reserved_output_tokens=100)
