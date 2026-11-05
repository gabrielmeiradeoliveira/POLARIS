"""Post-recovery causal holdout; agent-authored and not external validation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HoldoutScenario:
    id: str
    kind: str
    path: str
    category: str
    line: int
    before: str
    after: str
    oracle: str


def _pair(
    name: str,
    path: str,
    category: str,
    line: int,
    before: str,
    vulnerable: str,
    safe: str,
    oracle: str,
) -> tuple[HoldoutScenario, HoldoutScenario]:
    return (
        HoldoutScenario(f"h24-pos-{name}", "positive", path, category, line, before, vulnerable, oracle),
        HoldoutScenario(f"h24-neg-{name}", "negative", path, category, line, before, safe, oracle),
    )


CASES = tuple(
    scenario
    for pair in (
        _pair(
            "normalized-quota",
            "api/quota.py",
            "boundary_condition",
            5,
            "def subject(quota):\n    normalized = int(quota)\n    if normalized < 0: raise ValueError('quota')\n    return normalized\n",
            "def subject(quota):\n    normalized = int(quota)\n    return normalized\n",
            "def subject(quota):\n    normalized = int(quota)\n    if normalized <= -1: raise ValueError('quota')\n    return normalized\n",
            "negative_quota",
        ),
        _pair(
            "account-isolation",
            "storage/events.py",
            "logic_error",
            2,
            "def subject(events, account):\n    return [event for event in events if event['account'] == account]\n",
            "def subject(events, account):\n    return list(events)\n",
            "def subject(events, account):\n    return [event for event in events if account == event['account']]\n",
            "account_filter",
        ),
        _pair(
            "replay-marker",
            "payments/ledger.py",
            "state_mutation",
            2,
            "def subject(processed, event):\n    if event in processed: return 'ignored'\n    processed.add(event)\n    return 'applied'\n",
            "def subject(processed, event):\n    processed.add(event)\n    return 'applied'\n",
            "def subject(processed, event):\n    if event in processed: return 'ignored'\n    processed.add(event)\n    return 'applied'\n",
            "replay",
        ),
        _pair(
            "lease-cleanup",
            "workers/lease.py",
            "resource_management",
            2,
            "def subject(lease):\n    lease.close()\n    return 'done'\n",
            "def subject(lease):\n    return 'done'\n",
            "def subject(lease):\n    try: return 'done'\n    finally: lease.close()\n",
            "close",
        ),
        _pair(
            "page-limit",
            "api/feed.py",
            "boundary_condition",
            2,
            "def subject(entries, limit):\n    return entries[:min(limit, 100)]\n",
            "def subject(entries, limit):\n    return entries[:limit + 1]\n",
            "def subject(entries, limit):\n    ceiling = min(limit, 100)\n    return entries[:ceiling]\n",
            "page",
        ),
        _pair(
            "eligibility-inversion",
            "pricing/discount.py",
            "logic_error",
            2,
            "def subject(amount, eligible):\n    return amount * 0.8 if eligible else amount\n",
            "def subject(amount, eligible):\n    return amount * 0.8 if not eligible else amount\n",
            "def subject(amount, eligible):\n    return amount * 0.8 if eligible else amount\n",
            "discount",
        ),
    )
    for scenario in pair
)
