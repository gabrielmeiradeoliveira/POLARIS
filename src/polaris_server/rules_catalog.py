from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuleMetadata:
    ruleId: str
    name: str
    description: str
    language: str
    category: str  # RELIABILITY | MAINTAINABILITY | SECURITY
    type: str  # BUG | CODE_SMELL | VULNERABILITY
    severity: str
    status: str
    version: str
    remediationMinutes: int
    tags: tuple[str, ...]


RULES_CATALOG: tuple[RuleMetadata, ...] = (
    RuleMetadata("PY-SYN-001", "Avoid eval/exec", "Detects dynamic code execution via eval() or exec().", "python", "SECURITY", "VULNERABILITY", "MAJOR", "READY", "1.0.0", 15, ("security", "cwe-95")),
    RuleMetadata("PY-SEM-001", "Mutable default argument", "Detects mutable default arguments in Python function definitions.", "python", "RELIABILITY", "BUG", "MINOR", "READY", "1.0.0", 10, ("pitfall", "astroid")),
    RuleMetadata("CS-SYN-001", "Avoid empty catch blocks", "Detects empty catch blocks that swallow exceptions.", "csharp", "RELIABILITY", "BUG", "MAJOR", "READY", "1.0.0", 10, ("error-handling", "roslyn")),
    RuleMetadata("CS-SEM-001", "Method returns null literal", "Detects non-void methods returning null literals.", "csharp", "MAINTAINABILITY", "CODE_SMELL", "MINOR", "READY", "1.0.0", 10, ("nullability", "roslyn")),
    RuleMetadata("JV-SYN-001", "Avoid empty catch blocks", "Detects empty catch clauses in Java code.", "java", "RELIABILITY", "BUG", "MAJOR", "READY", "1.0.0", 10, ("error-handling", "javaparser")),
    RuleMetadata("JV-SEM-001", "Avoid System.out/err.println", "Detects direct console printing instead of structured logging.", "java", "MAINTAINABILITY", "CODE_SMELL", "MINOR", "READY", "1.0.0", 5, ("logging", "javaparser")),
    RuleMetadata("SQL-SYN-001", "Avoid SELECT *", "Detects wildcard column selection in SQL queries.", "sql", "MAINTAINABILITY", "CODE_SMELL", "MINOR", "READY", "1.0.0", 5, ("sqlglot", "performance")),
    RuleMetadata("SQL-CTX-001", "DELETE/UPDATE without WHERE", "Detects destructive DML statements without a WHERE clause.", "sql", "RELIABILITY", "BUG", "MAJOR", "READY", "1.0.0", 15, ("sqlglot", "safety")),
)


_ROOT = Path(__file__).resolve().parents[2]


def _load_py_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module {name} from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_production_inventory() -> list[dict[str, Any]]:
    """Load the 210-rule inventory directly from the 4 analyzer implementations."""
    inventory: list[dict[str, Any]] = []

    py_mod = _load_py_module("polaris_py_rules_prod", _ROOT / "analyzers" / "python" / "rules_engine.py")
    for r in py_mod.PYTHON_RULES:
        inventory.append(
            {
                "ruleId": r.rule_id,
                "name": r.name,
                "description": getattr(r, "message", r.name),
                "language": "python",
                "category": r.category,
                "severity": r.severity,
            }
        )

    cs_text = (_ROOT / "analyzers" / "csharp" / "CSharpRules.cs").read_text(encoding="utf-8")
    for m in re.finditer(r'new\("(?P<id>CS-[A-Z]+-\d+)",\s*"(?P<name>[^"]+)",\s*"(?P<cat>[^"]+)",\s*"(?P<sev>[^"]+)"', cs_text):
        inventory.append({"ruleId": m.group("id"), "name": m.group("name"), "description": m.group("name"), "language": "csharp", "category": m.group("cat"), "severity": m.group("sev")})
    for m in re.finditer(r'\("(?P<id>CS-[A-Z]+-\d+)",\s*"(?P<name>[^"]+)",\s*"(?P<cat>[^"]+)",\s*"(?P<sev>[^"]+)"', cs_text):
        if not any(x["ruleId"] == m.group("id") for x in inventory):
            inventory.append({"ruleId": m.group("id"), "name": m.group("name"), "description": m.group("name"), "language": "csharp", "category": m.group("cat"), "severity": m.group("sev")})

    jv_text = (_ROOT / "analyzers" / "java" / "src" / "main" / "java" / "com" / "polaris" / "analyzer" / "JavaRulesEngine.java").read_text(encoding="utf-8")
    for m in re.finditer(r'new JavaRuleDef\("(?P<id>JV-[A-Z]+-\d+)",\s*"(?P<name>[^"]+)",\s*"(?P<cat>[^"]+)",\s*"(?P<sev>[^"]+)"', jv_text):
        inventory.append({"ruleId": m.group("id"), "name": m.group("name"), "description": m.group("name"), "language": "java", "category": m.group("cat"), "severity": m.group("sev")})
    for m in re.finditer(r'\{"(?P<id>JV-[A-Z]+-\d+)",\s*"(?P<name>[^"]+)",\s*"(?P<cat>[^"]+)",\s*"(?P<sev>[^"]+)"', jv_text):
        if not any(x["ruleId"] == m.group("id") for x in inventory):
            inventory.append({"ruleId": m.group("id"), "name": m.group("name"), "description": m.group("name"), "language": "java", "category": m.group("cat"), "severity": m.group("sev")})

    sql_mod = _load_py_module("polaris_sql_rules_prod", _ROOT / "analyzers" / "sql" / "rules_engine.py")
    for r in sql_mod.SQL_RULES:
        inventory.append({"ruleId": r.rule_id, "name": r.name, "description": getattr(r, "message", r.name), "language": "sql", "category": r.category, "severity": r.severity})

    semantic_extras = [
        {"ruleId": "PY-SEM-NULL-001", "language": "python", "name": "Potential null dereference", "description": "Potential null dereference", "category": "reliability", "severity": "MAJOR"},
        {"ruleId": "PY-SEM-UNREACH-001", "language": "python", "name": "Unreachable code after terminating statement", "description": "Unreachable code after terminating statement", "category": "reliability", "severity": "MAJOR"},
        {"ruleId": "PY-SEM-RES-001", "language": "python", "name": "Unclosed resource", "description": "Unclosed resource", "category": "reliability", "severity": "MAJOR"},
        {"ruleId": "PY-SEM-DEAD-001", "language": "python", "name": "Dead store", "description": "Dead store", "category": "maintainability", "severity": "MINOR"},
        {"ruleId": "CS-SEM-UNREACH-001", "language": "csharp", "name": "Unreachable code in CFG", "description": "Unreachable code in CFG", "category": "reliability", "severity": "MAJOR"},
        {"ruleId": "JV-SEM-UNREACH-001", "language": "java", "name": "Unreachable code after terminating statement", "description": "Unreachable code after terminating statement", "category": "reliability", "severity": "MAJOR"},
    ]
    existing_ids = {x["ruleId"] for x in inventory}
    for extra in semantic_extras:
        if extra["ruleId"] not in existing_ids:
            inventory.append(extra)

    return [
        {
            "ruleId": r["ruleId"],
            "name": r["name"],
            "description": r["description"],
            "language": r["language"],
            "category": r["category"],
            "severity": r["severity"],
            "cwe": None,
            "implementationStatus": "IMPLEMENTED",
            "validationStatus": "VALIDATED" if r["ruleId"].startswith("SQL-") else "IMPLEMENTED",
            "semanticCapability": "-SEM-" in r["ruleId"],
            "parameters": [],
        }
        for r in inventory
    ]


def query_rules(language: str | None = None, category: str | None = None, severity: str | None = None) -> list[dict]:
    items = []
    for r in RULES_CATALOG:
        if language and r.language != language.lower():
            continue
        if category and r.category != category.upper():
            continue
        if severity and r.severity != severity.upper():
            continue
        items.append(asdict(r))
    return items
