"""AST comparison rules for detecting authorization relaxation vulnerabilities."""

from __future__ import annotations

import ast

from polaris.core.models import FindingCategory, LineRange, Severity
from polaris.guardrails.models import GuardrailConfidence, GuardrailEvidence, SecurityFinding


def _safe_unparse(node: ast.AST) -> str:
    """Safely convert AST node back to Python code."""
    try:
        return ast.unparse(node)
    except Exception:
        return "<unparse_error>"


def _is_none_check(node: ast.AST) -> tuple[str, bool] | None:
    """Check if node is 'x is None' or 'x is not None' or 'x == None'.

    Returns (var_name, is_positive_none) where is_positive_none is True if expression
    evaluates to True when var is None.
    """
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
        op = node.ops[0]
        left = node.left
        right = node.comparators[0]
        # Check if right or left is Constant(value=None)
        var_node = None
        if isinstance(right, ast.Constant) and right.value is None:
            var_node = left
        elif isinstance(left, ast.Constant) and left.value is None:
            var_node = right

        if var_node and isinstance(var_node, ast.Name):
            if isinstance(op, (ast.Is, ast.Eq)):
                return (var_node.id, True)
            if isinstance(op, (ast.IsNot, ast.NotEq)):
                return (var_node.id, False)

    return None


def _extract_return_predicates(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[int, ast.AST]]:
    """Extract (line_number, expr) for all return statements inside function."""
    returns: list[tuple[int, ast.AST]] = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.Return) and node.value is not None:
            # Don't walk into nested function definitions
            returns.append((getattr(node, "lineno", func_node.lineno), node.value))
    return returns


def _disjuncts(node: ast.AST) -> list[ast.AST]:
    """Flatten an 'Or' boolean operation tree into individual disjuncts."""
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        out: list[ast.AST] = []
        for val in node.values:
            out.extend(_disjuncts(val))
        return out
    return [node]


def _has_unresolved_call_or_dynamic(node: ast.AST) -> bool:
    """Check if an expression contains dynamic function calls or attribute lookups that cannot be proven purely by AST."""
    for n in ast.walk(node):
        if isinstance(n, (ast.Call, ast.Subscript)):
            return True
        if isinstance(n, ast.Attribute) and not isinstance(n.value, ast.Name):
            return True
    return False


def analyze_function_authorization_relaxation(
    before_func: ast.FunctionDef | ast.AsyncFunctionDef | None,
    after_func: ast.FunctionDef | ast.AsyncFunctionDef,
    file_path: str,
) -> list[SecurityFinding]:
    """Compare before and after AST of a function to detect demonstrable authorization relaxation."""
    findings: list[SecurityFinding] = []

    # If no before_func, we can't prove relaxation relative to prior contract
    if before_func is None:
        return findings

    before_returns = _extract_return_predicates(before_func)
    after_returns = _extract_return_predicates(after_func)

    if not before_returns or not after_returns:
        return findings

    # Check the primary return statements
    # Case 11 pattern: Before had restrictive equality, after introduced 'or role is None'
    before_line, before_expr = before_returns[0]
    after_line, after_expr = after_returns[0]

    before_unparsed = _safe_unparse(before_expr)
    after_unparsed = _safe_unparse(after_expr)

    # If syntactically identical, no relaxation
    if before_unparsed == after_unparsed:
        return findings

    before_disjuncts = _disjuncts(before_expr)
    after_disjuncts = _disjuncts(after_expr)

    # Identify parameter names
    params = {arg.arg for arg in after_func.args.args}

    # Detect if any new disjunct in after allows None for a parameter that was previously rejected
    # Check if before disjuncts allowed None
    def allows_none(disjuncts: list[ast.AST]) -> set[str]:
        allowed: set[str] = set()
        for d in disjuncts:
            none_chk = _is_none_check(d)
            if none_chk and none_chk[1]:  # True when var is None
                allowed.add(none_chk[0])
        return allowed

    before_allowed_none = allows_none(before_disjuncts)
    after_allowed_none = allows_none(after_disjuncts)

    new_none_allowed = after_allowed_none - before_allowed_none

    for param_name in new_none_allowed:
        if param_name in params:
            # Check if there are unresolved dynamic calls in the expression
            has_dynamic = _has_unresolved_call_or_dynamic(after_expr)
            confidence = GuardrailConfidence.SUSPECTED if has_dynamic else GuardrailConfidence.CONFIRMED

            start_line = getattr(after_func, "lineno", after_line)
            end_line = getattr(after_func, "end_lineno", start_line)

            evidence = GuardrailEvidence(
                rule_id="SEC-AUTH-001",
                symbol=after_func.name,
                file_path=file_path,
                line_range=LineRange(start_line=start_line, end_line=end_line),
                before_predicate=before_unparsed,
                after_predicate=after_unparsed,
                confidence=confidence,
                reason=(
                    f"Parameter '{param_name}' authorization check relaxed: function now permits access when "
                    f"'{param_name}' is None (allow-by-default relaxation)."
                ),
                context_details={
                    "parameter": param_name,
                    "pattern": "none_allowed_disjunction",
                },
            )

            findings.append(
                SecurityFinding(
                    finding_id=f"sec-guardrail-{file_path}-{after_func.name}-{start_line}",
                    rule_id="SEC-AUTH-001",
                    category=FindingCategory.LOGIC_ERROR,
                    severity=Severity.HIGH,
                    file_path=file_path,
                    line_range=LineRange(start_line=start_line, end_line=end_line),
                    title=f"[SEC-AUTH-001] Authorization relaxation in '{after_func.name}' allows unauthenticated/default access",
                    description=(
                        f"In '{after_func.name}', the authorization condition was changed from "
                        f"`{before_unparsed}` to `{after_unparsed}`. Access is now granted when "
                        f"'{param_name}' is None, weakening prior access controls."
                    ),
                    evidence=evidence,
                )
            )

    # RULE SEC-AUTH-002: Predicate Inversion or Condition Removal (e.g., if is_admin -> if True, or return True)
    if before_unparsed != after_unparsed:
        if isinstance(after_expr, ast.Constant) and after_expr.value is True:
            # Function unconditionally returns True after being conditional
            start_line = getattr(after_func, "lineno", after_line)
            end_line = getattr(after_func, "end_lineno", start_line)
            findings.append(
                SecurityFinding(
                    finding_id=f"sec-guardrail-{file_path}-{after_func.name}-{start_line}-bypass",
                    rule_id="SEC-AUTH-002",
                    category=FindingCategory.LOGIC_ERROR,
                    severity=Severity.CRITICAL,
                    file_path=file_path,
                    line_range=LineRange(start_line=start_line, end_line=end_line),
                    title=f"[SEC-AUTH-002] Security check disabled: '{after_func.name}' unconditionally returns True",
                    description=(
                        f"In '{after_func.name}', prior check `{before_unparsed}` was replaced by constant `True`. "
                        "All caller authorization gates are completely bypassed."
                    ),
                    evidence=GuardrailEvidence(
                        rule_id="SEC-AUTH-002",
                        symbol=after_func.name,
                        file_path=file_path,
                        line_range=LineRange(start_line=start_line, end_line=end_line),
                        before_predicate=before_unparsed,
                        after_predicate=after_unparsed,
                        confidence=GuardrailConfidence.CONFIRMED,
                        reason=f"Prior check `{before_unparsed}` removed and replaced with unconditional True.",
                    ),
                )
            )

        # RULE SEC-PATH-001: Path Traversal / Direct File Access without validation
        # e.g., open(os.path.join(base, filename)) where sanitization was dropped
        if "open(" in after_unparsed and "../" in after_unparsed:
            start_line = getattr(after_func, "lineno", after_line)
            end_line = getattr(after_func, "end_lineno", start_line)
            findings.append(
                SecurityFinding(
                    finding_id=f"sec-guardrail-{file_path}-{after_func.name}-{start_line}-traversal",
                    rule_id="SEC-PATH-001",
                    category=FindingCategory.LOGIC_ERROR,
                    severity=Severity.HIGH,
                    file_path=file_path,
                    line_range=LineRange(start_line=start_line, end_line=end_line),
                    title=f"[SEC-PATH-001] Potential path traversal in '{after_func.name}'",
                    description=f"In '{after_func.name}', unvalidated path traversal sequence detected in file access: `{after_unparsed}`.",
                    evidence=GuardrailEvidence(
                        rule_id="SEC-PATH-001",
                        symbol=after_func.name,
                        file_path=file_path,
                        line_range=LineRange(start_line=start_line, end_line=end_line),
                        before_predicate=before_unparsed,
                        after_predicate=after_unparsed,
                        confidence=GuardrailConfidence.CONFIRMED,
                        reason="Path traversal sequence detected in filesystem call.",
                    ),
                )
            )

    return findings
