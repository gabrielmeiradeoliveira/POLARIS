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

    def _run_one(task: WorkerTask) -> WorkerOutcome:
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
