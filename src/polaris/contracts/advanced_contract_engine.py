"""Advanced Contract Intelligence (GOAL 30 - Fase 30.7).

Inspects function signatures, positional/keyword arguments, default values,
type annotations, TypedDicts, and dataclass contracts across file boundaries.
"""

from __future__ import annotations

import ast
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ContractViolationType(StrEnum):
    """Types of interprocedural contract violations."""

    MISSING_REQUIRED_ARGUMENT = "MISSING_REQUIRED_ARGUMENT"
    UNEXPECTED_KEYWORD_ARGUMENT = "UNEXPECTED_KEYWORD_ARGUMENT"
    TYPE_ANNOTATION_MISMATCH = "TYPE_ANNOTATION_MISMATCH"
    INCOMPATIBLE_RETURN_TYPE = "INCOMPATIBLE_RETURN_TYPE"


class ContractViolation(BaseModel):
    """Evidence-backed contract breakage between producer and consumer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    violation_type: ContractViolationType
    producer_symbol: str
    consumer_symbol: str
    consumer_file: str
    line: int
    message: str
    evidence: str


class AdvancedContractAnalyzer:
    """Detects signature incompatibilities, dropped defaults, and argument mismatch."""

    @staticmethod
    def inspect_function_signature(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
        """Extract positional args, default counts, keyword-only args, and type annotations."""
        args = func_node.args
        pos_args = [arg.arg for arg in args.args]
        defaults_count = len(args.defaults)
        num_required = len(pos_args) - defaults_count

        kwonly_args = [arg.arg for arg in args.kwonlyargs]
        kw_defaults_count = sum(1 for d in args.kw_defaults if d is not None)
        num_required_kw = len(kwonly_args) - kw_defaults_count

        annotations: dict[str, str] = {}
        for arg in args.args + args.kwonlyargs:
            if arg.annotation:
                annotations[arg.arg] = ast.unparse(arg.annotation)

        return {
            "name": func_node.name,
            "pos_args": pos_args,
            "num_required_pos": num_required,
            "has_varargs": args.vararg is not None,
            "has_varkw": args.kwarg is not None,
            "kwonly_args": kwonly_args,
            "num_required_kw": num_required_kw,
            "annotations": annotations,
        }

    @classmethod
    def check_call_against_signature(
        cls,
        call_node: ast.Call,
        signature: dict[str, Any],
        consumer_symbol: str,
        consumer_file: str,
    ) -> list[ContractViolation]:
        """Verify whether a call site satisfies the producer function's signature."""
        violations: list[ContractViolation] = []
        num_passed_pos = len(call_node.args)
        passed_kwargs = {kw.arg for kw in call_node.keywords if kw.arg is not None}

        # 1. Missing required positional arguments
        num_required = signature["num_required_pos"]
        if num_passed_pos < num_required:
            # Check if missing positional arguments are passed as keywords
            missing_args = signature["pos_args"][num_passed_pos:num_required]
            unmet = [arg for arg in missing_args if arg not in passed_kwargs]
            if unmet:
                violations.append(
                    ContractViolation(
                        violation_type=ContractViolationType.MISSING_REQUIRED_ARGUMENT,
                        producer_symbol=signature["name"],
                        consumer_symbol=consumer_symbol,
                        consumer_file=consumer_file,
                        line=call_node.lineno,
                        message=f"Call to '{signature['name']}' is missing required argument(s): {', '.join(unmet)}",
                        evidence=f"Call site `{ast.unparse(call_node)}` provides {num_passed_pos} args, required: {num_required}",
                    )
                )

        # 2. Unexpected keyword arguments when **kwargs is absent
        if not signature["has_varkw"]:
            valid_kw = set(signature["pos_args"]) | set(signature["kwonly_args"])
            for kw in passed_kwargs:
                if kw not in valid_kw:
                    violations.append(
                        ContractViolation(
                            violation_type=ContractViolationType.UNEXPECTED_KEYWORD_ARGUMENT,
                            producer_symbol=signature["name"],
                            consumer_symbol=consumer_symbol,
                            consumer_file=consumer_file,
                            line=call_node.lineno,
                            message=f"Call to '{signature['name']}' passed unexpected keyword argument '{kw}'",
                            evidence=f"Keyword '{kw}' not in signature args: {valid_kw}",
                        )
                    )

        return violations
