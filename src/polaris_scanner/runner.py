from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from polaris_scanner.executor import ExecutionResult, run_analyzer_subprocess
from polaris_scanner.registry import AnalyzerSpec


@dataclass(frozen=True)
class WorkerTask:
    """A single language-batched worker execution unit."""

    language: str
    spec: AnalyzerSpec
    files: list[str]


@dataclass(frozen=True)
class WorkerOutcome:
    """Result of executing a WorkerTask."""

    language: str
    spec: AnalyzerSpec
    result: ExecutionResult


def run_workers_parallel(
    tasks: Sequence[WorkerTask],
    *,
    project_key: str,
    branch: str,
    target_dir: Path,
    repo_root: Path,
    timeout_seconds: int,
    env_overrides: Mapping[str, str] | None = None,
    max_workers: int | None = None,
    executor_fn: Callable[..., ExecutionResult] = run_analyzer_subprocess,
) -> list[WorkerOutcome]:
    """Execute independent language-batched analyzer workers concurrently."""
    if not tasks:
        return []

    worker_count = max_workers if max_workers and max_workers > 0 else min(len(tasks), os.cpu_count() or 4)
    worker_count = max(1, worker_count)

    def _run_in_process(task: WorkerTask) -> WorkerOutcome | None:
        import importlib.util
        import uuid
        inproc_map = {
            "typescript": ("analyzers/html/polaris_html_analyzer.py", "analyze_frontend_content"),
            "html": ("analyzers/html/polaris_html_analyzer.py", "analyze_frontend_content"),
            "php": ("analyzers/php/polaris_php_analyzer.py", "analyze_php_content"),
            "shell": ("analyzers/shell/polaris_shell_analyzer.py", "analyze_shell_content"),
            "kotlin": ("analyzers/kotlin/polaris_kotlin_analyzer.py", "analyze_kotlin_content"),
            "rust": ("analyzers/rust/polaris_rust_analyzer.py", "analyze_rust_content"),
            "cpp": ("analyzers/cpp/polaris_cpp_analyzer.py", "analyze_cpp_content"),
        }
        if task.language not in inproc_map or executor_fn is not run_analyzer_subprocess:
            return None
        rel_mod, fn_name = inproc_map[task.language]
        mod_path = repo_root / rel_mod
        spec = importlib.util.spec_from_file_location(f"polaris_inproc_{task.language}", mod_path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fn = getattr(mod, fn_name)
        issues: list[dict[str, Any]] = []
        root_resolved = target_dir.resolve()
        for f_str in task.files:
            p = Path(f_str).resolve()
            rel = p.relative_to(root_resolved).as_posix()
            text = p.read_text(encoding="utf-8", errors="replace")
            issues.extend(fn(text, rel))
        payload = {
            "schemaVersion": "1.0.0",
            "analysisId": str(uuid.uuid4()),
            "projectKey": project_key,
            "branch": branch,
            "analyzer": {"id": task.spec.id, "version": task.spec.version},
            "status": "COMPLETED",
            "totalFiles": len(task.files),
            "diagnostics": [],
            "issues": issues,
        }
        return WorkerOutcome(
            language=task.language,
            spec=task.spec,
            result=ExecutionResult(status="OK", exit_code=0, stdout="", stderr="", payload=payload),
        )

    def _run_one(task: WorkerTask) -> WorkerOutcome:
        inproc = _run_in_process(task)
        if inproc is not None:
            return inproc
        cmd = [
            *task.spec.command,
            "--project",
            project_key,
            "--branch",
            branch,
            "--root",
            str(target_dir),
            *task.files,
        ]
        res = executor_fn(
            cmd,
            cwd=repo_root,
            timeout_seconds=timeout_seconds,
            env_overrides=env_overrides,
        )
        return WorkerOutcome(language=task.language, spec=task.spec, result=res)

    outcomes: list[WorkerOutcome] = []
    if worker_count == 1 or len(tasks) == 1:
        for t in tasks:
            outcomes.append(_run_one(t))
        return outcomes

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = {pool.submit(_run_one, t): t.language for t in tasks}
        for fut in as_completed(futures):
            outcomes.append(fut.result())

    outcomes.sort(key=lambda o: o.language)
    return outcomes
