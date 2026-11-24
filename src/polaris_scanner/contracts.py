from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

CONTRACT_SCHEMA_VERSION = "1.0.0"
VALID_ANALYSIS_STATUSES = ("COMPLETED", "COMPLETED_WITH_WARNINGS", "FAILED")
VALID_SEVERITIES = ("INFO", "MINOR", "MAJOR", "CRITICAL", "BLOCKER")
VALID_CONFIDENCE_LEVELS = ("HIGH", "MEDIUM", "LOW")
VALID_LANGUAGES = ("python", "csharp", "java", "sql")


def is_valid_relative_posix_path(path_str: str) -> bool:
    """Verify path is relative, uses POSIX separators, and has no parent traversal."""
    if not path_str or "\\" in path_str or path_str.startswith("/"):
        return False
    pure = PurePosixPath(path_str)
    if pure.is_absolute():
        return False
    return ".." not in pure.parts


def validate_analysis_result(data: Any) -> list[str]:
    """Validate an analysis result payload against POLARIS contract v1.0.0."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Payload must be a JSON object"]

    required_top = ("schemaVersion", "analysisId", "projectKey", "branch", "analyzer", "status", "totalFiles", "diagnostics", "issues")
    for field_name in required_top:
        if field_name not in data:
            errors.append(f"Missing required field: {field_name}")

    if data.get("schemaVersion") != CONTRACT_SCHEMA_VERSION:
        errors.append(f"schemaVersion must be '{CONTRACT_SCHEMA_VERSION}'")

    if data.get("status") not in VALID_ANALYSIS_STATUSES:
        errors.append(f"status must be one of {VALID_ANALYSIS_STATUSES}")

    analyzer = data.get("analyzer")
    if not isinstance(analyzer, dict) or not analyzer.get("id") or not analyzer.get("version"):
        errors.append("analyzer must be an object with non-empty 'id' and 'version'")

    total_files = data.get("totalFiles")
    if not isinstance(total_files, int) or isinstance(total_files, bool) or total_files < 0:
        errors.append("totalFiles must be a non-negative integer")

    if not isinstance(data.get("diagnostics"), list):
        errors.append("diagnostics must be a list")

    issues = data.get("issues")
    if not isinstance(issues, list):
        errors.append("issues must be a list")
    else:
        for idx, issue in enumerate(issues):
            if not isinstance(issue, dict):
                errors.append(f"issues[{idx}] must be an object")
                continue
            for req in ("ruleId", "language", "severity", "location", "message"):
                if req not in issue:
                    errors.append(f"issues[{idx}] missing required field: {req}")
            if issue.get("language") not in VALID_LANGUAGES:
                errors.append(f"issues[{idx}].language must be one of {VALID_LANGUAGES}")
            if issue.get("severity") not in VALID_SEVERITIES:
                errors.append(f"issues[{idx}].severity must be one of {VALID_SEVERITIES}")
            if "confidence" in issue and issue["confidence"] is not None:
                if issue["confidence"] not in VALID_CONFIDENCE_LEVELS:
                    errors.append(f"issues[{idx}].confidence must be one of {VALID_CONFIDENCE_LEVELS}")
            loc = issue.get("location")
            if not isinstance(loc, dict):
                errors.append(f"issues[{idx}].location must be an object")
            else:
                file_path = loc.get("file")
                if not isinstance(file_path, str) or not is_valid_relative_posix_path(file_path):
                    errors.append(f"issues[{idx}].location.file must be a valid relative POSIX path")
                start_line = loc.get("startLine")
                if not isinstance(start_line, int) or isinstance(start_line, bool) or start_line < 1:
                    errors.append(f"issues[{idx}].location.startLine must be a 1-based integer >= 1")
                for opt_pos in ("endLine", "startColumn", "endColumn"):
                    if opt_pos in loc and loc[opt_pos] is not None:
                        val = loc[opt_pos]
                        if not isinstance(val, int) or isinstance(val, bool) or val < 1:
                            errors.append(f"issues[{idx}].location.{opt_pos} must be a 1-based integer >= 1")

    return errors


def write_report_atomic(report: dict[str, Any], output_path: Path) -> None:
    """Persist a JSON report atomically in UTF-8."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=".polaris-", suffix=".tmp", dir=str(output_path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
        os.replace(tmp_path, output_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def compute_issue_fingerprint(rule_id: str, file_path: str, start_line: int, message: str) -> str:
    """Compute a deterministic SHA-256 fingerprint for an issue occurrence."""
    import hashlib

    raw = f"{rule_id}|{file_path}|{start_line}|{message}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
