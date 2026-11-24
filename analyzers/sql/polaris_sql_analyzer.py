from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

ANALYZER_ID = "polaris-sql-analyzer"
ANALYZER_VERSION = "2.0.0"
CONTRACT_VERSION = "1.0.0"
SUPPORTED_DIALECTS = ("postgres", "tsql", "mysql", "oracle")


def analyze_sql_file(file_path: Path, root_dir: Path, dialect: str = "postgres") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Analyze a SQL file statically using SQLGlot without connecting to any DB."""
    issues: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    rel_path = file_path.resolve().relative_to(root_dir.resolve()).as_posix()

    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        diagnostics.append({"type": "read_error", "file": rel_path, "message": str(exc)})
        return issues, diagnostics

    if not source.strip():
        return issues, diagnostics

    try:
        statements = sqlglot.parse(source, read=dialect)
    except ParseError as exc:
        diagnostics.append({"type": "syntax_error", "file": rel_path, "message": str(exc)})
        return issues, diagnostics

    import importlib.util
    import sys as _sys
    _re_path = Path(__file__).with_name("rules_engine.py")
    _re_spec = importlib.util.spec_from_file_location("polaris_sql_rules_engine", _re_path)
    assert _re_spec and _re_spec.loader
    _re_mod = importlib.util.module_from_spec(_re_spec)
    _sys.modules[_re_spec.name] = _re_mod
    _re_spec.loader.exec_module(_re_mod)

    import os as _os
    disabled = {r.strip() for r in _os.getenv("POLARIS_DISABLED_RULES", "").split(",") if r.strip()}
    for stmt in statements:
        if stmt is None:
            continue
        for rule in _re_mod.SQL_RULES:
            if rule.rule_id in disabled:
                continue
            msg = rule.check(stmt)
            if msg:
                issues.append({
                    "ruleId": rule.rule_id,
                    "language": "sql",
                    "severity": rule.severity,
                    "location": {"file": rel_path, "startLine": 1, "startColumn": 1},
                    "message": msg,
                })

    issues.sort(key=lambda i: (i["location"]["file"], i["location"]["startLine"], i["ruleId"]))
    return issues, diagnostics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=ANALYZER_ID, description="POLARIS SQL Analyzer (SQLGlot)")
    parser.add_argument("--version", action="version", version=f"{ANALYZER_ID} {ANALYZER_VERSION}")
    parser.add_argument("--project", default="default-project")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--dialect", default="postgres", choices=SUPPORTED_DIALECTS)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args(argv)

    all_issues: list[dict[str, Any]] = []
    all_diagnostics: list[dict[str, Any]] = []

    for f in sorted(args.files):
        issues, diags = analyze_sql_file(f, args.root, dialect=args.dialect)
        all_issues.extend(issues)
        all_diagnostics.extend(diags)

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
