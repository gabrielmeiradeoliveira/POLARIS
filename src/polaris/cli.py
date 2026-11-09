"""Command-line interface for POLARIS."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated

import typer

from polaris import __version__
from polaris.core.config import OutputFormat, PolarisConfig
from polaris.core.errors import ExitCode, PolarisError
from polaris.core.models import BudgetTracker, ExecutionBudget
from polaris.core.orchestrator import AnalysisOrchestrator
from polaris.core.registry import ModuleRegistry, build_default_scanner_registry
from polaris.evaluation.history import CorpusKind, append_manifest, build_manifest, write_trend_reports
from polaris.evaluation.runner import evaluate_corpus, load_fixtures_from_file
from polaris.integrations.github.client import GitHubClient
from polaris.integrations.github.fixture_transport import FixtureGitHubTransport
from polaris.integrations.github.models import GitHubIntegrationError
from polaris.integrations.github.review_engine import GitHubPullRequestReview
from polaris.modules.code_review import CodeReviewModule
from polaris.providers.factory import create_provider
from polaris.providers.fake import FakeProvider
from polaris.quota.store import UsageStore
from polaris.reporting.formatter import (
    format_json_report,
    format_terminal_report,
    format_usage_json,
    format_usage_terminal,
)

app = typer.Typer(
    name="polaris",
    help="POLARIS: Open-source, modular, AI-powered software assurance and code review CLI.",
    add_completion=False,
    no_args_is_help=True,
)
github_app = typer.Typer(
    help="Review local GitHub PR fixtures without network access or publishing.",
    no_args_is_help=True,
)
app.add_typer(github_app, name="github")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"polaris {__version__}")
        raise typer.Exit(code=int(ExitCode.SUCCESS))


@app.callback()
def main_callback(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-V",
            help="Show the POLARIS version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """POLARIS CLI root callback."""


def build_default_registry() -> ModuleRegistry:
    """Create a ModuleRegistry populated with default POLARIS modules."""
    registry = ModuleRegistry()
    registry.register(CodeReviewModule())
    return registry


@github_app.command("review")
def github_review_command(
    repository: Annotated[str, typer.Option("--repo", help="GitHub repository in OWNER/REPO form.")],
    pull_request: Annotated[int, typer.Option("--pr", min=1, help="Pull request number in the local fixture.")],
    fixture: Annotated[
        Path, typer.Option("--fixture", exists=True, readable=True, help="Local GitHub API fixture JSON.")
    ],
    provider: Annotated[str, typer.Option("--provider", help="Offline provider; only 'fake' is supported.")] = "fake",
    output_format: Annotated[str, typer.Option("--format", help="Output format: terminal or json.")] = "terminal",
    max_requests: Annotated[
        int | None, typer.Option("--max-requests", min=1, help="Maximum fake-provider requests.")
    ] = None,
    max_tokens: Annotated[int | None, typer.Option("--max-tokens", min=1, help="Maximum fake-provider tokens.")] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Required safe mode; no network or publishing is possible.")
    ] = True,
) -> None:
    """Analyze a fixture PR end-to-end and simulate only review comments."""
    try:
        if provider.lower() != "fake":
            raise ValueError("GitHub fixture review supports only the offline 'fake' provider.")
        if output_format not in {OutputFormat.TERMINAL.value, OutputFormat.JSON.value}:
            raise ValueError("--format must be 'terminal' or 'json'.")
        if not dry_run:
            raise ValueError("GitHub review publishing is disabled; --dry-run is required.")
        owner, separator, repo_name = repository.partition("/")
        if not separator or not owner or not repo_name or "/" in repo_name:
            raise ValueError("--repo must use OWNER/REPO form.")

        budget_values: dict[str, int] = {}
        if max_requests is not None:
            budget_values["max_requests"] = max_requests
        if max_tokens is not None:
            budget_values["max_total_tokens"] = max_tokens
        engine = GitHubPullRequestReview(
            GitHubClient(FixtureGitHubTransport.from_path(fixture)),
            FakeProvider(),
            budget=ExecutionBudget(**budget_values),
        )
        report, summary = engine.review(owner, repo_name, pull_request)
        payload = {"report": report.model_dump(mode="json"), "summary": summary.model_dump(mode="json")}
        if output_format == OutputFormat.JSON.value:
            typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        else:
            typer.echo(
                f"GitHub fixture review: {repository}#{pull_request} | {summary.status} | "
                f"files={summary.files_analyzed} findings={summary.findings} "
                f"located={summary.findings_with_valid_location} "
                f"proposed_comments={summary.new_comments} duplicates={summary.duplicate_comments}"
            )
        raise typer.Exit(code=int(ExitCode.SUCCESS))
    except GitHubIntegrationError as exc:
        typer.echo(f"GitHub fixture error [{exc.category.value}]: {exc}", err=True)
        raise typer.Exit(code=int(ExitCode.GENERAL_ERROR)) from exc
    except ValueError as exc:
        typer.echo(f"Configuration error: {exc}", err=True)
        raise typer.Exit(code=int(ExitCode.CONFIGURATION_ERROR)) from exc
    except PolarisError as exc:
        typer.echo(f"Error: {exc.message}", err=True)
        raise typer.Exit(code=int(exc.exit_code)) from exc


@app.command("review")
def review_command(
    base: Annotated[
        str | None,
        typer.Option(
            "--base",
            "-b",
            help="Compare working tree against a specific Git revision (e.g., HEAD~1, main).",
        ),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option(
            "--provider",
            "-p",
            help="AI provider to use ('nvidia' or 'fake'). Defaults to POLARIS_PROVIDER or 'nvidia'.",
        ),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help="Model identifier override for the selected provider.",
        ),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Report output format: 'terminal', 'json', or 'sarif'.",
        ),
    ] = "terminal",
    repo: Annotated[
        Path | None,
        typer.Option(
            "--repo",
            "-r",
            help="Path to the target Git repository (defaults to current working directory).",
        ),
    ] = None,
    max_tokens: Annotated[
        int | None,
        typer.Option(
            "--max-tokens",
            help="Maximum total token budget for this analysis run.",
        ),
    ] = None,
    max_requests: Annotated[
        int | None,
        typer.Option(
            "--max-requests",
            help="Maximum API requests permitted during this analysis run.",
        ),
    ] = None,
    max_retries: Annotated[
        int | None,
        typer.Option(
            "--max-retries",
            help="Maximum automatic retries on transient HTTP 429/5xx or timeout (default: 0).",
        ),
    ] = None,
    timeout: Annotated[
        float | None,
        typer.Option(
            "--timeout",
            help="Per-request timeout in seconds.",
        ),
    ] = None,
    attempt_deadline: Annotated[
        float | None, typer.Option("--attempt-deadline", help="Optional per-attempt deadline in seconds.")
    ] = None,
    case_deadline: Annotated[
        float | None, typer.Option("--case-deadline", help="Optional per-case deadline in seconds.")
    ] = None,
    allow_external: Annotated[
        bool | None,
        typer.Option(
            "--allow-external/--no-allow-external",
            help="Explicitly authorize sending repository diffs to an external AI provider.",
        ),
    ] = None,
    db_path: Annotated[
        Path | None,
        typer.Option(
            "--db-path",
            help="Override path to the persistent SQLite usage database.",
        ),
    ] = None,
    context: Annotated[
        bool | None,
        typer.Option(
            "--context/--no-context",
            help="Enable or disable AST-based cross-file context engine (default: enabled).",
        ),
    ] = None,
    behavioral_delta: Annotated[
        bool | None,
        typer.Option(
            "--behavioral-delta/--no-behavioral-delta",
            help="Enable or disable AST-based behavioral delta analysis (default: disabled).",
        ),
    ] = None,
    hybrid_static_selection: Annotated[
        bool | None,
        typer.Option(
            "--hybrid-static-selection/--no-hybrid-static-selection",
            help="Opt in to conservative removal of exact supplementary context duplicates (default: disabled).",
        ),
    ] = None,
    static_relevance_selection: Annotated[
        bool | None,
        typer.Option(
            "--static-relevance-selection/--no-static-relevance-selection",
            help="Opt in to CFG/data-flow-informed ranking of proven direct context (default: disabled).",
        ),
    ] = None,
    context_tokens: Annotated[
        int | None,
        typer.Option(
            "--context-tokens",
            help="Maximum token budget allocated for supplementary repository context.",
        ),
    ] = None,
    context_files: Annotated[
        int | None,
        typer.Option(
            "--context-files",
            help="Maximum number of supplementary context files to select (default: 8).",
        ),
    ] = None,
    context_snippets: Annotated[
        int | None,
        typer.Option(
            "--context-snippets",
            help="Maximum number of supplementary code snippets to select (default: 16).",
        ),
    ] = None,
    strategy: Annotated[
        str | None,
        typer.Option(
            "--strategy",
            help="Review execution strategy: 'direct' (default standard pipeline) or 'hybrid' (GOAL 28 opt-in multi-stage arbitration engine).",
        ),
    ] = None,
    baseline_path: Annotated[
        Path | None,
        typer.Option(
            "--baseline",
            help="Path to an existing security baseline file to compare findings against.",
        ),
    ] = None,
    save_baseline_path: Annotated[
        Path | None,
        typer.Option(
            "--save-baseline",
            help="Path to save the current analysis findings as a new security baseline.",
        ),
    ] = None,
    fail_on_new: Annotated[
        bool | None,
        typer.Option(
            "--fail-on-new/--no-fail-on-new",
            help="Enforce quality gate evaluation strictly on new security regressions compared to baseline.",
        ),
    ] = None,
) -> None:
    """Analyze local Git changes for correctness bugs."""
    try:
        config = PolarisConfig.from_env_and_args(
            repo_path=repo,
            base_revision=base,
            provider=provider,
            model=model,
            output_format=output_format,
            allow_external_code=allow_external,
            max_tokens=max_tokens,
            max_requests=max_requests,
            max_retries=max_retries,
            timeout_seconds=timeout,
            attempt_deadline_seconds=attempt_deadline,
            case_deadline_seconds=case_deadline,
            usage_db_path=db_path,
            context_enabled=context,
            behavioral_delta_enabled=behavioral_delta,
            hybrid_static_selection_enabled=hybrid_static_selection,
            static_relevance_selection_enabled=static_relevance_selection,
            context_max_tokens=context_tokens,
            context_max_files=context_files,
            context_max_snippets=context_snippets,
        )
        llm_provider = create_provider(config)
        llm_provider.preserve_static_on_budget_skip = True

        is_hybrid = bool(strategy and strategy.strip().lower() == "hybrid")
        if is_hybrid:
            # Opt-in GOAL 30 Hybrid Review & Code Intelligence Execution
            typer.echo("[POLARIS HYBRID] Opt-in hybrid review & autonomous code intelligence engine activated.")

        registry = build_default_registry()
        orchestrator = AnalysisOrchestrator(
            config=config,
            provider=llm_provider,
            registry=registry,
        )
        report = orchestrator.run()

        # If HYBRID strategy is activated, enrich report with GOAL 30 deep intelligence
        if is_hybrid and report.files_analyzed:
            from polaris.review.orchestrator_3 import HybridOrchestrator3
            deep_orchestrator = HybridOrchestrator3()
            tracker = BudgetTracker(config.budget)
            # Run deep review across analyzed files
            deep_results = []
            for fpath in report.files_analyzed:
                full_p = Path(config.repo_path) / fpath
                after_c = full_p.read_text(encoding="utf-8", errors="replace") if full_p.is_file() else ""
                deep_res = deep_orchestrator.run_deep_review(
                    changed_file=fpath,
                    before_content=None,
                    after_content=after_c,
                    diff_text="",
                    provider=llm_provider,
                    tracker=tracker,
                )
                deep_results.append({
                    "file_path": fpath,
                    "fused_evidences": deep_res["fused_evidences"],
                    "risk_scores": deep_res["risk_scores"],
                    "dataflow_count": deep_res["dataflow_count"],
                })

            # Update report model with goal30 intelligence payload
            report = report.model_copy(update={"goal30_intelligence": {"analyses": deep_results}})

        # Execute deterministic security scanners on analyzed / changed files (and untracked files in local diff mode)
        scanner_registry = build_default_scanner_registry()
        logger = logging.getLogger(__name__)
        raw_scanner_results = []
        scanned_files_set = set(report.files_analyzed)

        # In local uncommitted diff review (base_revision is None), include untracked repository files in scan scope
        if config.base_revision is None:
            try:
                import subprocess
                res_untracked = subprocess.run(
                    ["git", "-c", f"safe.directory={config.repo_path}", "-C", str(config.repo_path), "ls-files", "--others", "--exclude-standard"],
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                )
                if res_untracked.returncode == 0:
                    for line in res_untracked.stdout.splitlines():
                        clean_u = line.strip().replace("\\", "/").lstrip("./")
                        if clean_u:
                            scanned_files_set.add(clean_u)
            except Exception as exc:
                logger.debug("Failed discovering untracked files for scanner coverage: %s", type(exc).__name__)

        effective_scanned_files = sorted(scanned_files_set)
        scanner_parse_errors: list[str] = []
        from polaris.security.contracts import ScannerReportParseError

        for fpath in effective_scanned_files:
            full_p = Path(config.repo_path) / fpath
            if full_p.is_file():
                try:
                    fcontent = full_p.read_text(encoding="utf-8", errors="replace")
                    raw_scanner_results.extend(scanner_registry.run_scanners_on_file(fpath, fcontent))
                except ScannerReportParseError as exc:
                    scanner_parse_errors.append(f"{fpath}: {exc.message}")
                    logger.warning("Security scanner report parse error in %s: %s", fpath, exc.message)
                except OSError as exc:
                    logger.debug("Failed reading file %s for scanning: %s", fpath, type(exc).__name__)

        if scanner_parse_errors:
            typer.echo(f"Security Scanner Report Parse Error: {scanner_parse_errors[0]}", err=True)
            raise typer.Exit(code=int(ExitCode.CONFIGURATION_ERROR))

        from polaris.evidence.platform import CanonicalFindingDomain, CanonicalSecurityFinding
        from polaris.policy.quality_gate import GateDecision, PolarisSecurityPolicy, SecurityQualityGateEngine
        from polaris.reporting.sarif import SarifReportFormatter

        canonical_findings: list[CanonicalSecurityFinding] = []

        # Map Code Review findings
        for f in report.findings:
            seed = f"CODE::{f.file_path}::{f.line_range.start_line}::{f.category.value}"
            import hashlib
            fid = f"find:{hashlib.sha256(seed.encode()).hexdigest()[:16]}"
            canonical_findings.append(
                CanonicalSecurityFinding(
                    finding_id=fid,
                    domain=CanonicalFindingDomain.CODE_INTELLIGENCE,
                    title=f.title,
                    severity=f.severity.value.upper(),
                    confidence=f.confidence.value.upper(),
                    file_path=f.file_path,
                    line=f.line_range.start_line,
                    rule_or_cve=f.category.value,
                    evidence_text=f.evidence,
                    remediation_hint=f.suggested_remediation or "",
                    risk_score=90.0 if f.severity.value.upper() == "CRITICAL" else 60.0,
                )
            )

        # Map Scanner results
        for sr in raw_scanner_results:
            if sr.scanner_id == "container_security":
                domain = CanonicalFindingDomain.CONTAINER
            elif sr.scanner_id == "docker_scout":
                domain = CanonicalFindingDomain.IMAGE_VULNERABILITY
            elif sr.scanner_id == "secret_detection":
                domain = CanonicalFindingDomain.SECRETS
            elif sr.scanner_id == "iac_security":
                domain = CanonicalFindingDomain.IAC
            else:
                domain = CanonicalFindingDomain.SUPPLY_CHAIN
            import hashlib
            seed = f"{sr.scanner_id.upper()}::{sr.file_path}::{sr.line}::{sr.rule_id}"
            fid = f"find:{hashlib.sha256(seed.encode()).hexdigest()[:16]}"
            canonical_findings.append(
                CanonicalSecurityFinding(
                    finding_id=fid,
                    domain=domain,
                    title=sr.title,
                    severity=sr.severity.upper(),
                    confidence=sr.confidence.upper(),
                    file_path=sr.file_path,
                    line=sr.line,
                    rule_or_cve=sr.rule_id,
                    evidence_text=sr.description,
                    remediation_hint=sr.remediation,
                    risk_score=90.0 if sr.severity.upper() == "CRITICAL" else 65.0,
                )
            )

        from polaris.policy.baseline import (
            BaselineError,
            SecurityBaselineEngine,
        )

        baseline_summary = None
        sarif_states: dict[str, str] = {}

        # 1. Handle baseline loading and comparison if requested
        if baseline_path is not None:
            try:
                loaded_baseline = SecurityBaselineEngine.load_from_file(baseline_path)
            except BaselineError as exc:
                typer.echo(f"Error loading baseline: {exc.message}", err=True)
                raise typer.Exit(code=int(ExitCode.CONFIGURATION_ERROR)) from exc

            is_curr_complete = report.status == "completed"
            trunc_reasons = [f"{w.code}: {w.message}" for w in report.warnings if "BUDGET" in w.code or "TRUNCAT" in w.code]
            baseline_summary = SecurityBaselineEngine.compare(
                current_findings=canonical_findings,
                baseline=loaded_baseline,
                current_files_analyzed=effective_scanned_files,
                current_is_complete=is_curr_complete,
                current_incompleteness_reasons=trunc_reasons,
            )

            # Map SARIF baseline states
            for cf in baseline_summary.existing_findings:
                sarif_states[cf.finding.finding_id] = "existing"
            for cf in baseline_summary.new_findings:
                sarif_states[cf.finding.finding_id] = "new"

        # 2. Handle saving baseline if requested
        if save_baseline_path is not None:
            try:
                is_curr_complete = report.status == "completed"
                trunc_reasons = [f"{w.code}: {w.message}" for w in report.warnings if "BUDGET" in w.code or "TRUNCAT" in w.code]
                new_baseline = SecurityBaselineEngine.create_baseline(
                    findings=canonical_findings,
                    files_analyzed=effective_scanned_files,
                    repository_root=str(config.repo_path),
                    base_revision=config.base_revision,
                    is_complete=is_curr_complete,
                    incompleteness_reasons=trunc_reasons,
                )
                SecurityBaselineEngine.save_to_file(new_baseline, save_baseline_path, overwrite=True)
            except BaselineError as exc:
                typer.echo(f"Error saving baseline: {exc.message}", err=True)
                raise typer.Exit(code=int(ExitCode.CONFIGURATION_ERROR)) from exc

        # 3. Evaluate Quality Gate Policy
        policy = PolarisSecurityPolicy.load_from_repo(config.repo_path)
        gate_decision = GateDecision.PASS
        blocking: list[str] = []

        is_curr_complete = report.status == "completed"
        trunc_reasons = [f"{w.code}: {w.message}" for w in report.warnings if "BUDGET" in w.code or "TRUNCAT" in w.code]

        should_fail_on_new = bool(fail_on_new or (policy and policy.fail_on_new))
        if policy is not None or should_fail_on_new:
            eval_findings = canonical_findings
            if should_fail_on_new and baseline_summary is not None:
                eval_findings = [it.finding for it in baseline_summary.new_findings]

            gate_decision, blocking = SecurityQualityGateEngine.evaluate(
                eval_findings,
                policy=policy,
                is_complete=is_curr_complete,
                incompleteness_reasons=trunc_reasons,
            )

        if config.output_format == OutputFormat.SARIF:
            sarif_dict = SarifReportFormatter.to_sarif(canonical_findings, baseline_states=sarif_states)
            typer.echo(json.dumps(sarif_dict, indent=2))
        elif config.output_format == OutputFormat.JSON:
            report_dict = json.loads(format_json_report(report))
            if baseline_summary is not None:
                report_dict["baseline_comparison"] = baseline_summary.model_dump()
            typer.echo(json.dumps(report_dict, indent=2))
        else:
            typer.echo(format_terminal_report(report))
            if raw_scanner_results:
                typer.echo("\nAdditional Security Scanner Findings:")
                for sr in raw_scanner_results:
                    typer.echo(f"  [{sr.severity.upper()}] {sr.file_path}:{sr.line} - {sr.title} ({sr.rule_id})")
            if baseline_summary is not None:
                typer.echo("\n--- Security Baseline Comparison ---")
                typer.echo(f"  Complete: {baseline_summary.is_complete}")
                typer.echo(
                    f"  Findings: NEW={baseline_summary.counts['new']}, "
                    f"EXISTING={baseline_summary.counts['existing']}, "
                    f"RESOLVED={baseline_summary.counts['resolved']}"
                )
                if baseline_summary.new_findings:
                    typer.echo("  New Findings:")
                    for it in baseline_summary.new_findings:
                        typer.echo(f"    + [{it.finding.severity}] {it.finding.file_path}:{it.finding.line} - {it.finding.title}")
                if baseline_summary.resolved_findings:
                    typer.echo("  Resolved Findings:")
                    for it in baseline_summary.resolved_findings:
                        typer.echo(f"    - [{it.finding.severity}] {it.finding.file_path}:{it.finding.line} - {it.finding.title}")

        if gate_decision == GateDecision.FAIL:
            typer.echo(f"\n[POLARIS QUALITY GATE] FAILED: {len(blocking)} blocking violation(s) found.", err=True)
            for blk in blocking:
                typer.echo(f"  - {blk}", err=True)
            raise typer.Exit(code=1)

        raise typer.Exit(code=int(ExitCode.SUCCESS))

    except PolarisError as exc:
        typer.echo(f"Error: {exc.message}", err=True)
        raise typer.Exit(code=int(exc.exit_code)) from exc
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Unexpected error: {exc}", err=True)
        raise typer.Exit(code=int(ExitCode.GENERAL_ERROR)) from exc


@app.command("usage")
def usage_command(
    provider: Annotated[
        str | None,
        typer.Option(
            "--provider",
            "-p",
            help="AI provider to inspect ('nvidia' or 'fake'). Defaults to POLARIS_PROVIDER or 'nvidia'.",
        ),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help="Model identifier override.",
        ),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Report output format: 'terminal', 'json', or 'sarif'.",
        ),
    ] = "terminal",
    scope: Annotated[
        str | None,
        typer.Option(
            "--scope",
            help="Quota scope override.",
        ),
    ] = None,
    db_path: Annotated[
        Path | None,
        typer.Option(
            "--db-path",
            help="Override path to the persistent SQLite usage database.",
        ),
    ] = None,
) -> None:
    """Display locally tracked persistent API usage and configured rate/daily limits."""
    try:
        config = PolarisConfig.from_env_and_args(
            provider=provider,
            model=model,
            output_format=output_format,
            quota_scope=scope,
            usage_db_path=db_path,
        )
        store = UsageStore(
            db_path=config.resolved_usage_db_path,
            reservation_ttl_seconds=config.budget.reservation_ttl_seconds,
        )
        snapshot = store.get_snapshot(
            provider=config.provider,
            model=config.resolved_model,
            quota_scope=config.resolved_quota_scope,
            quota_enabled=config.budget.quota_enabled,
            rate_limit_rpm=config.budget.rate_limit_rpm,
            rate_limit_tpm=config.budget.rate_limit_tpm,
            rate_limit_rpd=config.budget.rate_limit_rpd,
        )

        if config.output_format == OutputFormat.JSON:
            typer.echo(format_usage_json(snapshot))
        else:
            typer.echo(format_usage_terminal(snapshot))

        raise typer.Exit(code=int(ExitCode.SUCCESS))
    except PolarisError as exc:
        typer.echo(f"Error: {exc.message}", err=True)
        raise typer.Exit(code=int(exc.exit_code)) from exc
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Unexpected error: {exc}", err=True)
        raise typer.Exit(code=int(ExitCode.GENERAL_ERROR)) from exc


@app.command("evaluate")
def evaluate_command(
    fixtures_file: Annotated[
        Path,
        typer.Option(
            "--fixtures",
            help="Path to the evaluation fixtures JSON file.",
        ),
    ] = Path("evaluations/fixtures/code_review_corpus.json"),
    provider: Annotated[
        str,
        typer.Option(
            "--provider",
            "-p",
            help="Provider to evaluate ('fake' or 'nvidia').",
        ),
    ] = "fake",
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help="Model identifier override for provider evaluation.",
        ),
    ] = None,
    allow_external: Annotated[
        bool,
        typer.Option(
            "--allow-external/--no-allow-external",
            help="Explicitly authorize sending evaluation fixtures to an external AI provider.",
        ),
    ] = False,
    baseline: Annotated[
        bool,
        typer.Option(
            "--baseline",
            help="Evaluate using pre-MVP 1.3 baseline validator instead of Finding Intelligence Engine.",
        ),
    ] = False,
    end_to_end: Annotated[
        bool,
        typer.Option(
            "--end-to-end",
            "--e2e",
            help="Run full end-to-end review pipeline with configured provider instead of post-processing candidates.",
        ),
    ] = False,
    strict_severity: Annotated[
        bool,
        typer.Option(
            "--strict-severity",
            help="Require finding severity to strictly match ground truth severity for a match.",
        ),
    ] = False,
    max_cases: Annotated[
        int | None,
        typer.Option(
            "--max-cases",
            help="Maximum number of evaluation cases to execute from the fixture dataset.",
        ),
    ] = None,
    case_id: Annotated[
        list[str] | None,
        typer.Option("--case-id", help="Case ID to execute; repeat to form a stable evaluation batch."),
    ] = None,
    production_parity: Annotated[
        bool,
        typer.Option(
            "--production-parity", help="Materialize fixture sources and reuse production context preparation."
        ),
    ] = False,
    context_tokens: Annotated[
        int | None,
        typer.Option("--context-tokens", help="Maximum shared supplementary-context tokens for evaluation."),
    ] = None,
    behavioral_delta_reserved_tokens: Annotated[
        int | None,
        typer.Option(
            "--behavioral-delta-reserved-tokens", help="Fixed Behavioral Delta reservation inside context tokens."
        ),
    ] = None,
    max_requests: Annotated[
        int | None,
        typer.Option(
            "--max-requests",
            help="Maximum total API requests allowed across the evaluation run.",
        ),
    ] = None,
    max_tokens: Annotated[
        int | None,
        typer.Option(
            "--max-tokens",
            help="Maximum total tokens allowed across the evaluation run.",
        ),
    ] = None,
    timeout: Annotated[
        float | None,
        typer.Option(
            "--timeout",
            help="Per-request timeout in seconds for provider evaluation.",
        ),
    ] = None,
    attempt_deadline: Annotated[
        float | None, typer.Option("--attempt-deadline", help="Optional per-attempt deadline in seconds.")
    ] = None,
    case_deadline: Annotated[
        float | None, typer.Option("--case-deadline", help="Optional per-case deadline in seconds.")
    ] = None,
    max_retries: Annotated[
        int | None,
        typer.Option(
            "--max-retries",
            help="Maximum automatic retries on transient rate-limits or server errors.",
        ),
    ] = None,
    max_elapsed_seconds: Annotated[
        float | None,
        typer.Option(
            "--max-elapsed-seconds",
            help="Maximum total execution time budget in seconds across the evaluation run.",
        ),
    ] = None,
    skip_unsuitable: Annotated[
        bool,
        typer.Option(
            "--skip-unsuitable",
            help="Skip fixtures marked unsuitable for live defect detection benchmarking.",
        ),
    ] = False,
    detailed: Annotated[
        bool,
        typer.Option(
            "--detailed",
            "-d",
            "--diagnostics",
            help="Display detailed finding-level diagnostics for each evaluated case in terminal output.",
        ),
    ] = False,
    behavioral_delta: Annotated[
        bool | None,
        typer.Option(
            "--behavioral-delta/--no-behavioral-delta",
            help="Enable or disable AST-based behavioral delta analysis during evaluation (default: disabled).",
        ),
    ] = None,
    hybrid_static_selection: Annotated[
        bool | None,
        typer.Option(
            "--hybrid-static-selection/--no-hybrid-static-selection",
            help="Opt in to conservative removal of exact supplementary context duplicates (default: disabled).",
        ),
    ] = None,
    static_relevance_selection: Annotated[
        bool | None,
        typer.Option(
            "--static-relevance-selection/--no-static-relevance-selection",
            help="Opt in to CFG/data-flow-informed ranking of proven direct context (default: disabled).",
        ),
    ] = None,
    observability_file: Annotated[
        Path | None,
        typer.Option(
            "--observability-file",
            help="Write opt-in hash-only experimental telemetry to a local JSON file; prompts and responses are never stored.",
        ),
    ] = None,
    history_dir: Annotated[
        Path | None,
        typer.Option(
            "--history-dir",
            help="Append a sanitized immutable validation-history manifest and run-scoped trend reports here.",
        ),
    ] = None,
    history_run_id: Annotated[
        str | None,
        typer.Option("--history-run-id", help="Stable unique ID required when --history-dir is used."),
    ] = None,
    history_configuration: Annotated[
        str,
        typer.Option("--history-configuration", help="Declared benchmark configuration label, such as A, B, or C."),
    ] = "default",
    history_corpus_kind: Annotated[
        CorpusKind,
        typer.Option("--history-corpus-kind", help="Corpus provenance; real and synthetic histories remain separate."),
    ] = CorpusKind.SYNTHETIC,
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: 'terminal' or 'json'.",
        ),
    ] = "terminal",
) -> None:
    """Run the curated evaluation benchmark and report precision, recall, latency, and tokens."""
    try:
        config = PolarisConfig.from_env_and_args(
            provider=provider,
            model=model,
            allow_external_code=allow_external,
            behavioral_delta_enabled=behavioral_delta,
            hybrid_static_selection_enabled=hybrid_static_selection,
            static_relevance_selection_enabled=static_relevance_selection,
            context_max_tokens=context_tokens,
            behavioral_delta_reserved_tokens=behavioral_delta_reserved_tokens,
            max_tokens=max_tokens,
            max_requests=max_requests,
            max_retries=max_retries,
            timeout_seconds=timeout,
            attempt_deadline_seconds=attempt_deadline,
            case_deadline_seconds=case_deadline,
            max_elapsed_seconds=max_elapsed_seconds,
            output_format=output_format,
        )
        if config.provider != "fake":
            config.validate_provider_credentials()

        llm_provider = create_provider(config)
        if not fixtures_file.exists():
            typer.echo(f"Error: Evaluation fixtures file not found: '{fixtures_file}'", err=True)
            raise typer.Exit(code=int(ExitCode.CONFIGURATION_ERROR))

        fixtures = load_fixtures_from_file(fixtures_file)
        has_budget_override = (
            max_requests is not None
            or max_tokens is not None
            or timeout is not None
            or attempt_deadline is not None
            or case_deadline is not None
            or max_retries is not None
            or max_elapsed_seconds is not None
            or config.budget.max_elapsed_seconds != 360.0
        )
        eval_budget = (
            ExecutionBudget(
                **{
                    **config.budget.model_dump(),
                    **({"max_requests": max(len(fixtures) * 2, 100)} if max_requests is None else {}),
                    **({"max_total_tokens": 10_000_000} if max_tokens is None else {}),
                }
            )
            if has_budget_override
            else None
        )
        summary = evaluate_corpus(
            fixtures,
            provider=llm_provider,
            budget=eval_budget,
            use_baseline=baseline,
            force_end_to_end=end_to_end,
            strict_severity=strict_severity,
            max_cases=max_cases,
            skip_unsuitable=skip_unsuitable,
            behavioral_delta_enabled=config.behavioral_delta_enabled,
            hybrid_static_selection_enabled=config.hybrid_static_selection_enabled,
            static_relevance_selection_enabled=config.static_relevance_selection_enabled,
            production_parity=production_parity,
            context_limits=config.context_limits,
            case_ids=case_id,
            observability=observability_file is not None,
        )

        if observability_file is not None:
            observability_file.parent.mkdir(parents=True, exist_ok=True)
            observability_file.write_text(
                summary.model_dump_json(indent=2),
                encoding="utf-8",
            )

        if history_dir is not None:
            if history_run_id is None:
                raise typer.BadParameter("--history-run-id is required when --history-dir is used.")
            history_budget = eval_budget or config.budget
            manifest = build_manifest(
                run_id=history_run_id,
                summary=summary,
                corpus_path=fixtures_file,
                corpus_kind=history_corpus_kind,
                provider=llm_provider.provider_name,
                model=llm_provider.model_name,
                configuration=history_configuration,
                operational_limits=history_budget.model_dump(),
                repo_root=Path.cwd(),
            )
            manifest_path = append_manifest(history_dir, manifest)
            trend_json, trend_markdown = write_trend_reports(history_dir, run_id=history_run_id)
            typer.echo(f"History Manifest    : {manifest_path}", err=config.output_format == OutputFormat.JSON)
            typer.echo(
                f"History Trends      : {trend_json}, {trend_markdown}", err=config.output_format == OutputFormat.JSON
            )

        if config.output_format == OutputFormat.JSON:
            typer.echo(summary.model_dump_json(indent=2))
        else:
            engine_label = "Baseline Validator" if baseline else "Finding Intelligence Engine"
            if end_to_end:
                summary_title = f"POLARIS Evaluation Summary (End-to-End {llm_provider.provider_name} + {engine_label})"
            else:
                summary_title = f"POLARIS Evaluation Summary ({engine_label})"
            typer.echo("=" * 72)
            typer.echo(summary_title)
            typer.echo("=" * 72)
            typer.echo(
                f"Dataset Size        : {summary.dataset_size} "
                f"(positive={summary.positive_cases}, negative={summary.negative_cases})"
            )
            typer.echo(
                f"Provenance          : executable_verified={summary.verified_cases}, "
                f"documented_verified={summary.documented_verified_cases}, "
                f"reference_modeled={summary.reference_modeled_cases}, "
                f"unverified={summary.unverified_cases}"
            )
            typer.echo(
                f"Counts              : TP={summary.true_positives}, "
                f"FP={summary.false_positives}, FN={summary.false_negatives}"
            )
            prec_str = f"{summary.precision:.2%}" if summary.precision is not None else "N/A"
            rec_str = f"{summary.recall:.2%}" if summary.recall is not None else "N/A"
            f1_str = f"{summary.f1_score:.2%}" if summary.f1_score is not None else "N/A"
            fpr_str = f"{summary.false_positive_rate:.2%}" if summary.false_positive_rate is not None else "N/A"
            typer.echo(f"Precision           : {prec_str}")
            typer.echo(f"Recall              : {rec_str}")
            typer.echo(f"F1                  : {f1_str}")
            typer.echo(f"False Positive Rate : {fpr_str}")
            typer.echo(f"Duplicates Reduced  : {summary.duplicates_reduced}")
            typer.echo(f"Legitimate Rejected : {summary.legitimate_rejected}")
            if summary.severity_mismatches > 0:
                typer.echo(f"Severity Mismatches : {summary.severity_mismatches}")
            if summary.successful_cases > 0:
                typer.echo(f"Successful Cases    : {summary.successful_cases}")
            if summary.api_failed_cases > 0:
                typer.echo(f"API Failed Cases    : {summary.api_failed_cases}")
            if summary.timeout_cases > 0:
                typer.echo(f"Timeout Cases       : {summary.timeout_cases}")
            if summary.error_cases > 0:
                typer.echo(f"Error Cases         : {summary.error_cases}")
            if summary.unassessed_cases > 0:
                typer.echo(f"Unassessed Cases    : {summary.unassessed_cases}")
            if summary.budget_exhausted_cases > 0:
                typer.echo(f"Budget Exhausted    : {summary.budget_exhausted_cases}")
            if summary.skipped_cases > 0:
                typer.echo(f"Skipped Cases       : {summary.skipped_cases}")
            elif summary.failed_cases > 0:
                typer.echo(f"Failed Cases        : {summary.failed_cases}")
            if summary.budget_exhausted:
                typer.echo("Budget Status       : STOPPED (Budget / Quota Exhausted)")
            typer.echo(
                f"Latency             : total={summary.total_latency_ms} ms, avg={summary.average_latency_ms:.2f} ms"
            )
            typer.echo(
                f"Provider Tokens     : {summary.usage.total_tokens} "
                f"(prompt={summary.usage.prompt_tokens}, completion={summary.usage.completion_tokens})"
            )
            typer.echo("Local Engine Tokens : 0 (pure deterministic static analysis)")
            if summary.failed_cases > 0:
                typer.echo("-" * 72)
                typer.echo("Failed Case Diagnostics:")
                for case_res in summary.case_results:
                    if case_res.status != "completed":
                        typer.echo(f"  * Case ID          : {case_res.case_id}")
                        typer.echo(f"    Status           : {case_res.status}")
                        if case_res.error_category:
                            typer.echo(f"    Error Category   : {case_res.error_category}")
                        if case_res.http_status is not None:
                            typer.echo(f"    HTTP Status      : {case_res.http_status}")
                        typer.echo(f"    Duration         : {case_res.latency_ms} ms")
                        typer.echo(f"    Retries          : {case_res.retries_attempted}")
                        if case_res.error:
                            typer.echo(f"    Error Message    : {case_res.error}")
            if detailed:
                typer.echo("-" * 72)
                typer.echo("Finding-Level Evaluation Diagnostics:")
                for case_res in summary.case_results:
                    typer.echo(f"\n  Case ID: {case_res.case_id} [{case_res.status}]")
                    if not case_res.diagnostics:
                        if case_res.status != "completed":
                            typer.echo(
                                f"    (Diagnostics unavailable for non-completed case: {case_res.error or case_res.status})"
                            )
                        else:
                            typer.echo("    (No diagnostics recorded)")
                        continue

                    diag = case_res.diagnostics
                    typer.echo(f"    Parsed Candidates ({len(diag.candidate_findings)}):")
                    if not diag.candidate_findings:
                        typer.echo("      (none)")
                    for c in diag.candidate_findings:
                        c_lines = f"{c.start_line}-{c.end_line or c.start_line}"
                        typer.echo(
                            f"      * [{c.category.value}/{c.severity.value}] {c.file_path}:{c_lines} - {c.title}"
                        )

                    typer.echo(f"    Validated Findings ({len(diag.validated_findings)}):")
                    if not diag.validated_findings:
                        typer.echo("      (none)")
                    for f in diag.validated_findings:
                        f_lines = f"{f.line_range.start_line}-{f.line_range.end_line}"
                        typer.echo(
                            f"      * [{f.id}] [{f.category.value}/{f.severity.value}] {f.file_path}:{f_lines} - {f.title}"
                        )

                    typer.echo(f"    Rejected Candidates ({len(diag.rejected_candidates)}):")
                    if not diag.rejected_candidates:
                        typer.echo("      (none)")
                    for r in diag.rejected_candidates:
                        r_lines = f"{r.line_range.start_line}-{r.line_range.end_line}"
                        code_str = f" [{r.rejection_code}]" if r.rejection_code else ""
                        typer.echo(f"      * [{r.category.value}] {r.file_path}:{r_lines} - {r.title}{code_str}")
                        typer.echo(f"        Reason: {r.reason}")

                    typer.echo(f"    Matched Findings ({len(diag.matched_findings)}):")
                    if not diag.matched_findings:
                        typer.echo("      (none)")
                    for m in diag.matched_findings:
                        m_lines = f"{m.line_range.start_line}-{m.line_range.end_line}"
                        exp_lines = f"{m.expected_line_range.start_line}-{m.expected_line_range.end_line}"
                        exp_cats = [c.value for c in m.expected_allowed_categories] or (
                            [m.expected_category.value] if m.expected_category else ["any"]
                        )
                        sev_info = "exact" if m.severity_match else "mismatch"
                        typer.echo(
                            f"      * [{m.finding_id}] {m.file_path}:{m_lines} [{m.category.value}] -> "
                            f"matched expected at {m.expected_file_path}:{exp_lines} {exp_cats} (severity: {sev_info})"
                        )

                    typer.echo(f"    Unmatched Findings / False Positives ({len(diag.unmatched_findings)}):")
                    if not diag.unmatched_findings:
                        typer.echo("      (none)")
                    for u in diag.unmatched_findings:
                        u_lines = f"{u.line_range.start_line}-{u.line_range.end_line}"
                        typer.echo(
                            f"      * [{u.finding_id}] [{u.category.value}/{u.severity.value}] {u.file_path}:{u_lines} - {u.title}"
                        )
                        for reason in u.reasons:
                            typer.echo(f"        Reason: {reason}")

                    typer.echo(f"    Unmatched Expected Defects / False Negatives ({len(diag.unmatched_expected)}):")
                    if not diag.unmatched_expected:
                        typer.echo("      (none)")
                    for ue in diag.unmatched_expected:
                        ue_lines = f"{ue.line_range.start_line}-{ue.line_range.end_line}"
                        ue_cats = [c.value for c in ue.allowed_categories] or (
                            [ue.category.value] if ue.category else ["any"]
                        )
                        sev_str = ue.severity.value if ue.severity else "any"
                        typer.echo(
                            f"      * Expected defect at {ue.file_path}:{ue_lines} {ue_cats} (severity: {sev_str})"
                        )
                        typer.echo(f"        Reason: {ue.reason}")
            typer.echo("=" * 72)
        raise typer.Exit(code=int(ExitCode.SUCCESS))
    except PolarisError as exc:
        typer.echo(f"Error: {exc.message}", err=True)
        raise typer.Exit(code=int(exc.exit_code)) from exc


def main() -> None:
    """Entrypoint for the `polaris` console script."""
    app()
