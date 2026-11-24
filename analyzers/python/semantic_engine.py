"""Second-generation semantic engine: CFG, worklist data-flow solver, constant propagation, and nullability analysis."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple


@dataclass
class BasicBlock:
    """A basic block in a control-flow graph."""

    block_id: int
    label: str = ""
    statements: List[ast.stmt] = field(default_factory=list)
    predecessors: List[int] = field(default_factory=list)
    successors: List[int] = field(default_factory=list)
    branch_conditions: Dict[int, Tuple[ast.expr, bool]] = field(default_factory=dict)


class ControlFlowGraph:
    """Intra-procedural Control Flow Graph built from a Python AST function."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.blocks: Dict[int, BasicBlock] = {}
        self._next_id = 0
        self.entry_id = self.new_block("entry")
        self.exit_id = self.new_block("exit")
        self._loop_stack: List[Tuple[int, int]] = []

    def new_block(self, label: str = "") -> int:
        bid = self._next_id
        self._next_id += 1
        self.blocks[bid] = BasicBlock(block_id=bid, label=label or f"B{bid}")
        return bid

    def add_edge(self, src: int, dst: int, condition: Optional[Tuple[ast.expr, bool]] = None) -> None:
        if dst not in self.blocks[src].successors:
            self.blocks[src].successors.append(dst)
        if src not in self.blocks[dst].predecessors:
            self.blocks[dst].predecessors.append(src)
        if condition is not None:
            self.blocks[src].branch_conditions[dst] = condition

    @classmethod
    def from_function_ast(cls, func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> "ControlFlowGraph":
        cfg = cls(func_node.name)
        first_body = cfg.new_block("body")
        cfg.add_edge(cfg.entry_id, first_body)
        tail = cfg._build_stmt_list(func_node.body, first_body)
        if tail is not None:
            cfg.add_edge(tail, cfg.exit_id)
        return cfg

    def _build_stmt_list(self, stmts: List[ast.stmt], current_id: int) -> Optional[int]:
        cur: Optional[int] = current_id
        for stmt in stmts:
            if cur is None:
                # Unreachable code after return/raise; start a detached block for completeness
                cur = self.new_block("unreachable")
            cur = self._build_stmt(stmt, cur)
        return cur

    def _build_stmt(self, stmt: ast.stmt, current_id: int) -> Optional[int]:
        if isinstance(stmt, ast.If):
            self.blocks[current_id].statements.append(stmt)
            then_block = self.new_block("if_then")
            else_block = self.new_block("if_else")
            merge_block = self.new_block("if_merge")
            self.add_edge(current_id, then_block, condition=(stmt.test, True))
            self.add_edge(current_id, else_block, condition=(stmt.test, False))

            then_tail = self._build_stmt_list(stmt.body, then_block)
            if then_tail is not None:
                self.add_edge(then_tail, merge_block)

            else_tail = self._build_stmt_list(stmt.orelse, else_block) if stmt.orelse else else_block
            if else_tail is not None:
                self.add_edge(else_tail, merge_block)

            if not self.blocks[merge_block].predecessors:
                return None
            return merge_block

        if isinstance(stmt, (ast.While, ast.For, ast.AsyncFor)):
            header = self.new_block("loop_header")
            self.add_edge(current_id, header)
            self.blocks[header].statements.append(stmt)
            body_block = self.new_block("loop_body")
            after_block = self.new_block("loop_after")
            cond_expr = stmt.test if isinstance(stmt, ast.While) else None
            self.add_edge(header, body_block, condition=(cond_expr, True) if cond_expr else None)
            self.add_edge(header, after_block, condition=(cond_expr, False) if cond_expr else None)

            self._loop_stack.append((header, after_block))
            body_tail = self._build_stmt_list(stmt.body, body_block)
            self._loop_stack.pop()
            if body_tail is not None:
                self.add_edge(body_tail, header)
            return after_block

        if isinstance(stmt, ast.Break):
            self.blocks[current_id].statements.append(stmt)
            if self._loop_stack:
                self.add_edge(current_id, self._loop_stack[-1][1])
            return None

        if isinstance(stmt, ast.Continue):
            self.blocks[current_id].statements.append(stmt)
            if self._loop_stack:
                self.add_edge(current_id, self._loop_stack[-1][0])
            return None

        if isinstance(stmt, (ast.Return, ast.Raise)):
            self.blocks[current_id].statements.append(stmt)
            self.add_edge(current_id, self.exit_id)
            return None

        if isinstance(stmt, ast.Try):
            try_block = self.new_block("try")
            self.add_edge(current_id, try_block)
            merge_block = self.new_block("try_merge")
            try_tail = self._build_stmt_list(stmt.body, try_block)
            if try_tail is not None:
                self.add_edge(try_tail, merge_block)
            for handler in stmt.handlers:
                h_block = self.new_block("except")
                self.add_edge(try_block, h_block)
                h_tail = self._build_stmt_list(handler.body, h_block)
                if h_tail is not None:
                    self.add_edge(h_tail, merge_block)
            if stmt.finalbody:
                f_block = self.new_block("finally")
                self.add_edge(merge_block, f_block)
                return self._build_stmt_list(stmt.finalbody, f_block)
            return merge_block

        self.blocks[current_id].statements.append(stmt)
        return current_id


class WorklistSolver:
    """Generic forward data-flow worklist solver."""

    def __init__(
        self,
        cfg: ControlFlowGraph,
        initial_state: Callable[[], Dict[str, Any]],
        join: Callable[[List[Dict[str, Any]]], Dict[str, Any]],
        transfer: Callable[[BasicBlock, Dict[str, Any], Optional[Tuple[ast.expr, bool]]], Dict[str, Any]],
        max_iterations: int = 200,
    ) -> None:
        self.cfg = cfg
        self.initial_state = initial_state
        self.join = join
        self.transfer = transfer
        self.max_iterations = max_iterations

    def solve(self) -> Tuple[Dict[int, Dict[str, Any]], Dict[int, Dict[str, Any]]]:
        in_states: Dict[int, Dict[str, Any]] = {bid: self.initial_state() for bid in self.cfg.blocks}
        out_states: Dict[int, Dict[str, Any]] = {bid: self.initial_state() for bid in self.cfg.blocks}
        worklist: List[int] = list(self.cfg.blocks.keys())
        iterations = 0

        while worklist and iterations < self.max_iterations:
            iterations += 1
            bid = worklist.pop(0)
            block = self.cfg.blocks[bid]

            if block.predecessors:
                pred_outs: List[Dict[str, Any]] = []
                for pid in block.predecessors:
                    cond = self.cfg.blocks[pid].branch_conditions.get(bid)
                    if cond is not None:
                        pred_outs.append(self.transfer(self.cfg.blocks[pid], out_states[pid], cond))
                    else:
                        pred_outs.append(out_states[pid])
                in_states[bid] = self.join(pred_outs)
            else:
                in_states[bid] = self.initial_state()

            new_out = self.transfer(block, dict(in_states[bid]), None)
            if new_out != out_states[bid]:
                out_states[bid] = new_out
                for succ in block.successors:
                    if succ not in worklist:
                        worklist.append(succ)

        return in_states, out_states


_UNDEF = ("UNDEF", None)
_NAC = ("NAC", None)


class ConstantPropagationAnalysis:
    """Intra-procedural constant propagation over a ControlFlowGraph."""

    @staticmethod
    def _join_val(v1: Tuple[str, Any], v2: Tuple[str, Any]) -> Tuple[str, Any]:
        if v1[0] == "UNDEF":
            return v2
        if v2[0] == "UNDEF":
            return v1
        if v1 == v2:
            return v1
        return _NAC

    @classmethod
    def join(cls, states: List[Dict[str, Tuple[str, Any]]]) -> Dict[str, Tuple[str, Any]]:
        merged: Dict[str, Tuple[str, Any]] = {}
        keys: Set[str] = set()
        for s in states:
            keys.update(s.keys())
        for k in keys:
            acc = _UNDEF
            for s in states:
                acc = cls._join_val(acc, s.get(k, _UNDEF))
            merged[k] = acc
        return merged

    @classmethod
    def _eval_expr(cls, expr: ast.expr, state: Dict[str, Tuple[str, Any]]) -> Tuple[str, Any]:
        if isinstance(expr, ast.Constant):
            return ("CONST", expr.value)
        if isinstance(expr, ast.Name):
            return state.get(expr.id, _UNDEF)
        if isinstance(expr, ast.BinOp):
            left = cls._eval_expr(expr.left, state)
            right = cls._eval_expr(expr.right, state)
            if left[0] == "CONST" and right[0] == "CONST":
                try:
                    if isinstance(expr.op, ast.Add):
                        return ("CONST", left[1] + right[1])
                    if isinstance(expr.op, ast.Sub):
                        return ("CONST", left[1] - right[1])
                    if isinstance(expr.op, ast.Mult):
                        return ("CONST", left[1] * right[1])
                except Exception:
                    return _NAC
            if left[0] == "NAC" or right[0] == "NAC":
                return _NAC
            return _UNDEF
        return _NAC

    @classmethod
    def transfer(
        cls,
        block: BasicBlock,
        state: Dict[str, Tuple[str, Any]],
        edge_cond: Optional[Tuple[ast.expr, bool]],
    ) -> Dict[str, Tuple[str, Any]]:
        if edge_cond is not None:
            return dict(state)
        out = dict(state)
        for stmt in block.statements:
            if isinstance(stmt, ast.Assign):
                val = cls._eval_expr(stmt.value, out)
                for tgt in stmt.targets:
                    if isinstance(tgt, ast.Name):
                        out[tgt.id] = val
        return out

    @classmethod
    def analyze(cls, func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> Tuple[Dict[int, Dict[str, Tuple[str, Any]]], Dict[int, Dict[str, Tuple[str, Any]]]]:
        cfg = ControlFlowGraph.from_function_ast(func_node)
        solver = WorklistSolver(cfg, dict, cls.join, cls.transfer)
        return solver.solve()


class NullabilityAnalysis:
    """Intra-procedural nullability analysis with branch refinement."""

    NULL = "NULL"
    NON_NULL = "NON_NULL"
    MAYBE_NULL = "MAYBE_NULL"
    UNDEF = "UNDEF"

    @classmethod
    def _join_val(cls, v1: str, v2: str) -> str:
        if v1 == cls.UNDEF:
            return v2
        if v2 == cls.UNDEF:
            return v1
        if v1 == v2:
            return v1
        return cls.MAYBE_NULL

    @classmethod
    def join(cls, states: List[Dict[str, str]]) -> Dict[str, str]:
        merged: Dict[str, str] = {}
        keys: Set[str] = set()
        for s in states:
            keys.update(s.keys())
        for k in keys:
            acc = cls.UNDEF
            for s in states:
                acc = cls._join_val(acc, s.get(k, cls.UNDEF))
            merged[k] = acc
        return merged

    @classmethod
    def _eval_nullability(cls, expr: ast.expr, state: Dict[str, str]) -> str:
        if isinstance(expr, ast.Constant):
            return cls.NULL if expr.value is None else cls.NON_NULL
        if isinstance(expr, ast.Name):
            return state.get(expr.id, cls.MAYBE_NULL)
        if isinstance(expr, (ast.List, ast.Dict, ast.Set, ast.Tuple, ast.JoinedStr)):
            return cls.NON_NULL
        if isinstance(expr, ast.Call):
            if isinstance(expr.func, ast.Name) and expr.func.id in (
                "open", "list", "dict", "set", "tuple", "str", "int", "float", "bool", "urlparse"
            ):
                return cls.NON_NULL
            if (
                isinstance(expr.func, ast.Attribute)
                and isinstance(expr.func.value, ast.Name)
                and expr.func.value.id == "ipaddress"
                and expr.func.attr == "ip_address"
            ):
                return cls.NON_NULL
            return cls.MAYBE_NULL
        return cls.MAYBE_NULL

    @classmethod
    def transfer(
        cls,
        block: BasicBlock,
        state: Dict[str, str],
        edge_cond: Optional[Tuple[ast.expr, bool]],
    ) -> Dict[str, str]:
        out = dict(state)
        if edge_cond is not None:
            cond_expr, is_true = edge_cond
            if isinstance(cond_expr, ast.Compare) and len(cond_expr.ops) == 1 and len(cond_expr.comparators) == 1:
                op = cond_expr.ops[0]
                left = cond_expr.left
                right = cond_expr.comparators[0]
                if isinstance(left, ast.Name) and isinstance(right, ast.Constant) and right.value is None:
                    if isinstance(op, ast.Is):
                        out[left.id] = cls.NULL if is_true else cls.NON_NULL
                    elif isinstance(op, ast.IsNot):
                        out[left.id] = cls.NON_NULL if is_true else cls.NULL
            return out

        for stmt in block.statements:
            if isinstance(stmt, ast.Assign):
                val = cls._eval_nullability(stmt.value, out)
                for tgt in stmt.targets:
                    if isinstance(tgt, ast.Name):
                        out[tgt.id] = val
        return out

    @classmethod
    def find_null_dereferences(cls, func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[Dict[str, Any]]:
        cfg = ControlFlowGraph.from_function_ast(func_node)
        solver = WorklistSolver(cfg, dict, cls.join, cls.transfer)
        in_states, _ = solver.solve()
        findings: List[Dict[str, Any]] = []

        for bid, block in cfg.blocks.items():
            cur_state = dict(in_states[bid])
            for stmt in block.statements:
                nodes_to_check = [stmt.test] if isinstance(stmt, (ast.If, ast.While)) else [stmt]
                if isinstance(stmt, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.Try)):
                    if not isinstance(stmt, (ast.If, ast.While)):
                        nodes_to_check = []
                for root_node in nodes_to_check:
                    for node in ast.walk(root_node):
                        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                            var_name = node.value.id
                            null_state = cur_state.get(var_name, cls.UNDEF)
                            if null_state in (cls.NULL, cls.MAYBE_NULL):
                                findings.append(
                                    {
                                        "variable": var_name,
                                        "state": null_state,
                                        "line": getattr(node, "lineno", 0),
                                        "attribute": node.attr,
                                    }
                                )
                cur_state = cls.transfer(
                    BasicBlock(block_id=bid, statements=[stmt]), cur_state, None
                )
        return findings


class ResourceStateAnalysis:
    """Intra-procedural resource leak analysis over CFG (OPEN / CLOSED / ESCAPED)."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"
    ESCAPED = "ESCAPED"

    @classmethod
    def find_resource_leaks(cls, func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[Dict[str, Any]]:
        cfg = ControlFlowGraph.from_function_ast(func_node)
        opened_lines: Dict[str, int] = {}

        def _transfer(block: BasicBlock, state: Dict[str, str], _edge: Any = None) -> Dict[str, str]:
            out = dict(state)
            for stmt in block.statements:
                if isinstance(stmt, ast.With):
                    for item in stmt.items:
                        if isinstance(item.optional_vars, ast.Name):
                            out[item.optional_vars.id] = cls.CLOSED
                elif isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
                    func = stmt.value.func
                    if isinstance(func, ast.Name) and func.id == "open":
                        for tgt in stmt.targets:
                            if isinstance(tgt, ast.Name):
                                out[tgt.id] = cls.OPEN
                                opened_lines.setdefault(tgt.id, getattr(stmt, "lineno", 1))
                elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    call = stmt.value
                    if isinstance(call.func, ast.Attribute) and call.func.attr == "close" and isinstance(call.func.value, ast.Name):
                        out[call.func.value.id] = cls.CLOSED
                elif isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Name):
                    out[stmt.value.id] = cls.ESCAPED
            return out

        def _join(states: List[Dict[str, str]]) -> Dict[str, str]:
            merged: Dict[str, str] = {}
            for st in states:
                for k, v in st.items():
                    prev = merged.get(k)
                    if prev is None:
                        merged[k] = v
                    elif cls.OPEN in (prev, v):
                        merged[k] = cls.OPEN
                    elif cls.ESCAPED in (prev, v):
                        merged[k] = cls.ESCAPED
                    else:
                        merged[k] = cls.CLOSED
            return merged

        in_states, _ = WorklistSolver(cfg, dict, _join, _transfer).solve()
        leaks: List[Dict[str, Any]] = []
        leaked_vars: Set[str] = set()
        for bid, block in cfg.blocks.items():
            if bid == cfg.exit_id or not block.successors:
                out_state = _transfer(block, in_states.get(bid, {}))
                for var_name, st in out_state.items():
                    if st == cls.OPEN and var_name not in leaked_vars:
                        leaked_vars.add(var_name)
                        leaks.append({"variable": var_name, "line": opened_lines.get(var_name, 1), "state": cls.OPEN})
        return leaks


class DeadStoreAnalysis:
    """Detects local variable assignments overwritten or never read before exit."""

    @classmethod
    def find_dead_stores(cls, func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        pending_write: Dict[str, int] = {}

        for stmt in func_node.body:
            if isinstance(stmt, ast.Assign):
                for node in ast.walk(stmt.value):
                    if isinstance(node, ast.Name):
                        pending_write.pop(node.id, None)
                for tgt in stmt.targets:
                    if isinstance(tgt, ast.Name):
                        if tgt.id in pending_write and not tgt.id.startswith("_"):
                            findings.append(
                                {
                                    "variable": tgt.id,
                                    "line": pending_write[tgt.id],
                                }
                            )
                        pending_write[tgt.id] = getattr(stmt, "lineno", 1)
            else:
                for node in ast.walk(stmt):
                    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                        pending_write.pop(node.id, None)

        for var_name, lineno in pending_write.items():
            if not var_name.startswith("_"):
                findings.append({"variable": var_name, "line": lineno})
        return findings
