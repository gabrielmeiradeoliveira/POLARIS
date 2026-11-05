"""Frozen local RC1 complex-system catalog; never derived from POLARIS output."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    application: str
    difficulty: str
    kind: str
    category: str
    before: str
    after: str
    contract: str
    files: tuple[str, ...]
    oracle_input: int
    finding_line: int


_APPS = (
    ("api_auth", "authorization", ("routes.py", "service.py", "repository.py")),
    ("orders_payments", "state_mutation", ("orders.py", "payments.py", "inventory.py")),
    ("etl_replay", "logic_error", ("ingest.py", "checkpoint.py", "store.py")),
    ("async_workers", "concurrency", ("queue.py", "worker.py", "locks.py")),
    ("cache_contracts", "type_mismatch", ("cache.py", "service.py", "consumer.py")),
)
_LEVELS = ("N1",) * 12 + ("N2",) * 24 + ("N3",) * 24


def build_catalog() -> tuple[Scenario, ...]:
    """Build 60 causal contracts with executable N1/N2/N3 structural depth.

    The local catalog is still development evidence only. N1 has a direct
    guard, N2 adds a normalization helper, and N3 crosses policy and
    repository objects before the guarded return.
    """
    scenarios: list[Scenario] = []
    for index, level in enumerate(_LEVELS, start=1):
        app, category, files = _APPS[(index - 1) % len(_APPS)]
        positive = index % 2 == 1
        kind = "positive" if positive else "negative"
        if level == "N1":
            before = "def contract(value):\n    if value < 0: raise ValueError('invalid')\n    return value\n"
            after = (
                "def contract(value):\n    return value\n"
                if positive
                else "def contract(value):\n    if value < 0: raise ValueError('invalid')\n    return int(value)\n"
            )
            finding_line = 2
        elif level == "N2":
            before = (
                "def normalize(value):\n"
                "    return int(value)\n\n"
                "def contract(value):\n"
                "    normalized = normalize(value)\n"
                "    if normalized < 0: raise ValueError('invalid')\n"
                "    return normalized\n"
            )
            after = (
                "def normalize(value):\n"
                "    return int(value)\n\n"
                "def contract(value):\n"
                "    normalized = normalize(value)\n"
                "    return normalized\n"
                if positive
                else "def normalize(value):\n    return int(value)\n\ndef contract(value):\n    normalized = normalize(value)\n    if normalized < 0: raise ValueError('invalid')\n    return int(normalized)\n"
            )
            finding_line = 5
        else:
            before = (
                "class Policy:\n"
                "    def normalize(self, value):\n"
                "        return int(value)\n\n"
                "class Repository:\n"
                "    def prepare(self, value):\n"
                "        return Policy().normalize(value)\n\n"
                "def contract(value):\n"
                "    prepared = Repository().prepare(value)\n"
                "    if prepared < 0: raise ValueError('invalid')\n"
                "    return prepared\n"
            )
            after = (
                "class Policy:\n"
                "    def normalize(self, value):\n"
                "        return int(value)\n\n"
                "class Repository:\n"
                "    def prepare(self, value):\n"
                "        return Policy().normalize(value)\n\n"
                "def contract(value):\n"
                "    prepared = Repository().prepare(value)\n"
                "    return prepared\n"
                if positive
                else "class Policy:\n    def normalize(self, value):\n        return int(value)\n\nclass Repository:\n    def prepare(self, value):\n        return Policy().normalize(value)\n\ndef contract(value):\n    prepared = Repository().prepare(value)\n    if prepared < 0: raise ValueError('invalid')\n    return int(prepared)\n"
            )
            finding_line = 11
        scenarios.append(
            Scenario(
                id=f"g24-{app}-{index:02d}", application=app, difficulty=level, kind=kind,
                category=category, before=before, after=after,
                contract="negative values must be rejected before state, authorization, or persistence effects",
                files=files if level != "N1" else (files[0],),
                oracle_input=-1,
                finding_line=finding_line,
            )
        )
    return tuple(scenarios)


CATALOG = build_catalog()
