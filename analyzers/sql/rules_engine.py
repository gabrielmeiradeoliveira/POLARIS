from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlglot import exp


@dataclass(frozen=True)
class SqlRuleDef:
    rule_id: str
    name: str
    category: str
    severity: str
    capability: str
    description: str
    check: Callable[[exp.Expression], str | None]


def _has_select_star(stmt: exp.Expression) -> str | None:
    for star in stmt.find_all(exp.Star):
        if isinstance(star.parent, (exp.Select, exp.Column)):
            return "Avoid SELECT * in SQL queries"
    return None


def _delete_without_where(stmt: exp.Expression) -> str | None:
    if isinstance(stmt, exp.Delete) and stmt.args.get("where") is None:
        return "DELETE without WHERE clause"
    return None


def _update_without_where(stmt: exp.Expression) -> str | None:
    if isinstance(stmt, exp.Update) and stmt.args.get("where") is None:
        return "UPDATE without WHERE clause"
    return None


def _eq_null(stmt: exp.Expression) -> str | None:
    for eq in stmt.find_all(exp.EQ, exp.NEQ):
        if isinstance(eq.right, exp.Null) or isinstance(eq.left, exp.Null):
            return "Use IS NULL / IS NOT NULL instead of = NULL / <> NULL"
    return None


def _cross_join(stmt: exp.Expression) -> str | None:
    for j in stmt.find_all(exp.Join):
        if j.kind == "CROSS" or (j.args.get("on") is None and j.args.get("using") is None and j.kind != "NATURAL"):
            return "Potential cartesian join without ON/USING condition"
    return None


def _distinct_with_group_by(stmt: exp.Expression) -> str | None:
    if isinstance(stmt, exp.Select) and stmt.args.get("distinct") and stmt.args.get("group"):
        return "Redundant DISTINCT with GROUP BY"
    return None


def _drop_statement(stmt: exp.Expression) -> str | None:
    if isinstance(stmt, exp.Drop):
        return "Destructive DROP statement requires review"
    return None


def _truncate_statement(stmt: exp.Expression) -> str | None:
    if stmt.key in ("truncate", "truncatetable"):
        return "Destructive TRUNCATE statement requires review"
    return None


def _leading_wildcard_like(stmt: exp.Expression) -> str | None:
    for lk in stmt.find_all(exp.Like, exp.ILike):
        if isinstance(lk.right, exp.Literal) and lk.right.is_string and lk.right.this.startswith("%"):
            return "Leading wildcard in LIKE predicate may prevent index usage"
    return None


def _not_in_subquery(stmt: exp.Expression) -> str | None:
    for n in stmt.find_all(exp.Not):
        if isinstance(n.this, exp.In) and isinstance(n.this.args.get("query"), exp.Subquery):
            return "NOT IN with subquery can behave unexpectedly with NULLs; prefer NOT EXISTS"
    return None


def _union_without_all(stmt: exp.Expression) -> str | None:
    for u in stmt.find_all(exp.Union):
        if u.args.get("distinct", True):
            return "Consider UNION ALL instead of UNION if duplicates are not expected"
    return None


def _or_in_where(stmt: exp.Expression) -> str | None:
    w = stmt.args.get("where")
    if w and list(w.find_all(exp.Or)):
        return "OR condition in WHERE clause; verify indexability"
    return None


def _having_without_group_by(stmt: exp.Expression) -> str | None:
    if isinstance(stmt, exp.Select) and stmt.args.get("having") and not stmt.args.get("group"):
        return "HAVING clause without GROUP BY"
    return None


def _limit_without_order(stmt: exp.Expression) -> str | None:
    if isinstance(stmt, exp.Select) and stmt.args.get("limit") and not stmt.args.get("order"):
        return "LIMIT without ORDER BY produces non-deterministic results"
    return None


def _nested_subquery(stmt: exp.Expression) -> str | None:
    subs = list(stmt.find_all(exp.Subquery))
    if len(subs) >= 3:
        return "Excessive subquery nesting (>=3); consider CTEs"
    return None


def _many_joins(stmt: exp.Expression) -> str | None:
    if len(list(stmt.find_all(exp.Join))) > 5:
        return "Query has >5 JOINs; review complexity"
    return None


def _count_star_in_exists(stmt: exp.Expression) -> str | None:
    for ex in stmt.find_all(exp.Exists):
        if list(ex.find_all(exp.Count)):
            return "Avoid COUNT() inside EXISTS(); use SELECT 1"
    return None


def _order_by_rand(stmt: exp.Expression) -> str | None:
    o = stmt.args.get("order")
    if o and any(fn.sql_name().upper() in {"RAND", "RANDOM"} for fn in o.find_all(exp.Anonymous, exp.Rand)):
        return "ORDER BY RAND()/RANDOM() forces full sort"
    return None


def _select_into(stmt: exp.Expression) -> str | None:
    if isinstance(stmt, exp.Select) and stmt.args.get("into"):
        return "SELECT INTO creates implicit table; prefer explicit CREATE/INSERT"
    return None


def _insert_without_columns(stmt: exp.Expression) -> str | None:
    if isinstance(stmt, exp.Insert) and not isinstance(stmt.this, exp.Schema):
        return "INSERT without explicit column list"
    return None


SQL_RULES: list[SqlRuleDef] = [
    SqlRuleDef("SQL-SYN-001", "Avoid SELECT *", "MAINTAINABILITY", "MINOR", "syntactic", "Avoid SELECT *.", _has_select_star),
    SqlRuleDef("SQL-CTX-001", "DELETE/UPDATE without WHERE", "RELIABILITY", "MAJOR", "semantic", "DELETE without WHERE.", _delete_without_where),
    SqlRuleDef("SQL-CTX-002", "UPDATE without WHERE", "RELIABILITY", "MAJOR", "semantic", "UPDATE without WHERE.", _update_without_where),
    SqlRuleDef("SQL-SYN-002", "Comparison with NULL", "RELIABILITY", "MAJOR", "semantic", "Use IS NULL.", _eq_null),
    SqlRuleDef("SQL-CTX-003", "Cartesian JOIN", "RELIABILITY", "MAJOR", "semantic", "JOIN without ON/USING.", _cross_join),
    SqlRuleDef("SQL-SYN-003", "Redundant DISTINCT", "MAINTAINABILITY", "MINOR", "semantic", "DISTINCT with GROUP BY.", _distinct_with_group_by),
    SqlRuleDef("SQL-CTX-004", "Destructive DROP", "SECURITY", "MAJOR", "contextual", "DROP statement review.", _drop_statement),
    SqlRuleDef("SQL-CTX-005", "Destructive TRUNCATE", "SECURITY", "MAJOR", "contextual", "TRUNCATE statement review.", _truncate_statement),
    SqlRuleDef("SQL-SYN-004", "Leading wildcard LIKE", "PERFORMANCE", "MINOR", "syntactic", "LIKE '%...' non-sargable.", _leading_wildcard_like),
    SqlRuleDef("SQL-CTX-006", "NOT IN subquery", "RELIABILITY", "MAJOR", "semantic", "NOT IN with subquery.", _not_in_subquery),
    SqlRuleDef("SQL-SYN-005", "UNION vs UNION ALL", "PERFORMANCE", "INFO", "syntactic", "Prefer UNION ALL.", _union_without_all),
    SqlRuleDef("SQL-SYN-006", "OR in WHERE", "PERFORMANCE", "INFO", "syntactic", "OR in WHERE clause.", _or_in_where),
    SqlRuleDef("SQL-CTX-007", "HAVING without GROUP BY", "RELIABILITY", "MAJOR", "semantic", "HAVING without GROUP BY.", _having_without_group_by),
    SqlRuleDef("SQL-CTX-008", "LIMIT without ORDER BY", "RELIABILITY", "MINOR", "semantic", "Non-deterministic LIMIT.", _limit_without_order),
    SqlRuleDef("SQL-SYN-007", "Deep subquery nesting", "MAINTAINABILITY", "MINOR", "syntactic", "Nested subqueries >=3.", _nested_subquery),
    SqlRuleDef("SQL-SYN-008", "Excessive JOINs", "MAINTAINABILITY", "MINOR", "syntactic", "More than 5 JOINs.", _many_joins),
    SqlRuleDef("SQL-SYN-009", "COUNT in EXISTS", "PERFORMANCE", "MINOR", "semantic", "COUNT() inside EXISTS().", _count_star_in_exists),
    SqlRuleDef("SQL-CTX-009", "ORDER BY RANDOM", "PERFORMANCE", "MINOR", "semantic", "ORDER BY RAND()/RANDOM().", _order_by_rand),
    SqlRuleDef("SQL-CTX-010", "SELECT INTO", "MAINTAINABILITY", "MINOR", "contextual", "SELECT INTO implicit table.", _select_into),
    SqlRuleDef("SQL-SYN-010", "INSERT without columns", "MAINTAINABILITY", "MINOR", "syntactic", "INSERT without column list.", _insert_without_columns),
]
