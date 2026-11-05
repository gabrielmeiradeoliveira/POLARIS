"""Bounded, intraprocedural Python static analysis used for context relevance.

The engine deliberately models only evidence available from the standard-library
``ast`` tree.  It does not claim interprocedural precision, execute code, or
resolve dynamic dispatch.  Unknown values are represented explicitly so callers
can choose a safe fallback instead of fabricating a relationship.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import StrEnum


class StaticAnalysisStatus(StrEnum):
    PARSED = "parsed"
    SYNTAX_ERROR = "syntax_error"
    COMPLEXITY_LIMIT = "complexity_limit"


class ControlFlowKind(StrEnum):
    ENTRY = "entry"
    STATEMENT = "statement"
    CONDITION = "condition"
    LOOP = "loop"
    EXCEPTION = "exception"
    FINALLY = "finally"
    EXIT = "exit"


class DataFlowCertainty(StrEnum):
    PROVEN = "proven"
    POSSIBLE = "possible"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class StructuralFact:
    kind: str
    name: str | None
    line: int
    end_line: int
    detail: str = ""


@dataclass(frozen=True)
class ControlFlowNode:
    node_id: str
    kind: ControlFlowKind
    line: int
    end_line: int
    label: str


@dataclass(frozen=True)
class ControlFlowEdge:
    source_id: str
    target_id: str
    kind: str = "next"


@dataclass(frozen=True)
class DataFlowFact:
    name: str
    definition_line: int | None
    use_line: int
    certainty: DataFlowCertainty
    kind: str


@dataclass(frozen=True)
class BehavioralSignal:
    kind: str
    line: int
    detail: str


@dataclass(frozen=True)
class ProcedureAnalysis:
    qualified_name: str
    start_line: int
    end_line: int
    cfg_nodes: tuple[ControlFlowNode, ...]
    cfg_edges: tuple[ControlFlowEdge, ...]
    data_flow: tuple[DataFlowFact, ...]
    signals: tuple[BehavioralSignal, ...]
    complexity: int
    incomplete: bool = False
    unreachable_lines: tuple[int, ...] = ()


@dataclass(frozen=True)
class StaticAnalysisResult:
    status: StaticAnalysisStatus
    structures: tuple[StructuralFact, ...] = ()
    procedures: tuple[ProcedureAnalysis, ...] = ()
    diagnostics: tuple[str, ...] = ()


def _names(node: ast.AST | None) -> set[str]:
    if node is None:
        return set()
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)}


def _target_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        return set().union(*(_target_names(item) for item in node.elts)) if node.elts else set()
    if isinstance(node, ast.Starred):
        return _target_names(node.value)
    return set()


def _future_assignment_lines(node: ast.AST) -> dict[str, int]:
    """Return the earliest lexical assignment line for each local name.

    Nested functions and classes create independent scopes, so their bindings
    are deliberately excluded from the enclosing procedure's approximation.
    """
    found: dict[str, int] = {}

    def visit(current: ast.AST) -> None:
        if current is not node and isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return
        if isinstance(current, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = current.targets if isinstance(current, ast.Assign) else [current.target]
            for target in targets:
                for name in _target_names(target):
                    found[name] = min(found.get(name, current.lineno), current.lineno)
        elif isinstance(current, (ast.For, ast.AsyncFor)):
            for name in _target_names(current.target):
                found[name] = min(found.get(name, current.lineno), current.lineno)
        elif isinstance(current, ast.ExceptHandler) and current.name:
            found[current.name] = min(found.get(current.name, current.lineno), current.lineno)
        for child in ast.iter_child_nodes(current):
            visit(child)

    visit(node)
    return found


class _ProcedureBuilder:
    """Build a deliberately small CFG and reaching-definition approximation."""

    def __init__(self, name: str, node: ast.FunctionDef | ast.AsyncFunctionDef, max_nodes: int) -> None:
        self.name, self.node, self.max_nodes = name, node, max_nodes
        self.nodes: list[ControlFlowNode] = []
        self.edges: list[ControlFlowEdge] = []
        self.facts: list[DataFlowFact] = []
        self.signals: list[BehavioralSignal] = []
        self.definitions: dict[str, int] = {arg.arg: node.lineno for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]}
        if node.args.vararg:
            self.definitions[node.args.vararg.arg] = node.lineno
        if node.args.kwarg:
            self.definitions[node.args.kwarg.arg] = node.lineno
        self.future_assignments = _future_assignment_lines(node)
        self.complexity = 1
        self.incomplete = False
        self.loop_stack: list[tuple[str, list[str]]] = []
        self.unreachable_lines: list[int] = []

    def add(self, kind: ControlFlowKind, stmt: ast.AST, label: str) -> str:
        if len(self.nodes) >= self.max_nodes:
            self.incomplete = True
            return "limit"
        node_id = f"{self.name}:{len(self.nodes)}"
        self.nodes.append(ControlFlowNode(node_id, kind, getattr(stmt, "lineno", self.node.lineno), getattr(stmt, "end_lineno", getattr(stmt, "lineno", self.node.lineno)), label))
        return node_id

    def connect(self, left: str | None, right: str | None, kind: str = "next") -> None:
        if left and right and left != "limit" and right != "limit":
            self.edges.append(ControlFlowEdge(left, right, kind))

    def uses(self, value: ast.AST | None, line: int, kind: str = "use") -> None:
        for name in sorted(_names(value)):
            definition = self.definitions.get(name)
            certainty = DataFlowCertainty.PROVEN if definition is not None else DataFlowCertainty.POSSIBLE
            fact_kind = kind
            if definition is None:
                future_assignment = self.future_assignments.get(name)
                if future_assignment is not None:
                    fact_kind = (
                        "possible_use_before_assignment"
                        if future_assignment > line
                        else "possible_unbound_local"
                    )
            self.facts.append(DataFlowFact(name, definition, line, certainty, fact_kind))

    @staticmethod
    def _merge_continuing_definitions(paths: list[dict[str, int]]) -> dict[str, int]:
        """Keep only bindings proven to exist on every path that continues.

        The analysis records a single representative source line for a binding;
        when separate branches assign it, the earliest valid assignment is
        evidence of the binding while membership in every continuing path is the
        proof that the use itself is safe from an unbound-local path.
        """
        if not paths:
            return {}
        common_names = set(paths[0])
        for definitions in paths[1:]:
            common_names.intersection_update(definitions)
        return {name: min(definitions[name] for definitions in paths) for name in common_names}

    def statement_list(self, statements: list[ast.stmt], incoming: str | None) -> list[str]:
        exits = [incoming] if incoming else []
        for stmt in statements:
            if not exits and incoming is not None:
                self.unreachable_lines.append(stmt.lineno)
            next_exits: list[str] = []
            for predecessor in exits or [None]:
                next_exits.extend(self.statement(stmt, predecessor))
            exits = next_exits
        return exits

    def statement(self, stmt: ast.stmt, previous: str | None) -> list[str]:
        if self.incomplete:
            return [previous] if previous else []
        if isinstance(stmt, (ast.Return, ast.Raise)):
            current = self.add(ControlFlowKind.EXIT, stmt, type(stmt).__name__.lower())
            self.connect(previous, current)
            self.uses(getattr(stmt, "value", None), stmt.lineno, "return" if isinstance(stmt, ast.Return) else "raise")
            self.signals.append(BehavioralSignal("return" if isinstance(stmt, ast.Return) else "exception", stmt.lineno, type(stmt).__name__))
            return []
        if isinstance(stmt, ast.Continue):
            current = self.add(ControlFlowKind.STATEMENT, stmt, "continue")
            self.connect(previous, current)
            if self.loop_stack:
                self.connect(current, self.loop_stack[-1][0], "continue")
            else:
                self.incomplete = True
            self.signals.append(BehavioralSignal("continue", stmt.lineno, "continue"))
            return []
        if isinstance(stmt, ast.Break):
            current = self.add(ControlFlowKind.STATEMENT, stmt, "break")
            self.connect(previous, current)
            if self.loop_stack:
                self.loop_stack[-1][1].append(current)
            else:
                self.incomplete = True
            self.signals.append(BehavioralSignal("break", stmt.lineno, "break"))
            return []
        if isinstance(stmt, ast.If):
            current = self.add(ControlFlowKind.CONDITION, stmt, "if")
            self.connect(previous, current)
            self.uses(stmt.test, stmt.lineno, "condition")
            self.signals.append(BehavioralSignal("condition", stmt.lineno, "if"))
            self.complexity += 1
            before_branch = dict(self.definitions)
            yes = self.statement_list(stmt.body, current)
            yes_definitions = dict(self.definitions)
            self.definitions = dict(before_branch)
            no = self.statement_list(stmt.orelse, current) if stmt.orelse else [current]
            no_definitions = dict(self.definitions)
            continuing_definitions: list[dict[str, int]] = []
            if yes:
                continuing_definitions.append(yes_definitions)
            if no:
                continuing_definitions.append(no_definitions)
            self.definitions = self._merge_continuing_definitions(continuing_definitions)
            return [*yes, *no]
        if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            current = self.add(ControlFlowKind.LOOP, stmt, "loop")
            self.connect(previous, current)
            self.uses(stmt.iter if hasattr(stmt, "iter") else stmt.test, stmt.lineno, "loop")
            if hasattr(stmt, "target"):
                for name in _target_names(stmt.target):
                    self.definitions[name] = stmt.lineno
            self.signals.append(BehavioralSignal("loop", stmt.lineno, type(stmt).__name__))
            self.complexity += 1
            breaks: list[str] = []
            self.loop_stack.append((current, breaks))
            body_exits = self.statement_list(stmt.body, current)
            self.loop_stack.pop()
            for exit_id in body_exits:
                self.connect(exit_id, current, "loop_back")
            return [current, *breaks]
        if isinstance(stmt, ast.Try):
            current = self.add(ControlFlowKind.EXCEPTION, stmt, "try")
            self.connect(previous, current)
            self.complexity += len(stmt.handlers)
            before_try = dict(self.definitions)
            body_exits = self.statement_list(stmt.body, current)
            body_definitions = dict(self.definitions)
            continuing_paths: list[dict[str, int]] = []
            if body_exits:
                if stmt.orelse:
                    self.definitions = dict(body_definitions)
                    body_exits = self.statement_list(stmt.orelse, body_exits[0])
                    self.signals.append(BehavioralSignal("exception_else", stmt.orelse[0].lineno, "try_else"))
                    body_definitions = dict(self.definitions)
                if body_exits:
                    continuing_paths.append(body_definitions)
            handler_exits: list[str] = []
            for handler in stmt.handlers:
                self.definitions = dict(before_try)
                handler_id = self.add(ControlFlowKind.EXCEPTION, handler, "except")
                self.connect(current, handler_id, "exception")
                if handler.name:
                    self.definitions[handler.name] = handler.lineno
                exits = self.statement_list(handler.body, handler_id)
                handler_exits.extend(exits)
                if exits:
                    continuing_paths.append(dict(self.definitions))
                self.signals.append(BehavioralSignal("exception_handler", handler.lineno, "except"))
            exits = [*body_exits, *handler_exits]
            self.definitions = self._merge_continuing_definitions(continuing_paths)
            if stmt.finalbody:
                final_id = self.add(ControlFlowKind.FINALLY, stmt.finalbody[0], "finally")
                for exit_id in exits or [current]:
                    self.connect(exit_id, final_id, "finally")
                return self.statement_list(stmt.finalbody, final_id)
            return exits
        current = self.add(ControlFlowKind.STATEMENT, stmt, type(stmt).__name__)
        self.connect(previous, current)
        if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            value = getattr(stmt, "value", None)
            self.uses(value, stmt.lineno, "assignment")
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            for target in targets:
                for name in _target_names(target):
                    self.definitions[name] = stmt.lineno
                    self.signals.append(BehavioralSignal("assignment", stmt.lineno, name))
        elif isinstance(stmt, ast.Expr):
            self.uses(stmt.value, stmt.lineno)
            if isinstance(stmt.value, ast.Call):
                self.signals.append(BehavioralSignal("call", stmt.lineno, ast.unparse(stmt.value.func)))
        return [current]

    def build(self) -> ProcedureAnalysis:
        entry = self.add(ControlFlowKind.ENTRY, self.node, "entry")
        exits = self.statement_list(self.node.body, entry)
        terminal = self.add(ControlFlowKind.EXIT, self.node, "exit")
        for exit_id in exits:
            self.connect(exit_id, terminal)
        return ProcedureAnalysis(
            self.name,
            self.node.lineno,
            getattr(self.node, "end_lineno", self.node.lineno),
            tuple(self.nodes),
            tuple(self.edges),
            tuple(self.facts),
            tuple(self.signals),
            self.complexity,
            self.incomplete,
            tuple(sorted(set(self.unreachable_lines))),
        )


class PythonStaticAnalyzer:
    """Extract structural, control-flow, and data-flow evidence from Python source."""

    def __init__(self, max_nodes_per_procedure: int = 200) -> None:
        self.max_nodes_per_procedure = max_nodes_per_procedure

    def analyze_source(self, source: str, file_path: str = "source.py") -> StaticAnalysisResult:
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError as exc:
            return StaticAnalysisResult(StaticAnalysisStatus.SYNTAX_ERROR, diagnostics=(f"SyntaxError line {exc.lineno or 1}: {exc.msg}",))
        structures: list[StructuralFact] = []
        procedures: list[ProcedureAnalysis] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = ", ".join(ast.unparse(base) for base in node.bases)
                structures.append(StructuralFact("class", node.name, node.lineno, getattr(node, "end_lineno", node.lineno), bases))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                prefix = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
                structures.append(StructuralFact(prefix, node.name, node.lineno, getattr(node, "end_lineno", node.lineno)))
                procedures.append(_ProcedureBuilder(node.name, node, self.max_nodes_per_procedure).build())
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                structures.append(StructuralFact("import", None, node.lineno, getattr(node, "end_lineno", node.lineno), ast.unparse(node)))
        status = StaticAnalysisStatus.COMPLEXITY_LIMIT if any(proc.incomplete for proc in procedures) else StaticAnalysisStatus.PARSED
        diagnostics = ("One or more procedures reached the CFG node limit; their results are incomplete.",) if status == StaticAnalysisStatus.COMPLEXITY_LIMIT else ()
        return StaticAnalysisResult(status, tuple(sorted(structures, key=lambda fact: (fact.line, fact.kind, fact.name or ""))), tuple(sorted(procedures, key=lambda proc: (proc.start_line, proc.qualified_name))), diagnostics)
