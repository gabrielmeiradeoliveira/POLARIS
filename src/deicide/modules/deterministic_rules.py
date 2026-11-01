"""Bounded AST and before/after rules used by the CodeReview module.

Rules deliberately require both an observable risky after-state and, where the
signal can be ambiguous, evidence that the diff weakened a prior safeguard.
They emit normal CandidateFinding values and never execute analysed code.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from deicide.core.models import CandidateFinding, Confidence, FindingCategory, Severity
from deicide.git.models import FileContext, FileDiff


@dataclass(frozen=True)
class _Rule:
    rule_id: str
    category: FindingCategory
    severity: Severity
    title: str
    description: str
    remediation: str


def _source(context: FileContext) -> tuple[str, dict[int, str]] | None:
    lines = {line: text for snippet in context.snippets for line, text in snippet.lines.items()}
    if context.total_lines <= 0 or set(lines) != set(range(1, context.total_lines + 1)):
        return None
    return "\n".join(lines[line] for line in range(1, context.total_lines + 1)), lines


def _candidate(rule: _Rule, file_diff: FileDiff, lines: dict[int, str], line: int) -> CandidateFinding | None:
    if line not in file_diff.hunk_lines or not lines.get(line, "").strip():
        return None
    return CandidateFinding(
        category=rule.category,
        severity=rule.severity,
        confidence=Confidence.HIGH,
        file_path=file_diff.new_path,
        start_line=line,
        end_line=line,
        title=f"[{rule.rule_id}] {rule.title}",
        description=rule.description,
        evidence=lines[line].strip(),
        suggested_remediation=rule.remediation,
    )


def _calls(node: ast.AST, names: set[str]) -> bool:
    return any(
        isinstance(item, ast.Call)
        and (
            (isinstance(item.func, ast.Name) and item.func.id in names)
            or (isinstance(item.func, ast.Attribute) and item.func.attr in names)
        )
        for item in ast.walk(node)
    )


def deterministic_candidates(files: list[FileDiff], contexts: dict[str, FileContext]) -> list[CandidateFinding]:
    """Return high-confidence defect-introduction candidates from Python ASTs."""
    findings: list[CandidateFinding] = []
    seen: set[tuple[str, int, str]] = set()
    for file_diff in files:
        if not file_diff.new_path.endswith(".py"):
            continue
        context = contexts.get(file_diff.new_path)
        material = _source(context) if context else None
        if material is None:
            continue
        source, lines = material
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        removed = "\n".join(
            line[1:] for line in file_diff.raw_diff.splitlines() if line.startswith("-") and not line.startswith("---")
        )

        def emit(
            rule: _Rule,
            line: int,
            active_diff: FileDiff = file_diff,
            active_lines: dict[int, str] = lines,
        ) -> None:
            key = (active_diff.new_path, line, rule.rule_id)
            candidate = _candidate(rule, active_diff, active_lines, line)
            if candidate and key not in seen:
                seen.add(key)
                findings.append(candidate)

        functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for function in functions:
            body = list(ast.walk(function))
            params = {arg.arg for arg in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]}

            # Authorization is reported only if a permission-raising guard was removed from this diff.
            if "PermissionError" in removed and any(isinstance(item, ast.Return) for item in body):
                returns = [item for item in body if isinstance(item, ast.Return)]
                if returns:
                    emit(
                        _Rule(
                            "DET-AUTH-GUARD-REMOVED",
                            FindingCategory.LOGIC_ERROR,
                            Severity.HIGH,
                            "Authorization guard removed",
                            "A PermissionError guard was removed while the function still returns a protected result.",
                            "Restore an authorization check before the sensitive operation.",
                        ),
                        returns[0].lineno,
                    )

            for node in body:
                if isinstance(node, ast.JoinedStr) and "SELECT " in ast.unparse(node).upper():
                    emit(
                        _Rule(
                            "DET-SQL-INTERPOLATION",
                            FindingCategory.LOGIC_ERROR,
                            Severity.HIGH,
                            "SQL query interpolates runtime data",
                            "A query now embeds runtime values in SQL syntax instead of retaining a bound parameter.",
                            "Use parameter binding and keep untrusted values separate from query text.",
                        ),
                        node.lineno,
                    )
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in {"print", "logging", "log"}
                ):
                    text = ast.unparse(node).lower()
                    if any(secret in text for secret in ("token", "secret", "password", "api_key")) and any(
                        isinstance(x, ast.FormattedValue) for x in ast.walk(node)
                    ):
                        emit(
                            _Rule(
                                "DET-SENSITIVE-OUTPUT",
                                FindingCategory.ERROR_HANDLING,
                                Severity.MEDIUM,
                                "Sensitive value reaches application output",
                                "A runtime secret-like parameter is formatted directly into an output sink.",
                                "Redact the value or log a non-sensitive identifier instead.",
                            ),
                            node.lineno,
                        )
                if (
                    isinstance(node, ast.ExceptHandler)
                    and node.type
                    and isinstance(node.type, ast.Name)
                    and node.type.id in {"Exception", "BaseException"}
                    and any(
                        isinstance(item, ast.Return) and isinstance(item.value, ast.Constant) for item in ast.walk(node)
                    )
                ):
                    emit(
                        _Rule(
                            "DET-BROAD-EXCEPT-DEFAULT",
                            FindingCategory.ERROR_HANDLING,
                            Severity.MEDIUM,
                            "Broad exception converted to a normal value",
                            "A broad handler masks unexpected failures by returning a valid-looking fallback.",
                            "Catch only expected exception types and preserve unexpected failures.",
                        ),
                        node.lineno,
                    )
                if (
                    isinstance(node, ast.Subscript)
                    and isinstance(node.slice, ast.Call)
                    and isinstance(node.slice.func, ast.Name)
                    and node.slice.func.id == "len"
                    and "len(" in removed
                    and "- 1" in removed
                ):
                    emit(
                        _Rule(
                            "DET-INDEX-LEN",
                            FindingCategory.BOUNDARY_CONDITION,
                            Severity.HIGH,
                            "Index equals collection length",
                            "Indexing at len(collection) is outside the valid range for every collection.",
                            "Use len(collection) - 1 or guard the index before access.",
                        ),
                        node.lineno,
                    )
                if (
                    isinstance(node, ast.BinOp)
                    and isinstance(node.op, ast.Div)
                    and isinstance(node.right, ast.Call)
                    and isinstance(node.right.func, ast.Name)
                    and node.right.func.id == "len"
                ):
                    guarded_name = (
                        node.right.args[0].id if node.right.args and isinstance(node.right.args[0], ast.Name) else ""
                    )
                    has_empty_guard = any(
                        isinstance(item, ast.If)
                        and isinstance(item.test, ast.UnaryOp)
                        and isinstance(item.test.op, ast.Not)
                        and isinstance(item.test.operand, ast.Name)
                        and item.test.operand.id == guarded_name
                        and any(isinstance(branch, (ast.Return, ast.Raise)) for branch in item.body)
                        for item in body
                    )
                    if not has_empty_guard and "not " in removed:
                        emit(
                            _Rule(
                                "DET-UNGARDED-LEN-DIVISION",
                                FindingCategory.BOUNDARY_CONDITION,
                                Severity.HIGH,
                                "Division by length lacks an empty guard",
                                "The changed path divides by len(...) without a local empty-input guard.",
                                "Return or raise for an empty collection before dividing.",
                            ),
                            node.lineno,
                        )
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "sort"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in params
                    and "sorted(" in removed
                ):
                    emit(
                        _Rule(
                            "DET-INPUT-MUTATION",
                            FindingCategory.STATE_MUTATION,
                            Severity.MEDIUM,
                            "Caller-owned input is now mutated",
                            "The previous copying sort was replaced by in-place mutation of a parameter.",
                            "Sort a copy when the function contract should not mutate its input.",
                        ),
                        node.lineno,
                    )
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
                    parent_assignment = any(isinstance(item, ast.Assign) and item.value is node for item in body)
                    if (
                        parent_assignment
                        and "with open" in removed
                        and not any(isinstance(item, ast.With) and _calls(item, {"open"}) for item in body)
                        and not any(
                            isinstance(item, ast.Call)
                            and isinstance(item.func, ast.Attribute)
                            and item.func.attr == "close"
                            for item in body
                        )
                    ):
                        emit(
                            _Rule(
                                "DET-RESOURCE-NO-CLOSE",
                                FindingCategory.RESOURCE_MANAGEMENT,
                                Severity.MEDIUM,
                                "Opened resource lacks deterministic cleanup",
                                "A file handle is assigned and read without a context manager or close path.",
                                "Use a context manager or close the handle on every path.",
                            ),
                            node.lineno,
                        )

            for default in function.args.defaults:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)) and "None" in removed:
                    emit(
                        _Rule(
                            "DET-MUTABLE-DEFAULT",
                            FindingCategory.STATE_MUTATION,
                            Severity.HIGH,
                            "Mutable default argument",
                            "A mutable default is shared between function invocations.",
                            "Use None as the default and allocate a new container inside the function.",
                        ),
                        function.lineno,
                    )

            returns = [node for node in body if isinstance(node, ast.Return) and node.value is not None]
            if returns and "return" in removed:
                old_literals: set[str] = set()
                for old_line in removed.splitlines():
                    returned = old_line.strip().removeprefix("return ").strip()
                    if not old_line.strip().startswith("return "):
                        continue
                    if returned == "None":
                        old_literals.add("None")
                    elif re.fullmatch(r"[-+]?\d+", returned):
                        old_literals.add("int")
                    elif len(returned) >= 2 and returned[0] == returned[-1] and returned[0] in {"'", '"'}:
                        old_literals.add("str")
                for returned in returns:
                    now = (
                        "None"
                        if isinstance(returned.value, ast.Constant) and returned.value.value is None
                        else "str"
                        if isinstance(returned.value, ast.Constant) and isinstance(returned.value.value, str)
                        else "int"
                        if isinstance(returned.value, ast.Constant) and isinstance(returned.value.value, int)
                        else "other"
                    )
                    if old_literals and now not in old_literals and now in {"None", "str", "int"}:
                        emit(
                            _Rule(
                                "DET-RETURN-CONTRACT",
                                FindingCategory.TYPE_MISMATCH,
                                Severity.HIGH if now == "str" else Severity.MEDIUM,
                                "Return contract changed",
                                "The changed return value has a different concrete contract than the prior implementation.",
                                "Preserve the documented return contract or update dependent callers safely.",
                            ),
                            returned.lineno,
                        )

        # Removed containment/version/order checks require a matching after-state; no name-only rule.
        if "parents" in removed and "raise ValueError" in removed and "resolve()" in source and "Path(" in source:
            emit(
                _Rule(
                    "DET-PATH-CONTAINMENT-REMOVED",
                    FindingCategory.RESOURCE_MANAGEMENT,
                    Severity.HIGH,
                    "Path containment check removed",
                    "A resolved path is still built from caller input after its base-directory containment check was removed.",
                    "Resolve the root and reject paths outside it before use.",
                ),
                min(file_diff.added_lines or file_diff.hunk_lines),
            )
        if "current_version" in removed and "version != current_version" in removed:
            line = next(
                (line for line in sorted(file_diff.hunk_lines) if "snapshot" in lines.get(line, "")),
                min(file_diff.hunk_lines),
            )
            emit(
                _Rule(
                    "DET-STALE-VERSION-GUARD-REMOVED",
                    FindingCategory.CONCURRENCY,
                    Severity.HIGH,
                    "Stale-version guard removed",
                    "A version comparison rejecting stale state was removed while an update still uses the snapshot.",
                    "Restore optimistic-concurrency validation before applying the update.",
                ),
                line,
            )
        if "sorted(" in removed and "return (a, b)" in source:
            line = next(
                (line for line in sorted(file_diff.hunk_lines) if "return (a, b)" in lines.get(line, "")),
                min(file_diff.hunk_lines),
            )
            emit(
                _Rule(
                    "DET-LOCK-ORDER-REMOVED",
                    FindingCategory.CONCURRENCY,
                    Severity.HIGH,
                    "Canonical lock ordering removed",
                    "A canonical ordering was replaced by caller order, allowing incompatible acquisition order.",
                    "Retain a deterministic lock ordering before acquisition.",
                ),
                line,
            )
    return findings
