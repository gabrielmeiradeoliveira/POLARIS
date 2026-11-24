from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class IncrementalCache:
    analyzer_version: str
    profile_hash: str
    entries: dict[str, dict[str, Any]] = field(default_factory=dict)

    def make_key(self, file_path: str, content_hash: str) -> str:
        raw = f"{file_path}:{content_hash}:{self.analyzer_version}:{self.profile_hash}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, file_path: str, content_hash: str) -> list[dict[str, Any]] | None:
        key = self.make_key(file_path, content_hash)
        entry = self.entries.get(key)
        return entry["issues"] if entry else None

    def put(self, file_path: str, content_hash: str, issues: list[dict[str, Any]]) -> None:
        key = self.make_key(file_path, content_hash)
        self.entries[key] = {"file": file_path, "issues": issues}

    def to_json(self) -> str:
        return json.dumps({"analyzer_version": self.analyzer_version, "profile_hash": self.profile_hash, "entries": self.entries}, indent=2)
