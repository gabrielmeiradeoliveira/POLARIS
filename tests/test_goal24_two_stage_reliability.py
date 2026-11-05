"""RC1 regression coverage for preserving deterministic findings across provider failure."""

from __future__ import annotations

import difflib

from polaris.core.models import BudgetTracker, ExecutionBudget
from polaris.git.analyzer import parse_unified_diff
from polaris.git.models import ContextSnippet, DiffBundle, FileContext
from polaris.modules.code_review import CodeReviewModule


class FailingProvider:
    provider_name = "controlled-failure"
    model_name = "controlled-failure-v1"
    preserve_static_on_failure = True

    def generate(self, _request: object) -> object:
        raise TimeoutError("controlled provider failure")


def test_provider_failure_preserves_pre_ai_deterministic_findings() -> None:
    before = "def add(item, items=None):\n    items = [] if items is None else items\n    return items\n"
    after = "def add(item, items=[]):\n    items.append(item)\n    return items\n"
    path = "service.py"
    patch = "".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile=f"a/{path}", tofile=f"b/{path}"))
    files = parse_unified_diff(f"diff --git a/{path} b/{path}\n{patch}")
    bundle = DiffBundle(repository_root=".", target_description="controlled provider failure", files=files)
    context = FileContext(file_path=path, total_lines=3, snippets=[ContextSnippet(start_line=1, end_line=3, lines={1: "def add(item, items=[]):", 2: "    items.append(item)", 3: "    return items"})])
    tracker = BudgetTracker(ExecutionBudget(max_total_tokens=10_000, max_requests=2))

    candidates = CodeReviewModule().analyze(bundle, {path: context}, FailingProvider(), tracker)

    assert any("DET-MUTABLE-DEFAULT" in candidate.title for candidate in candidates)
    assert any(warning.code == "PROVIDER_STAGE_FAILED_STATIC_PRESERVED" for warning in tracker.warnings)
