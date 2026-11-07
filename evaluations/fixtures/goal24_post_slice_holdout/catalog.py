"""Internally authored causal holdout, frozen before first engine execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PostSliceScenario:
    id: str
    kind: str
    category: str
    expected_path: str
    expected_line: int
    before_files: dict[str, str]
    after_files: dict[str, str]
    entrypoint: str
    oracle: str


def _pair(
    name: str,
    category: str,
    path: str,
    line: int,
    before: dict[str, str],
    vulnerable: dict[str, str],
    safe: dict[str, str],
    entrypoint: str,
    oracle: str,
) -> tuple[PostSliceScenario, PostSliceScenario]:
    return (
        PostSliceScenario(f"psh-pos-{name}", "positive", category, path, line, before, vulnerable, entrypoint, oracle),
        PostSliceScenario(f"psh-neg-{name}", "negative", category, path, line, before, safe, entrypoint, oracle),
    )


CASES = tuple(
    scenario
    for pair in (
        _pair(
            "api-page-bound",
            "boundary_condition",
            "api/page.py",
            2,
            {"api/page.py": "def subject(items, limit):\n    return items[:min(limit, 50)]\n"},
            {"api/page.py": "def subject(items, limit):\n    return items[:limit + 1]\n"},
            {"api/page.py": "def subject(items, limit):\n    ceiling = min(limit, 50)\n    return items[:ceiling]\n"},
            "subject",
            "page_bound",
        ),
        _pair(
            "authorization-scope",
            "logic_error",
            "routes/export.py",
            2,
            {
                "policy/roles.py": "ALLOWED = {'admin'}\n",
                "routes/export.py": "def subject(role):\n    if role not in ALLOWED: raise PermissionError('export')\n    return 'export'\n",
            },
            {
                "policy/roles.py": "ALLOWED = {'admin', 'viewer'}\n",
                "routes/export.py": "def subject(role):\n    if role not in ALLOWED: raise PermissionError('export')\n    return 'export'\n",
            },
            {
                "policy/roles.py": "ALLOWED = frozenset(('admin',))\n",
                "routes/export.py": "def subject(role):\n    if role not in ALLOWED: raise PermissionError('export')\n    return 'export'\n",
            },
            "subject",
            "authorization",
        ),
        _pair(
            "payment-replay",
            "state_mutation",
            "payments/ledger.py",
            2,
            {"payments/ledger.py": "def subject(seen, key):\n    if key in seen: return 'duplicate'\n    seen.add(key)\n    return 'charged'\n"},
            {"payments/ledger.py": "def subject(seen, key):\n    seen.add(key)\n    return 'charged'\n"},
            {"payments/ledger.py": "def subject(seen, key):\n    if key in seen:\n        return 'duplicate'\n    seen.add(key)\n    return 'charged'\n"},
            "subject",
            "replay",
        ),
        _pair(
            "etl-required-id",
            "type_mismatch",
            "etl/transform.py",
            2,
            {"etl/transform.py": "def subject(row):\n    return row['event_id']\n"},
            {"etl/transform.py": "def subject(row):\n    return row.get('event_id')\n"},
            {"etl/transform.py": "def subject(row):\n    return row['event_id']\n"},
            "subject",
            "required_id",
        ),
        _pair(
            "cache-invalidation",
            "state_mutation",
            "cache/update.py",
            3,
            {"cache/update.py": "def subject(cache, key, value):\n    cache[key] = value\n    cache.pop('derived:' + key, None)\n    return value\n"},
            {"cache/update.py": "def subject(cache, key, value):\n    cache[key] = value\n    return value\n"},
            {"cache/update.py": "def subject(cache, key, value):\n    cache[key] = value\n    del cache['derived:' + key]\n    return value\n"},
            "subject",
            "cache",
        ),
        _pair(
            "lock-order",
            "concurrency",
            "workers/locks.py",
            2,
            {"workers/locks.py": "def subject(a, b):\n    return tuple(sorted((a, b)))\n"},
            {"workers/locks.py": "def subject(a, b):\n    return (a, b)\n"},
            {"workers/locks.py": "def subject(a, b):\n    first, second = sorted((a, b))\n    return first, second\n"},
            "subject",
            "lock_order",
        ),
        _pair(
            "contract-numeric-total",
            "type_mismatch",
            "billing/total.py",
            2,
            {"billing/total.py": "def subject(value):\n    return int(value)\n"},
            {"billing/total.py": "def subject(value):\n    return str(int(value))\n"},
            {"billing/total.py": "def subject(value):\n    return int(float(value))\n"},
            "subject",
            "numeric_contract",
        ),
        _pair(
            "exception-swallowing",
            "error_handling",
            "jobs/importer.py",
            3,
            {"jobs/importer.py": "def subject(value):\n    try:\n        return int(value)\n    except ValueError:\n        raise\n"},
            {"jobs/importer.py": "def subject(value):\n    try:\n        return int(value)\n    except ValueError:\n        return 0\n"},
            {"jobs/importer.py": "def subject(value):\n    try:\n        return int(value)\n    except ValueError as exc:\n        raise ValueError('invalid import') from exc\n"},
            "subject",
            "exception",
        ),
        _pair(
            "data-flow-tenant",
            "logic_error",
            "service/query.py",
            2,
            {
                "service/query.py": "def subject(rows, tenant):\n    return [row for row in rows if row['tenant'] == tenant]\n",
                "service/format.py": "def format_rows(rows):\n    return list(rows)\n",
            },
            {
                "service/query.py": "def subject(rows, tenant):\n    return format_rows(rows)\n",
                "service/format.py": "def format_rows(rows):\n    return list(rows)\n",
            },
            {
                "service/query.py": "def subject(rows, tenant):\n    return [row for row in rows if tenant == row['tenant']]\n",
                "service/format.py": "def format_rows(rows):\n    return list(rows)\n",
            },
            "subject",
            "tenant_flow",
        ),
    )
    for scenario in pair
)
