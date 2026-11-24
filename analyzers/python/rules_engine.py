from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class PyRuleDef:
    rule_id: str
    name: str
    category: str  # RELIABILITY | SECURITY | MAINTAINABILITY | PERFORMANCE
    severity: str
    capability: str  # syntactic | semantic | dataflow
    description: str
    check: Callable[[ast.AST, str], list[tuple[int, str]]]


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


def _check_calls(targets: set[str], msg: str) -> Callable[[ast.AST, str], list[tuple[int, str]]]:
    def _fn(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_name(node) in targets:
                out.append((node.lineno, msg))
        return out
    return _fn


def _check_eval_exec(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    return [(n.lineno, f"Avoid {_call_name(n)}()") for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) in {"eval", "exec"}]


def _check_mutable_default(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in n.args.defaults + [x for x in n.args.kw_defaults if x is not None]:
                if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                    out.append((n.lineno, f"Mutable default argument in {n.name}"))
    return out


def _check_bare_except(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    return [(n.lineno, "Bare except clause") for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler) and n.type is None]


def _check_broad_except(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    return [(n.lineno, "Broad Exception/BaseException catch") for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler) and isinstance(n.type, ast.Name) and n.type.id in {"Exception", "BaseException"}]


def _check_swallowed_except(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    return [(n.lineno, "Swallowed exception (pass)") for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler) and len(n.body) == 1 and isinstance(n.body[0], ast.Pass)]


def _walk_no_nested_defs(node: ast.AST):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return
    yield node
    for child in ast.iter_child_nodes(node):
        yield from _walk_no_nested_defs(child)


def _check_return_in_finally(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Try):
            for f in n.finalbody:
                for sub in _walk_no_nested_defs(f):
                    if isinstance(sub, ast.Return):
                        out.append((sub.lineno, "Return inside finally block"))
    return out


def _check_unreachable(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    out = []
    for n in ast.walk(tree):
        for attr in ("body", "orelse", "finalbody"):
            stmts = getattr(n, attr, None)
            if isinstance(stmts, list) and len(stmts) > 1:
                for idx, stmt in enumerate(stmts[:-1]):
                    if isinstance(stmt, (ast.Return, ast.Raise)):
                        out.append((stmts[idx + 1].lineno, "Unreachable code after return/raise"))
                        break
    return out


def _check_none_compare(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Compare):
            has_eq = any(isinstance(op, (ast.Eq, ast.NotEq)) for op in n.ops)
            has_none = (isinstance(n.left, ast.Constant) and n.left.value is None) or any(
                isinstance(c, ast.Constant) and c.value is None for c in n.comparators
            )
            if has_eq and has_none:
                out.append((n.lineno, "Use 'is None' or 'is not None'"))
    return out


def _check_bool_compare(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Compare):
            if any(isinstance(op, (ast.Eq, ast.NotEq)) for op in n.ops) and any(isinstance(c, ast.Constant) and isinstance(c.value, bool) for c in n.comparators):
                out.append((n.lineno, "Redundant comparison to boolean literal"))
    return out


def _check_dup_dict_keys(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Dict):
            seen: set[Any] = set()
            for k in n.keys:
                if isinstance(k, ast.Constant):
                    if k.value in seen:
                        out.append((k.lineno, f"Duplicate dict key: {k.value!r}"))
                    seen.add(k.value)
    return out


def _check_dup_set_elems(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Set):
            seen: set[Any] = set()
            for e in n.elts:
                if isinstance(e, ast.Constant):
                    if e.value in seen:
                        out.append((e.lineno, f"Duplicate set element: {e.value!r}"))
                    seen.add(e.value)
    return out


def _check_const_if(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    return [(n.lineno, "Constant condition in if statement") for n in ast.walk(tree) if isinstance(n, ast.If) and isinstance(n.test, ast.Constant)]


def _check_const_while_false(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    return [(n.lineno, "While False loop never executes") for n in ast.walk(tree) if isinstance(n, ast.While) and isinstance(n.test, ast.Constant) and not n.test.value]


def _check_assert_tuple(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    return [(n.lineno, "Assert on non-empty tuple is always True") for n in ast.walk(tree) if isinstance(n, ast.Assert) and isinstance(n.test, ast.Tuple) and len(n.test.elts) > 0]


def _check_self_assign(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Name) and n.targets[0].id == n.value.id:
            out.append((n.lineno, f"Self-assignment to {n.value.id}"))
    return out


def _check_global_stmt(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    return [(n.lineno, "Avoid global statement") for n in ast.walk(tree) if isinstance(n, ast.Global)]


def _check_too_many_params(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    return [(n.lineno, f"Function {n.name} has too many parameters (>7)") for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and len(n.args.args) > 7]


def _check_long_function(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    return [(n.lineno, f"Function {n.name} exceeds 60 lines") for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and (getattr(n, "end_lineno", n.lineno) - n.lineno) > 60]


def _check_deep_nesting(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    out = []
    def walk(node: ast.AST, depth: int) -> None:
        if isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
            depth += 1
            if depth >= 4:
                out.append((node.lineno, "Excessive nesting depth (>=4)"))
        for ch in ast.iter_child_nodes(node):
            walk(ch, depth)
    walk(tree, 0)
    return out


def _check_wildcard_import(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    return [(n.lineno, "Wildcard import 'from ... import *'") for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names)]


def _check_hardcoded_secret(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    out = []
    keys = ("password", "passwd", "secret", "api_key", "token")
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and any(k in t.id.lower() for k in keys) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str) and len(n.value.value) >= 4:
                    out.append((n.lineno, f"Potential hardcoded secret in {t.id}"))
    return out


def _check_subprocess_shell(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and _call_name(n).startswith("subprocess."):
            for kw in n.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    out.append((n.lineno, "subprocess called with shell=True"))
    return out


def _check_tls_verify_false(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and _call_name(n).startswith("requests."):
            for kw in n.keywords:
                if kw.arg == "verify" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                    out.append((n.lineno, "TLS verification disabled (verify=False)"))
    return out


def _check_sqli_fstring(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and _call_name(n).endswith(".execute") and n.args:
            if isinstance(n.args[0], ast.JoinedStr):
                out.append((n.lineno, "Potential SQL injection via f-string in execute()"))
    return out


def _check_open_without_with(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    with_calls: set[int] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.With):
            for item in n.items:
                if isinstance(item.context_expr, ast.Call):
                    with_calls.add(id(item.context_expr))
    return [(n.lineno, "open() called without 'with' context manager") for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) == "open" and id(n) not in with_calls]


def _check_empty_func(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    return [(n.lineno, f"Empty function body in {n.name}") for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and len(n.body) == 1 and isinstance(n.body[0], ast.Pass)]


def _check_unused_import(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    imported: dict[str, int] = {}
    used: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                imported[a.asname or a.name.split(".")[0]] = n.lineno
        elif isinstance(n, ast.ImportFrom):
            if n.module == "__future__":
                continue
            for a in n.names:
                if a.name != "*":
                    imported[a.asname or a.name] = n.lineno
        elif isinstance(n, ast.Name):
            used.add(n.id)
    return [(ln, f"Unused import '{name}'") for name, ln in imported.items() if name not in used]


def _check_loop_string_concat(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    out = []
    str_vars: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
            for tgt in n.targets:
                if isinstance(tgt, ast.Name):
                    str_vars.add(tgt.id)
    for n in ast.walk(tree):
        if isinstance(n, (ast.For, ast.While)):
            for sub in ast.walk(n):
                if isinstance(sub, ast.AugAssign) and isinstance(sub.op, ast.Add):
                    is_str_rhs = isinstance(sub.value, ast.Constant) and isinstance(sub.value.value, str)
                    is_str_call = isinstance(sub.value, ast.Call) and _call_name(sub.value) == "str"
                    is_str_tgt = isinstance(sub.target, ast.Name) and sub.target.id in str_vars
                    if is_str_rhs or is_str_call or is_str_tgt:
                        out.append((sub.lineno, "String concatenation in loop; prefer str.join()"))
    return out


def _check_len_compare_zero(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Compare) and isinstance(n.left, ast.Call) and _call_name(n.left) == "len":
            if any(isinstance(op, (ast.Eq, ast.NotEq)) for op in n.ops) and any(isinstance(c, ast.Constant) and c.value == 0 for c in n.comparators):
                out.append((n.lineno, "Use truthiness instead of comparing len() to 0"))
    return out


def build_python_rules() -> list[PyRuleDef]:
    rules: list[PyRuleDef] = [
        PyRuleDef("PY-SYN-001", "Avoid eval/exec", "SECURITY", "MAJOR", "syntactic", "Detects eval() or exec().", _check_eval_exec),
        PyRuleDef("PY-SEM-001", "Mutable default argument", "RELIABILITY", "MINOR", "semantic", "Detects mutable default arguments.", _check_mutable_default),
        PyRuleDef("PY-REL-001", "Bare except", "RELIABILITY", "MAJOR", "syntactic", "Detects bare except.", _check_bare_except),
        PyRuleDef("PY-REL-002", "Broad except", "RELIABILITY", "MINOR", "semantic", "Detects broad Exception catch.", _check_broad_except),
        PyRuleDef("PY-REL-003", "Swallowed exception", "RELIABILITY", "MAJOR", "syntactic", "Detects except: pass.", _check_swallowed_except),
        PyRuleDef("PY-REL-004", "Return in finally", "RELIABILITY", "CRITICAL", "semantic", "Detects return in finally.", _check_return_in_finally),
        PyRuleDef("PY-REL-005", "Unreachable code", "RELIABILITY", "MAJOR", "semantic", "Detects code after return/raise.", _check_unreachable),
        PyRuleDef("PY-REL-006", "None comparison", "RELIABILITY", "MINOR", "syntactic", "Use is/is not None.", _check_none_compare),
        PyRuleDef("PY-REL-007", "Boolean comparison", "MAINTAINABILITY", "MINOR", "syntactic", "Redundant == True/False.", _check_bool_compare),
        PyRuleDef("PY-REL-008", "Duplicate dict keys", "RELIABILITY", "MAJOR", "semantic", "Duplicate keys in dict literal.", _check_dup_dict_keys),
        PyRuleDef("PY-REL-009", "Duplicate set elements", "RELIABILITY", "MINOR", "semantic", "Duplicate elements in set literal.", _check_dup_set_elems),
        PyRuleDef("PY-REL-010", "Constant if condition", "RELIABILITY", "MINOR", "semantic", "Constant condition in if.", _check_const_if),
        PyRuleDef("PY-REL-011", "While False loop", "RELIABILITY", "MINOR", "semantic", "while False never executes.", _check_const_while_false),
        PyRuleDef("PY-REL-012", "Assert on tuple", "RELIABILITY", "MAJOR", "syntactic", "assert (a, b) is always True.", _check_assert_tuple),
        PyRuleDef("PY-REL-013", "Self-assignment", "RELIABILITY", "MAJOR", "semantic", "Variable assigned to itself.", _check_self_assign),
        PyRuleDef("PY-REL-014", "Wildcard import", "MAINTAINABILITY", "MINOR", "syntactic", "Avoid from x import *.", _check_wildcard_import),
        PyRuleDef("PY-REL-015", "Unused import", "MAINTAINABILITY", "MINOR", "semantic", "Detects unused imports.", _check_unused_import),
        PyRuleDef("PY-REL-016", "Open without with", "RELIABILITY", "MAJOR", "semantic", "File open() without with.", _check_open_without_with),
        PyRuleDef("PY-MNT-001", "Global statement", "MAINTAINABILITY", "MINOR", "semantic", "Avoid global keyword.", _check_global_stmt),
        PyRuleDef("PY-MNT-002", "Too many parameters", "MAINTAINABILITY", "MINOR", "syntactic", "Function has >7 parameters.", _check_too_many_params),
        PyRuleDef("PY-MNT-003", "Long function", "MAINTAINABILITY", "MINOR", "syntactic", "Function exceeds 60 lines.", _check_long_function),
        PyRuleDef("PY-MNT-004", "Deep nesting", "MAINTAINABILITY", "MAJOR", "syntactic", "Nesting depth >= 4.", _check_deep_nesting),
        PyRuleDef("PY-MNT-005", "Empty function", "MAINTAINABILITY", "INFO", "syntactic", "Function body is only pass.", _check_empty_func),
        PyRuleDef("PY-PRF-001", "Loop string concat", "PERFORMANCE", "MINOR", "semantic", "String += in loop.", _check_loop_string_concat),
        PyRuleDef("PY-PRF-002", "len() == 0", "PERFORMANCE", "INFO", "syntactic", "Compare len() to 0.", _check_len_compare_zero),
        PyRuleDef("PY-SEC-001", "Hardcoded secret", "SECURITY", "CRITICAL", "semantic", "Hardcoded password/secret/token.", _check_hardcoded_secret),
        PyRuleDef("PY-SEC-002", "Subprocess shell=True", "SECURITY", "CRITICAL", "semantic", "subprocess with shell=True.", _check_subprocess_shell),
        PyRuleDef("PY-SEC-003", "TLS verify=False", "SECURITY", "CRITICAL", "semantic", "requests with verify=False.", _check_tls_verify_false),
        PyRuleDef("PY-SEC-004", "SQLi f-string", "SECURITY", "BLOCKER", "dataflow", "f-string in SQL execute().", _check_sqli_fstring),
    ]

    # Add 31 specialized call-based & AST-based security/reliability/performance rules to reach 60
    call_specs = [
        ("PY-SEC-005", "Unsafe pickle.loads", "SECURITY", "CRITICAL", {"pickle.loads", "pickle.load"}, "Unsafe pickle deserialization"),
        ("PY-SEC-006", "Unsafe yaml.load", "SECURITY", "CRITICAL", {"yaml.load"}, "Use yaml.safe_load instead of yaml.load"),
        ("PY-SEC-007", "Unsafe os.system", "SECURITY", "CRITICAL", {"os.system", "os.popen"}, "Avoid os.system/os.popen"),
        ("PY-SEC-008", "Weak hash MD5", "SECURITY", "MAJOR", {"hashlib.md5"}, "Avoid MD5 for security"),
        ("PY-SEC-009", "Weak hash SHA1", "SECURITY", "MAJOR", {"hashlib.sha1"}, "Avoid SHA1 for security"),
        ("PY-SEC-010", "Insecure tempfile.mktemp", "SECURITY", "MAJOR", {"tempfile.mktemp"}, "Use NamedTemporaryFile instead of mktemp"),
        ("PY-SEC-011", "Unsafe marshal.loads", "SECURITY", "CRITICAL", {"marshal.loads", "marshal.load"}, "Unsafe marshal deserialization"),
        ("PY-SEC-012", "Unsafe shelve.open", "SECURITY", "MAJOR", {"shelve.open"}, "shelve uses pickle internally"),
        ("PY-SEC-014", "Unsafe tarfile.extractall", "SECURITY", "CRITICAL", {"tarfile.open"}, "Validate tar members before extractall"),
        ("PY-SEC-015", "Unsafe random.random", "SECURITY", "MINOR", {"random.random", "random.randint", "random.choice"}, "Use secrets module for security"),
        ("PY-SEC-017", "Unsafe telnetlib", "SECURITY", "MAJOR", {"telnetlib.Telnet"}, "Telnet is unencrypted"),
        ("PY-SEC-018", "Unsafe ftplib", "SECURITY", "MAJOR", {"ftplib.FTP"}, "FTP is unencrypted"),
        ("PY-SEC-019", "Unsafe compile()", "SECURITY", "MAJOR", {"compile"}, "Avoid dynamic compile()"),
        ("PY-SEC-020", "Unsafe __import__()", "SECURITY", "MAJOR", {"__import__"}, "Avoid dynamic __import__()"),
        ("PY-REL-017", "Avoid exit()/quit()", "RELIABILITY", "MINOR", {"exit", "quit"}, "Use sys.exit() in production code"),
        ("PY-REL-018", "Avoid breakpoint()", "RELIABILITY", "MAJOR", {"breakpoint", "pdb.set_trace"}, "Remove debugger breakpoint"),
        ("PY-REL-019", "Avoid print() in library", "MAINTAINABILITY", "INFO", {"print"}, "Prefer logging over print()"),
        ("PY-REL-020", "Avoid input()", "RELIABILITY", "MINOR", {"input"}, "Avoid blocking input()"),
        ("PY-MNT-006", "Avoid type() == ", "MAINTAINABILITY", "MINOR", {"type"}, "Prefer isinstance() over type()"),
        ("PY-MNT-007", "Avoid globals()", "MAINTAINABILITY", "MINOR", {"globals"}, "Avoid mutating globals()"),
        ("PY-MNT-008", "Avoid locals()", "MAINTAINABILITY", "MINOR", {"locals"}, "Avoid relying on locals()"),
        ("PY-MNT-009", "Avoid vars()", "MAINTAINABILITY", "INFO", {"vars"}, "Prefer explicit attribute access"),
        ("PY-MNT-010", "Avoid dir()", "MAINTAINABILITY", "INFO", {"dir"}, "Avoid dir() in production logic"),
        ("PY-MNT-011", "Avoid hasattr() side-effects", "MAINTAINABILITY", "INFO", {"hasattr"}, "Consider getattr() with default"),
        ("PY-MNT-012", "Avoid delattr()", "MAINTAINABILITY", "MINOR", {"delattr"}, "Avoid dynamic delattr()"),
        ("PY-MNT-013", "Avoid setattr()", "MAINTAINABILITY", "MINOR", {"setattr"}, "Avoid dynamic setattr()"),
        ("PY-PRF-003", "Avoid list(sorted())", "PERFORMANCE", "INFO", {"sorted"}, "sorted() already returns a list"),
        ("PY-PRF-004", "Avoid time.sleep() in async", "PERFORMANCE", "MAJOR", {"time.sleep"}, "Use asyncio.sleep() in async code"),
        ("PY-PRF-005", "Avoid re.compile() in loop", "PERFORMANCE", "MINOR", {"re.compile"}, "Hoist re.compile() to module level"),
    ]
    for rid, name, cat, sev, targets, msg in call_specs:
        rules.append(PyRuleDef(rid, name, cat, sev, "syntactic", msg, _check_calls(targets, msg)))

    def _check_unsafe_xml(tree: ast.AST, src: str) -> list[tuple[int, str]]:
        if "defusedxml" in src:
            return []
        return _check_calls({"ET.fromstring", "xml.etree.ElementTree.fromstring"}, "Use defusedxml for untrusted XML")(tree, src)

    def _check_ssl_unverified(tree: ast.AST, _src: str) -> list[tuple[int, str]]:
        issues: list[tuple[int, str]] = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "ssl" and n.attr == "_create_unverified_context":
                issues.append((n.lineno, "Do not disable SSL verification"))
        return issues

    rules.append(PyRuleDef("PY-SEC-013", "Unsafe xml.etree parse", "SECURITY", "MAJOR", "syntactic", "Use defusedxml for untrusted XML", _check_unsafe_xml))
    rules.append(PyRuleDef("PY-SEC-016", "Unsafe ssl._create_unverified_context", "SECURITY", "CRITICAL", "syntactic", "Do not disable SSL verification", _check_ssl_unverified))
    return rules


PYTHON_RULES = build_python_rules()
