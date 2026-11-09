"""Interprocedural cross-file contract analysis engine (GOAL 28.3)."""

from __future__ import annotations

import ast
from dataclasses import dataclass

from polaris.contracts.consumer_tracker import (
    find_consumer_subscripts,
    infer_return_contract,
    safe_unparse,
)
from polaris.contracts.models import (
    ContractFinding,
    ContractKind,
    IncompatibilityEvidence,
    InferredContract,
    PropagationStep,
)
from polaris.core.models import CandidateFinding, Confidence, FindingCategory, LineRange, Severity
from polaris.guardrails.models import GuardrailConfidence


@dataclass
class _FileAST:
    file_path: str
    content: str
    tree: ast.AST
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef]
    imports: dict[str, tuple[str, str]]  # local_alias -> (module_path, exported_symbol)


def _normalize_mod_path(module_str: str) -> str:
    """Convert a dotted Python import path into a relative file path (e.g. 'adapters.id' -> 'adapters/id.py')."""
    rel = module_str.replace(".", "/")
    return f"{rel}.py"


def _parse_file(file_path: str, content: str, max_file_size_bytes: int) -> _FileAST | None:
    if len(content.encode("utf-8")) > max_file_size_bytes:
        return None
    try:
        tree = ast.parse(content, filename=file_path)
    except SyntaxError:
        return None

    funcs: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs[node.name] = node

    # Collect imports: from X import Y as Z
    imports: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            mod_file = _normalize_mod_path(node.module)
            for alias in node.names:
                local_name = alias.asname or alias.name
                imports[local_name] = (mod_file, alias.name)

    return _FileAST(
        file_path=file_path,
        content=content,
        tree=tree,
        functions=funcs,
        imports=imports,
    )


class CrossFileContractEngine:
    """Engine for bounded interprocedural cross-file contract propagation."""

    def __init__(
        self,
        max_depth: int = 5,
        max_nodes: int = 50,
        max_file_size_bytes: int = 500_000,
    ) -> None:
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self.max_file_size_bytes = max_file_size_bytes

    def analyze_contracts(
        self,
        changed_file: str,
        before_content: str | None,
        after_content: str,
        related_files: dict[str, str],  # path -> content
    ) -> list[ContractFinding]:
        """Analyze changed function return contracts and trace callers/consumers across related files."""
        findings: list[ContractFinding] = []

        # Parse changed file
        after_parsed = _parse_file(changed_file, after_content, self.max_file_size_bytes)
        if not after_parsed:
            return findings

        before_parsed = _parse_file(changed_file, before_content, self.max_file_size_bytes) if before_content else None

        # Parse all related files
        parsed_related: dict[str, _FileAST] = {}
        for path, code in related_files.items():
            # Normalize path slashes to forward slashes
            norm_p = path.replace("\\", "/")
            if norm_p != changed_file:
                p_ast = _parse_file(norm_p, code, self.max_file_size_bytes)
                if p_ast:
                    parsed_related[norm_p] = p_ast

        # Inspect each function in changed_file
        for func_name, after_func in after_parsed.functions.items():
            before_func = before_parsed.functions.get(func_name) if before_parsed else None

            after_contract = infer_return_contract(after_func)
            before_contract = infer_return_contract(before_func) if before_func else None

            # Detect if a contract weakened / broke
            # Specific trigger: previously guaranteed keys, now SCALAR_OR_PASSTHROUGH, NONE or UNKNOWN
            if (
                before_contract
                and before_contract.kind == ContractKind.DICT_LITERAL
                and before_contract.guaranteed_keys
                and (
                    after_contract.kind != ContractKind.DICT_LITERAL
                    or not set(before_contract.guaranteed_keys).issubset(set(after_contract.guaranteed_keys))
                )
            ):
                    # Potential contract break! Trace downstream consumers across files
                    missing_keys = set(before_contract.guaranteed_keys) - set(after_contract.guaranteed_keys)
                    traced = self._trace_consumers(
                        origin_file=changed_file,
                        origin_symbol=func_name,
                        origin_line=getattr(after_func, "lineno", 1),
                        before_contract=before_contract,
                        after_contract=after_contract,
                        missing_keys=missing_keys,
                        all_files=parsed_related,
                    )
                    findings.extend(traced)

        return findings

    def _trace_consumers(
        self,
        origin_file: str,
        origin_symbol: str,
        origin_line: int,
        before_contract: InferredContract,
        after_contract: InferredContract,
        missing_keys: set[str],
        all_files: dict[str, _FileAST],
    ) -> list[ContractFinding]:
        """Search downstream callers using BFS propagation bounded by max_depth and max_nodes."""
        findings: list[ContractFinding] = []

        # Queue of (current_file, current_symbol, current_line, path_steps, visited_symbols)
        queue: list[tuple[str, str, int, list[PropagationStep], set[str]]] = [
            (
                origin_file,
                origin_symbol,
                origin_line,
                [
                    PropagationStep(
                        step_index=1,
                        file_path=origin_file,
                        symbol=origin_symbol,
                        line_number=origin_line,
                        action="origin_definition",
                        expression=after_contract.raw_expression,
                    )
                ],
                {f"{origin_file}:{origin_symbol}"},
            )
        ]

        nodes_visited = 0

        while queue and nodes_visited < self.max_nodes:
            curr_file, curr_sym, curr_line, curr_path, visited = queue.pop(0)
            nodes_visited += 1

            if len(curr_path) > self.max_depth:
                continue

            # Look across all files for callers of curr_sym from curr_file
            for candidate_path, candidate_ast in all_files.items():
                # Check if candidate imports curr_sym from curr_file
                matching_aliases = [
                    alias
                    for alias, (mod, exp) in candidate_ast.imports.items()
                    if exp == curr_sym and (mod == curr_file or curr_file.endswith(mod))
                ]

                if not matching_aliases:
                    continue

                for alias in matching_aliases:
                    # In candidate_ast, check which functions call `alias(...)`
                    for caller_name, caller_func in candidate_ast.functions.items():
                        caller_key = f"{candidate_path}:{caller_name}"
                        if caller_key in visited:
                            continue  # Break cycle

                        # Check if caller calls alias(...)
                        call_nodes: list[ast.Call] = []
                        for n in ast.walk(caller_func):
                            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == alias:
                                call_nodes.append(n)

                        if not call_nodes:
                            continue

                        # Caller calls alias! Now check if caller directly consumes missing_keys
                        # or passes the call through in its return statement
                        subscripts = find_consumer_subscripts(caller_func)
                        for access in subscripts:
                            if access.required_key in missing_keys:
                                # Incompatible consumer found!
                                new_step = PropagationStep(
                                    step_index=len(curr_path) + 1,
                                    file_path=candidate_path,
                                    symbol=caller_name,
                                    line_number=access.line_number,
                                    action="consumes_subscript",
                                    expression=f"{safe_unparse(access.target_expr)}['{access.required_key}']",
                                )
                                full_path = curr_path + [new_step]

                                # Determine confidence:
                                # If after_contract is SCALAR_OR_PASSTHROUGH with unknown parameter type -> SUSPECTED
                                # If after_contract is NONE or explicit incompatible literal -> CONFIRMED
                                if after_contract.kind == ContractKind.NONE:
                                    confidence = GuardrailConfidence.CONFIRMED
                                    limitations = []
                                elif after_contract.kind == ContractKind.SCALAR_OR_PASSTHROUGH:
                                    # Passthrough x might dynamically be a dict, so static proof is incomplete
                                    confidence = GuardrailConfidence.SUSPECTED
                                    limitations = [
                                        "Parameter type of 'x' cannot be proven statically without runtime annotations; "
                                        "passthrough may evaluate to dict or scalar."
                                    ]
                                else:
                                    confidence = GuardrailConfidence.SUSPECTED
                                    limitations = ["Return structure type is partially unresolved."]

                                evidence = IncompatibilityEvidence(
                                    origin_file=origin_file,
                                    origin_symbol=origin_symbol,
                                    origin_line=origin_line,
                                    before_contract=before_contract,
                                    after_contract=after_contract,
                                    consumer_file=candidate_path,
                                    consumer_symbol=caller_name,
                                    consumer_line=access.line_number,
                                    required_operation=f"['{access.required_key}']",
                                    propagation_path=full_path,
                                    confidence=confidence,
                                    reason=(
                                        f"Contract break: '{origin_symbol}' in '{origin_file}' no longer guarantees "
                                        f"key '{access.required_key}', which is required by consumer '{caller_name}' "
                                        f"in '{candidate_path}' at line {access.line_number}."
                                    ),
                                    limitations=limitations,
                                )

                                findings.append(
                                    ContractFinding(
                                        finding_id=f"contract-{origin_file}-{origin_symbol}-{access.required_key}",
                                        rule_id="CONTRACT-001",
                                        category=FindingCategory.TYPE_MISMATCH,
                                        severity=Severity.HIGH,
                                        file_path=origin_file,
                                        line_range=LineRange(start_line=origin_line, end_line=origin_line),
                                        title=f"[CONTRACT-001] Cross-file contract violation: '{origin_symbol}' breaks key '{access.required_key}' expected by '{candidate_path}'",
                                        description=(
                                            f"Function '{origin_symbol}' changed return contract from `{before_contract.raw_expression}` "
                                            f"to `{after_contract.raw_expression}`. Downstream consumer `{caller_name}` at "
                                            f"{candidate_path}:{access.line_number} indexes `['{access.required_key}']`."
                                        ),
                                        evidence=evidence,
                                    )
                                )

                        # Check if caller function returns the result of alias(...) (passthrough forwarding)
                        returns_alias = False
                        for n in ast.walk(caller_func):
                            if isinstance(n, ast.Return) and n.value is not None:
                                for sub in ast.walk(n.value):
                                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == alias:
                                        returns_alias = True
                                        break

                        if returns_alias:
                            # Forward propagation to caller!
                            forward_step = PropagationStep(
                                step_index=len(curr_path) + 1,
                                file_path=candidate_path,
                                symbol=caller_name,
                                line_number=getattr(caller_func, "lineno", 1),
                                action="forwards_call",
                                expression=safe_unparse(caller_func),
                            )
                            new_visited = set(visited)
                            new_visited.add(caller_key)
                            queue.append(
                                (
                                    candidate_path,
                                    caller_name,
                                    getattr(caller_func, "lineno", 1),
                                    curr_path + [forward_step],
                                    new_visited,
                                )
                            )

        return findings

    def to_candidate_findings(self, contract_findings: list[ContractFinding]) -> list[CandidateFinding]:
        """Convert deterministic contract findings to standard POLARIS CandidateFindings."""
        candidates: list[CandidateFinding] = []
        for cf in contract_findings:
            conf = Confidence.HIGH if cf.evidence.confidence == GuardrailConfidence.CONFIRMED else Confidence.MEDIUM
            path_summary = " -> ".join(f"{s.symbol} ({s.file_path}:{s.line_number})" for s in cf.evidence.propagation_path)
            candidates.append(
                CandidateFinding(
                    category=cf.category,
                    severity=cf.severity,
                    confidence=conf,
                    file_path=cf.file_path,
                    start_line=cf.line_range.start_line,
                    end_line=cf.line_range.end_line,
                    title=cf.title,
                    description=cf.description,
                    evidence=f"[{cf.rule_id}][{cf.evidence.confidence.value}] {cf.evidence.reason} Trail: [{path_summary}]",
                    suggested_remediation="Preserve previous dictionary structure or adapt downstream consumers.",
                )
            )
        return candidates
