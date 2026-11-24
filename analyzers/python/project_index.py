"""Project Intelligence: project-wide symbol index and incremental cache key computation."""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set


@dataclass
class ModuleInfo:
    """Indexed metadata for a single Python module."""

    rel_path: str
    content_hash: str
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)


class ProjectIndex:
    """Static project-wide symbol and import index (never executes analyzed code)."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.modules: Dict[str, ModuleInfo] = {}

    def index_directory(self) -> None:
        for py_file in sorted(self.root.rglob("*.py")):
            self.index_file(py_file)

    def index_file(self, path: Path) -> ModuleInfo:
        resolved = path.resolve()
        rel = resolved.relative_to(self.root).as_posix()
        raw = resolved.read_bytes()
        content_hash = hashlib.sha256(raw).hexdigest()

        info = ModuleInfo(rel_path=rel, content_hash=content_hash)
        try:
            tree = ast.parse(raw.decode("utf-8", errors="replace"), filename=rel)
        except SyntaxError:
            self.modules[rel] = info
            return info

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                info.functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                info.classes.append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    info.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                info.imports.append(node.module)

        self.modules[rel] = info
        return info

    def compute_cache_key(
        self,
        rel_path: str,
        engine_version: str = "2.2.0",
        profile_version: str = "default",
    ) -> str:
        mod = self.modules.get(rel_path)
        if mod is None:
            raise KeyError(f"Module not indexed: {rel_path}")
        h = hashlib.sha256()
        h.update(rel_path.encode("utf-8"))
        h.update(mod.content_hash.encode("utf-8"))
        h.update(engine_version.encode("utf-8"))
        h.update(profile_version.encode("utf-8"))
        for imp in sorted(set(mod.imports)):
            dep_rel = imp.replace(".", "/") + ".py"
            if dep_rel in self.modules:
                h.update(self.modules[dep_rel].content_hash.encode("utf-8"))
        return h.hexdigest()
