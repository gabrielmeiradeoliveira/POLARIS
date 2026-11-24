from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".cs": "csharp",
    ".java": "java",
    ".sql": "sql",
}


@dataclass(frozen=True)
class DiscoveredFile:
    """Represents a source file discovered for analysis."""

    absolute_path: Path
    relative_path: str  # POSIX relative path
    language: str
    size_bytes: int


@dataclass(frozen=True)
class SkippedFile:
    """Represents a file skipped during discovery with a reason."""

    relative_path: str
    reason: str


@dataclass(frozen=True)
class DiscoveryResult:
    """Deterministic output of file discovery."""

    root_dir: Path
    files: tuple[DiscoveredFile, ...]
    skipped: tuple[SkippedFile, ...]
    total_bytes: int


def discover_files(
    root_dir: Path,
    *,
    exclusions: Iterable[str] = (".git", ".venv", "node_modules", "bin", "obj", "target", "build", "dist"),
    languages: Iterable[str] = ("python", "csharp", "java", "sql"),
    max_file_bytes: int = 1 * 1024 * 1024,
    max_files: int = 10000,
    max_total_bytes: int = 100 * 1024 * 1024,
) -> DiscoveryResult:
    """Discover supported source files deterministically and safely."""
    resolved_root = root_dir.resolve()
    if not resolved_root.exists() or not resolved_root.is_dir():
        raise FileNotFoundError(f"Target directory does not exist: {root_dir}")

    excluded_set = {e.strip() for e in exclusions if e.strip()}
    allowed_langs = {lang.strip().lower() for lang in languages if lang.strip()}

    discovered: list[DiscoveredFile] = []
    skipped: list[SkippedFile] = []
    total_bytes = 0
    limit_reached = False

    for dirpath, dirnames, filenames in os.walk(resolved_root, topdown=True, followlinks=False):
        current_dir = Path(dirpath)
        # Filter out excluded directories and symlinks/junctions deterministically
        kept_dirs: list[str] = []
        for d in sorted(dirnames):
            if d in excluded_set:
                continue
            candidate_dir = current_dir / d
            if candidate_dir.is_symlink():
                rel = candidate_dir.relative_to(resolved_root).as_posix()
                skipped.append(SkippedFile(relative_path=rel, reason="symlink_directory"))
                continue
            try:
                if not candidate_dir.resolve().is_relative_to(resolved_root):
                    rel = candidate_dir.relative_to(resolved_root).as_posix()
                    skipped.append(SkippedFile(relative_path=rel, reason="outside_root"))
                    continue
            except OSError:
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs

        for fname in sorted(filenames):
            file_path = current_dir / fname
            rel_posix = file_path.relative_to(resolved_root).as_posix()

            if file_path.is_symlink():
                skipped.append(SkippedFile(relative_path=rel_posix, reason="symlink_file"))
                continue

            try:
                resolved_file = file_path.resolve()
                if not resolved_file.is_relative_to(resolved_root):
                    skipped.append(SkippedFile(relative_path=rel_posix, reason="outside_root"))
                    continue
            except OSError:
                skipped.append(SkippedFile(relative_path=rel_posix, reason="unresolvable_path"))
                continue

            lang = EXTENSION_TO_LANGUAGE.get(file_path.suffix.lower())
            if lang is None or lang not in allowed_langs:
                continue

            try:
                size = file_path.stat().st_size
            except OSError:
                skipped.append(SkippedFile(relative_path=rel_posix, reason="stat_error"))
                continue

            if size > max_file_bytes:
                skipped.append(SkippedFile(relative_path=rel_posix, reason="exceeds_max_file_bytes"))
                continue

            if len(discovered) >= max_files:
                skipped.append(SkippedFile(relative_path=rel_posix, reason="exceeds_max_files"))
                limit_reached = True
                continue

            if total_bytes + size > max_total_bytes:
                skipped.append(SkippedFile(relative_path=rel_posix, reason="exceeds_max_total_bytes"))
                limit_reached = True
                continue

            discovered.append(
                DiscoveredFile(
                    absolute_path=resolved_file,
                    relative_path=rel_posix,
                    language=lang,
                    size_bytes=size,
                )
            )
            total_bytes += size

        if limit_reached and len(discovered) >= max_files:
            break

    discovered.sort(key=lambda f: f.relative_path)
    skipped.sort(key=lambda s: s.relative_path)

    return DiscoveryResult(
        root_dir=resolved_root,
        files=tuple(discovered),
        skipped=tuple(skipped),
        total_bytes=total_bytes,
    )
