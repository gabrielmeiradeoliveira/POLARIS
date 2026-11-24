from __future__ import annotations

import hashlib
import re
try:
    import defusedxml.ElementTree as ET
except ImportError:  # pragma: no cover
    import xml.etree.ElementTree as ET
from pathlib import PurePosixPath
from typing import Any


def parse_cobertura_xml(xml_content: str, project_files: set[str]) -> dict[str, Any]:
    """Safely parse Cobertura XML coverage report without DTD/XXE."""
    if "<!DOCTYPE" in xml_content or "<!ENTITY" in xml_content:
        raise ValueError("Unsafe XML constructs (DOCTYPE/ENTITY) are not allowed")
    root = ET.fromstring(xml_content)
    lines_valid = 0
    lines_covered = 0
    matched_files: dict[str, dict[str, int]] = {}

    for cls in root.findall(".//class"):
        filename = cls.attrib.get("filename", "").replace("\\", "/")
        norm = str(PurePosixPath(filename))
        if norm.startswith("..") or norm.startswith("/"):
            continue
        if project_files and norm not in project_files:
            continue
        file_total = 0
        file_cov = 0
        for line in cls.findall(".//line"):
            file_total += 1
            if int(line.attrib.get("hits", "0")) > 0:
                file_cov += 1
        lines_valid += file_total
        lines_covered += file_cov
        matched_files[norm] = {"lines_valid": file_total, "lines_covered": file_cov}

    pct = round((lines_covered / lines_valid) * 100.0, 2) if lines_valid > 0 else 0.0
    return {"lines_valid": lines_valid, "lines_covered": lines_covered, "coverage_percent": pct, "files": matched_files}


def detect_duplications(files_content: dict[str, str], window_size: int = 6) -> dict[str, Any]:
    """Deterministic token-window duplication detector across files."""
    seen: dict[str, list[tuple[str, int]]] = {}
    duplicated_blocks: list[dict[str, Any]] = []

    for path, content in sorted(files_content.items()):
        tokens = re.findall(r"[A-Za-z_]\w*|\d+|[^\s\w]", content)
        if len(tokens) < window_size:
            continue
        for idx in range(len(tokens) - window_size + 1):
            window = " ".join(tokens[idx : idx + window_size])
            digest = hashlib.sha256(window.encode("utf-8")).hexdigest()[:16]
            seen.setdefault(digest, []).append((path, idx))

    for digest, occurrences in seen.items():
        if len(occurrences) > 1:
            duplicated_blocks.append({"hash": digest, "occurrences": [{"file": p, "token_offset": o} for p, o in occurrences]})

    return {"duplicated_blocks_count": len(duplicated_blocks), "blocks": duplicated_blocks}
