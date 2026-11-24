from __future__ import annotations

import argparse
import gzip
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Iterable

from polaris_scanner.cache import IncrementalScanCache, compute_bytes_sha256, is_binary_bytes, is_minified_asset
from polaris_scanner.config import ConfigValidationError, load_scanner_config
from polaris_scanner.contracts import CONTRACT_SCHEMA_VERSION, compute_issue_fingerprint, validate_analysis_result, write_report_atomic
from polaris_scanner.discovery import discover_files
from polaris_scanner.registry import AnalyzerRegistry
from polaris_scanner.runner import WorkerTask, run_workers_parallel

SCANNER_VERSION = "2.6.0"


def discover_source_files(
    root_dir: Path,
    exclusions: Iterable[str] = (".git", ".venv", "node_modules", "bin", "obj", "target", "build", "dist"),
    max_file_bytes: int = 1 * 1024 * 1024,
) -> list[tuple[Path, str, str]]:
    """Backward-compatible wrapper around discover_files."""
    result = discover_files(root_dir, exclusions=exclusions, max_file_bytes=max_file_bytes)
    return [(f.absolute_path, f.relative_path, f.language) for f in result.files]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="polaris-scanner", description="POLARIS local deterministic scanner CLI")
    parser.add_argument("--version", action="version", version=f"polaris-scanner {SCANNER_VERSION}")

    subparsers = parser.add_subparsers(dest="command")

    def add_common_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument("--target", type=Path, default=Path("."), help="Target directory to scan")
        p.add_argument("--project", dest="project_key", type=str, default=None, help="Project key")
        p.add_argument("--branch", type=str, default=None, help="Branch name")
        p.add_argument("--exclude", type=str, default=None, help="Comma-separated directory exclusions")
        p.add_argument("--languages", type=str, default=None, help="Comma-separated languages (python,csharp,java,sql)")
        p.add_argument("--output", dest="output_path", type=Path, default=None, help="Output JSON report path")
        p.add_argument("--timeout", dest="timeout_seconds", type=int, default=None, help="Analyzer timeout in seconds")
        p.add_argument("--log-level", dest="log_level", type=str, default=None, help="Log level (DEBUG, INFO, WARNING, ERROR)")
        p.add_argument("--server", type=str, default=None, help="POLARIS Server URL for connected mode")
        p.add_argument("--fail-on-quality-gate", action="store_true", help="Exit with code 3 if Quality Gate status is FAILED")
        p.add_argument("--target-branch", type=str, default=None, help="Base branch for differential/PR analysis")
        p.add_argument("--pr-key", type=str, default=None, help="Pull Request identifier (e.g. PR-42)")
        p.add_argument("--new-code-since", type=str, default=None, help="Base commit/tag for new code period")
        p.add_argument("--config", type=Path, default=None, help="Path to polaris.json config file")
        p.add_argument("--no-cache", action="store_true", help="Disable incremental SHA-256 scan cache")
        p.add_argument("--clear-cache", action="store_true", help="Clear incremental scan cache before running")
        p.add_argument("--cache-dir", dest="cache_dir", type=Path, default=None, help="Cache directory (default .polaris in cwd)")
        p.add_argument("--workers", type=int, default=None, help="Maximum parallel analyzer workers")
        p.add_argument("--profile", type=str, default="auto", choices=("auto", "low-spec", "max"), help="Resource profile")
        p.add_argument("--max-file-size", dest="max_file_size", type=int, default=5 * 1024 * 1024, help="Max file size in bytes (default 5MB)")
        p.add_argument("--include-minified", action="store_true", help="Include minified .js/.mjs/.css assets")
        p.add_argument("--changed-only", action="store_true", help="Analyze only git modified/untracked files offline")
        p.add_argument("--format", dest="output_format", type=str, default="json", choices=("json", "sarif"), help="Output format")
        p.add_argument("--sbom-out", dest="sbom_out", type=Path, default=None, help="Output CycloneDX 1.5 SBOM JSON path")
        p.add_argument("--verbose", action="store_true", help="Enable verbose output")

    discover_parser = subparsers.add_parser("discover", help="Discover supported source files in target directory")
    add_common_flags(discover_parser)
    analyze_parser = subparsers.add_parser("analyze", help="Discover and analyze source files with POLARIS analyzers")
    add_common_flags(analyze_parser)
    add_common_flags(parser)
    return parser


def fetch_effective_profile(server_url: str, project_key: str) -> dict[str, object]:
    url = f"{server_url.rstrip('/')}/api/v1/quality-profiles/projects/{project_key}/effective-profile"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Effective profile HTTP {resp.status}")
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch effective profile from {url}: {exc}") from exc
    if not isinstance(data, dict) or "profileHash" not in data or "disabledRules" not in data:
        raise RuntimeError(f"Invalid effective profile contract from {url}")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    try:
        config = load_scanner_config(
            target_dir=args.target,
            config_file=args.config,
            cli_overrides={
                "project_key": args.project_key,
                "branch": args.branch,
                "exclusions": args.exclude,
                "languages": args.languages,
                "output_path": args.output_path,
                "timeout_seconds": args.timeout_seconds,
                "log_level": args.log_level,
            },
        )
    except ConfigValidationError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

    try:
        discovery = discover_files(
            config.target_dir,
            exclusions=config.exclusions,
            languages=config.languages,
            max_file_bytes=config.max_file_bytes,
            max_files=config.max_files,
            max_total_bytes=config.max_total_bytes,
        )
    except FileNotFoundError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    registry = AnalyzerRegistry()
    all_issues: list[dict] = []
    all_diagnostics: list[dict] = [
        {"type": "skipped_file", "file": s.relative_path, "reason": s.reason}
        for s in discovery.skipped
    ]
    partial_failure = False

    if args.command == "analyze":
        if getattr(args, "changed_only", False):
            import subprocess as _sp
            try:
                st = _sp.run(
                    ["git", "-C", str(config.target_dir), "status", "--porcelain"],
                    capture_output=True, text=True, timeout=5, check=False,
                )
                changed_rels = {
                    line[3:].strip().replace("\\", "/")
                    for line in st.stdout.splitlines()
                    if len(line) > 3
                }
            except Exception:
                changed_rels = set()
            if not changed_rels:
                return 0
            discovery.files[:] = [f for f in discovery.files if f.relative_path in changed_rels]
            if not discovery.files:
                return 0

        env_overrides: dict[str, str] | None = None
        if getattr(args, "profile", "balanced") == "low-spec":
            env_overrides = {
                "DOTNET_GCHeapHardLimit": "0x10000000",
                "JAVA_TOOL_OPTIONS": "-Xmx256m -XX:+UseSerialGC",
            }
        profile_hash = "default"
        if args.server:
            try:
                eff = fetch_effective_profile(args.server, config.project_key)
                profile_hash = str(eff.get("profileHash") or "default")
                raw_disabled = eff.get("disabledRules", [])
                disabled = [str(r) for r in (raw_disabled if isinstance(raw_disabled, list) else []) if str(r).strip()]
                if disabled:
                    env_overrides = {**(env_overrides or {}), "POLARIS_DISABLED_RULES": ",".join(disabled)}
            except Exception as exc:
                all_diagnostics.append({"type": "profile_fetch_warning", "message": str(exc)})

        use_cache = not getattr(args, "no_cache", False)
        clear_cache = getattr(args, "clear_cache", False)
        cache_dir = getattr(args, "cache_dir", None) or (Path.cwd() / ".polaris")
        cache_path = cache_dir / "cache.json.gz"
        cache: IncrementalScanCache | None = None
        if use_cache or clear_cache:
            cache = IncrementalScanCache(cache_path)
            if clear_cache:
                cache.clear()

        by_lang: dict[str, list[str]] = {}
        file_hashes: dict[str, tuple[str, str]] = {}
        try:
            for f in discovery.files:
                spec = registry.get_by_language(f.language)
                if spec is None:
                    continue
                if cache is not None and use_cache:
                    raw_bytes = f.absolute_path.read_bytes()
                    if len(raw_bytes) > getattr(args, "max_file_size", 5 * 1024 * 1024):
                        all_diagnostics.append({"type": "skipped_file", "file": f.relative_path, "reason": "max_file_size"})
                        continue
                    if is_binary_bytes(raw_bytes):
                        all_diagnostics.append({"type": "skipped_file", "file": f.relative_path, "reason": "binary"})
                        continue
                    if not getattr(args, "include_minified", False) and is_minified_asset(f.absolute_path, raw_bytes):
                        all_diagnostics.append({"type": "skipped_file", "file": f.relative_path, "reason": "minified_asset"})
                        continue
                    f_sha = compute_bytes_sha256(raw_bytes)
                    file_hashes[f.relative_path] = (f_sha, spec.version)
                    cached = cache.get(
                        file_sha256=f_sha,
                        rule_profile_hash=profile_hash,
                        worker_version=spec.version,
                    )
                    if cached is not None:
                        for issue in cached.issues:
                            issue.setdefault("confidence", "HIGH")
                            all_issues.append(issue)
                        continue
                by_lang.setdefault(f.language, []).append(str(f.absolute_path))

            tasks = [
                WorkerTask(language=lang, spec=registry.get_by_language(lang), files=files)
                for lang, files in sorted(by_lang.items())
                if registry.get_by_language(lang) is not None and files
            ]
            repo_root = Path(__file__).resolve().parents[2]
            outcomes = run_workers_parallel(
                tasks,
                project_key=config.project_key,
                branch=config.branch,
                target_dir=config.target_dir,
                repo_root=repo_root,
                timeout_seconds=config.timeout_seconds,
                env_overrides=env_overrides,
                max_workers=getattr(args, "workers", None),
            )

            issues_by_file: dict[str, list[dict]] = {}
            for outcome in outcomes:
                exec_res = outcome.result
                lang = outcome.language
                if exec_res.status != "OK" or exec_res.payload is None:
                    partial_failure = True
                    all_diagnostics.append({"type": "analyzer_error", "language": lang, "message": exec_res.error_message or exec_res.status})
                    continue
                contract_errors = validate_analysis_result(exec_res.payload)
                if contract_errors:
                    partial_failure = True
                    all_diagnostics.append({"type": "contract_error", "language": lang, "message": "; ".join(contract_errors)})
                    continue
                all_diagnostics.extend(exec_res.payload.get("diagnostics", []))
                for issue in exec_res.payload.get("issues", []):
                    loc = issue["location"]
                    issue.setdefault("confidence", "HIGH")
                    issue["fingerprint"] = compute_issue_fingerprint(
                        issue["ruleId"], loc["file"], loc["startLine"], issue["message"]
                    )
                    all_issues.append(issue)
                    issues_by_file.setdefault(loc["file"], []).append(issue)

            if cache is not None and use_cache:
                for rel_path, (f_sha, w_ver) in file_hashes.items():
                    if rel_path in issues_by_file or any(
                        str(f.absolute_path) in by_lang.get(f.language, [])
                        for f in discovery.files
                        if f.relative_path == rel_path
                    ):
                        cache.put(
                            file_path=rel_path,
                            file_sha256=f_sha,
                            rule_profile_hash=profile_hash,
                            worker_version=w_ver,
                            issues=issues_by_file.get(rel_path, []),
                        )
                cache.commit()
        finally:
            if cache is not None:
                cache.close()

        all_issues.sort(key=lambda i: (i["location"]["file"], i["location"]["startLine"], i["ruleId"]))

    status = "COMPLETED"
    if partial_failure or all_diagnostics:
        status = "COMPLETED_WITH_WARNINGS"

    report = {
        "schemaVersion": CONTRACT_SCHEMA_VERSION,
        "analysisId": str(uuid.uuid4()),
        "projectKey": config.project_key,
        "branch": config.branch,
        "analyzer": {
            "id": "polaris-scanner",
            "version": SCANNER_VERSION,
        },
        "status": status,
        "totalFiles": len(discovery.files),
        "diagnostics": all_diagnostics,
        "issues": all_issues,
        "discoveredFiles": [
            {"file": f.relative_path, "language": f.language, "sizeBytes": f.size_bytes}
            for f in discovery.files
        ],
        "registeredAnalyzers": [spec.id for spec in registry.list_all()],
    }

    if args.server:
        server_url = args.server.rstrip("/")
        try:
            proj_req = urllib.request.Request(
                f"{server_url}/api/v1/projects",
                data=json.dumps({"projectKey": config.project_key, "name": config.project_key}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                urllib.request.urlopen(proj_req, timeout=10).close()
            except urllib.error.HTTPError as exc:
                if exc.code not in (200, 201, 409):
                    raise
            ana_req = urllib.request.Request(
                f"{server_url}/api/v1/analyses",
                data=gzip.compress(json.dumps(report).encode("utf-8")),
                headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
                method="POST",
            )
            with urllib.request.urlopen(ana_req, timeout=15) as resp:
                if resp.status not in (200, 201):
                    print(json.dumps({"error": f"Server returned HTTP {resp.status}"}), file=sys.stderr)
                    return 1
                if getattr(args, "fail_on_quality_gate", False):
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    qg = resp_data.get("quality_gate") or resp_data.get("qualityGate") or {}
                    if isinstance(qg, dict) and qg.get("status") == "FAILED":
                        print(json.dumps({"quality_gate": qg}), file=sys.stderr)
                        return 3
        except Exception as exc:
            print(json.dumps({"error": f"Failed to upload analysis to {server_url}: {exc}"}), file=sys.stderr)
            return 1

    if getattr(args, "sbom_out", None) is not None:
        from polaris_scanner.exporters.sbom import export_cyclonedx_1_5
        write_report_atomic(export_cyclonedx_1_5([], project_name=config.project_key), args.sbom_out)

    out_payload = report
    if getattr(args, "output_format", "json") == "sarif":
        from polaris_scanner.exporters.sarif import export_sarif_2_1_0
        out_payload = export_sarif_2_1_0(report)

    if config.output_path is not None:
        write_report_atomic(out_payload, config.output_path)
    else:
        print(json.dumps(out_payload, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
