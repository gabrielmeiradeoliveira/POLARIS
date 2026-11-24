import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from analyzers import ANALYZERS


def scan_directory(root_dir: Path, project_key: str, branch: str = "main", commit: str = "local") -> dict:
    root_resolved = root_dir.resolve()
    files_report = []
    all_issues = []
    metrics_by_file = {}

    for path in sorted(root_resolved.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        ext = path.suffix.lower()
        if ext not in ANALYZERS:
            continue
        rel_path = path.relative_to(root_resolved).as_posix()
        language, analyzer_fn = ANALYZERS[ext]
        content = path.read_text(encoding="utf-8", errors="replace")
        result = analyzer_fn(path, rel_path, content)
        files_report.append({"path": rel_path, "language": language, "state": result["state"]})
        all_issues.extend(result["issues"])
        metrics_by_file[rel_path] = result["metrics"]

    return {
        "schemaVersion": "1.0.0",
        "analysisId": f"anl-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "projectKey": project_key,
        "branch": branch,
        "commit": commit,
        "status": "COMPLETED",
        "files": files_report,
        "issues": all_issues,
        "metrics": metrics_by_file,
    }


def submit_report(server_url: str, report: dict) -> dict:
    data = json.dumps(report).encode("utf-8")
    req = urllib.request.Request(
        f"{server_url.rstrip('/')}/api/v1/analyses",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))
