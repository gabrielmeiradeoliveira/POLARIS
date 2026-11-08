"""Static Dataflow Analysis Engine (GOAL 30 - Fase 30.5).

Tracks intraprocedural def-use chains, taint propagation, sanitizers,
and sources/sinks across Python ASTs.
"""

from __future__ import annotations

import ast
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TaintStatus(StrEnum):
    """Certainty of taint reaching a sink."""

    PROVEN = "PROVEN"
    POSSIBLE = "POSSIBLE"
    UNKNOWN = "UNKNOWN"


class TaintFlow(BaseModel):
    """Represents a traced dataflow path from source to sink."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = Field(..., min_length=1)
    sink: str = Field(..., min_length=1)
    variable: str = Field(..., min_length=1)
    line: int = Field(..., ge=1)
    status: TaintStatus
    evidence: str = ""


class DataflowAnalysisEngine:
    """Analyzes AST code blocks to track untrusted taint propagation to dangerous sinks."""

    DEFAULT_SOURCES = {"request.args", "request.form", "request.json", "user_input", "params"}
    DEFAULT_SINKS = {"cursor.execute", "os.system", "subprocess.run", "eval", "exec"}
    DEFAULT_SANITIZERS = {"int", "escape", "quote", "sanitize"}

    def __init__(
        self,
        sources: set[str] | None = None,
        sinks: set[str] | None = None,
        sanitizers: set[str] | None = None,
    ) -> None:
        self.sources = sources or self.DEFAULT_SOURCES
        self.sinks = sinks or self.DEFAULT_SINKS
        self.sanitizers = sanitizers or self.DEFAULT_SANITIZERS

    def analyze_source(self, code: str) -> list[TaintFlow]:
        """Parse Python source and trace taint from sources to sinks."""
        try:
            tree = ast.parse(code)
        except Exception:
            return []

        flows: list[TaintFlow] = []
        tainted_vars: dict[str, str] = {}  # var_name -> source_expr

        class FlowVisitor(ast.NodeVisitor):
            def visit_Assign(self, node: ast.Assign) -> None:
                # Check if RHS has a taint source
                rhs_source = self._find_source(node.value)
                rhs_sanitized = self._is_sanitized(node.value)

                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if rhs_sanitized:
                            tainted_vars.pop(target.id, None)
                        elif rhs_source:
                            tainted_vars[target.id] = rhs_source
                        else:
                            # Check if RHS expression uses tainted variables (e.g. f-string or binary op)
                            taint_in_rhs = self._find_taint(node.value)
                            if taint_in_rhs:
                                tainted_vars[target.id] = taint_in_rhs
                self.generic_visit(node)

            def visit_Call(self, node: ast.Call) -> None:
                # Check if this call is a sink
                call_name = self._get_call_name(node.func)
                for sink in DataflowAnalysisEngine.DEFAULT_SINKS:
                    if sink in call_name:
                        # Check arguments
                        for arg in node.args:
                            arg_source = self._find_taint(arg)
                            if arg_source:
                                flows.append(
                                    TaintFlow(
                                        source=arg_source,
                                        sink=call_name,
                                        variable=ast.unparse(arg),
                                        line=node.lineno,
                                        status=TaintStatus.PROVEN,
                                        evidence=f"Tainted data from '{arg_source}' reached sink '{call_name}' at line {node.lineno}",
                                    )
                                )
                self.generic_visit(node)

            def _get_call_name(self, func_node: ast.AST) -> str:
                return ast.unparse(func_node)

            def _find_source(self, expr_node: ast.AST) -> str | None:
                code_repr = ast.unparse(expr_node)
                for src in DataflowAnalysisEngine.DEFAULT_SOURCES:
                    if src in code_repr:
                        return src
                return None

            def _is_sanitized(self, expr_node: ast.AST) -> bool:
                if isinstance(expr_node, ast.Call):
                    name = ast.unparse(expr_node.func)
                    return any(san in name for san in DataflowAnalysisEngine.DEFAULT_SANITIZERS)
                return False

            def _find_taint(self, expr_node: ast.AST) -> str | None:
                if isinstance(expr_node, ast.Name) and expr_node.id in tainted_vars:
                    return tainted_vars[expr_node.id]
                if isinstance(expr_node, ast.JoinedStr):  # f-string
                    for part in expr_node.values:
                        if isinstance(part, ast.FormattedValue) and isinstance(part.value, ast.Name) and part.value.id in tainted_vars:
                            return tainted_vars[part.value.id]
                src = self._find_source(expr_node)
                if src and not self._is_sanitized(expr_node):
                    return src
                return None

        visitor = FlowVisitor()
        visitor.visit(tree)
        return flows
