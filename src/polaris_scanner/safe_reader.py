from __future__ import annotations

from pathlib import Path

ENCODINGS = ("utf-8", "utf-8-sig", "cp1252", "latin-1")


def read_text_safe(file_path: Path, max_bytes: int = 1024 * 1024) -> tuple[str | None, str | None]:
    """Read file with deterministic encoding fallback chain; never raises UnicodeDecodeError."""
    try:
        raw = file_path.read_bytes()
    except OSError as exc:
        return None, f"read_error:{exc}"
    if len(raw) > max_bytes:
        return None, "max_file_size"
    if b"\x00" in raw[:8192]:
        return None, "binary"
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), None
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace"), None


def classify_file_scope(rel_path: str) -> str:
    """Classify file into prod, test, or generated."""
    low = rel_path.lower().replace("\\", "/")
    if any(tok in low for tok in ("migrations/", ".designer.cs", ".pb.go")):
        return "generated"
    if any(tok in low for tok in ("tests/", "__tests__/", ".spec.", "test.")):
        return "test"
    return "prod"
