from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def compute_bytes_sha256(data: bytes) -> str:
    """Compute SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 hex digest of a file's contents."""
    return compute_bytes_sha256(file_path.read_bytes())


def is_binary_bytes(data: bytes) -> bool:
    """Return True if a null byte appears in the first 8 KB."""
    return b"\x00" in data[:8192]


def is_minified_asset(file_path: Path, data: bytes) -> bool:
    """Return True only for confirmed minified .js/.mjs/.css bundles."""
    suffix = file_path.suffix.lower()
    if suffix not in {".js", ".mjs", ".css"}:
        return False
    name_lower = file_path.name.lower()
    if ".min." in name_lower or ".bundle." in name_lower:
        return True
    if len(data) > 10 * 1024:
        text = data.decode("utf-8", errors="ignore")
        lines = text.splitlines() or [text]
        avg_len = len(text) / len(lines)
        if avg_len > 200:
            return True
    return False


@dataclass(frozen=True)
class CachedFileResult:
    """Cached analysis result for a single file."""

    issues: list[dict[str, Any]]
    file_metrics: dict[str, Any]


class IncrementalScanCache:
    """Persistent gzip-compressed JSON cache keyed by (file_sha256, rule_profile_hash, worker_version, deps_hash)."""

    def __init__(self, cache_path: Path) -> None:
        self.cache_path = cache_path
        self._entries: dict[str, dict[str, Any]] = {}
        if self.cache_path.exists():
            try:
                with gzip.open(self.cache_path, "rt", encoding="utf-8") as gz:
                    loaded = json.load(gz)
                    if isinstance(loaded, dict):
                        self._entries = loaded
            except Exception:
                self._entries = {}

    @staticmethod
    def make_key(
        file_sha256: str,
        rule_profile_hash: str,
        worker_version: str,
        deps_hash: str = "",
    ) -> str:
        raw = f"{file_sha256}:{rule_profile_hash}:{worker_version}:{deps_hash}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(
        self,
        *,
        file_sha256: str,
        rule_profile_hash: str,
        worker_version: str,
        deps_hash: str = "",
    ) -> CachedFileResult | None:
        key = self.make_key(file_sha256, rule_profile_hash, worker_version, deps_hash)
        entry = self._entries.get(key)
        if not entry:
            return None
        return CachedFileResult(
            issues=entry.get("issues", []),
            file_metrics=entry.get("file_metrics", {}),
        )

    def put(
        self,
        *,
        file_path: str,
        file_sha256: str,
        rule_profile_hash: str,
        worker_version: str,
        issues: list[dict[str, Any]],
        file_metrics: dict[str, Any] | None = None,
        deps_hash: str = "",
    ) -> None:
        key = self.make_key(file_sha256, rule_profile_hash, worker_version, deps_hash)
        self._entries[key] = {
            "file_path": file_path,
            "issues": issues,
            "file_metrics": file_metrics or {},
        }

    def commit(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(prefix=".polaris-cache-", suffix=".json.gz.tmp", dir=str(self.cache_path.parent))
        except (PermissionError, OSError):
            fallback_dir = Path(tempfile.gettempdir()) / "polaris-cache"
            fallback_dir.mkdir(parents=True, exist_ok=True)
            self.cache_path = fallback_dir / self.cache_path.name
            fd, tmp_name = tempfile.mkstemp(prefix=".polaris-cache-", suffix=".json.gz.tmp", dir=str(fallback_dir))
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as raw_f:
                with gzip.GzipFile(fileobj=raw_f, mode="wb") as gz:
                    gz.write(json.dumps(self._entries, ensure_ascii=False).encode("utf-8"))
            os.replace(tmp_path, self.cache_path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise

    def clear(self) -> None:
        self._entries.clear()
        if self.cache_path.exists():
            self.cache_path.unlink(missing_ok=True)

    def close(self) -> None:
        pass

    def __enter__(self) -> IncrementalScanCache:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
