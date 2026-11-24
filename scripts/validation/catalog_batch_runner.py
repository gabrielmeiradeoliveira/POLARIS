from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
VALIDATE_SCRIPT = ROOT / "scripts" / "validation" / "validate_rules.py"
RULES_FIXTURES_DIR = ROOT / "tests" / "fixtures" / "rules"
PILOT_FIXTURES_DIR = ROOT / "tests" / "fixtures" / "pilot_160"
DEFAULT_STATE_FILE = ROOT / "vault" / "09-Validation" / "Evidence" / "GOAL-047-070-MASTER" / "batch_state.json"

sys.path.insert(0, str(ROOT / "scripts" / "validation"))
import validate_rules  # noqa: E402


def _fixture_status(rule: dict[str, str]) -> str:
    rid = rule["ruleId"]
    lang = rule["language"]
    pilot_f = PILOT_FIXTURES_DIR / lang / f"{rid}.json"
    rules_f = RULES_FIXTURES_DIR / lang / f"{rid}.json"
    fpath = pilot_f if pilot_f.exists() else rules_f
    if not fpath.exists():
        return "MISSING_FIXTURE"
    try:
        data = json.loads(fpath.read_text(encoding="utf-8"))
        cases = data.get("cases", [])
        if not cases or any("code" not in c for c in cases):
            return "STUB_NO_CODE"
        return "READY"
    except Exception:
        return "INVALID_JSON"


def build_queue(language: str | None = None) -> list[dict[str, Any]]:
    inventory = validate_rules.load_inventory()
    queue: list[dict[str, Any]] = []
    for r in inventory:
        if language and r["language"] != language:
            continue
        queue.append(
            {
                "ruleId": r["ruleId"],
                "language": r["language"],
                "category": r.get("category", "unknown"),
                "severity": r.get("severity", "MAJOR"),
                "fixtureStatus": _fixture_status(r),
            }
        )
    return queue


def _resolve_state_file(state_dir: Path | None) -> Path:
    if state_dir is not None:
        return state_dir / "batch_state.json"
    env_dir = os.environ.get("POLARIS_STATE_DIR")
    if env_dir:
        return Path(env_dir) / "batch_state.json"
    return DEFAULT_STATE_FILE


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".batch_state_", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="POLARIS Catalog Batch Validation Orchestrator")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--pending", action="store_true")
    parser.add_argument("--language", choices=["python", "csharp", "java", "sql"])
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--state-dir", type=Path, help="Optional local authorized state directory")
    args = parser.parse_args(argv)

    state_file = _resolve_state_file(args.state_dir)
    queue = build_queue(args.language)
    ready = [q for q in queue if q["fixtureStatus"] == "READY"]
    pending = [q for q in queue if q["fixtureStatus"] != "READY"]

    if args.status or args.report:
        by_lang: dict[str, dict[str, int]] = {}
        for q in queue:
            lang = q["language"]
            by_lang.setdefault(lang, {"total": 0, "ready": 0, "pending": 0})
            by_lang[lang]["total"] += 1
            if q["fixtureStatus"] == "READY":
                by_lang[lang]["ready"] += 1
            else:
                by_lang[lang]["pending"] += 1
        print(f"TOTAL={len(queue)} READY={len(ready)} PENDING={len(pending)}")
        for lang, counts in sorted(by_lang.items()):
            print(f"  {lang}: total={counts['total']} ready={counts['ready']} pending={counts['pending']}")
        if args.report and state_file.exists():
            saved = json.loads(state_file.read_text(encoding="utf-8"))
            print(f"STATE_FILE={state_file} COMPLETED_RULES={len(saved.get('completedRules', []))}")
        return 0

    if args.pending:
        batch = pending[: args.batch_size]
        for item in batch:
            print(f"{item['language']}\t{item['ruleId']}\t{item['category']}\t{item['fixtureStatus']}")
        return 0

    prior_state: dict[str, Any] = {}
    if args.resume and state_file.exists():
        prior_state = json.loads(state_file.read_text(encoding="utf-8"))

    completed: list[str] = list(dict.fromkeys(prior_state.get("completedRules", [])))
    completed_set = set(completed)
    to_run = [q for q in ready if q["ruleId"] not in completed_set][: args.batch_size]

    results: dict[str, Any] = dict(prior_state.get("results", {}))
    failed_rules: list[str] = []
    for item in to_run:
        rid = item["ruleId"]
        proc = subprocess.run(
            [sys.executable, str(VALIDATE_SCRIPT), "--rule", rid],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        out = proc.stdout.strip()
        results[rid] = {"returncode": proc.returncode, "output": out}
        if proc.returncode == 0:
            if rid not in completed_set:
                completed.append(rid)
                completed_set.add(rid)
        else:
            failed_rules.append(rid)
        print(f"{rid}: {out}")

    new_state = {
        "total": len(queue),
        "ready": len(ready),
        "pending": len(pending),
        "completedRules": completed,
        "failedRules": failed_rules,
        "results": results,
    }
    try:
        _atomic_write_json(state_file, new_state)
    except PermissionError as exc:
        print(
            f"ERROR: PermissionError writing state file '{state_file}': {exc}. "
            "Use --state-dir or POLARIS_STATE_DIR to specify an authorized local directory.",
            file=sys.stderr,
        )
        return 1
    return 0 if not failed_rules else 1


if __name__ == "__main__":
    raise SystemExit(main())
