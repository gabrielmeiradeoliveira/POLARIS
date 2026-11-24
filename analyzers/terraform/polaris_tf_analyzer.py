from __future__ import annotations

import argparse
import json
import re
import uuid
from pathlib import Path
from typing import Any

ANALYZER_ID = "polaris-terraform-analyzer"
ANALYZER_VERSION = "3.0.0"
CONTRACT_VERSION = "1.0.0"

_RULES: list[tuple[str, str, str, re.Pattern[str], str]] = [
    ("TF-SEC-001", "BLOCKER", "SECURITY", re.compile(r"""(?i)\b(?:password|secret|api_key|access_key|token)\s*=\s*["'][^"']{6,}["']"""), "Hardcoded secret in Terraform configuration"),
    ("TF-SEC-002", "CRITICAL", "SECURITY", re.compile(r"""cidr_blocks\s*=\s*\[[^\]]*(?:0\.0\.0\.0/0|::/0)"""), "Security group ingress open to 0.0.0.0/0 or ::/0"),
    ("TF-SEC-003", "CRITICAL", "SECURITY", re.compile(r"""(?i)(?:acl\s*=\s*["']public-read|allUsers|allAuthenticatedUsers)"""), "Publicly accessible storage bucket or IAM member"),
    ("TF-SEC-004", "BLOCKER", "SECURITY", re.compile(r"""(?i)actions?\s*[:=]\s*\[?\s*["']\*["']"""), "Overly permissive IAM wildcard '*' action"),
    ("TF-SEC-005", "CRITICAL", "SECURITY", re.compile(r"""publicly_accessible\s*=\s*true"""), "Database instance configured as publicly accessible"),
    ("TF-SEC-006", "MAJOR", "SECURITY", re.compile(r"""(?:encrypted|storage_encrypted)\s*=\s*false"""), "Storage or database encryption disabled"),
    ("TF-SEC-007", "MAJOR", "SECURITY", re.compile(r"""(?i)(?:protocol\s*=\s*["']HTTP["']|TLSv1\.[01])"""), "Unencrypted HTTP listener or deprecated TLS < 1.2"),
    ("TF-SEC-008", "MINOR", "SECURITY", re.compile(r"""(?i)(?:enable_logging|logging_enabled)\s*=\s*false"""), "Audit or flow logging disabled"),
    ("TF-REL-001", "MINOR", "RELIABILITY", re.compile(r"""required_providers\s*\{(?![^}]*version\s*=)"""), "Provider block missing explicit version constraint"),
    ("TF-REL-002", "MAJOR", "RELIABILITY", re.compile(r"""resource\s+["'](?:aws_db_instance|aws_s3_bucket)["'](?![^}]*prevent_destroy\s*=\s*true)"""), "Stateful database or bucket missing lifecycle prevent_destroy = true"),
]


def analyze_tf_content(content: str, file_path: str = "main.tf") -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    lines = content.splitlines()
    for rule_id, severity, category, pat, message in _RULES:
        if rule_id in ("TF-REL-001", "TF-REL-002"):
            m = pat.search(content)
            if m:
                line_no = content[: m.start()].count("\n") + 1
                issues.append({
                    "ruleId": f"terraform:{rule_id}",
                    "language": "terraform",
                    "severity": severity,
                    "category": category,
                    "confidence": "HIGH",
                    "location": {"file": file_path, "startLine": line_no},
                    "message": message,
                })
            continue
        for idx, line in enumerate(lines, start=1):
            if pat.search(line):
                issues.append({
                    "ruleId": f"terraform:{rule_id}",
                    "language": "terraform",
                    "severity": severity,
                    "category": category,
                    "confidence": "HIGH",
                    "location": {"file": file_path, "startLine": idx},
                    "message": message,
                })
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()
    root_dir = Path(args.root).resolve()
    all_issues: list[dict[str, Any]] = []
    for f in args.files:
        p = Path(f).resolve()
        rel = p.relative_to(root_dir).as_posix()
        all_issues.extend(analyze_tf_content(p.read_text(encoding="utf-8", errors="replace"), rel))
    print(json.dumps({
        "schemaVersion": CONTRACT_VERSION,
        "analysisId": str(uuid.uuid4()),
        "projectKey": args.project,
        "branch": args.branch,
        "analyzer": {"id": ANALYZER_ID, "version": ANALYZER_VERSION},
        "status": "COMPLETED",
        "totalFiles": len(args.files),
        "diagnostics": [],
        "issues": all_issues,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
