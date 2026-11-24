from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProjectManifest:
    analysis_id: str
    project_key: str
    mode: str  # FILE | MODULE | PROJECT
    root: str
    source_files: list[str] = field(default_factory=list)
    file_hashes: dict[str, str] = field(default_factory=dict)
    metadata_files: list[str] = field(default_factory=list)


def discover_project_manifest(root_dir: Path, project_key: str, analysis_id: str, mode: str = "PROJECT") -> ProjectManifest:
    """Safely discover project files and metadata without executing any project code."""
    if mode not in ("FILE", "MODULE", "PROJECT"):
        raise ValueError(f"Invalid analysis mode: {mode}")
    root_resolved = root_dir.resolve()
    source_exts = {".py", ".cs", ".java", ".sql"}
    meta_names = {"pyproject.toml", "pom.xml"}
    meta_exts = {".sln", ".csproj"}

    source_files: list[str] = []
    file_hashes: dict[str, str] = {}
    metadata_files: list[str] = []

    for p in sorted(root_resolved.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root_resolved).as_posix()
        if any(part in (".git", ".venv", "node_modules", "bin", "obj", "target", "__pycache__") for part in p.parts):
            continue
        if p.name in meta_names or p.suffix.lower() in meta_exts:
            metadata_files.append(rel)
        elif p.suffix.lower() in source_exts:
            source_files.append(rel)
            file_hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest()

    return ProjectManifest(
        analysis_id=analysis_id,
        project_key=project_key,
        mode=mode,
        root=str(root_resolved),
        source_files=source_files,
        file_hashes=file_hashes,
        metadata_files=metadata_files,
    )
