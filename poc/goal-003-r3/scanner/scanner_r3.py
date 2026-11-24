import json
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
R2_ROOT = REPO_ROOT / "poc" / "goal-003-r2"
VENV_PY = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
CS_DLL = R2_ROOT / "csharp_analyzer" / "bin" / "Release" / "net11.0" / "PolarisCSharpAnalyzer.dll"
JV_JAR = R2_ROOT / "java_analyzer" / "target" / "polaris-java-analyzer-0.1.0.jar"

MAX_FILE_BYTES = 1 * 1024 * 1024  # 1 MB
ANALYZER_TIMEOUT_SEC = 15


def run_scanner(target_dir: Path, project_key: str, exclusions: tuple = (".git", "node_modules", ".venv")) -> dict:
    root = target_dir.resolve()
    issues = []
    analyzed_files = 0
    has_errors = False

    for path in sorted(root.rglob("*")):
        if any(part in exclusions for part in path.parts):
            continue
        if path.is_symlink() or not path.is_file():
            continue
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(root)
        except Exception:
            has_errors = True
            continue
        if resolved.stat().st_size > MAX_FILE_BYTES:
            has_errors = True
            continue

        ext = resolved.suffix.lower()
        rel_path = resolved.relative_to(root).as_posix()
        cmd = None
        lang = None
        if ext == ".py":
            lang, cmd = "python", [str(VENV_PY), str(R2_ROOT / "python_analyzer" / "analyze.py"), str(resolved)]
        elif ext == ".cs":
            lang, cmd = "csharp", ["dotnet", str(CS_DLL), str(resolved)]
        elif ext == ".java":
            lang, cmd = "java", ["java", "-jar", str(JV_JAR), str(resolved)]
        elif ext == ".sql":
            lang, cmd = "sql", [str(VENV_PY), str(R2_ROOT / "sql_analyzer" / "analyze.py"), str(resolved), "postgres"]
        else:
            continue

        analyzed_files += 1
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=ANALYZER_TIMEOUT_SEC)
            if proc.returncode != 0:
                has_errors = True
                continue
            data = json.loads(proc.stdout)
            if data.get("state") != "ANALYZED_SUCCESS":
                has_errors = True
            for iss in data.get("issues", []):
                issues.append({
                    "ruleId": iss["ruleId"],
                    "language": lang,
                    "severity": "MEDIUM",
                    "location": {"file": rel_path, "startLine": iss.get("line", 1)},
                    "message": iss.get("message", f"Regra {iss['ruleId']} violada."),
                })
        except Exception:
            has_errors = True

    return {
        "schemaVersion": "1.0.0",
        "analysisId": f"r3-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        "projectKey": project_key,
        "branch": "main",
        "status": "COMPLETED_WITH_WARNINGS" if has_errors else "COMPLETED",
        "totalFiles": analyzed_files,
        "issues": issues,
    }


def submit_to_backend(api_url: str, report: dict) -> dict:
    req = urllib.request.Request(
        f"{api_url.rstrip('/')}/api/v1/analyses",
        data=json.dumps(report).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))
