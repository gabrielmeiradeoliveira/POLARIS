"""Deterministic Behavioral Delta Analysis Engine for DEICIDE.

Compares pre-change and post-change code across Git diff hunks using Python AST
analysis, symbol extraction, and cross-file dependency graphs to surface structured
evidence about behavioral changes without independently declaring defects or
bypassing the Finding Intelligence Engine.
"""

from __future__ import annotations

import ast
import builtins
import contextlib
import hashlib
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from deicide.context.changed_symbols import identify_changed_symbols
from deicide.context.dependency_graph import DependencyGraph, build_dependency_graph
from deicide.context.models import FileAnalysisStatus
from deicide.context.project_index import ProjectIndex, file_path_to_module_name
from deicide.context.python_ast import PythonAstAnalyzer
from deicide.core.models import Confidence, LineRange, estimate_token_count
from deicide.git.analyzer import ensure_safe_repo_file, normalize_repo_relative_path
from deicide.git.models import DiffBundle, FileContext, FileDiff

_MUTATING_METHODS: frozenset[str] = frozenset(
    {
        "update",
        "append",
        "extend",
        "insert",
        "pop",
        "remove",
        "clear",
        "setdefault",
        "sort",
        "reverse",
        "add",
        "discard",
    }
)

_COPY_CONSTRUCTORS: frozenset[str] = frozenset({"dict", "list", "set", "frozenset", "tuple"})
_COPY_METHODS: frozenset[str] = frozenset({"copy", "deepcopy"})
_CLAMP_FUNCTIONS: frozenset[str] = frozenset({"max", "min"})
_RESOURCE_CLEANUP_METHODS: frozenset[str] = frozenset({"close", "release", "shutdown", "cleanup"})


class BehavioralDeltaType(StrEnum):
    """Classification of a deterministic behavioral change extracted from a diff."""

    GUARD_REMOVAL = "guard_removal"
    GUARD_MODIFICATION = "guard_modification"
    GUARD_ADDITION = "guard_addition"
    SIGNATURE_CONTRACT_CHANGE = "signature_contract_change"
    EXCEPTION_HANDLING_CHANGE = "exception_handling_change"
    STATE_MUTATION_CHANGE = "state_mutation_change"
    RETURN_BEHAVIOR_CHANGE = "return_behavior_change"
    RESOURCE_LIFECYCLE_CHANGE = "resource_lifecycle_change"
    DATA_FLOW_CONTRACT_CHANGE = "data_flow_contract_change"


class BehavioralDelta(BaseModel):
    """Structured evidence record describing a behavioral change in a Git diff.

    Strictly separates `observed_change` (verifiable syntactic/semantic facts)
    from `inferred_risk` (potential behavioral impact to be evaluated during review).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    delta_id: str = Field(..., min_length=1)
    delta_type: BehavioralDeltaType
    file_path: str = Field(..., min_length=1)
    symbol_name: str | None = None
    qualified_name: str | None = None
    line_range: LineRange
    changed_lines: list[int] = Field(default_factory=list)
    before_evidence: str = ""
    after_evidence: str = ""
    related_callers: list[str] = Field(default_factory=list)
    related_dependencies: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.HIGH
    observed_change: str = Field(
        ...,
        min_length=1,
        description="Strictly factual description of the observed semantic/syntactic change.",
    )
    inferred_risk: str = Field(
        ...,
        min_length=1,
        description="Potential behavioral impact framed as a hypothesis to verify, not an automatic defect.",
    )

    @property
    def affected_symbol(self) -> str | None:
        """Return the most specific symbol identifier affected by this delta."""
        return self.qualified_name or self.symbol_name

    @property
    def evidence_strength(self) -> Confidence:
        """Alias for confidence representing deterministic evidence strength."""
        return self.confidence

    @property
    def impact_explanation(self) -> str:
        """Combined explanation pairing observed semantic change with inferred risk."""
        return f"Observed change: {self.observed_change} | Potential impact: {self.inferred_risk}"


class BehavioralDeltaResult(BaseModel):
    """Aggregated result of running Behavioral Delta Analysis across a DiffBundle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    deltas: list[BehavioralDelta] = Field(default_factory=list)
    files_analyzed: int = Field(default=0, ge=0)
    serialized_summary: str = ""
    estimated_tokens: int = Field(default=0, ge=0)


def _compute_delta_id(
    file_path: str,
    delta_type: BehavioralDeltaType,
    symbol_name: str | None,
    line_range: LineRange,
    before_evidence: str,
    after_evidence: str,
) -> str:
    raw = (
        f"{file_path}|{delta_type.value}|{symbol_name or '<module>'}|"
        f"{line_range.start_line}:{line_range.end_line}|{before_evidence.strip()}|{after_evidence.strip()}"
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]
    return f"delta-{digest}"


def _safe_unparse(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node).strip()
    except Exception:
        return ""


def _reconstruct_before_and_after_source(
    file_diff: FileDiff,
    file_context: FileContext | None,
    repo_root: Path | None = None,
) -> tuple[str, str, dict[int, str]]:
    """Reconstruct pre-change ('before') and post-change ('after') source strings for a file."""
    norm_path = normalize_repo_relative_path(file_diff.new_path)
    after_lines: list[str] = []
    numbered_after: dict[int, str] = {}

    # 1. Try reading full post-change file from FileContext if complete
    if file_context is not None and file_context.snippets:
        for snippet in file_context.snippets:
            for ln, text in snippet.lines.items():
                numbered_after[ln] = text
        if file_context.total_lines > 0 and len(numbered_after) == file_context.total_lines:
            after_lines = [numbered_after.get(i, "") for i in range(1, file_context.total_lines + 1)]

    # 2. If not complete in FileContext, try reading from repo_root if available
    if not after_lines and repo_root is not None:
        with contextlib.suppress(Exception):
            safe_path = ensure_safe_repo_file(repo_root, norm_path)
            if safe_path.exists() and safe_path.is_file():
                raw_text = safe_path.read_text(encoding="utf-8")
                after_lines = raw_text.splitlines()
                for idx, line in enumerate(after_lines, start=1):
                    numbered_after.setdefault(idx, line)

    # 3. Populate any missing lines from diff hunks and assemble after_lines
    for hunk in file_diff.hunks:
        cur_new = max(1, hunk.new_start)
        for hline in hunk.lines:
            if hline.startswith(("+", " ")) and not hline.startswith("+++"):
                numbered_after.setdefault(cur_new, hline[1:])
                cur_new += 1

    if not after_lines and numbered_after:
        max_ln = max(numbered_after.keys())
        after_lines = [numbered_after.get(i, "") for i in range(1, max_ln + 1)]

    # 4. Reconstruct before_lines by inverting hunks from bottom to top
    before_lines = list(after_lines)
    sorted_hunks = sorted(file_diff.hunks, key=lambda h: h.new_start, reverse=True)
    for hunk in sorted_hunks:
        old_hunk_lines = [
            hline[1:] for hline in hunk.lines if hline.startswith(("-", " ")) and not hline.startswith("---")
        ]
        actual_new_span = sum(1 for hline in hunk.lines if hline.startswith(("+", " ")) and not hline.startswith("+++"))
        if before_lines and hunk.new_start >= 1:
            start_idx = max(0, hunk.new_start - 1)
            end_idx = min(len(before_lines), start_idx + actual_new_span)
            before_lines[start_idx:end_idx] = old_hunk_lines
        elif not before_lines:
            before_lines = old_hunk_lines

    before_source = "\n".join(before_lines)
    after_source = "\n".join(after_lines)
    return before_source, after_source, numbered_after


class _ScopedFunctionCollector(ast.NodeVisitor):
    """Collect AST FunctionDef/AsyncFunctionDef nodes indexed by qualified name."""

    def __init__(self) -> None:
        self.scope: list[str] = []
        self.functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        for child in node.body:
            self.visit(child)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        qual = ".".join([*self.scope, node.name])
        self.functions[qual] = node
        self.scope.append(node.name)
        for child in node.body:
            self.visit(child)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        qual = ".".join([*self.scope, node.name])
        self.functions[qual] = node
        self.scope.append(node.name)
        for child in node.body:
            self.visit(child)
        self.scope.pop()


def _build_in_memory_index_and_graph(
    diff_bundle: DiffBundle,
    contexts: dict[str, FileContext] | None,
    repo_root: Path | None,
    analyzer: PythonAstAnalyzer,
) -> tuple[ProjectIndex, DependencyGraph, dict[str, ast.AST]]:
    """Build a deterministic in-memory ProjectIndex and DependencyGraph from available contexts."""
    effective_root = repo_root or Path(".")
    index = ProjectIndex(repo_root=effective_root)
    parsed_trees: dict[str, ast.AST] = {}

    source_map: dict[str, str] = {}
    if contexts:
        for fpath, fctx in sorted(contexts.items()):
            if not fpath.endswith(".py"):
                continue
            norm = normalize_repo_relative_path(fpath)
            lines_dict: dict[int, str] = {}
            for snip in fctx.snippets:
                lines_dict.update(snip.lines)
            if lines_dict:
                max_ln = max(fctx.total_lines, max(lines_dict.keys()))
                source_map[norm] = "\n".join(lines_dict.get(i, "") for i in range(1, max_ln + 1))

    for fdiff in diff_bundle.reviewable_files:
        if not fdiff.new_path.endswith(".py"):
            continue
        norm = normalize_repo_relative_path(fdiff.new_path)
        if norm not in source_map:
            _, after_src, _ = _reconstruct_before_and_after_source(
                fdiff,
                contexts.get(norm) if contexts else None,
                repo_root=repo_root,
            )
            if after_src.strip():
                source_map[norm] = after_src

    for rel_path, src in sorted(source_map.items()):
        analysis = analyzer.analyze_source(src, file_path=rel_path)
        index.file_analyses[rel_path] = analysis
        mod_name = file_path_to_module_name(rel_path)
        if mod_name and mod_name not in index.module_to_file:
            index.module_to_file[mod_name] = rel_path
            index.file_to_module[rel_path] = mod_name

        if analysis.status == FileAnalysisStatus.PARSED:
            index.symbols_by_module.setdefault(mod_name, [])
            for sym in analysis.symbols:
                index.symbols_by_id[sym.id] = sym
                index.symbols_by_module[mod_name].append(sym)
                index.qualified_to_symbol[(mod_name, sym.qualified_name)] = sym
            with contextlib.suppress(SyntaxError):
                parsed_trees[rel_path] = ast.parse(src, filename=rel_path)

    graph = build_dependency_graph(index)
    return index, graph, parsed_trees


def _collect_caller_details(
    file_path: str,
    qualified_name: str,
    simple_name: str,
    project_index: ProjectIndex,
    dependency_graph: DependencyGraph,
    parsed_trees: dict[str, ast.AST],
) -> tuple[list[str], list[str], list[tuple[str, int, int]]]:
    """Return (related_callers, related_dependencies, caller_arg_counts).

    Each item in `caller_arg_counts` is (caller_desc, num_pos_args, num_kw_args).
    """
    mod_name = project_index.get_module_for_file(file_path) or file_path_to_module_name(file_path)
    target_sym = project_index.resolve_symbol(mod_name, qualified_name) if mod_name else None

    related_callers: list[str] = []
    related_deps: list[str] = []
    caller_arg_counts: list[tuple[str, int, int, bool]] = []

    if target_sym is not None:
        caller_evidences = dependency_graph.get_callers_with_evidence(target_sym.id)
        for ev in caller_evidences:
            c_file = ev.caller_node.file_path
            c_qual = ev.caller_node.qualified_name
            c_line = ev.call_site.start_line
            call_summary = f"{c_file}:{c_qual} (line {c_line})"

            # Inspect AST call site if available to count arguments
            tree = parsed_trees.get(c_file)
            if tree is not None:
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and getattr(node, "lineno", -1) == c_line:
                        func_unparsed = _safe_unparse(node.func)
                        if func_unparsed == simple_name or func_unparsed.endswith(f".{simple_name}"):
                            has_starred = any(isinstance(a, ast.Starred) for a in node.args)
                            has_kwargs = any(k.arg is None for k in node.keywords)
                            is_dynamic = has_starred or has_kwargs
                            pos_count = len(node.args)
                            kw_count = len(node.keywords)
                            call_expr = _safe_unparse(node)
                            call_summary = f"{c_file}:{c_qual} (line {c_line}: `{call_expr}`)"
                            caller_arg_counts.append((call_summary, pos_count, kw_count, is_dynamic))
                            break
            related_callers.append(call_summary)

        callees = dependency_graph.get_callees(target_sym.id)
        for callee in callees:
            related_deps.append(f"{callee.file_path}:{callee.qualified_name}")

    return sorted(set(related_callers)), sorted(set(related_deps)), caller_arg_counts


def _extract_signature_spec(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, Any]:
    """Extract parameter names, defaults, required counts, and return annotation from a function AST."""
    posonly = [a.arg for a in getattr(node.args, "posonlyargs", [])]
    regular = [a.arg for a in node.args.args]
    all_pos = posonly + regular

    is_method = bool(all_pos and all_pos[0] in ("self", "cls"))
    effective_pos = all_pos[1:] if is_method else all_pos

    num_defaults = len(node.args.defaults)
    default_map: dict[str, str] = {}
    if num_defaults > 0:
        for arg_name, def_node in zip(all_pos[-num_defaults:], node.args.defaults, strict=False):
            default_map[arg_name] = _safe_unparse(def_node)

    kwonly_names = [a.arg for a in node.args.kwonlyargs]
    kwonly_defaults: dict[str, str] = {}
    for arg_name, kw_def in zip(kwonly_names, node.args.kw_defaults, strict=False):
        if kw_def is not None:
            kwonly_defaults[arg_name] = _safe_unparse(kw_def)

    required_pos = [p for p in effective_pos if p not in default_map]
    required_kwonly = [k for k in kwonly_names if k not in kwonly_defaults]

    mutable_defaults: list[str] = []
    for arg_name, def_node in zip(all_pos[-num_defaults:] if num_defaults else [], node.args.defaults, strict=False):
        if isinstance(def_node, (ast.List, ast.Dict, ast.Set)) or (
            isinstance(def_node, ast.Call)
            and isinstance(def_node.func, ast.Name)
            and def_node.func.id in {"list", "dict", "set"}
        ):
            mutable_defaults.append(f"{arg_name}={_safe_unparse(def_node)}")

    return {
        "effective_pos": effective_pos,
        "required_pos": required_pos,
        "default_map": default_map,
        "kwonly_names": kwonly_names,
        "required_kwonly": required_kwonly,
        "has_vararg": node.args.vararg is not None,
        "has_kwarg": node.args.kwarg is not None,
        "return_annotation": _safe_unparse(node.returns) if node.returns else None,
        "mutable_defaults": mutable_defaults,
    }


def _format_func_header(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    args_str = _safe_unparse(node.args)
    ret_str = f" -> {_safe_unparse(node.returns)}" if node.returns else ""
    return f"{prefix} {node.name}({args_str}){ret_str}:"


def _detect_signature_deltas(
    file_path: str,
    qual_name: str,
    before_fn: ast.FunctionDef | ast.AsyncFunctionDef,
    after_fn: ast.FunctionDef | ast.AsyncFunctionDef,
    related_callers: list[str],
    related_deps: list[str],
    caller_arg_counts: list[tuple[str, int, int, bool]],
) -> list[BehavioralDelta]:
    deltas: list[BehavioralDelta] = []
    before_spec = _extract_signature_spec(before_fn)
    after_spec = _extract_signature_spec(after_fn)

    before_header = _format_func_header(before_fn)
    after_header = _format_func_header(after_fn)

    changes: list[str] = []
    risks: list[str] = []

    # 1. Check default value removals on existing parameters
    removed_defaults = [
        p for p in after_spec["effective_pos"] if p in before_spec["default_map"] and p not in after_spec["default_map"]
    ]
    if removed_defaults:
        params_str = ", ".join(f"'{p}' (was `{p}={before_spec['default_map'][p]}`)" for p in removed_defaults)
        changes.append(
            f"Removed default value from parameter(s) {params_str}, increasing required positional arguments "
            f"from {len(before_spec['required_pos'])} to {len(after_spec['required_pos'])}."
        )
        risks.append(
            f"Callers invoking `{after_fn.name}` without explicitly passing {', '.join(repr(p) for p in removed_defaults)} "
            "will raise TypeError at runtime."
        )

    # 2. Check added required positional or keyword-only parameters
    added_req_pos = [
        p for p in after_spec["required_pos"] if p not in before_spec["effective_pos"] and p not in removed_defaults
    ]
    if added_req_pos:
        changes.append(f"Added required positional parameter(s): {', '.join(repr(p) for p in added_req_pos)}.")
        risks.append(
            f"Existing callers not supplying {', '.join(repr(p) for p in added_req_pos)} may fail with TypeError."
        )

    added_req_kw = [k for k in after_spec["required_kwonly"] if k not in before_spec["required_kwonly"]]
    if added_req_kw:
        changes.append(f"Added required keyword-only parameter(s): {', '.join(repr(k) for k in added_req_kw)}.")
        risks.append(f"Callers omitting keyword argument(s) {', '.join(repr(k) for k in added_req_kw)} will fail.")

    # 3. Check removed parameters
    removed_params = [p for p in before_spec["effective_pos"] if p not in after_spec["effective_pos"]]
    if removed_params and not after_spec["has_vararg"]:
        changes.append(f"Removed parameter(s) {', '.join(repr(p) for p in removed_params)} from `{after_fn.name}`.")
        risks.append("Callers passing removed positional or keyword arguments may fail with TypeError.")

    # 4. Check parameter reordering among shared parameters
    common_before = [p for p in before_spec["effective_pos"] if p in after_spec["effective_pos"]]
    common_after = [p for p in after_spec["effective_pos"] if p in before_spec["effective_pos"]]
    if common_before != common_after:
        changes.append(f"Reordered parameters from `({', '.join(common_before)})` to `({', '.join(common_after)})`.")
        risks.append("Positional callers may pass arguments to unintended parameters.")

    # 5. Check incompatible return annotation change
    b_ret = before_spec["return_annotation"]
    a_ret = after_spec["return_annotation"]
    if b_ret and a_ret and b_ret != a_ret:
        changes.append(f"Changed return type annotation from `{b_ret}` to `{a_ret}`.")
        risks.append(f"Downstream callers expecting `{b_ret}` return semantics may be impacted.")

    if changes:
        min_req = len(after_spec["required_pos"])
        broken_callers = [
            desc for desc, pos_cnt, kw_cnt, is_dyn in caller_arg_counts if not is_dyn and (pos_cnt + kw_cnt) < min_req
        ]
        if broken_callers:
            risks.append(
                f"Detected {len(broken_callers)} caller(s) passing fewer than {min_req} required argument(s): "
                + "; ".join(broken_callers)
                + "."
            )

        line_range = LineRange(start_line=after_fn.lineno, end_line=after_fn.lineno)
        delta_id = _compute_delta_id(
            file_path,
            BehavioralDeltaType.SIGNATURE_CONTRACT_CHANGE,
            qual_name,
            line_range,
            before_header,
            after_header,
        )
        deltas.append(
            BehavioralDelta(
                delta_id=delta_id,
                delta_type=BehavioralDeltaType.SIGNATURE_CONTRACT_CHANGE,
                file_path=file_path,
                symbol_name=after_fn.name,
                qualified_name=qual_name,
                line_range=line_range,
                changed_lines=[after_fn.lineno],
                before_evidence=before_header,
                after_evidence=after_header,
                related_callers=related_callers,
                related_dependencies=related_deps,
                confidence=Confidence.HIGH,
                observed_change=" ".join(changes),
                inferred_risk=" ".join(risks),
            )
        )

    # 6. Check newly introduced mutable default arguments
    new_mutable_defaults = [m for m in after_spec["mutable_defaults"] if m not in before_spec["mutable_defaults"]]
    if new_mutable_defaults:
        line_range = LineRange(start_line=after_fn.lineno, end_line=after_fn.lineno)
        delta_id = _compute_delta_id(
            file_path,
            BehavioralDeltaType.STATE_MUTATION_CHANGE,
            qual_name,
            line_range,
            before_header,
            after_header,
        )
        deltas.append(
            BehavioralDelta(
                delta_id=delta_id,
                delta_type=BehavioralDeltaType.STATE_MUTATION_CHANGE,
                file_path=file_path,
                symbol_name=after_fn.name,
                qualified_name=qual_name,
                line_range=line_range,
                changed_lines=[after_fn.lineno],
                before_evidence=before_header,
                after_evidence=after_header,
                related_callers=related_callers,
                related_dependencies=related_deps,
                confidence=Confidence.HIGH,
                observed_change=(
                    f"Introduced mutable default argument(s) {', '.join(f'`{m}`' for m in new_mutable_defaults)} "
                    f"in `{after_fn.name}`."
                ),
                inferred_risk=(
                    "In-place mutations to the default container will persist across subsequent calls that omit the argument."
                ),
            )
        )

    return deltas


def _is_early_exit_if(node: ast.If) -> bool:
    """Return True if `node.body` ends with or contains Return, Raise, Continue, or Break."""
    return any(isinstance(stmt, (ast.Return, ast.Raise, ast.Continue, ast.Break)) for stmt in node.body)


def _find_unguarded_operations_on_names(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    guarded_names: set[str],
) -> list[tuple[str, int, str]]:
    """Find divisions, subscripts, or calls in `func_node` referencing `guarded_names`."""
    ops: list[tuple[str, int, str]] = []
    for child in ast.walk(func_node):
        if isinstance(child, ast.BinOp) and isinstance(child.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            right_names = {n.id for n in ast.walk(child.right) if isinstance(n, ast.Name)}
            if right_names & guarded_names:
                ops.append(("division/modulo", getattr(child, "lineno", func_node.lineno), _safe_unparse(child)))
        elif isinstance(child, ast.Subscript):
            sub_names = {n.id for n in ast.walk(child) if isinstance(n, ast.Name)}
            if sub_names & guarded_names:
                ops.append(("subscript access", getattr(child, "lineno", func_node.lineno), _safe_unparse(child)))
    return ops


def _detect_guard_deltas(
    file_path: str,
    qual_name: str,
    before_fn: ast.FunctionDef | ast.AsyncFunctionDef,
    after_fn: ast.FunctionDef | ast.AsyncFunctionDef,
    file_diff: FileDiff,
    related_callers: list[str],
    related_deps: list[str],
) -> list[BehavioralDelta]:
    deltas: list[BehavioralDelta] = []

    before_ifs = [n for n in ast.walk(before_fn) if isinstance(n, ast.If)]
    after_ifs = [n for n in ast.walk(after_fn) if isinstance(n, ast.If)]

    before_test_map = {_safe_unparse(n.test): n for n in before_ifs if _safe_unparse(n.test)}
    after_test_map = {_safe_unparse(n.test): n for n in after_ifs if _safe_unparse(n.test)}

    removed_tests = [t for t in before_test_map if t not in after_test_map]
    added_tests = [t for t in after_test_map if t not in before_test_map]

    # Case 1: Condition modified at the same guard position (matched by identical body statements)
    paired_modified: set[str] = set()
    for rem_test in removed_tests:
        b_node = before_test_map[rem_test]
        b_body = [_safe_unparse(s) for s in b_node.body]
        for add_test in added_tests:
            if add_test in paired_modified:
                continue
            a_node = after_test_map[add_test]
            a_body = [_safe_unparse(s) for s in a_node.body]
            if b_body == a_body:
                paired_modified.add(rem_test)
                paired_modified.add(add_test)
                start_ln = getattr(a_node, "lineno", after_fn.lineno)
                end_ln = getattr(a_node, "end_lineno", start_ln)
                line_range = LineRange(start_line=start_ln, end_line=end_ln)
                before_ev = f"if {rem_test}:"
                after_ev = f"if {add_test}:"
                delta_id = _compute_delta_id(
                    file_path,
                    BehavioralDeltaType.GUARD_MODIFICATION,
                    qual_name,
                    line_range,
                    before_ev,
                    after_ev,
                )
                deltas.append(
                    BehavioralDelta(
                        delta_id=delta_id,
                        delta_type=BehavioralDeltaType.GUARD_MODIFICATION,
                        file_path=file_path,
                        symbol_name=after_fn.name,
                        qualified_name=qual_name,
                        line_range=line_range,
                        changed_lines=sorted(set(range(start_ln, end_ln + 1))),
                        before_evidence=before_ev,
                        after_evidence=after_ev,
                        related_callers=related_callers,
                        related_dependencies=related_deps,
                        confidence=Confidence.HIGH,
                        observed_change=(
                            f"Modified conditional guard in `{qual_name}` from `{before_ev}` to `{after_ev}`."
                        ),
                        inferred_risk=(
                            "Altered condition boundary or boolean logic may change which edge-case inputs trigger the branch; "
                            "verify boundary behavior matches specification."
                        ),
                    )
                )
                break

    # Case 2: Removed early-exit guard clauses
    for rem_test in removed_tests:
        if rem_test in paired_modified:
            continue
        b_node = before_test_map[rem_test]
        if not _is_early_exit_if(b_node):
            continue

        guarded_vars = {n.id for n in ast.walk(b_node.test) if isinstance(n, ast.Name)}
        ops = _find_unguarded_operations_on_names(after_fn, guarded_vars)
        before_ev = _safe_unparse(b_node)

        if ops:
            op_kind, op_line, op_expr = ops[0]
            after_ev = op_expr
            start_ln = min(op_line, after_fn.end_lineno or op_line)
            end_ln = op_line
            # Expand start_ln to include preceding added lines in the same hunk if present
            for hunk in file_diff.hunks:
                if hunk.new_line_range and hunk.new_line_range.contains_line(op_line) and hunk.added_line_numbers:
                    start_ln = min(min(hunk.added_line_numbers), op_line)
                    end_ln = max(max(hunk.added_line_numbers), op_line)
                    break
            risk_msg = (
                f"Downstream {op_kind} `{op_expr}` (line {op_line}) executes without the prior `if {rem_test}:` check, "
                f"which may raise an unhandled runtime error (e.g. ZeroDivisionError or boundary error) on edge inputs."
            )
        else:
            start_ln = after_fn.lineno
            end_ln = getattr(after_fn, "end_lineno", start_ln)
            after_ev = _safe_unparse(after_fn.body[0]) if after_fn.body else _format_func_header(after_fn)
            risk_msg = f"Inputs previously short-circuited by `if {rem_test}:` now continue into the main body of `{qual_name}`."

        line_range = LineRange(start_line=start_ln, end_line=max(start_ln, end_ln))
        delta_id = _compute_delta_id(
            file_path,
            BehavioralDeltaType.GUARD_REMOVAL,
            qual_name,
            line_range,
            before_ev,
            after_ev,
        )
        deltas.append(
            BehavioralDelta(
                delta_id=delta_id,
                delta_type=BehavioralDeltaType.GUARD_REMOVAL,
                file_path=file_path,
                symbol_name=after_fn.name,
                qualified_name=qual_name,
                line_range=line_range,
                changed_lines=sorted(set(range(line_range.start_line, line_range.end_line + 1))),
                before_evidence=before_ev,
                after_evidence=after_ev,
                related_callers=related_callers,
                related_dependencies=related_deps,
                confidence=Confidence.HIGH,
                observed_change=(f"Removed early-exit guard clause `if {rem_test}:` from `{qual_name}`."),
                inferred_risk=risk_msg,
            )
        )

    # Case 3: Added early-exit guard clauses (often a protective bug fix)
    for add_test in added_tests:
        if add_test in paired_modified:
            continue
        a_node = after_test_map[add_test]
        if not _is_early_exit_if(a_node):
            continue
        start_ln = getattr(a_node, "lineno", after_fn.lineno)
        end_ln = getattr(a_node, "end_lineno", start_ln)
        line_range = LineRange(start_line=start_ln, end_line=max(start_ln, end_ln))
        after_ev = _safe_unparse(a_node)
        delta_id = _compute_delta_id(
            file_path,
            BehavioralDeltaType.GUARD_ADDITION,
            qual_name,
            line_range,
            "",
            after_ev,
        )
        deltas.append(
            BehavioralDelta(
                delta_id=delta_id,
                delta_type=BehavioralDeltaType.GUARD_ADDITION,
                file_path=file_path,
                symbol_name=after_fn.name,
                qualified_name=qual_name,
                line_range=line_range,
                changed_lines=sorted(set(range(start_ln, end_ln + 1))),
                before_evidence="(no guard prior to operation)",
                after_evidence=after_ev,
                related_callers=related_callers,
                related_dependencies=related_deps,
                confidence=Confidence.MEDIUM,
                observed_change=(f"Added protective early-exit guard `if {add_test}:` in `{qual_name}`."),
                inferred_risk=(
                    "Adds defensive boundary handling for edge-case inputs; verify the guard condition "
                    "is accurate and does not unintentionally reject valid inputs (often a legitimate bug fix)."
                ),
            )
        )

    # Case 4: Removed boundary clamping calls (`max(...)` or `min(...)`)
    before_returns = [n for n in ast.walk(before_fn) if isinstance(n, ast.Return) and n.value is not None]
    after_returns = [n for n in ast.walk(after_fn) if isinstance(n, ast.Return) and n.value is not None]

    for b_ret in before_returns:
        b_val = b_ret.value
        if (
            isinstance(b_val, ast.Call)
            and isinstance(b_val.func, ast.Name)
            and b_val.func.id in _CLAMP_FUNCTIONS
            and len(b_val.args) == 2
        ):
            clamp_fn = b_val.func.id
            arg0_str = _safe_unparse(b_val.args[0])
            arg1_str = _safe_unparse(b_val.args[1])

            for a_ret in after_returns:
                a_val_str = _safe_unparse(a_ret.value)
                if a_val_str in (arg0_str, arg1_str):
                    bound_str = arg0_str if a_val_str == arg1_str else arg1_str
                    ret_ln = getattr(a_ret, "lineno", after_fn.lineno)
                    line_range = LineRange(start_line=ret_ln, end_line=ret_ln)
                    before_ev = _safe_unparse(b_ret)
                    after_ev = _safe_unparse(a_ret)
                    delta_id = _compute_delta_id(
                        file_path,
                        BehavioralDeltaType.GUARD_REMOVAL,
                        qual_name,
                        line_range,
                        before_ev,
                        after_ev,
                    )
                    bound_kind = "lower bound" if clamp_fn == "max" else "upper bound"
                    deltas.append(
                        BehavioralDelta(
                            delta_id=delta_id,
                            delta_type=BehavioralDeltaType.GUARD_REMOVAL,
                            file_path=file_path,
                            symbol_name=after_fn.name,
                            qualified_name=qual_name,
                            line_range=line_range,
                            changed_lines=[ret_ln],
                            before_evidence=before_ev,
                            after_evidence=after_ev,
                            related_callers=related_callers,
                            related_dependencies=related_deps,
                            confidence=Confidence.HIGH,
                            observed_change=(
                                f"Removed `{clamp_fn}({bound_str}, ...)` clamping call in `{qual_name}`, "
                                f"changing `{before_ev}` to `{after_ev}`."
                            ),
                            inferred_risk=(
                                f"Return value is no longer clamped to {bound_kind} `{bound_str}`, "
                                f"allowing `{a_val_str}` to underflow or overflow past `{bound_str}` on boundary inputs."
                            ),
                        )
                    )

    return deltas


def _is_exception_covered(exc_name: str, covering_set: set[str]) -> bool:
    """Return True if `exc_name` is caught by any handler in `covering_set`.

    Correctly enforces Python exception hierarchy:
    - `<bare except>` and `BaseException` catch all exceptions, including `KeyboardInterrupt` and `SystemExit`.
    - `Exception` catches all standard exceptions and custom subclasses of `Exception`,
      but does NOT catch `BaseException`, `KeyboardInterrupt`, `SystemExit`, or `GeneratorExit`.
    - Built-in exception inheritance (e.g. `LookupError` covering `KeyError`) is respected.
    """
    if "<bare except>" in covering_set or "BaseException" in covering_set:
        return True
    if exc_name in covering_set:
        return True

    is_non_standard = exc_name in {"BaseException", "KeyboardInterrupt", "SystemExit", "GeneratorExit"}
    if "Exception" in covering_set:
        if is_non_standard:
            return False
        builtin_cls = getattr(builtins, exc_name, None)
        if builtin_cls is not None and isinstance(builtin_cls, type) and issubclass(builtin_cls, BaseException):
            return issubclass(builtin_cls, Exception)
        return True

    exc_cls = getattr(builtins, exc_name, None)
    if exc_cls is not None and isinstance(exc_cls, type) and issubclass(exc_cls, BaseException):
        for cov in covering_set:
            cov_cls = getattr(builtins, cov, None)
            if (
                cov_cls is not None
                and isinstance(cov_cls, type)
                and issubclass(cov_cls, BaseException)
                and issubclass(exc_cls, cov_cls)
            ):
                return True

    return False


def _extract_caught_exception_names(handler: ast.ExceptHandler) -> list[str]:
    if handler.type is None:
        return ["<bare except>"]
    if isinstance(handler.type, ast.Tuple):
        return [_safe_unparse(elt) for elt in handler.type.elts if _safe_unparse(elt)]
    name = _safe_unparse(handler.type)
    return [name] if name else ["Exception"]


def _detect_exception_deltas(
    file_path: str,
    qual_name: str,
    before_fn: ast.FunctionDef | ast.AsyncFunctionDef,
    after_fn: ast.FunctionDef | ast.AsyncFunctionDef,
    related_callers: list[str],
    related_deps: list[str],
) -> list[BehavioralDelta]:
    deltas: list[BehavioralDelta] = []
    before_tries = [n for n in ast.walk(before_fn) if isinstance(n, ast.Try)]
    after_tries = [n for n in ast.walk(after_fn) if isinstance(n, ast.Try)]

    if before_tries and not after_tries:
        b_try = before_tries[0]
        caught: list[str] = []
        for h in b_try.handlers:
            caught.extend(_extract_caught_exception_names(h))
        start_ln = after_fn.lineno
        end_ln = getattr(after_fn, "end_lineno", start_ln)
        line_range = LineRange(start_line=start_ln, end_line=max(start_ln, end_ln))
        before_ev = _safe_unparse(b_try)
        after_ev = _safe_unparse(after_fn)
        delta_id = _compute_delta_id(
            file_path,
            BehavioralDeltaType.EXCEPTION_HANDLING_CHANGE,
            qual_name,
            line_range,
            before_ev,
            after_ev,
        )
        deltas.append(
            BehavioralDelta(
                delta_id=delta_id,
                delta_type=BehavioralDeltaType.EXCEPTION_HANDLING_CHANGE,
                file_path=file_path,
                symbol_name=after_fn.name,
                qualified_name=qual_name,
                line_range=line_range,
                changed_lines=sorted(set(range(start_ln, end_ln + 1))),
                before_evidence=before_ev,
                after_evidence=after_ev,
                related_callers=related_callers,
                related_dependencies=related_deps,
                confidence=Confidence.HIGH,
                observed_change=(
                    f"Removed `try/except` block previously catching `{', '.join(caught)}` in `{qual_name}`."
                ),
                inferred_risk=(
                    f"Exceptions ({', '.join(caught)}) raised inside `{qual_name}` are no longer caught locally "
                    "and will propagate uncaught to callers."
                ),
            )
        )
        return deltas

    for b_try, a_try in zip(before_tries, after_tries, strict=False):
        b_caught: list[str] = []
        for h in b_try.handlers:
            b_caught.extend(_extract_caught_exception_names(h))
        a_caught: list[str] = []
        for h in a_try.handlers:
            a_caught.extend(_extract_caught_exception_names(h))

        covering_set = set(a_caught)
        removed_excs = [e for e in b_caught if not _is_exception_covered(e, covering_set)]
        try_body_summary = _safe_unparse(a_try.body[0]) if a_try.body else "try block"
        start_ln = getattr(a_try, "lineno", after_fn.lineno)
        end_ln = getattr(a_try, "end_lineno", start_ln)
        line_range = LineRange(start_line=start_ln, end_line=max(start_ln, end_ln))

        if removed_excs:
            before_ev = _safe_unparse(b_try)
            after_ev = _safe_unparse(a_try)
            delta_id = _compute_delta_id(
                file_path,
                BehavioralDeltaType.EXCEPTION_HANDLING_CHANGE,
                qual_name,
                line_range,
                before_ev,
                after_ev,
            )
            rem_str = ", ".join(removed_excs)
            kept_str = ", ".join(a_caught) if a_caught else "none"
            deltas.append(
                BehavioralDelta(
                    delta_id=delta_id,
                    delta_type=BehavioralDeltaType.EXCEPTION_HANDLING_CHANGE,
                    file_path=file_path,
                    symbol_name=after_fn.name,
                    qualified_name=qual_name,
                    line_range=line_range,
                    changed_lines=sorted(set(range(start_ln, end_ln + 1))),
                    before_evidence=before_ev,
                    after_evidence=after_ev,
                    related_callers=related_callers,
                    related_dependencies=related_deps,
                    confidence=Confidence.HIGH,
                    observed_change=(
                        f"Removed exception handler(s) for `{rem_str}` around `{try_body_summary}` in `{qual_name}` "
                        f"(remaining caught exceptions: `{kept_str}`)."
                    ),
                    inferred_risk=(
                        f"If `{try_body_summary}` raises `{rem_str}`, the exception will no longer be caught "
                        f"by `{qual_name}`, potentially causing an unhandled crash on malformed or unexpected inputs."
                    ),
                )
            )

        # Check if exception handling was broadened to bare except or BaseException/Exception swallowing
        broad_added = [
            e for e in a_caught if e in ("<bare except>", "BaseException", "Exception") and e not in b_caught
        ]
        if broad_added:
            before_ev = _safe_unparse(b_try)
            after_ev = _safe_unparse(a_try)
            delta_id = _compute_delta_id(
                file_path,
                BehavioralDeltaType.EXCEPTION_HANDLING_CHANGE,
                qual_name,
                line_range,
                before_ev,
                f"broad:{after_ev}",
            )
            has_interrupt_catch = any(e in ("<bare except>", "BaseException") for e in broad_added)
            if has_interrupt_catch:
                risk_desc = (
                    "Broad catch clauses (`BaseException` or bare `except:`) intercept system interrupts "
                    "(KeyboardInterrupt, SystemExit) and unexpected programming errors, preventing graceful process termination."
                )
            else:
                risk_desc = (
                    "Broad catch clauses (`except Exception:`) may mask unexpected programming errors or defects, "
                    "though standard Python exception hierarchy ensures KeyboardInterrupt and SystemExit are not intercepted."
                )
            deltas.append(
                BehavioralDelta(
                    delta_id=delta_id,
                    delta_type=BehavioralDeltaType.EXCEPTION_HANDLING_CHANGE,
                    file_path=file_path,
                    symbol_name=after_fn.name,
                    qualified_name=qual_name,
                    line_range=line_range,
                    changed_lines=sorted(set(range(start_ln, end_ln + 1))),
                    before_evidence=before_ev,
                    after_evidence=after_ev,
                    related_callers=related_callers,
                    related_dependencies=related_deps,
                    confidence=Confidence.MEDIUM,
                    observed_change=(
                        f"Broadened exception handler in `{qual_name}` to catch `{', '.join(broad_added)}`."
                    ),
                    inferred_risk=risk_desc,
                )
            )

    return deltas


def _unwrap_copied_source(expr: ast.AST) -> str | None:
    """If `expr` is `dict(x)`, `list(x)`, `x.copy()`, `copy.deepcopy(x)`, or `x[:]`, return unparsed `x`."""
    if isinstance(expr, ast.Call):
        if isinstance(expr.func, ast.Name) and expr.func.id in _COPY_CONSTRUCTORS and len(expr.args) == 1:
            return _safe_unparse(expr.args[0])
        if isinstance(expr.func, ast.Attribute) and expr.func.attr in _COPY_METHODS:
            if len(expr.args) == 0:
                return _safe_unparse(expr.func.value)
            if len(expr.args) == 1 and _safe_unparse(expr.func.value) == "copy":
                return _safe_unparse(expr.args[0])
    if (
        isinstance(expr, ast.Subscript)
        and isinstance(expr.slice, ast.Slice)
        and expr.slice.lower is None
        and expr.slice.upper is None
        and expr.slice.step is None
    ):
        return _safe_unparse(expr.value)
    return None


def _find_mutations_on_var(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    var_name: str,
) -> list[tuple[int, str]]:
    """Find in-place mutations (`var.update(...)`, `var[k] = v`, `del var[k]`) on `var_name`."""
    mutations: list[tuple[int, str]] = []
    for child in ast.walk(func_node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
            if _safe_unparse(child.func.value) == var_name and child.func.attr in _MUTATING_METHODS:
                mutations.append((getattr(child, "lineno", func_node.lineno), _safe_unparse(child)))
        elif isinstance(child, (ast.Assign, ast.AugAssign)):
            targets = child.targets if isinstance(child, ast.Assign) else [child.target]
            for t in targets:
                if isinstance(t, ast.Subscript) and _safe_unparse(t.value) == var_name:
                    mutations.append((getattr(child, "lineno", func_node.lineno), _safe_unparse(child)))
        elif isinstance(child, ast.Delete):
            for t in child.targets:
                if isinstance(t, ast.Subscript) and _safe_unparse(t.value) == var_name:
                    mutations.append((getattr(child, "lineno", func_node.lineno), _safe_unparse(child)))
    return sorted(mutations, key=lambda item: item[0])


def _detect_state_mutation_deltas(
    file_path: str,
    qual_name: str,
    before_fn: ast.FunctionDef | ast.AsyncFunctionDef,
    after_fn: ast.FunctionDef | ast.AsyncFunctionDef,
    related_callers: list[str],
    related_deps: list[str],
) -> list[BehavioralDelta]:
    deltas: list[BehavioralDelta] = []

    before_copied_vars: dict[str, tuple[str, str]] = {}
    for node in ast.walk(before_fn):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            var_name = node.targets[0].id
            copied_src = _unwrap_copied_source(node.value)
            if copied_src:
                before_copied_vars[var_name] = (copied_src, _safe_unparse(node))

    for node in ast.walk(after_fn):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            var_name = node.targets[0].id
            if var_name in before_copied_vars:
                expected_src, before_assign_str = before_copied_vars[var_name]
                after_rhs_str = _safe_unparse(node.value)
                if after_rhs_str == expected_src:
                    mutations = _find_mutations_on_var(after_fn, var_name)
                    assign_ln = getattr(node, "lineno", after_fn.lineno)
                    end_ln = mutations[-1][0] if mutations else assign_ln
                    line_range = LineRange(start_line=assign_ln, end_line=max(assign_ln, end_ln))
                    after_assign_str = _safe_unparse(node)
                    mut_desc = (
                        f" followed by in-place mutation `{mutations[0][1]}` (line {mutations[0][0]})"
                        if mutations
                        else ""
                    )
                    after_ev = f"{after_assign_str}\n{mutations[0][1]}" if mutations else after_assign_str
                    delta_id = _compute_delta_id(
                        file_path,
                        BehavioralDeltaType.STATE_MUTATION_CHANGE,
                        qual_name,
                        line_range,
                        before_assign_str,
                        after_ev,
                    )
                    deltas.append(
                        BehavioralDelta(
                            delta_id=delta_id,
                            delta_type=BehavioralDeltaType.STATE_MUTATION_CHANGE,
                            file_path=file_path,
                            symbol_name=after_fn.name,
                            qualified_name=qual_name,
                            line_range=line_range,
                            changed_lines=sorted(set(range(assign_ln, max(assign_ln, end_ln) + 1))),
                            before_evidence=before_assign_str,
                            after_evidence=after_ev,
                            related_callers=related_callers,
                            related_dependencies=related_deps,
                            confidence=Confidence.HIGH,
                            observed_change=(
                                f"Replaced defensive copy `{before_assign_str}` with direct reference aliasing "
                                f"`{after_assign_str}` in `{qual_name}`{mut_desc}."
                            ),
                            inferred_risk=(
                                f"Mutating `{var_name}` in-place now directly mutates shared/caller state `{expected_src}`, "
                                "potentially causing cross-call or cross-request state pollution."
                            ),
                        )
                    )

    # Check direct in-place mutations added on `self.<attr>` or input parameters
    spec = _extract_signature_spec(after_fn)
    tracked_targets = {
        f"self.{node.attr}"
        for node in ast.walk(after_fn)
        if isinstance(node, ast.Attribute) and _safe_unparse(node.value) == "self"
    }
    tracked_targets.update(spec["effective_pos"])

    for target_expr in sorted(tracked_targets):
        before_muts = _find_mutations_on_var(before_fn, target_expr)
        after_muts = _find_mutations_on_var(after_fn, target_expr)
        if after_muts and not before_muts:
            mut_ln, mut_str = after_muts[0]
            line_range = LineRange(start_line=mut_ln, end_line=mut_ln)
            delta_id = _compute_delta_id(
                file_path,
                BehavioralDeltaType.STATE_MUTATION_CHANGE,
                qual_name,
                line_range,
                "",
                mut_str,
            )
            deltas.append(
                BehavioralDelta(
                    delta_id=delta_id,
                    delta_type=BehavioralDeltaType.STATE_MUTATION_CHANGE,
                    file_path=file_path,
                    symbol_name=after_fn.name,
                    qualified_name=qual_name,
                    line_range=line_range,
                    changed_lines=[mut_ln],
                    before_evidence=f"(no in-place mutation on `{target_expr}`)",
                    after_evidence=mut_str,
                    related_callers=related_callers,
                    related_dependencies=related_deps,
                    confidence=Confidence.MEDIUM,
                    observed_change=(f"Added in-place mutation `{mut_str}` on `{target_expr}` in `{qual_name}`."),
                    inferred_risk=(
                        f"Directly mutates `{target_expr}` in-place; verify whether callers or instance state "
                        "expect `{target_expr}` to remain unmodified."
                    ),
                )
            )

    return deltas


def _detect_resource_lifecycle_deltas(
    file_path: str,
    qual_name: str,
    before_fn: ast.FunctionDef | ast.AsyncFunctionDef,
    after_fn: ast.FunctionDef | ast.AsyncFunctionDef,
    related_callers: list[str],
    related_deps: list[str],
) -> list[BehavioralDelta]:
    deltas: list[BehavioralDelta] = []

    before_withs = [n for n in ast.walk(before_fn) if isinstance(n, (ast.With, ast.AsyncWith))]
    after_withs = [n for n in ast.walk(after_fn) if isinstance(n, (ast.With, ast.AsyncWith))]

    if len(before_withs) > len(after_withs):
        b_with_items = [_safe_unparse(item.context_expr) for w in before_withs for item in w.items]
        a_with_items = {_safe_unparse(item.context_expr) for w in after_withs for item in w.items}
        removed_ctx = [c for c in b_with_items if c not in a_with_items]
        if removed_ctx:
            start_ln = after_fn.lineno
            end_ln = getattr(after_fn, "end_lineno", start_ln)
            line_range = LineRange(start_line=start_ln, end_line=max(start_ln, end_ln))
            before_ev = f"with {', '.join(removed_ctx)}:"
            after_ev = _safe_unparse(after_fn)
            delta_id = _compute_delta_id(
                file_path,
                BehavioralDeltaType.RESOURCE_LIFECYCLE_CHANGE,
                qual_name,
                line_range,
                before_ev,
                after_ev,
            )
            deltas.append(
                BehavioralDelta(
                    delta_id=delta_id,
                    delta_type=BehavioralDeltaType.RESOURCE_LIFECYCLE_CHANGE,
                    file_path=file_path,
                    symbol_name=after_fn.name,
                    qualified_name=qual_name,
                    line_range=line_range,
                    changed_lines=sorted(set(range(start_ln, end_ln + 1))),
                    before_evidence=before_ev,
                    after_evidence=after_ev,
                    related_callers=related_callers,
                    related_dependencies=related_deps,
                    confidence=Confidence.HIGH,
                    observed_change=(
                        f"Removed `with` context manager wrapping `{', '.join(removed_ctx)}` in `{qual_name}`."
                    ),
                    inferred_risk=(
                        "Resource acquisition is no longer managed by a context manager; verify deterministic "
                        "cleanup on both normal and exception paths to prevent resource leaks."
                    ),
                )
            )

    before_closes = [
        _safe_unparse(n)
        for n in ast.walk(before_fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in _RESOURCE_CLEANUP_METHODS
    ]
    after_closes = {
        _safe_unparse(n)
        for n in ast.walk(after_fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in _RESOURCE_CLEANUP_METHODS
    }
    removed_closes = [c for c in before_closes if c not in after_closes]
    if removed_closes:
        start_ln = after_fn.lineno
        end_ln = getattr(after_fn, "end_lineno", start_ln)
        line_range = LineRange(start_line=start_ln, end_line=max(start_ln, end_ln))
        before_ev = ", ".join(removed_closes)
        after_ev = _safe_unparse(after_fn)
        delta_id = _compute_delta_id(
            file_path,
            BehavioralDeltaType.RESOURCE_LIFECYCLE_CHANGE,
            qual_name,
            line_range,
            before_ev,
            after_ev,
        )
        deltas.append(
            BehavioralDelta(
                delta_id=delta_id,
                delta_type=BehavioralDeltaType.RESOURCE_LIFECYCLE_CHANGE,
                file_path=file_path,
                symbol_name=after_fn.name,
                qualified_name=qual_name,
                line_range=line_range,
                changed_lines=sorted(set(range(start_ln, end_ln + 1))),
                before_evidence=before_ev,
                after_evidence=after_ev,
                related_callers=related_callers,
                related_dependencies=related_deps,
                confidence=Confidence.HIGH,
                observed_change=(f"Removed explicit resource cleanup call(s) `{before_ev}` in `{qual_name}`."),
                inferred_risk=(
                    "Underlying handle, connection, or lock may remain open after function exit if not closed elsewhere."
                ),
            )
        )

    return deltas


def _is_none_return(node: ast.Return) -> bool:
    if node.value is None:
        return True
    return isinstance(node.value, ast.Constant) and node.value.value is None


def _simple_assignment_name(statement: ast.stmt) -> str | None:
    """Return the single local name assigned by a simple assignment statement."""
    target: ast.expr | None = None
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        target = statement.targets[0]
    elif isinstance(statement, ast.AnnAssign):
        target = statement.target
    return target.id if isinstance(target, ast.Name) else None


def _detect_conditional_binding_deltas(
    file_path: str,
    qual_name: str,
    before_fn: ast.FunctionDef | ast.AsyncFunctionDef,
    after_fn: ast.FunctionDef | ast.AsyncFunctionDef,
    related_callers: list[str],
    related_deps: list[str],
) -> list[BehavioralDelta]:
    """Detect a formerly unconditional local binding made conditional before use.

    This narrowly recognizes a structural replacement: an earlier top-level
    assignment becomes the same assignment inside an ``if`` without an ``else``
    and a later top-level statement reads that name. It is evidence of a changed
    local-variable contract, not a claim that every conditional is defective.
    """
    before_assignments = {
        name: statement
        for statement in before_fn.body
        if (name := _simple_assignment_name(statement)) is not None
    }
    deltas: list[BehavioralDelta] = []
    for index, statement in enumerate(after_fn.body):
        if not isinstance(statement, ast.If) or statement.orelse:
            continue
        for nested in statement.body:
            name = _simple_assignment_name(nested)
            if name is None or name not in before_assignments:
                continue
            before_assignment = before_assignments[name]
            before_value = getattr(before_assignment, "value", None)
            after_value = getattr(nested, "value", None)
            if before_value is None or after_value is None or ast.dump(before_value) != ast.dump(after_value):
                continue

            later_use: ast.Name | None = None
            reassigned = False
            for later_statement in after_fn.body[index + 1 :]:
                if _simple_assignment_name(later_statement) == name:
                    reassigned = True
                    break
                for node in ast.walk(later_statement):
                    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == name:
                        later_use = node
                        break
                if later_use is not None:
                    break
            if reassigned or later_use is None:
                continue

            line = getattr(nested, "lineno", getattr(statement, "lineno", after_fn.lineno))
            line_range = LineRange(start_line=line, end_line=getattr(nested, "end_lineno", line))
            before_ev = _safe_unparse(before_assignment)
            after_ev = _safe_unparse(statement)
            delta_id = _compute_delta_id(
                file_path,
                BehavioralDeltaType.DATA_FLOW_CONTRACT_CHANGE,
                qual_name,
                line_range,
                before_ev,
                after_ev,
            )
            deltas.append(
                BehavioralDelta(
                    delta_id=delta_id,
                    delta_type=BehavioralDeltaType.DATA_FLOW_CONTRACT_CHANGE,
                    file_path=file_path,
                    symbol_name=after_fn.name,
                    qualified_name=qual_name,
                    line_range=line_range,
                    changed_lines=list(range(line_range.start_line, line_range.end_line + 1)),
                    before_evidence=before_ev,
                    after_evidence=after_ev,
                    related_callers=related_callers,
                    related_dependencies=related_deps,
                    confidence=Confidence.HIGH,
                    observed_change=(
                        f"Made local binding `{name}` conditional in `{qual_name}` while a later statement still reads it."
                    ),
                    inferred_risk=(
                        f"When the new condition is false, `{name}` may be unbound at the later use; verify all paths "
                        "initialize the value or return before that use."
                    ),
                )
            )
    return deltas


def _detect_return_behavior_deltas(
    file_path: str,
    qual_name: str,
    before_fn: ast.FunctionDef | ast.AsyncFunctionDef,
    after_fn: ast.FunctionDef | ast.AsyncFunctionDef,
    existing_deltas: list[BehavioralDelta],
    related_callers: list[str],
    related_deps: list[str],
) -> list[BehavioralDelta]:
    """Detect newly introduced None return paths when no prior delta already explains the return change."""
    if any(
        d.qualified_name == qual_name
        and d.delta_type
        in {
            BehavioralDeltaType.GUARD_REMOVAL,
            BehavioralDeltaType.GUARD_ADDITION,
            BehavioralDeltaType.GUARD_MODIFICATION,
        }
        for d in existing_deltas
    ):
        return []

    deltas: list[BehavioralDelta] = []
    before_returns = [n for n in ast.walk(before_fn) if isinstance(n, ast.Return)]
    after_returns = [n for n in ast.walk(after_fn) if isinstance(n, ast.Return)]

    before_had_none = any(_is_none_return(r) for r in before_returns)
    after_none_returns = [r for r in after_returns if _is_none_return(r)]

    if before_returns and not before_had_none and after_none_returns:
        r_node = after_none_returns[0]
        r_ln = getattr(r_node, "lineno", after_fn.lineno)
        line_range = LineRange(start_line=r_ln, end_line=r_ln)
        before_ev = _safe_unparse(before_returns[0])
        after_ev = _safe_unparse(r_node) or "return None"
        delta_id = _compute_delta_id(
            file_path,
            BehavioralDeltaType.RETURN_BEHAVIOR_CHANGE,
            qual_name,
            line_range,
            before_ev,
            after_ev,
        )
        deltas.append(
            BehavioralDelta(
                delta_id=delta_id,
                delta_type=BehavioralDeltaType.RETURN_BEHAVIOR_CHANGE,
                file_path=file_path,
                symbol_name=after_fn.name,
                qualified_name=qual_name,
                line_range=line_range,
                changed_lines=[r_ln],
                before_evidence=before_ev,
                after_evidence=after_ev,
                related_callers=related_callers,
                related_dependencies=related_deps,
                confidence=Confidence.HIGH,
                observed_change=(
                    f"Introduced `None` return path (`{after_ev}` at line {r_ln}) in `{qual_name}`, "
                    "which previously returned non-None values on all return statements."
                ),
                inferred_risk=(
                    "Callers dereferencing the return value of `{qual_name}` without a `None` check "
                    "may encounter AttributeError or TypeError."
                ),
            )
        )

    return deltas


def serialize_behavioral_deltas(deltas: list[BehavioralDelta]) -> str:
    """Serialize behavioral deltas into a deterministic, human- and LLM-readable evidence block."""
    if not deltas:
        return ""

    blocks: list[str] = []
    for idx, delta in enumerate(deltas, start=1):
        loc_str = (
            f"{delta.file_path}:{delta.line_range.start_line}"
            if delta.line_range.start_line == delta.line_range.end_line
            else f"{delta.file_path}:{delta.line_range.start_line}-{delta.line_range.end_line}"
        )
        sym_str = delta.affected_symbol or "<module>"
        lines = [
            f"[DELTA {idx}] type={delta.delta_type.value} | confidence={delta.confidence.value} | "
            f"location={loc_str} | symbol={sym_str}",
            f"  Before Evidence : {delta.before_evidence or '(none)'}",
            f"  After Evidence  : {delta.after_evidence or '(none)'}",
            f"  Observed Change : {delta.observed_change}",
            f"  Inferred Risk   : {delta.inferred_risk}",
        ]
        if delta.related_callers:
            lines.append(f"  Related Callers : {'; '.join(delta.related_callers)}")
        if delta.related_dependencies:
            lines.append(f"  Dependencies    : {'; '.join(delta.related_dependencies)}")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def analyze_behavioral_deltas(
    diff_bundle: DiffBundle,
    contexts: dict[str, FileContext] | None = None,
    *,
    repo_root: Path | None = None,
    project_index: ProjectIndex | None = None,
    dependency_graph: DependencyGraph | None = None,
    context_result: Any | None = None,
    enabled: bool = True,
) -> BehavioralDeltaResult:
    """Deterministically extract BehavioralDelta records across reviewable files in `diff_bundle`.

    Reuses `PythonAstAnalyzer`, `ProjectIndex`, `DependencyGraph`, and `identify_changed_symbols`
    without making any LLM requests or bypassing `FindingIntelligenceEngine`.
    """
    if not enabled:
        return BehavioralDeltaResult(
            deltas=[],
            files_analyzed=0,
            serialized_summary="",
            estimated_tokens=0,
        )

    analyzer = PythonAstAnalyzer()
    active_index = project_index
    active_graph = dependency_graph
    parsed_trees: dict[str, ast.AST] = {}

    if active_index is None or active_graph is None:
        active_index, active_graph, parsed_trees = _build_in_memory_index_and_graph(
            diff_bundle=diff_bundle,
            contexts=contexts,
            repo_root=repo_root,
            analyzer=analyzer,
        )
    else:
        # Populate AST trees for indexed files when repo_root is available
        for rel_path in active_index.file_analyses:
            if repo_root is not None:
                with contextlib.suppress(Exception):
                    safe_p = ensure_safe_repo_file(repo_root, rel_path)
                    if safe_p.exists() and safe_p.is_file():
                        parsed_trees[rel_path] = ast.parse(safe_p.read_text(encoding="utf-8"), filename=rel_path)

    all_deltas: list[BehavioralDelta] = []
    files_analyzed = 0

    for file_diff in diff_bundle.reviewable_files:
        norm_path = normalize_repo_relative_path(file_diff.new_path)
        if not norm_path.endswith(".py"):
            continue

        files_analyzed += 1
        file_ctx = contexts.get(norm_path) if contexts else None
        before_src, after_src, _ = _reconstruct_before_and_after_source(
            file_diff=file_diff,
            file_context=file_ctx,
            repo_root=repo_root,
        )
        if not before_src.strip() or not after_src.strip():
            continue

        try:
            before_tree = ast.parse(before_src, filename=norm_path)
            after_tree = ast.parse(after_src, filename=norm_path)
        except SyntaxError:
            continue

        parsed_trees.setdefault(norm_path, after_tree)

        after_analysis = active_index.get_analysis(norm_path) or analyzer.analyze_source(
            after_src,
            file_path=norm_path,
        )
        changed_syms_res = identify_changed_symbols(file_diff, after_analysis)
        changed_qual_names = {cs.qualified_name for cs in changed_syms_res.changed_symbols}

        before_collector = _ScopedFunctionCollector()
        before_collector.visit(before_tree)
        after_collector = _ScopedFunctionCollector()
        after_collector.visit(after_tree)

        for qual_name, after_fn in sorted(after_collector.functions.items()):
            before_fn = before_collector.functions.get(qual_name)
            if before_fn is None:
                continue

            fn_start = getattr(after_fn, "lineno", 1)
            fn_end = max(fn_start, getattr(after_fn, "end_lineno", fn_start))
            fn_range = LineRange(start_line=fn_start, end_line=fn_end)

            if qual_name not in changed_qual_names and not file_diff.has_changed_overlap(fn_range):
                continue

            if ast.dump(before_fn) == ast.dump(after_fn):
                continue

            related_callers, related_deps, caller_arg_counts = _collect_caller_details(
                file_path=norm_path,
                qualified_name=qual_name,
                simple_name=after_fn.name,
                project_index=active_index,
                dependency_graph=active_graph,
                parsed_trees=parsed_trees,
            )

            fn_deltas: list[BehavioralDelta] = []
            fn_deltas.extend(
                _detect_signature_deltas(
                    file_path=norm_path,
                    qual_name=qual_name,
                    before_fn=before_fn,
                    after_fn=after_fn,
                    related_callers=related_callers,
                    related_deps=related_deps,
                    caller_arg_counts=caller_arg_counts,
                )
            )
            fn_deltas.extend(
                _detect_guard_deltas(
                    file_path=norm_path,
                    qual_name=qual_name,
                    before_fn=before_fn,
                    after_fn=after_fn,
                    file_diff=file_diff,
                    related_callers=related_callers,
                    related_deps=related_deps,
                )
            )
            fn_deltas.extend(
                _detect_exception_deltas(
                    file_path=norm_path,
                    qual_name=qual_name,
                    before_fn=before_fn,
                    after_fn=after_fn,
                    related_callers=related_callers,
                    related_deps=related_deps,
                )
            )
            fn_deltas.extend(
                _detect_state_mutation_deltas(
                    file_path=norm_path,
                    qual_name=qual_name,
                    before_fn=before_fn,
                    after_fn=after_fn,
                    related_callers=related_callers,
                    related_deps=related_deps,
                )
            )
            fn_deltas.extend(
                _detect_resource_lifecycle_deltas(
                    file_path=norm_path,
                    qual_name=qual_name,
                    before_fn=before_fn,
                    after_fn=after_fn,
                    related_callers=related_callers,
                    related_deps=related_deps,
                )
            )
            fn_deltas.extend(
                _detect_conditional_binding_deltas(
                    file_path=norm_path,
                    qual_name=qual_name,
                    before_fn=before_fn,
                    after_fn=after_fn,
                    related_callers=related_callers,
                    related_deps=related_deps,
                )
            )
            fn_deltas.extend(
                _detect_return_behavior_deltas(
                    file_path=norm_path,
                    qual_name=qual_name,
                    before_fn=before_fn,
                    after_fn=after_fn,
                    existing_deltas=fn_deltas,
                    related_callers=related_callers,
                    related_deps=related_deps,
                )
            )
            all_deltas.extend(fn_deltas)

    serialized = serialize_behavioral_deltas(all_deltas)
    est_tokens = estimate_token_count(serialized) if serialized else 0

    return BehavioralDeltaResult(
        deltas=all_deltas,
        files_analyzed=files_analyzed,
        serialized_summary=serialized,
        estimated_tokens=est_tokens,
    )
