import ast
import hashlib
import re
from pathlib import Path


def _fingerprint(rule_id: str, rel_path: str, snippet: str) -> str:
    raw = f"{rule_id}:{rel_path}:{snippet.strip()}".encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()[:16]


def analyze_python(path: Path, rel_path: str, content: str) -> dict:
    loc = sum(1 for line in content.splitlines() if line.strip())
    issues = []
    complexity = 1
    try:
        tree = ast.parse(content, filename=rel_path)
    except SyntaxError as exc:
        return {
            "state": "PARSE_ERROR",
            "error": str(exc),
            "issues": [],
            "metrics": {"loc": loc, "cyclomatic_complexity": 0},
        }

    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With)):
            complexity += 1
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
            issues.append({
                "ruleId": "PY-S001",
                "severity": "HIGH",
                "category": "VULNERABILITY",
                "fingerprint": _fingerprint("PY-S001", rel_path, node.func.id),
                "primaryLocation": {"file": rel_path, "startLine": node.lineno, "endLine": node.lineno},
                "message": f"Uso inseguro de {node.func.id}() detectado.",
            })

    return {
        "state": "ANALYZED_SUCCESS",
        "issues": issues,
        "metrics": {"loc": loc, "cyclomatic_complexity": complexity},
    }


def analyze_csharp(path: Path, rel_path: str, content: str) -> dict:
    lines = content.splitlines()
    loc = sum(1 for line in lines if line.strip())
    complexity = 1 + sum(len(re.findall(r"\b(if|for|foreach|while|catch|case)\b", line)) for line in lines)
    issues = []
    for idx, line in enumerate(lines, start=1):
        if "Console.WriteLine" in line:
            issues.append({
                "ruleId": "CS-M001",
                "severity": "LOW",
                "category": "CODE_SMELL",
                "fingerprint": _fingerprint("CS-M001", rel_path, line),
                "primaryLocation": {"file": rel_path, "startLine": idx, "endLine": idx},
                "message": "Evite Console.WriteLine em código de produção.",
            })
    return {
        "state": "ANALYZED_SUCCESS",
        "issues": issues,
        "metrics": {"loc": loc, "cyclomatic_complexity": complexity},
    }


def analyze_java(path: Path, rel_path: str, content: str) -> dict:
    lines = content.splitlines()
    loc = sum(1 for line in lines if line.strip())
    complexity = 1 + sum(len(re.findall(r"\b(if|for|while|catch|case)\b", line)) for line in lines)
    issues = []
    for idx, line in enumerate(lines, start=1):
        if "System.out.println" in line:
            issues.append({
                "ruleId": "JV-M001",
                "severity": "LOW",
                "category": "CODE_SMELL",
                "fingerprint": _fingerprint("JV-M001", rel_path, line),
                "primaryLocation": {"file": rel_path, "startLine": idx, "endLine": idx},
                "message": "Substitua System.out.println por um logger.",
            })
    return {
        "state": "ANALYZED_SUCCESS",
        "issues": issues,
        "metrics": {"loc": loc, "cyclomatic_complexity": complexity},
    }


def analyze_sql(path: Path, rel_path: str, content: str) -> dict:
    lines = content.splitlines()
    loc = sum(1 for line in lines if line.strip())
    issues = []
    for idx, line in enumerate(lines, start=1):
        if re.search(r"\bSELECT\s+\*", line, re.IGNORECASE):
            issues.append({
                "ruleId": "SQL-M001",
                "severity": "MEDIUM",
                "category": "CODE_SMELL",
                "fingerprint": _fingerprint("SQL-M001", rel_path, line),
                "primaryLocation": {"file": rel_path, "startLine": idx, "endLine": idx},
                "message": "Evite SELECT * em consultas SQL.",
            })
    return {
        "state": "ANALYZED_SUCCESS",
        "issues": issues,
        "metrics": {"loc": loc, "cyclomatic_complexity": 1},
    }


ANALYZERS = {
    ".py": ("python", analyze_python),
    ".cs": ("csharp", analyze_csharp),
    ".java": ("java", analyze_java),
    ".sql": ("sql", analyze_sql),
}
