"""Static contract inferrer and consumer tracker for Python ASTs (GOAL 28.3)."""

from __future__ import annotations

import ast

from polaris.contracts.models import ContractKind, InferredContract


def safe_unparse(node: ast.AST) -> str:
    """Safely convert AST node to code representation."""
    try:
        return ast.unparse(node)
    except Exception:
        return "<unparse_error>"


def infer_return_contract(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> InferredContract:
    """Statically inspect return statements of a function to infer its return contract."""
    return_exprs: list[ast.AST] = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.Return) and node.value is not None:
            return_exprs.append(node.value)

    if not return_exprs:
        # Function has no explicit return expression (returns None implicitly)
        return InferredContract(
            kind=ContractKind.NONE,
            guaranteed_keys=[],
            raw_expression="None",
        )

    # Inspect primary return
    primary = return_exprs[0]
    raw = safe_unparse(primary)

    # 1. Dict literal: return {'value': x}
    if isinstance(primary, ast.Dict):
        keys: list[str] = []
        for k in primary.keys:
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                keys.append(k.value)
        return InferredContract(
            kind=ContractKind.DICT_LITERAL,
            guaranteed_keys=keys,
            raw_expression=raw,
        )

    # 2. Constant None: return None
    if isinstance(primary, ast.Constant) and primary.value is None:
        return InferredContract(
            kind=ContractKind.NONE,
            guaranteed_keys=[],
            raw_expression=raw,
        )

    # 3. Known non-dict literals (integer, string, boolean, float) or tuples / lists
    if isinstance(primary, (ast.Tuple, ast.List)):
        return InferredContract(
            kind=ContractKind.SCALAR_OR_PASSTHROUGH,
            guaranteed_keys=[],
            raw_expression=raw,
        )

    if isinstance(primary, ast.Constant) and isinstance(primary.value, (int, str, bool, float)):
        return InferredContract(
            kind=ContractKind.SCALAR_OR_PASSTHROUGH,
            guaranteed_keys=[],
            raw_expression=raw,
        )

    # 4. Parameter passthrough: return x (where x is in func parameters)
    params = {arg.arg for arg in func_node.args.args}
    if isinstance(primary, ast.Name) and primary.id in params:
        return InferredContract(
            kind=ContractKind.SCALAR_OR_PASSTHROUGH,
            guaranteed_keys=[],
            raw_expression=raw,
        )

    return InferredContract(
        kind=ContractKind.UNKNOWN,
        guaranteed_keys=[],
        raw_expression=raw,
    )


class ConsumerAccess:
    """An operation in an AST that accesses keys or attributes on an expression."""

    def __init__(self, target_expr: ast.AST, required_key: str, line_number: int, is_subscript: bool) -> None:
        self.target_expr = target_expr
        self.required_key = required_key
        self.line_number = line_number
        self.is_subscript = is_subscript


def find_consumer_subscripts(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ConsumerAccess]:
    """Find dictionary index operations (e.g. obj['value']) inside a function."""
    accesses: list[ConsumerAccess] = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.Subscript):
            # Check slice / index
            slice_node = node.slice
            key_name: str | None = None
            if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
                key_name = slice_node.value

            if key_name is not None:
                accesses.append(
                    ConsumerAccess(
                        target_expr=node.value,
                        required_key=key_name,
                        line_number=getattr(node, "lineno", func_node.lineno),
                        is_subscript=True,
                    )
                )
    return accesses
