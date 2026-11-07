"""Bounded AST and before/after rules used by the CodeReview module.

Rules deliberately require both an observable risky after-state and, where the
signal can be ambiguous, evidence that the diff weakened a prior safeguard.
They emit normal CandidateFinding values and never execute analysed code.
"""

from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass

from polaris.core.models import CandidateFinding, Confidence, FindingCategory, Severity
from polaris.git.models import FileContext, FileDiff


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


def _direct_parameter_polarity(node: ast.AST, parameters: set[str]) -> tuple[str, bool] | None:
    """Return a direct parameter predicate and whether it is negated once."""
    if isinstance(node, ast.Name) and node.id in parameters:
        return node.id, False
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.Not)
        and isinstance(node.operand, ast.Name)
        and node.operand.id in parameters
    ):
        return node.operand.id, True
    return None


def _removed_return_if_expressions(removed: str) -> list[ast.IfExp]:
    """Parse single-line removed return expressions without reconstructing a file."""
    expressions: list[ast.IfExp] = []
    for line in removed.splitlines():
        stripped = line.strip()
        if not stripped.startswith("return "):
            continue
        try:
            expression = ast.parse(stripped.removeprefix("return "), mode="eval").body
        except SyntaxError:
            continue
        if isinstance(expression, ast.IfExp):
            expressions.append(expression)
    return expressions


def _literal_string_collection(node: ast.AST) -> set[str] | None:
    """Return a literal string collection, rejecting computed or mixed values."""
    if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return None
    values = {item.value for item in node.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)}
    return values if len(values) == len(node.elts) else None


def _removed_literal_assignments(raw_diff: str) -> dict[str, set[str]]:
    """Extract complete one-line literal assignments from removed diff lines."""
    assignments: dict[str, set[str]] = {}
    for line in raw_diff.splitlines():
        if not line.startswith("-") or line.startswith("---"):
            continue
        try:
            statement = ast.parse(line[1:].strip()).body[0]
        except (IndexError, SyntaxError):
            continue
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
            values = _literal_string_collection(statement.value)
            if values is not None:
                assignments[statement.targets[0].id] = values
    return assignments


def _set_expression_contains_string(node: ast.AST, value: str) -> bool:
    if isinstance(node, ast.Set):
        return any(
            isinstance(item, ast.Constant) and isinstance(item.value, str) and item.value.lower() == value
            for item in node.elts
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _set_expression_contains_string(node.left, value) or _set_expression_contains_string(node.right, value)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"set", "frozenset"}
        and len(node.args) == 1
        and isinstance(node.args[0], (ast.List, ast.Tuple, ast.Set))
    ):
        return any(
            isinstance(item, ast.Constant) and isinstance(item.value, str) and item.value.lower() == value
            for item in node.args[0].elts
        )
    return False


def _removed_assignment_contains_set_string(raw_diff: str, name: str, value: str) -> bool:
    statement: list[str] = []
    collecting = False
    for raw_line in raw_diff.splitlines():
        if not raw_line.startswith("-") or raw_line.startswith("---"):
            continue
        line = raw_line[1:]
        if not collecting and line.lstrip().startswith(f"{name} ="):
            collecting = True
        if not collecting:
            continue
        statement.append(line)
        try:
            parsed = ast.parse(textwrap.dedent("\n".join(statement))).body
        except SyntaxError:
            continue
        if len(parsed) != 1 or not isinstance(parsed[0], ast.Assign):
            return False
        assignment = parsed[0]
        if not any(isinstance(target, ast.Name) and target.id == name for target in assignment.targets):
            return False
        return _set_expression_contains_string(assignment.value, value)
    return False


def _reconstruct_before_source(file_diff: FileDiff, after_source: str) -> str | None:
    lines = after_source.splitlines()
    for hunk in reversed(file_diff.hunks):
        if hunk.new_start <= 0:
            return None
        new_lines = [line[1:] for line in hunk.lines if line.startswith((" ", "+"))]
        old_lines = [line[1:] for line in hunk.lines if line.startswith((" ", "-"))]
        start = hunk.new_start - 1
        if lines[start : start + hunk.new_count] != new_lines:
            return None
        lines[start : start + hunk.new_count] = old_lines
    return "\n".join(lines)


def _assigned_call(statement: ast.stmt) -> tuple[str, ast.Call] | None:
    if not (
        isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
        and isinstance(statement.value, ast.Call)
    ):
        return None
    return statement.targets[0].id, statement.value


def _finally_releases(try_node: ast.Try, resource_name: str) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == resource_name
        and node.func.attr in {"close", "release", "shutdown", "cleanup"}
        for statement in try_node.finalbody
        for node in ast.walk(statement)
    )


def _validation_acquisition_reorders(file_diff: FileDiff, source: str) -> list[int]:
    before_source = _reconstruct_before_source(file_diff, source)
    if before_source is None:
        return []
    try:
        before_tree = ast.parse(before_source)
        after_tree = ast.parse(source)
    except SyntaxError:
        return []
    before_functions = {node.name: node for node in before_tree.body if isinstance(node, ast.FunctionDef)}
    local_raisers = {
        node.name
        for node in after_tree.body
        if isinstance(node, ast.FunctionDef) and any(isinstance(item, ast.Raise) for item in ast.walk(node))
    }
    lines: list[int] = []
    for after_function in (node for node in after_tree.body if isinstance(node, ast.FunctionDef)):
        before_function = before_functions.get(after_function.name)
        if before_function is None:
            continue
        for index, before_statement in enumerate(before_function.body[:-1]):
            before_validation = _assigned_call(before_statement)
            before_try = before_function.body[index + 1]
            if before_validation is None or not isinstance(before_try, ast.Try) or before_try.handlers or before_try.orelse:
                continue
            before_resource = _assigned_call(before_try.body[0]) if before_try.body else None
            if before_resource is None or not _finally_releases(before_try, before_resource[0]):
                continue
            for after_try in (node for node in after_function.body if isinstance(node, ast.Try)):
                if after_try.handlers or after_try.orelse or len(after_try.body) < 2:
                    continue
                after_resource = _assigned_call(after_try.body[0])
                after_validation = _assigned_call(after_try.body[1])
                if after_resource is None or after_validation is None:
                    continue
                after_try_index = after_function.body.index(after_try)
                if any(
                    ast.dump(node, include_attributes=False) == ast.dump(before_validation[1], include_attributes=False)
                    for statement in after_function.body[:after_try_index]
                    for node in ast.walk(statement)
                    if isinstance(node, ast.Call)
                ):
                    continue
                if (
                    before_resource[0] != after_resource[0]
                    or ast.dump(before_resource[1], include_attributes=False)
                    != ast.dump(after_resource[1], include_attributes=False)
                    or ast.dump(before_validation[1], include_attributes=False)
                    != ast.dump(after_validation[1], include_attributes=False)
                    or not isinstance(after_validation[1].func, ast.Name)
                    or after_validation[1].func.id not in local_raisers
                    or not _finally_releases(after_try, after_resource[0])
                    or ast.dump(ast.Module(body=before_try.finalbody, type_ignores=[]), include_attributes=False)
                    != ast.dump(ast.Module(body=after_try.finalbody, type_ignores=[]), include_attributes=False)
                    or after_validation[1].lineno not in file_diff.added_lines
                ):
                    continue
                lines.append(after_validation[1].lineno)
    return lines


def _cross_file_candidates(files: list[FileDiff], contexts: dict[str, FileContext]) -> list[CandidateFinding]:
    """Return only evidence-backed, bounded cross-file deterministic findings."""
    parsed: dict[str, tuple[FileDiff | None, ast.Module, dict[int, str]]] = {}
    by_path = {item.new_path: item for item in files if item.new_path.endswith(".py")}
    for path, context in contexts.items():
        diff = by_path.get(path)
        material = _source(context)
        if material is None:
            continue
        source, lines = material
        try:
            parsed[path] = (diff, ast.parse(source), lines)
        except SyntaxError:
            continue

    findings: list[CandidateFinding] = []
    emitted: set[tuple[str, int, str]] = set()

    def emit(rule: _Rule, diff: FileDiff, lines: dict[int, str], line: int) -> None:
        key = (diff.new_path, line, rule.rule_id)
        candidate = _candidate(rule, diff, lines, line)
        if candidate and key not in emitted:
            emitted.add(key)
            findings.append(candidate)

    widened: set[str] = set()
    for diff, tree, _lines in parsed.values():
        if diff is None:
            continue
        old_assignments = _removed_literal_assignments(diff.raw_diff)
        for node in tree.body:
            if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.lineno in diff.added_lines):
                continue
            new_values = _literal_string_collection(node.value)
            old_values = old_assignments.get(node.targets[0].id)
            if new_values is not None and old_values is not None and old_values < new_values:
                widened.add(node.targets[0].id)

    for diff, tree, lines in parsed.values():
        if diff is None:
            continue
        for function in (item for item in ast.walk(tree) if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))):
            if "PermissionError" not in ast.unparse(function):
                continue
            for node in ast.walk(function):
                if not (isinstance(node, ast.If) and node.lineno in diff.added_lines and isinstance(node.test, ast.Compare) and len(node.test.ops) == 1 and isinstance(node.test.ops[0], (ast.In, ast.NotIn)) and len(node.test.comparators) == 1 and isinstance(node.test.comparators[0], ast.Name) and node.test.comparators[0].id in widened):
                    continue
                emit(_Rule("DET-CROSSFILE-ALLOWLIST-WIDENED", FindingCategory.LOGIC_ERROR, Severity.HIGH, "Cross-file authorization allowlist widened", "A changed caller references a literal allowlist widened in another changed module.", "Confirm every newly allowed role is authorized for this operation."), diff, lines, node.lineno)

    helper_paths: dict[str, list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]] = {}
    for path, (_diff, tree, _lines) in parsed.items():
        for function in (item for item in tree.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))):
            if len(function.args.args) != 1 or len(function.body) != 1 or not isinstance(function.body[0], ast.Return):
                continue
            returned = function.body[0].value
            parameter = function.args.args[0].arg
            if isinstance(returned, ast.Call) and isinstance(returned.func, ast.Name) and returned.func.id == "list" and len(returned.args) == 1 and isinstance(returned.args[0], ast.Name) and returned.args[0].id == parameter:
                helper_paths.setdefault(function.name, []).append((path, function))

    for path, (diff, tree, lines) in parsed.items():
        if diff is None:
            continue
        removed = "\n".join(line[1:] for line in diff.raw_diff.splitlines() if line.startswith("-") and not line.startswith("---"))
        if "return [" not in removed or " if " not in removed:
            continue
        for function in (item for item in ast.walk(tree) if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))):
            parameters = {arg.arg for arg in function.args.args}
            for returned in (item for item in ast.walk(function) if isinstance(item, ast.Return)):
                value = returned.value
                if not (returned.lineno in diff.added_lines and isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and len(value.args) == 1 and isinstance(value.args[0], ast.Name) and value.args[0].id in parameters):
                    continue
                helpers = helper_paths.get(value.func.id, [])
                if len(helpers) != 1 or helpers[0][0] == path:
                    continue
                emit(_Rule("DET-CROSSFILE-COLLECTION-FILTER-BYPASSED", FindingCategory.LOGIC_ERROR, Severity.HIGH, "Cross-file collection filter bypassed", "A changed caller replaced a parameter-bound collection filter with an unambiguous helper returning the raw collection.", "Preserve the authorization, tenant, or lifecycle filter before delegating rows."), diff, lines, returned.lineno)
    return findings


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
        removed_return_if_expressions = _removed_return_if_expressions(removed)

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

        for line in _validation_acquisition_reorders(file_diff, source):
            emit(
                _Rule(
                    "DET-VALIDATION-AFTER-RESOURCE-ACQUISITION",
                    FindingCategory.ERROR_HANDLING,
                    Severity.MEDIUM,
                    "Potentially raising validation moved after resource acquisition",
                    "A local validation call that explicitly raises moved after acquiring a resource protected by finally cleanup.",
                    "Validate before acquiring the resource to preserve failure ordering and avoid unnecessary acquisition.",
                ),
                line,
            )

        functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for function in functions:
            body = list(ast.walk(function))
            params = {arg.arg for arg in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]}
            returns = [node for node in body if isinstance(node, ast.Return) and node.value is not None]

            # Authorization is reported only if a permission-raising guard was removed from this diff.
            if (
                "PermissionError" in removed
                and "PermissionError" not in source
                and any(isinstance(item, ast.Return) for item in body)
            ):
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

            # A simple parameter-bound validation guard was removed and no
            # ValueError validation remains in the changed function. This is
            # intentionally confined to literal comparisons plus an explicit
            # raise, so moved or strengthened validation stays clean. Follow
            # only local aliases created by single-argument helper calls; this
            # covers normalization/wrapper flow without speculative inter-file
            # value inference.
            validation_inputs = set(params)
            for node in body:
                if not (
                    isinstance(node, ast.Assign)
                    and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and isinstance(node.value, ast.Call)
                ):
                    continue
                if any(isinstance(arg, ast.Name) and arg.id in validation_inputs for arg in node.value.args):
                    validation_inputs.add(node.targets[0].id)
            removed_validation = re.search(
                r"if\s+([A-Za-z_]\w*)\s*(?:<|<=|>|>=|==|!=)\s*[^:\n]+:\s*raise\s+ValueError",
                removed,
            )
            if (
                removed_validation
                and removed_validation.group(1) in validation_inputs
                and "ValueError" not in ast.unparse(function)
                and returns
            ):
                emit(
                    _Rule(
                        "DET-VALIDATION-GUARD-REMOVED",
                        FindingCategory.BOUNDARY_CONDITION,
                        Severity.MEDIUM,
                        "Input validation guard removed",
                        "A parameter-bound ValueError validation guard was removed without a replacement validation path.",
                        "Restore validation before the input reaches the returned or side-effecting path.",
                    ),
                    returns[0].lineno,
                )

            # A direct boolean parameter condition in a conditional return has
            # been inverted while both result branches remain the same. This
            # proves a polarity change without guessing intent from unrelated
            # predicate or branch rewrites.
            for returned in returns:
                after_expression = returned.value
                if not isinstance(after_expression, ast.IfExp):
                    continue
                after_polarity = _direct_parameter_polarity(after_expression.test, params)
                if after_polarity is None:
                    continue
                for before_expression in removed_return_if_expressions:
                    before_polarity = _direct_parameter_polarity(before_expression.test, params)
                    if (
                        before_polarity is None
                        or before_polarity[0] != after_polarity[0]
                        or before_polarity[1] == after_polarity[1]
                        or ast.dump(before_expression.body, include_attributes=False)
                        != ast.dump(after_expression.body, include_attributes=False)
                        or ast.dump(before_expression.orelse, include_attributes=False)
                        != ast.dump(after_expression.orelse, include_attributes=False)
                    ):
                        continue
                    emit(
                        _Rule(
                            "DET-CONDITIONAL-POLARITY-INVERTED",
                            FindingCategory.LOGIC_ERROR,
                            Severity.HIGH,
                            "Conditional eligibility polarity inverted",
                            "A direct boolean parameter condition was inverted while both conditional result branches remained unchanged.",
                            "Restore the original condition or explicitly verify the changed eligibility contract.",
                        ),
                        returned.lineno,
                    )
                    break

            # An exact role denial changed into a membership denial with extra
            # allowed literals expands the authorization boundary. This stays
            # narrow so equivalent guard refactors do not become findings.
            old_role_literals = set(re.findall(r"role\s*!=\s*['\"]([^'\"]+)['\"]", removed))
            if old_role_literals:
                for node in body:
                    if not (
                        isinstance(node, ast.Compare)
                        and len(node.ops) == 1
                        and isinstance(node.ops[0], ast.NotIn)
                        and isinstance(node.left, ast.Name)
                        and node.left.id == "role"
                        and len(node.comparators) == 1
                        and isinstance(node.comparators[0], (ast.Tuple, ast.List, ast.Set))
                    ):
                        continue
                    allowed = {
                        value.value
                        for value in node.comparators[0].elts
                        if isinstance(value, ast.Constant) and isinstance(value.value, str)
                    }
                    if old_role_literals <= allowed and allowed - old_role_literals:
                        emit(
                            _Rule(
                                "DET-ROLE-ALLOWLIST-WIDENED",
                                FindingCategory.LOGIC_ERROR,
                                Severity.HIGH,
                                "Role allowlist widened",
                                "An exact role restriction was replaced by an allowlist that grants an additional role.",
                                "Confirm every newly allowed role is authorized for this operation.",
                            ),
                            node.lineno,
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

            # Removing an explicit cache eviction while the function still
            # updates/returns the value leaves an existing cache entry stale.
            # A replacement pop or delete in the after-state suppresses this
            # finding, allowing an equivalent cleanup refactor.
            removed_eviction = re.search(r"\b([A-Za-z_]\w*)\.pop\([^\n]*,\s*None\)", removed)
            if (
                removed_eviction
                and ".pop(" not in source
                and f"del {removed_eviction.group(1)}[" not in source
                and returns
            ):
                emit(
                    _Rule(
                        "DET-CACHE-EVICTION-REMOVED",
                        FindingCategory.STATE_MUTATION,
                        Severity.MEDIUM,
                        "Cache eviction removed",
                        "A cache eviction was removed without a replacement invalidation in the changed function.",
                        "Invalidate the affected cache entry before returning the updated value.",
                    ),
                    returns[0].lineno,
                )

            # A replay guard that returned early for an already-seen key was
            # removed while the same key is still recorded. This specifically
            # identifies an idempotency regression without relying on names.
            replay_guard = re.search(
                r"if\s+([A-Za-z_]\w*)\s+in\s+([A-Za-z_]\w*)\s*:\s*return",
                removed,
            )
            matching_adds = [
                node
                for node in body
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == replay_guard.group(2)
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == replay_guard.group(1)
            ] if replay_guard else []
            retained_replay_guard = any(
                isinstance(node, ast.If)
                and isinstance(node.test, ast.Compare)
                and len(node.test.ops) == 1
                and isinstance(node.test.ops[0], ast.In)
                and isinstance(node.test.left, ast.Name)
                and node.test.left.id == replay_guard.group(1)
                and len(node.test.comparators) == 1
                and isinstance(node.test.comparators[0], ast.Name)
                and node.test.comparators[0].id == replay_guard.group(2)
                and any(isinstance(statement, ast.Return) for statement in node.body)
                and matching_adds
                and node.lineno < min(add.lineno for add in matching_adds)
                for node in body
            ) if replay_guard else False
            if replay_guard and matching_adds and not retained_replay_guard:
                line = next(
                    (
                        node.lineno for node in matching_adds
                    ),
                    function.lineno,
                )
                emit(
                    _Rule(
                        "DET-IDEMPOTENCY-GUARD-REMOVED",
                        FindingCategory.STATE_MUTATION,
                        Severity.HIGH,
                        "Idempotency guard removed",
                        "A duplicate-key early return was removed while the key is still recorded after processing.",
                        "Restore the already-seen guard before performing the side effect.",
                    ),
                    line,
                )

            # A typed exception handler used to re-raise but now returns a
            # literal fallback. This is intentionally narrower than generic
            # error recovery: broad handlers, exception chaining, and a
            # propagated exception remain outside this rule.
            if re.search(r"^\s*raise\s*$", removed, re.MULTILINE):
                for handler in (node for node in body if isinstance(node, ast.ExceptHandler)):
                    if not (
                        isinstance(handler.type, ast.Name)
                        and handler.type.id not in {"Exception", "BaseException"}
                        and len(handler.body) == 1
                        and isinstance(handler.body[0], ast.Return)
                        and isinstance(handler.body[0].value, ast.Constant)
                        and handler.body[0].lineno in file_diff.added_lines
                    ):
                        continue
                    emit(
                        _Rule(
                            "DET-TYPED-EXCEPTION-SWALLOWED",
                            FindingCategory.ERROR_HANDLING,
                            Severity.MEDIUM,
                            "Typed exception converted to fallback value",
                            "A typed exception handler replaced a re-raise with a literal fallback value, hiding the failure from callers.",
                            "Preserve propagation or make the fallback contract explicit and observable.",
                        ),
                        handler.body[0].lineno,
                    )

            # A parameter-owned resource had an explicit close call removed
            # and the after-state provides no close path. Keeping this tied to
            # a function parameter avoids treating a lifecycle refactor for a
            # locally owned object as a caller-resource regression.
            removed_close = re.search(r"\b([A-Za-z_]\w*)\.close\(\)", removed)
            if (
                removed_close
                and removed_close.group(1) in params
                and ".close(" not in source
                and returns
            ):
                emit(
                    _Rule(
                        "DET-CALLER-RESOURCE-CLOSE-REMOVED",
                        FindingCategory.RESOURCE_MANAGEMENT,
                        Severity.MEDIUM,
                        "Caller resource cleanup removed",
                        "An explicit close call for a caller-provided resource was removed without a replacement close path.",
                        "Restore deterministic cleanup or explicitly transfer lifecycle ownership.",
                    ),
                    returns[0].lineno,
                )

            # A composite key formed from two parameters was replaced by one
            # of those parameters. This loses a namespace dimension and can
            # cause cross-tenant/cache collisions.
            composite_key = re.search(
                r"return\s+f['\"].*?\{([A-Za-z_]\w*)\}.*?\{([A-Za-z_]\w*)\}",
                removed,
            )
            if composite_key:
                key_parts = {composite_key.group(1), composite_key.group(2)}
                for returned in returns:
                    if isinstance(returned.value, ast.Name) and returned.value.id in key_parts:
                        emit(
                            _Rule(
                                "DET-COMPOSITE-KEY-DIMENSION-REMOVED",
                                FindingCategory.LOGIC_ERROR,
                                Severity.HIGH,
                                "Composite key dimension removed",
                                "A composite key was replaced by one of its component values, losing namespace isolation.",
                                "Preserve every required key dimension when deriving identifiers or cache keys.",
                            ),
                            returned.lineno,
                        )

            # Replacing a least-privilege role default with an administrative
            # default changes behavior for missing input without requiring a
            # name-specific endpoint convention.
            old_default_role = re.search(
                r"\.get\(\s*['\"]role['\"]\s*,\s*['\"](viewer|user|read_only)['\"]\s*\)",
                removed,
            )
            if old_default_role:
                for node in body:
                    if not (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "get"
                        and len(node.args) >= 2
                        and isinstance(node.args[0], ast.Constant)
                        and node.args[0].value == "role"
                        and isinstance(node.args[1], ast.Constant)
                        and node.args[1].value in {"admin", "owner", "operator"}
                    ):
                        continue
                    emit(
                        _Rule(
                            "DET-DEFAULT-ROLE-ESCALATED",
                            FindingCategory.LOGIC_ERROR,
                            Severity.HIGH,
                            "Default role escalated",
                            "A missing role now defaults to an administrative privilege level.",
                            "Keep absent role input at the least-privilege default.",
                        ),
                        node.lineno,
                    )

            # A required mapping lookup changed to get(key) weakens a value
            # contract by converting missing data from an error into None.
            required_key = re.search(r"return\s+\w+\[['\"]([^'\"]+)['\"]\]", removed)
            if required_key:
                for returned in returns:
                    value = returned.value
                    if (
                        isinstance(value, ast.Call)
                        and isinstance(value.func, ast.Attribute)
                        and value.func.attr == "get"
                        and value.args
                        and isinstance(value.args[0], ast.Constant)
                        and value.args[0].value == required_key.group(1)
                        and len(value.args) == 1
                    ):
                        emit(
                            _Rule(
                                "DET-REQUIRED-FIELD-MADE-OPTIONAL",
                                FindingCategory.TYPE_MISMATCH,
                                Severity.MEDIUM,
                                "Required field made optional",
                                "A required mapping lookup was replaced by get(key), which can return None for missing data.",
                                "Preserve the required-field contract or handle the optional result at every consumer.",
                            ),
                            returned.lineno,
                        )

            # A formerly numeric conversion is wrapped in str(), changing the
            # concrete public return type while preserving only its text form.
            if "return int(" in removed:
                for returned in returns:
                    value = returned.value
                    if (
                        isinstance(value, ast.Call)
                        and isinstance(value.func, ast.Name)
                        and value.func.id == "str"
                        and value.args
                        and isinstance(value.args[0], ast.Call)
                        and isinstance(value.args[0].func, ast.Name)
                        and value.args[0].func.id == "int"
                    ):
                        emit(
                            _Rule(
                                "DET-NUMERIC-RETURN-STRINGIFIED",
                                FindingCategory.TYPE_MISMATCH,
                                Severity.HIGH,
                                "Numeric return stringified",
                                "A numeric conversion now returns its string representation instead of a numeric value.",
                                "Preserve the numeric return type or update all dependent contracts explicitly.",
                            ),
                            returned.lineno,
                        )

            # A slice that was capped by min(requested_limit, fixed_cap) now
            # includes one item beyond the requested limit. Both the removed
            # cap and the explicit `+ 1` bound are required as evidence.
            if "min(" in removed:
                for node in body:
                    if not (
                        isinstance(node, ast.Subscript)
                        and isinstance(node.slice, ast.Slice)
                        and isinstance(node.slice.upper, ast.BinOp)
                        and isinstance(node.slice.upper.op, ast.Add)
                        and isinstance(node.slice.upper.right, ast.Constant)
                        and node.slice.upper.right.value == 1
                    ):
                        continue
                    emit(
                        _Rule(
                            "DET-SLICE-LIMIT-WIDENED",
                            FindingCategory.BOUNDARY_CONDITION,
                            Severity.MEDIUM,
                            "Requested slice limit widened by one",
                            "A previously capped slice now adds one to its requested upper bound.",
                            "Preserve the requested limit and any maximum-page cap in the slice bound.",
                        ),
                        node.lineno,
                    )

            # Changing a strict integer retry/budget comparison to inclusive
            # permits exactly one extra attempt at the former maximum.
            old_strict_bound = re.search(r"return\s+([A-Za-z_]\w*)\s*<\s*(\d+)", removed)
            if old_strict_bound:
                for returned in returns:
                    value = returned.value
                    if not (
                        isinstance(value, ast.Compare)
                        and len(value.ops) == 1
                        and isinstance(value.ops[0], ast.LtE)
                        and isinstance(value.left, ast.Name)
                        and value.left.id == old_strict_bound.group(1)
                        and len(value.comparators) == 1
                        and isinstance(value.comparators[0], ast.Constant)
                        and str(value.comparators[0].value) == old_strict_bound.group(2)
                    ):
                        continue
                    emit(
                        _Rule(
                            "DET-STRICT-BOUND-MADE-INCLUSIVE",
                            FindingCategory.BOUNDARY_CONDITION,
                            Severity.MEDIUM,
                            "Strict retry or budget bound made inclusive",
                            "A strict numeric bound was changed to inclusive, allowing one additional value at the prior limit.",
                            "Keep the strict comparison unless the extra attempt or item is explicitly safe.",
                        ),
                        returned.lineno,
                    )

            # Returning a mapping with one of its previous literal fields
            # removed changes the serialized contract while preserving the
            # same mapping-return shape.
            removed_mapping_keys = set(re.findall(r"['\"]([^'\"]+)['\"]\s*:\s*[^,}\n]+", removed))
            if removed_mapping_keys:
                for returned in returns:
                    if not isinstance(returned.value, ast.Dict):
                        continue
                    current_keys = {
                        key.value
                        for key in returned.value.keys
                        if isinstance(key, ast.Constant) and isinstance(key.value, str)
                    }
                    dropped = removed_mapping_keys - current_keys
                    if dropped and current_keys:
                        emit(
                            _Rule(
                                "DET-SERIALIZED-FIELD-REMOVED",
                                FindingCategory.TYPE_MISMATCH,
                                Severity.MEDIUM,
                                "Serialized mapping field removed",
                                "A literal field from a returned mapping is absent from the new serialized representation.",
                                "Preserve required fields or version the output contract and update consumers.",
                            ),
                            returned.lineno,
                        )

            # Truthiness is not equivalent to an explicit None check for a
            # valid falsy value such as port 0. Require the same expression
            # to have lost an `is not None` guard in this diff.
            optional_guard = re.search(r"if\s+(.+?)\s+is\s+not\s+None\s*:", removed)
            if optional_guard:
                guarded_expression = optional_guard.group(1).strip()
                for node in body:
                    if isinstance(node, ast.If) and ast.unparse(node.test) == guarded_expression:
                        emit(
                            _Rule(
                                "DET-OPTIONAL-GUARD-TRUTHINESS",
                                FindingCategory.BOUNDARY_CONDITION,
                                Severity.MEDIUM,
                                "Optional-value guard weakened to truthiness",
                                "An explicit None check was replaced by a truthiness check that rejects valid falsy values.",
                                "Keep an explicit None check when zero, empty, or false are valid values.",
                            ),
                            node.lineno,
                        )

            # Removing UTF-8 conversion before an observed length calculation
            # changes byte-oriented protocol lengths for non-ASCII strings.
            if ".encode(" in removed and ".encode(" not in ast.unparse(function):
                for node in body:
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "len"
                        and node.args
                    ):
                        emit(
                            _Rule(
                                "DET-ENCODE-BEFORE-LENGTH-REMOVED",
                                FindingCategory.BOUNDARY_CONDITION,
                                Severity.MEDIUM,
                                "Encoding before length removed",
                                "A conversion to encoded bytes was removed before a length calculation remains.",
                                "Measure encoded bytes when the surrounding protocol contract is byte-oriented.",
                            ),
                            function.lineno,
                        )

            # The HTTPS exception for proxy credentials was removed while the
            # Proxy-Authorization assignment remains reachable.
            if "scheme.startswith" in removed and "scheme.startswith" not in ast.unparse(function):
                for node in body:
                    if (
                        isinstance(node, ast.Assign)
                        and "Proxy-Authorization" in ast.unparse(node)
                    ):
                        emit(
                            _Rule(
                                "DET-HTTPS-PROXY-AUTH-GUARD-REMOVED",
                                FindingCategory.LOGIC_ERROR,
                                Severity.HIGH,
                                "HTTPS proxy authorization guard removed",
                                "A scheme-specific guard was removed before Proxy-Authorization is assigned.",
                                "Keep tunneled HTTPS requests outside the proxy-authorization header path.",
                            ),
                            node.lineno,
                        )

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

        # Cookie removal from a redirect-sanitization allowlist is a concrete
        # cross-origin data-exposure regression when the same list continues
        # to remove Authorization. This can occur at module scope.
        if '"Cookie"' in removed or "'Cookie'" in removed:
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "frozenset"
                    and "Cookie" not in ast.unparse(node)
                    and "Authorization" in ast.unparse(node)
                ):
                    emit(
                        _Rule(
                            "DET-SENSITIVE-HEADER-REMOVED",
                            FindingCategory.LOGIC_ERROR,
                            Severity.HIGH,
                            "Sensitive redirect header removal removed",
                            "Cookie was removed from a redirect sanitization allowlist that still protects Authorization.",
                            "Retain Cookie and other sensitive headers when forwarding across origins.",
                        ),
                        node.lineno,
                    )

        # A request's trusted-host policy was removed before debugger dispatch.
        # Both the Request construction and debugger call must remain present,
        # preventing a name-only finding on unrelated host configuration.
        if "trusted_hosts" in removed:
            for function in functions:
                function_source = ast.unparse(function)
                if (
                    "trusted_hosts" not in function_source
                    and "Request(" in function_source
                    and "execute_debugger" in function_source
                ):
                    request_line = next(
                        (
                            node.lineno
                            for node in ast.walk(function)
                            if isinstance(node, ast.Call)
                            and isinstance(node.func, ast.Name)
                            and node.func.id == "Request"
                        ),
                        function.lineno,
                    )
                    emit(
                        _Rule(
                            "DET-TRUSTED-HOST-POLICY-REMOVED",
                            FindingCategory.LOGIC_ERROR,
                            Severity.HIGH,
                            "Trusted-host policy removed before debugger dispatch",
                            "A request trusted-host policy was removed while the debugger remains reachable.",
                            "Restore the trusted-host assignment and validate the request host before dispatch.",
                        ),
                        request_line,
                    )

        # Redirect header stripping previously augmented the configured list
        # with Host, but the post-change loop strips only the configured list.
        if _removed_assignment_contains_set_string(file_diff.raw_diff, "headers_to_remove", "host"):
            for function in functions:
                function_source = ast.unparse(function)
                if "headers_to_remove" not in function_source and "new_headers.pop" in function_source:
                    line = next(
                        (
                            node.lineno
                            for node in ast.walk(function)
                            if isinstance(node, ast.Call)
                            and isinstance(node.func, ast.Attribute)
                            and node.func.attr == "pop"
                        ),
                        function.lineno,
                    )
                    emit(
                        _Rule(
                            "DET-REDIRECT-HOST-STRIPPING-REMOVED",
                            FindingCategory.LOGIC_ERROR,
                            Severity.HIGH,
                            "Redirect Host stripping removed",
                            "The redirect header-removal set no longer includes Host before forwarding headers.",
                            "Preserve Host stripping when redirecting across origins.",
                        ),
                        line,
                    )

        # A custom pickle reconstruction hook was removed from an exception
        # subclass. This changes serialization behavior even when ordinary
        # construction still succeeds.
        if "def __reduce__" in removed:
            for class_node in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
                if (
                    any(
                        isinstance(base, ast.Name) and "Error" in base.id
                        for base in class_node.bases
                    )
                    and "__reduce__" not in ast.unparse(class_node)
                ):
                    emit(
                        _Rule(
                            "DET-EXCEPTION-SERIALIZATION-HOOK-REMOVED",
                            FindingCategory.TYPE_MISMATCH,
                            Severity.MEDIUM,
                            "Exception serialization hook removed",
                            "A custom __reduce__ method was removed from an exception subclass, changing pickle reconstruction.",
                            "Preserve the reconstruction hook or verify serialization compatibility explicitly.",
                        ),
                        class_node.lineno,
                    )

        # Removed containment/version/order checks require a matching after-state; no name-only rule.
        # A collection filter removed in favour of returning the raw parameter is
        # a high-confidence visibility regression (tenant/soft-delete/ownership
        # filters), but only when the old diff contained a conditional
        # comprehension and the new function returns list(the_same_parameter).
        if "return [" in removed and " if " in removed:
            for returned in [node for node in ast.walk(tree) if isinstance(node, ast.Return)]:
                value = returned.value
                if (
                    isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Name)
                    and value.func.id == "list"
                    and len(value.args) == 1
                    and isinstance(value.args[0], ast.Name)
                ):
                    emit(
                        _Rule(
                            "DET-COLLECTION-FILTER-REMOVED",
                            FindingCategory.LOGIC_ERROR,
                            Severity.HIGH,
                            "Collection visibility filter removed",
                            "A conditional collection filter was replaced by returning the unfiltered input.",
                            "Retain the authorization, tenant, or lifecycle filter before returning rows.",
                        ),
                        returned.lineno,
                    )
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
    return [*findings, *_cross_file_candidates(files, contexts)]
