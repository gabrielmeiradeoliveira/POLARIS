from __future__ import annotations

from typing import Any

import sqlglot
from sqlglot import exp


def resolve_sql_semantics(sql: str, schema: dict[str, list[str]], dialect: str = "postgres") -> dict[str, Any]:
    """Resolve table aliases, CTEs, and column references against a static schema."""
    stmt = sqlglot.parse_one(sql, read=dialect)
    ctes = {cte.alias_or_name for cte in stmt.find_all(exp.CTE)}
    aliases: dict[str, str] = {}
    for tbl in stmt.find_all(exp.Table):
        tname = tbl.name
        alias = tbl.alias_or_name or tname
        aliases[alias] = tname

    unknown_columns: list[str] = []
    ambiguous_columns: list[str] = []
    lineage: list[dict[str, str]] = []
    for col in stmt.find_all(exp.Column):
        cname = col.name
        tref = col.table
        if tref and tref in aliases:
            real_tbl = aliases[tref]
            if real_tbl in schema and cname != "*" and cname not in schema[real_tbl]:
                unknown_columns.append(f"{tref}.{cname}")
            else:
                lineage.append({"column": cname, "source_table": real_tbl})
        elif len(aliases) == 1:
            real_tbl = next(iter(aliases.values()))
            if real_tbl in schema and cname != "*" and cname not in schema[real_tbl]:
                unknown_columns.append(cname)
            else:
                lineage.append({"column": cname, "source_table": real_tbl})
        elif not tref and len(aliases) > 1 and cname != "*":
            matching_tables = [t for t in aliases.values() if t in schema and cname in schema[t]]
            if len(matching_tables) > 1:
                ambiguous_columns.append(cname)
            elif len(matching_tables) == 1:
                lineage.append({"column": cname, "source_table": matching_tables[0]})

    return {
        "dialect": dialect,
        "ctes": sorted(ctes),
        "aliases": aliases,
        "lineage": lineage,
        "unknown_columns": unknown_columns,
        "ambiguous_columns": ambiguous_columns,
    }
