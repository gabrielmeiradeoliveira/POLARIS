"""Behavioral Delta 3.0 (GOAL 30 - Fase 30.8).

Performs semantic comparison between pre-change and post-change ASTs
to surface structured BehavioralChange evidence across mutation, returns, and conditions.
"""

from __future__ import annotations

import ast
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SemanticChangeCategory(StrEnum):
    """Category of behavioral delta."""

    RETURN_VALUE_MODIFIED = "RETURN_VALUE_MODIFIED"
    VALIDATION_RELAXED = "VALIDATION_RELAXED"
    EXCEPTION_ALTERED = "EXCEPTION_ALTERED"
    CRITICAL_CALL_REMOVED = "CRITICAL_CALL_REMOVED"
    PREDICATE_MUTATED = "PREDICATE_MUTATED"


class BehavioralChange(BaseModel):
    """Structured representation of a code behavioral delta."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol_name: str
    category: SemanticChangeCategory
    file_path: str
    line: int
    before_repr: str
    after_repr: str
    description: str


class BehavioralDelta3:
    """Semantic AST differential analyzer."""

    @classmethod
    def compare_functions(
        cls,
        before_ast: ast.FunctionDef | ast.AsyncFunctionDef,
        after_ast: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
    ) -> list[BehavioralChange]:
        """Detect semantic behavioral changes in function bodies."""
        changes: list[BehavioralChange] = []

        # 1. Inspect return expressions
        before_returns = [ast.unparse(n.value) for n in ast.walk(before_ast) if isinstance(n, ast.Return) and n.value]
        after_returns = [ast.unparse(n.value) for n in ast.walk(after_ast) if isinstance(n, ast.Return) and n.value]

        if before_returns != after_returns:
            changes.append(
                BehavioralChange(
                    symbol_name=after_ast.name,
                    category=SemanticChangeCategory.RETURN_VALUE_MODIFIED,
                    file_path=file_path,
                    line=after_ast.lineno,
                    before_repr="; ".join(before_returns) or "None",
                    after_repr="; ".join(after_returns) or "None",
                    description=f"Function '{after_ast.name}' return value altered from `{before_returns}` to `{after_returns}`",
                )
            )

        # 2. Inspect removed calls (e.g. security audits or cleanup)
        before_calls = {ast.unparse(n.func) for n in ast.walk(before_ast) if isinstance(n, ast.Call)}
        after_calls = {ast.unparse(n.func) for n in ast.walk(after_ast) if isinstance(n, ast.Call)}
        removed_calls = before_calls - after_calls

        for call in sorted(removed_calls):
            if any(term in call for term in ("check", "validate", "auth", "audit", "clean")):
                changes.append(
                    BehavioralChange(
                        symbol_name=after_ast.name,
                        category=SemanticChangeCategory.CRITICAL_CALL_REMOVED,
                        file_path=file_path,
                        line=after_ast.lineno,
                        before_repr=call,
                        after_repr="<omitted>",
                        description=f"Critical validation/security call `{call}` was dropped in '{after_ast.name}'",
                    )
                )

        return changes
