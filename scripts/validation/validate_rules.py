from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from polaris_server.rule_metrics import RuleEvalCase, compute_rule_metrics


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_inventory() -> list[dict[str, str]]:
    """Load the 200-rule inventory directly from the 4 analyzer implementations."""
    inventory: list[dict[str, str]] = []

    py_mod = _load_module("polaris_py_rules_inv", ROOT / "analyzers" / "python" / "rules_engine.py")
    for r in py_mod.PYTHON_RULES:
        inventory.append({"ruleId": r.rule_id, "language": "python", "name": r.name, "category": r.category, "severity": r.severity})

    sql_mod = _load_module("polaris_sql_rules_inv", ROOT / "analyzers" / "sql" / "rules_engine.py")
    for r in sql_mod.SQL_RULES:
        inventory.append({"ruleId": r.rule_id, "language": "sql", "name": r.name, "category": r.category, "severity": r.severity})

    cs_text = (ROOT / "analyzers" / "csharp" / "CSharpRules.cs").read_text(encoding="utf-8")
    for m in re.finditer(r'new\("(?P<id>CS-[A-Z]+-\d+)",\s*"(?P<name>[^"]+)",\s*"(?P<cat>[^"]+)",\s*"(?P<sev>[^"]+)"', cs_text):
        inventory.append({"ruleId": m.group("id"), "language": "csharp", "name": m.group("name"), "category": m.group("cat"), "severity": m.group("sev")})
    for m in re.finditer(r'\("(?P<id>CS-[A-Z]+-\d+)",\s*"(?P<name>[^"]+)",\s*"(?P<cat>[^"]+)",\s*"(?P<sev>[^"]+)"', cs_text):
        if not any(x["ruleId"] == m.group("id") for x in inventory):
            inventory.append({"ruleId": m.group("id"), "language": "csharp", "name": m.group("name"), "category": m.group("cat"), "severity": m.group("sev")})

    jv_text = (ROOT / "analyzers" / "java" / "src" / "main" / "java" / "com" / "polaris" / "analyzer" / "JavaRulesEngine.java").read_text(encoding="utf-8")
    for m in re.finditer(r'new JavaRuleDef\("(?P<id>JV-[A-Z]+-\d+)",\s*"(?P<name>[^"]+)",\s*"(?P<cat>[^"]+)",\s*"(?P<sev>[^"]+)"', jv_text):
        inventory.append({"ruleId": m.group("id"), "language": "java", "name": m.group("name"), "category": m.group("cat"), "severity": m.group("sev")})
    for m in re.finditer(r'\{"(?P<id>JV-[A-Z]+-\d+)",\s*"(?P<name>[^"]+)",\s*"(?P<cat>[^"]+)",\s*"(?P<sev>[^"]+)"', jv_text):
        if not any(x["ruleId"] == m.group("id") for x in inventory):
            inventory.append({"ruleId": m.group("id"), "language": "java", "name": m.group("name"), "category": m.group("cat"), "severity": m.group("sev")})

    semantic_extras = [
        {"ruleId": "PY-SEM-NULL-001", "language": "python", "name": "Potential null dereference", "category": "reliability", "severity": "MAJOR"},
        {"ruleId": "PY-SEM-UNREACH-001", "language": "python", "name": "Unreachable code after terminating statement", "category": "reliability", "severity": "MAJOR"},
        {"ruleId": "PY-SEM-RES-001", "language": "python", "name": "Unclosed resource", "category": "reliability", "severity": "MAJOR"},
        {"ruleId": "PY-SEM-DEAD-001", "language": "python", "name": "Dead store", "category": "maintainability", "severity": "MINOR"},
        {"ruleId": "CS-SEM-UNREACH-001", "language": "csharp", "name": "Unreachable code in CFG", "category": "reliability", "severity": "MAJOR"},
        {"ruleId": "JV-SEM-UNREACH-001", "language": "java", "name": "Unreachable code after terminating statement", "category": "reliability", "severity": "MAJOR"},
    ]
    existing_ids = {x["ruleId"] for x in inventory}
    for extra in semantic_extras:
        if extra["ruleId"] not in existing_ids:
            inventory.append(extra)

    return inventory


def validate_fixtures_for_rule(rule: dict[str, str], fixtures_dir: Path) -> tuple[bool, list[RuleEvalCase], list[str]]:
    """Validate that a rule has >=3 positive, >=3 negative, >=2 edge cases and evaluate them."""
    fpath = fixtures_dir / rule["language"] / f"{rule['ruleId']}.json"
    pilot_fpath = ROOT / "tests" / "fixtures" / "pilot_160" / rule["language"] / f"{rule['ruleId']}.json"
    use_pilot_fallback = fixtures_dir == (ROOT / "tests" / "fixtures" / "rules")
    if use_pilot_fallback and pilot_fpath.exists():
        fpath = pilot_fpath
    elif not fpath.exists():
        return False, [], [f"Missing fixture file: {fpath}"]
    data = json.loads(fpath.read_text(encoding="utf-8"))
    cases_raw = data.get("cases", [])
    pos = [c for c in cases_raw if c.get("kind") == "positive"]
    neg = [c for c in cases_raw if c.get("kind") == "negative"]
    edge = [c for c in cases_raw if c.get("kind") == "edge"]
    errors: list[str] = []
    if len(pos) < 3:
        errors.append(f"{rule['ruleId']}: expected >=3 positive cases, got {len(pos)}")
    if len(neg) < 3:
        errors.append(f"{rule['ruleId']}: expected >=3 negative cases, got {len(neg)}")
    if len(edge) < 2:
        errors.append(f"{rule['ruleId']}: expected >=2 edge cases, got {len(edge)}")
    if errors:
        return False, [], errors

    eval_cases = []
    for c in cases_raw:
        if "code" not in c:
            return False, [], [f"{rule['ruleId']}: fixture case {c.get('caseId')} missing 'code' (simulated validation forbidden)"]

    lang = rule["language"]
    if lang in ("csharp", "java"):
        ext = ".cs" if lang == "csharp" else ".java"
        with tempfile.TemporaryDirectory() as td:
            tpath = Path(td)
            case_files: list[tuple[dict[str, Any], Path]] = []
            for idx, c in enumerate(cases_raw):
                fpath_tmp = tpath / f"case_{idx}{ext}"
                fpath_tmp.write_text(c["code"], encoding="utf-8")
                case_files.append((c, fpath_tmp))

            if lang == "csharp":
                dll = ROOT / "analyzers" / "csharp" / "bin" / "Release" / "net10.0" / "PolarisCSharpAnalyzer.dll"
                cmd = ["dotnet", str(dll), "--root", str(tpath), *[str(p) for _, p in case_files]]
            else:
                jar = ROOT / "analyzers" / "java" / "target" / "polaris-java-analyzer.jar"
                cmd = ["java", "-jar", str(jar), "--root", str(tpath), *[str(p) for _, p in case_files]]

            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.returncode != 0:
                return False, [], [f"{rule['ruleId']}: {lang} analyzer exited with {proc.returncode}: {proc.stderr[:200]}"]
            try:
                payload = json.loads(proc.stdout)
            except json.JSONDecodeError as exc:
                return False, [], [f"{rule['ruleId']}: invalid JSON from {lang} analyzer: {exc}"]

            issues_by_file: dict[str, list[dict[str, Any]]] = {}
            for issue in payload.get("issues", []):
                f_rel = issue.get("location", {}).get("file", "")
                issues_by_file.setdefault(f_rel, []).append(issue)

            for c, fpath_tmp in case_files:
                observed = any(i.get("ruleId") == rule["ruleId"] for i in issues_by_file.get(fpath_tmp.name, []))
                exp = bool(c.get("expectedPositive", c.get("expected")))
                ec = RuleEvalCase(rule["ruleId"], exp, observed)
                eval_cases.append(ec)
                if ec.expected_positive != ec.detected:
                    errors.append(f"{rule['ruleId']}: case {c.get('caseId', '?')} ({c.get('kind', '?')}) expected={exp} observed={observed}")
    else:
        for c in cases_raw:
            with tempfile.TemporaryDirectory() as td:
                tpath = Path(td)
                ext = ".py" if lang == "python" else ".sql"
                fpath_tmp = tpath / f"case{ext}"
                fpath_tmp.write_text(c["code"], encoding="utf-8")
                if lang == "python":
                    py_anl = _load_module("polaris_py_anl_exec", ROOT / "analyzers" / "python" / "polaris_python_analyzer.py")
                    issues, _ = py_anl.analyze_python_file(fpath_tmp, tpath)
                else:
                    sql_anl = _load_module("polaris_sql_anl_exec", ROOT / "analyzers" / "sql" / "polaris_sql_analyzer.py")
                    issues, _ = sql_anl.analyze_sql_file(fpath_tmp, tpath)
                observed = any(i["ruleId"] == rule["ruleId"] for i in issues)
            exp = bool(c.get("expectedPositive", c.get("expected")))
            ec = RuleEvalCase(rule["ruleId"], exp, observed)
            eval_cases.append(ec)
            if ec.expected_positive != ec.detected:
                errors.append(f"{rule['ruleId']}: case {c.get('caseId', '?')} ({c.get('kind', '?')}) expected={exp} observed={observed}")
    passed = all(ec.expected_positive == ec.detected for ec in eval_cases)
    return passed, eval_cases, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="POLARIS 2.0 Automated Rule Validator")
    parser.add_argument("--language", choices=["python", "csharp", "java", "sql"])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--pilot", action="store_true", help="Validate the 20-rule / 160-case pilot")
    parser.add_argument("--rule", help="Validate a single ruleId")
    parser.add_argument("--fixtures-dir", type=Path, default=ROOT / "tests" / "fixtures" / "rules")
    parser.add_argument("--json", type=Path, help="Optional JSON output path")
    args = parser.parse_args(argv)

    t0 = time.perf_counter()
    inventory = load_inventory()
    if args.pilot:
        if args.fixtures_dir == ROOT / "tests" / "fixtures" / "rules":
            args.fixtures_dir = ROOT / "tests" / "fixtures" / "pilot_160"
        pilot_ids = {
            "PY-SYN-001", "PY-REL-001", "PY-SEM-001", "PY-SEC-001", "PY-MNT-001",
            "CS-SYN-001", "CS-SEM-001", "CS-REL-001", "CS-SEC-001", "CS-MNT-001",
            "JV-SYN-001", "JV-SEM-001", "JV-REL-001", "JV-SEC-001", "JV-MNT-001",
            "SQL-SYN-001", "SQL-SYN-002", "SQL-SYN-003", "SQL-CTX-001", "SQL-CTX-002",
        }
        target_rules = [r for r in inventory if r["ruleId"] in pilot_ids]
    elif args.language:
        target_rules = [r for r in inventory if r["language"] == args.language]
    elif args.rule:
        target_rules = [r for r in inventory if r["ruleId"] == args.rule]
    else:
        target_rules = inventory

    if not target_rules:
        print("ERROR: No matching rules found.", file=sys.stderr)
        return 1

    all_eval_cases: list[RuleEvalCase] = []
    all_errors: list[str] = []
    passed_rules = 0
    failed_rules = 0
    not_executed_rules = 0
    infra_errors = 0

    for rule in target_rules:
        ok, evals, errs = validate_fixtures_for_rule(rule, args.fixtures_dir)
        all_eval_cases.extend(evals)
        all_errors.extend(errs)
        if not evals:
            not_executed_rules += 1
            infra_errors += len(errs)
        elif ok:
            passed_rules += 1
        else:
            failed_rules += 1

    metrics = compute_rule_metrics(all_eval_cases)
    elapsed = round(time.perf_counter() - t0, 4)

    cases_executed = len(all_eval_cases)
    cases_passed = sum(1 for ec in all_eval_cases if ec.expected_positive == ec.detected)
    cases_failed = cases_executed - cases_passed
    cases_not_executed = 0
    cases_total = cases_executed + cases_not_executed

    summary = {
        "rules_checked": len(target_rules),
        "rules_passed": passed_rules,
        "rules_failed": failed_rules,
        "rules_not_executed": not_executed_rules,
        "cases_total": cases_total,
        "cases_executed": cases_executed,
        "cases_passed": cases_passed,
        "cases_failed": cases_failed,
        "cases_not_executed": cases_not_executed,
        "infrastructure_errors": infra_errors,
        "elapsed_seconds": elapsed,
        "errors": all_errors[:50],
        "metrics": metrics,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(
        f"RULES_CHECKED={len(target_rules)} RULES_PASSED={passed_rules} "
        f"RULES_FAILED={failed_rules} RULES_NOT_EXECUTED={not_executed_rules} "
        f"CASES_TOTAL={cases_total} CASES_EXECUTED={cases_executed} "
        f"CASES_PASSED={cases_passed} CASES_FAILED={cases_failed} "
        f"CASES_NOT_EXECUTED={cases_not_executed} INFRASTRUCTURE_ERRORS={infra_errors} "
        f"ERRORS={len(all_errors)} TIME={elapsed}s"
    )
    return 0 if not all_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
