from __future__ import annotations

import argparse
import ast
import json
import uuid
from pathlib import Path
from typing import Any

import astroid
import libcst as cst

ANALYZER_ID = "polaris-python-analyzer"
ANALYZER_VERSION = "2.0.0"
CONTRACT_VERSION = "1.0.0"

RULES = [
    {
        "id": "PY-SYN-001",
        "name": "Avoid eval/exec",
        "description": "Detects calls to eval() or exec() in Python code.",
        "language": "python",
        "severity": "MAJOR",
        "type": "syntactic",
        "version": "1.0.0",
    },
    {
        "id": "PY-SEM-001",
        "name": "Mutable default argument",
        "description": "Detects mutable default arguments (list, dict, set) in function definitions.",
        "language": "python",
        "severity": "MINOR",
        "type": "semantic",
        "version": "1.0.0",
    },
]


def analyze_python_file(file_path: Path, root_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Analyze a single Python file statically without executing or importing it."""
    issues: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    rel_path = file_path.resolve().relative_to(root_dir.resolve()).as_posix()

    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        diagnostics.append({"type": "read_error", "file": rel_path, "message": str(exc)})
        return issues, diagnostics

    # 1. AST + LibCST syntactic parse
    try:
        tree = ast.parse(source, filename=rel_path)
        cst.parse_module(source)
    except SyntaxError as exc:
        diagnostics.append({
            "type": "syntax_error",
            "file": rel_path,
            "line": exc.lineno or 1,
            "message": str(exc.msg),
        })
        return issues, diagnostics

    # PY-SYN-001: eval/exec via AST
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
            issues.append({
                "ruleId": "PY-SYN-001",
                "language": "python",
                "severity": "MAJOR",
                "location": {
                    "file": rel_path,
                    "startLine": node.lineno,
                    "startColumn": node.col_offset + 1,
                },
                "message": f"Avoid dynamic execution with '{node.func.id}()'",
            })

    # 3. Execute expanded 60-rule AST engine
    import importlib.util
    import sys as _sys
    _re_mod = _sys.modules.get("polaris_py_rules_engine")
    if _re_mod is None:
        _re_path = Path(__file__).with_name("rules_engine.py")
        _re_spec = importlib.util.spec_from_file_location("polaris_py_rules_engine", _re_path)
        assert _re_spec and _re_spec.loader
        _re_mod = importlib.util.module_from_spec(_re_spec)
        _sys.modules[_re_spec.name] = _re_mod
        _re_spec.loader.exec_module(_re_mod)
    for rule in _re_mod.PYTHON_RULES:
        if rule.rule_id in ("PY-SYN-001", "PY-SEM-001"):
            continue
        for ln, msg in rule.check(tree, source):
            issues.append({
                "ruleId": rule.rule_id,
                "language": "python",
                "severity": rule.severity,
                "location": {"file": rel_path, "startLine": ln, "startColumn": 1},
                "message": msg,
            })

    # 2. Astroid semantic/scope inspection (no execution/import of target)
    try:
        module = astroid.parse(source, module_name=file_path.stem)
        for fn in module.nodes_of_class(astroid.FunctionDef):
            for default in fn.args.defaults or []:
                if isinstance(default, (astroid.List, astroid.Dict, astroid.Set)):
                    issues.append({
                        "ruleId": "PY-SEM-001",
                        "language": "python",
                        "severity": "MINOR",
                        "location": {
                            "file": rel_path,
                            "startLine": default.lineno or fn.lineno or 1,
                            "startColumn": (default.col_offset or 0) + 1,
                        },
                        "message": f"Mutable default argument in function '{fn.name}'",
                    })
    except Exception as exc:
        diagnostics.append({"type": "semantic_partial", "file": rel_path, "message": str(exc)})

    # 4. Second-generation semantic engine (CFG, Nullability, Unreachable code)
    try:
        _se_mod = _sys.modules.get("polaris_py_semantic_engine")
        if _se_mod is None:
            _se_path = Path(__file__).with_name("semantic_engine.py")
            _se_spec = importlib.util.spec_from_file_location("polaris_py_semantic_engine", _se_path)
            if _se_spec and _se_spec.loader:
                _se_mod = importlib.util.module_from_spec(_se_spec)
                _sys.modules[_se_spec.name] = _se_mod
                _se_spec.loader.exec_module(_se_mod)
        if _se_mod is not None:
            for fn_node in ast.walk(tree):
                if isinstance(fn_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for nf in _se_mod.NullabilityAnalysis.find_null_dereferences(fn_node):
                        issues.append({
                            "ruleId": "PY-SEM-NULL-001",
                            "language": "python",
                            "severity": "MAJOR",
                            "location": {
                                "file": rel_path,
                                "startLine": nf["line"] or 1,
                                "startColumn": 1,
                            },
                            "message": f"Potential None dereference on '{nf['variable']}.{nf['attribute']}' (state={nf['state']})",
                        })
                    cfg = _se_mod.ControlFlowGraph.from_function_ast(fn_node)
                    for blk in cfg.blocks.values():
                        if blk.label == "unreachable" and blk.statements:
                            issues.append({
                                "ruleId": "PY-SEM-UNREACH-001",
                                "language": "python",
                                "severity": "MINOR",
                                "location": {
                                    "file": rel_path,
                                    "startLine": getattr(blk.statements[0], "lineno", 1),
                                    "startColumn": 1,
                                },
                                "message": f"Unreachable code detected in function '{fn_node.name}'",
                            })
                    for rl in _se_mod.ResourceStateAnalysis.find_resource_leaks(fn_node):
                        issues.append({
                            "ruleId": "PY-SEM-RES-001",
                            "language": "python",
                            "severity": "MAJOR",
                            "location": {
                                "file": rel_path,
                                "startLine": rl["line"] or 1,
                                "startColumn": 1,
                            },
                            "message": f"Resource '{rl['variable']}' opened without guaranteed close()",
                        })
                    for ds in _se_mod.DeadStoreAnalysis.find_dead_stores(fn_node):
                        issues.append({
                            "ruleId": "PY-SEM-DEAD-001",
                            "language": "python",
                            "severity": "MINOR",
                            "location": {
                                "file": rel_path,
                                "startLine": ds["line"] or 1,
                                "startColumn": 1,
                            },
                            "message": f"Dead store: '{ds['variable']}' is overwritten before being read",
                        })
    except Exception as exc:
        diagnostics.append({"type": "semantic_engine_error", "file": rel_path, "message": str(exc)})

    import os as _os
    disabled = {r.strip() for r in _os.getenv("POLARIS_DISABLED_RULES", "").split(",") if r.strip()}
    if disabled:
        issues = [i for i in issues if i.get("ruleId") not in disabled]
    issues.sort(key=lambda i: (i["location"]["file"], i["location"]["startLine"], i["ruleId"]))
    return issues, diagnostics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=ANALYZER_ID, description="POLARIS Python Analyzer (AST, LibCST, Astroid)")
    parser.add_argument("--version", action="version", version=f"{ANALYZER_ID} {ANALYZER_VERSION}")
    parser.add_argument("--project", default="default-project")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args(argv)

    all_issues: list[dict[str, Any]] = []
    all_diagnostics: list[dict[str, Any]] = []
    project_sources: dict[str, str] = {}

    for f in sorted(args.files):
        issues, diags = analyze_python_file(f, args.root)
        all_issues.extend(issues)
        all_diagnostics.extend(diags)
        if f.exists():
            try:
                rel = f.resolve().relative_to(args.root.resolve()).as_posix()
            except ValueError:
                rel = f.name
            project_sources[rel] = f.read_text(encoding="utf-8", errors="replace")

    if project_sources:
        import importlib.util
        _te_path = Path(__file__).with_name("taint_engine.py")
        _te_spec = importlib.util.spec_from_file_location("polaris_py_taint_engine", _te_path)
        if _te_spec and _te_spec.loader:
            import sys as _sys
            _te_mod = importlib.util.module_from_spec(_te_spec)
            _sys.modules[_te_spec.name] = _te_mod
            _te_spec.loader.exec_module(_te_mod)
            for finding in _te_mod.analyze_python_project(project_sources):
                sink_file = finding.flow_steps[-1]["file"] if finding.flow_steps else ""
                all_issues.append({
                    "ruleId": finding.rule_id,
                    "language": "python",
                    "severity": "CRITICAL",
                    "location": {"file": sink_file, "startLine": finding.line, "startColumn": 1},
                    "message": finding.message,
                    "cwe": finding.cwe,
                    "flowSteps": finding.flow_steps,
                })

    status = "COMPLETED" if not all_diagnostics else "COMPLETED_WITH_WARNINGS"
    payload = {
        "schemaVersion": CONTRACT_VERSION,
        "analysisId": str(uuid.uuid4()),
        "projectKey": args.project,
        "branch": args.branch,
        "analyzer": {"id": ANALYZER_ID, "version": ANALYZER_VERSION},
        "status": status,
        "totalFiles": len(args.files),
        "diagnostics": all_diagnostics,
        "issues": all_issues,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
