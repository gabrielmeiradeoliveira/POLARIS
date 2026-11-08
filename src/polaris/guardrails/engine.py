"""Orchestrator and analyzer engine for deterministic Security Guardrails."""

from __future__ import annotations

import ast

from polaris.core.models import CandidateFinding, Confidence
from polaris.guardrails.authorization import analyze_function_authorization_relaxation
from polaris.guardrails.models import GuardrailConfidence, SecurityFinding


def _extract_functions(tree: ast.AST) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Map function name to AST function node (skipping nested/inner functions for stability)."""
    funcs: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for node in tree.body if hasattr(tree, "body") else []:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs[node.name] = node
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    funcs[f"{node.name}.{item.name}"] = item
    return funcs


class SecurityGuardrailEngine:
    """Deterministic security analyzer operating on AST representations of changes."""

    def __init__(self, max_file_size_bytes: int = 500_000) -> None:
        self.max_file_size_bytes = max_file_size_bytes

    def analyze_file_change(
        self,
        file_path: str,
        before_content: str | None,
        after_content: str,
    ) -> list[SecurityFinding]:
        """Analyze a single file change for deterministic security vulnerabilities."""
        findings: list[SecurityFinding] = []

        if not file_path.endswith(".py"):
            return findings

        if len(after_content.encode("utf-8")) > self.max_file_size_bytes:
            return findings

        try:
            after_tree = ast.parse(after_content, filename=file_path)
        except SyntaxError:
            # Controlled syntax failure without raising unhandled errors
            return findings

        before_tree: ast.AST | None = None
        if before_content is not None:
            try:
                before_tree = ast.parse(before_content, filename=file_path)
            except SyntaxError:
                before_tree = None

        before_funcs = _extract_functions(before_tree) if before_tree else {}
        after_funcs = _extract_functions(after_tree)

        for name, after_func in after_funcs.items():
            before_func = before_funcs.get(name)
            # Run authorization relaxation guardrail
            auth_findings = analyze_function_authorization_relaxation(
                before_func=before_func,
                after_func=after_func,
                file_path=file_path,
            )
            findings.extend(auth_findings)

        return findings

    def to_candidate_findings(self, security_findings: list[SecurityFinding]) -> list[CandidateFinding]:
        """Convert deterministic security findings to standard POLARIS CandidateFindings."""
        candidates: list[CandidateFinding] = []
        for sf in security_findings:
            conf = Confidence.HIGH if sf.evidence.confidence == GuardrailConfidence.CONFIRMED else Confidence.MEDIUM
            candidates.append(
                CandidateFinding(
                    category=sf.category,
                    severity=sf.severity,
                    confidence=conf,
                    file_path=sf.file_path,
                    start_line=sf.line_range.start_line,
                    end_line=sf.line_range.end_line,
                    title=sf.title,
                    description=sf.description,
                    evidence=f"[{sf.rule_id}][{sf.evidence.confidence.value}] {sf.evidence.reason} (predicate: `{sf.evidence.after_predicate}`)",
                    suggested_remediation="Revert authorization bypass or enforce explicit check before permitting access.",
                )
            )
        return candidates
