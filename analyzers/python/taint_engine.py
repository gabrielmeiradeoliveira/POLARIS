from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any

SOURCES = {"request.args.get", "request.form.get", "input", "sys.argv"}
SANITIZERS = {"shlex.quote", "os.path.basename", "int", "float"}
SINKS = {
    "cursor.execute": ("CWE-89", "SQL Injection"),
    "os.system": ("CWE-78", "Command Injection"),
    "subprocess.run": ("CWE-78", "Command Injection"),
    "open": ("CWE-22", "Path Traversal"),
}


@dataclass
class TaintFinding:
    rule_id: str
    cwe: str
    category: str
    line: int
    message: str
    flow_steps: list[dict[str, Any]] = field(default_factory=list)
    confidence: str = "HIGH"


_TAINT_FAST_PATH_TOKENS = tuple(SOURCES) + tuple(SINKS.keys())


def has_taint_tokens(source_code: str) -> bool:
    """Fast-path pre-filter: return True only if source_code contains at least one source or sink token."""
    return any(tok in source_code for tok in _TAINT_FAST_PATH_TOKENS)


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        parts = [node.func.attr]
        cur = node.func.value
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""


def _expr_taint(node: ast.AST, tainted: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]] | None:
    if isinstance(node, ast.Name) and node.id in tainted:
        return tainted[node.id]
    if isinstance(node, ast.Call):
        cname = _call_name(node)
        if cname in SANITIZERS:
            return None
        if cname in SOURCES:
            return [{"line": node.lineno, "kind": "SOURCE", "detail": f"Untrusted input from {cname}()"}]
    if isinstance(node, ast.JoinedStr):
        for val in node.values:
            if isinstance(val, ast.FormattedValue):
                t = _expr_taint(val.value, tainted)
                if t:
                    return t + [{"line": node.lineno, "kind": "PROPAGATION", "detail": "Formatted into f-string"}]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        lt = _expr_taint(node.left, tainted)
        rt = _expr_taint(node.right, tainted)
        if lt or rt:
            return (lt or rt or []) + [{"line": node.lineno, "kind": "PROPAGATION", "detail": "String concatenation"}]
    return None


def analyze_python_taint(tree: ast.AST, source_code: str | None = None) -> list[TaintFinding]:
    """Run intraprocedural taint analysis on each function in a Python AST."""
    if source_code is not None and not has_taint_tokens(source_code):
        return []
    findings: list[TaintFinding] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        tainted: dict[str, list[dict[str, Any]]] = {}
        for stmt in ast.walk(fn):
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                var = stmt.targets[0].id
                t = _expr_taint(stmt.value, tainted)
                if t:
                    tainted[var] = t + [{"line": stmt.lineno, "kind": "PROPAGATION", "detail": f"Assigned to '{var}'"}]
                else:
                    tainted.pop(var, None)
            elif isinstance(stmt, ast.Call):
                cname = _call_name(stmt)
                if cname in SINKS and stmt.args:
                    # Parameterized cursor.execute(sql, params) with 2+ args is safe if sql itself isn't tainted
                    t = _expr_taint(stmt.args[0], tainted)
                    if t:
                        cwe, label = SINKS[cname]
                        steps = t + [{"line": stmt.lineno, "kind": "SINK", "detail": f"Reached {cname}()"}]
                        findings.append(TaintFinding("PY-TAINT-001", cwe, label, stmt.lineno, f"Tainted data reaches {cname}() ({cwe})", steps))
    return findings


def analyze_python_project(files: dict[str, str]) -> list[TaintFinding]:
    """Project-oriented interprocedural Python taint analysis across multiple files."""
    func_index: dict[str, tuple[str, ast.FunctionDef]] = {}
    for rel, src in files.items():
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_index[node.name] = (rel, node)

    project_sinks = {
        **SINKS,
        "session.execute": ("CWE-89", "SQL Injection"),
        "execute": ("CWE-89", "SQL Injection"),
        "subprocess.Popen": ("CWE-78", "Command Injection"),
        "Path.read_text": ("CWE-22", "Path Traversal"),
        "read_text": ("CWE-22", "Path Traversal"),
    }

    findings: list[TaintFinding] = []

    def _trace(fn_node: ast.FunctionDef, cur_file: str, steps: list[dict[str, Any]], visited: set[str]) -> None:
        for node in ast.walk(fn_node):
            if isinstance(node, ast.Call):
                cname = _call_name(node)
                short = cname.split(".")[-1]
                if cname in project_sinks or short in project_sinks:
                    cwe, cat = project_sinks.get(cname) or project_sinks[short]
                    # Parameterized DB-API / SQLAlchemy with 2+ args and literal query is safe
                    if cwe == "CWE-89" and len(node.args) >= 2 and isinstance(node.args[0], ast.Constant):
                        continue
                    rule_id = "PY-TAINT-001" if cwe == "CWE-89" else ("PY-TAINT-002" if cwe == "CWE-78" else "PY-TAINT-003")
                    findings.append(
                        TaintFinding(
                            rule_id=rule_id,
                            cwe=cwe,
                            category=cat,
                            line=getattr(node, "lineno", 1),
                            message=f"Interprocedural {cat} ({cwe})",
                            flow_steps=[
                                *steps,
                                {"file": cur_file, "line": getattr(node, "lineno", 1), "kind": "SINK", "detail": f"{cat} sink '{cname}()'"},
                            ],
                        )
                    )
                elif short in func_index and short not in visited:
                    next_file, next_fn = func_index[short]
                    visited.add(short)
                    _trace(
                        next_fn,
                        next_file,
                        [*steps, {"file": cur_file, "line": getattr(node, "lineno", 1), "kind": "PROPAGATION", "detail": f"Call to {short}()"}],
                        visited,
                    )

    for fname, (rel, fnode) in func_index.items():
        is_entry = "controller" in rel.lower() or "route" in rel.lower() or "view" in rel.lower() or any(
            isinstance(d, ast.Call) and any(k in _call_name(d).lower() for k in ("route", "get", "post"))
            for d in fnode.decorator_list
        )
        if is_entry and fnode.args.args:
            _trace(
                fnode,
                rel,
                [{"file": rel, "line": fnode.lineno, "kind": "SOURCE", "detail": f"HTTP input in {fname}"}],
                {fname},
            )
    return findings
