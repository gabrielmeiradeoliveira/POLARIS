"""Tests for CLI commands, exit codes, terminal output, and strict JSON output."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from deicide.cli import app
from deicide.core.errors import ExitCode
from tests.conftest import run_git_cmd

runner = CliRunner()


def test_cli_help_and_version() -> None:
    res_help = runner.invoke(app, ["--help"])
    assert res_help.exit_code == 0
    assert "DEICIDE" in res_help.stdout
    assert "review" in res_help.stdout

    res_ver = runner.invoke(app, ["--version"])
    assert res_ver.exit_code == 0
    assert "deicide 0.1.0" in res_ver.stdout

    # Verify subcommands do not advertise Gemini
    for cmd in [["review", "--help"], ["usage", "--help"], ["evaluate", "--help"]]:
        res = runner.invoke(app, cmd)
        assert res.exit_code == 0
        assert "gemini" not in res.stdout.lower()
        assert "nvidia" in res.stdout.lower()


def test_cli_review_fake_terminal_and_json(temp_git_repo: Path) -> None:
    calc_file = temp_git_repo / "src" / "calc.py"
    calc_file.write_text(
        "def add(a: int, b: int) -> float:\n    return (a + b) / 0\n",
        encoding="utf-8",
    )

    res_term = runner.invoke(
        app,
        ["review", "--provider", "fake", "--repo", str(temp_git_repo)],
    )
    assert res_term.exit_code == int(ExitCode.SUCCESS)
    assert "DEICIDE Code Review Report" in res_term.stdout
    assert "Division or modulo by zero" in res_term.stdout

    res_json = runner.invoke(
        app,
        ["review", "--provider", "fake", "--format", "json", "--repo", str(temp_git_repo)],
    )
    assert res_json.exit_code == int(ExitCode.SUCCESS)
    payload = json.loads(res_json.stdout)
    assert payload["platform"] == "DEICIDE"
    assert payload["status"] == "completed"
    assert payload["provider"]["provider_name"] == "fake"
    assert len(payload["findings"]) == 1
    assert payload["findings"][0]["file_path"] == "src/calc.py"
    assert payload["findings"][0]["line_range"]["start_line"] == 2


def test_cli_review_with_base_revision(temp_git_repo: Path) -> None:
    calc_file = temp_git_repo / "src" / "calc.py"
    calc_file.write_text(
        "def compute_ratio(items: list[int]) -> float:\n    return sum(items) / len(items)\n",
        encoding="utf-8",
    )
    run_git_cmd(temp_git_repo, "add", ".")
    run_git_cmd(temp_git_repo, "commit", "-m", "Add buggy compute_ratio")

    res = runner.invoke(
        app,
        [
            "review",
            "--base",
            "HEAD~1",
            "--provider",
            "fake",
            "--format",
            "json",
            "--repo",
            str(temp_git_repo),
        ],
    )
    assert res.exit_code == int(ExitCode.SUCCESS)
    data = json.loads(res.stdout)
    assert data["base_revision"] == "HEAD~1"
    assert len(data["findings"]) == 1
    assert data["findings"][0]["category"] == "boundary_condition"


def test_cli_error_exit_codes(temp_git_repo: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("DEICIDE_API_KEY", raising=False)

    # Missing API credentials -> CONFIGURATION_ERROR (2)
    res_creds = runner.invoke(
        app,
        ["review", "--provider", "nvidia", "--repo", str(temp_git_repo)],
    )
    assert res_creds.exit_code == int(ExitCode.CONFIGURATION_ERROR)

    # Unsupported provider (gemini is no longer supported) -> CONFIGURATION_ERROR (2)
    res_gemini = runner.invoke(
        app,
        ["review", "--provider", "gemini", "--repo", str(temp_git_repo)],
    )
    assert res_gemini.exit_code == int(ExitCode.CONFIGURATION_ERROR)
    assert "Unsupported provider 'gemini'" in res_gemini.stderr

    # Unsupported provider -> CONFIGURATION_ERROR (2)
    res_prov = runner.invoke(
        app,
        ["review", "--provider", "invalid_provider", "--repo", str(temp_git_repo)],
    )
    assert res_prov.exit_code == int(ExitCode.CONFIGURATION_ERROR)

    # Invalid repository -> REPOSITORY_ERROR (3)
    non_repo = tmp_path / "plain_dir"
    non_repo.mkdir()
    res_repo = runner.invoke(
        app,
        ["review", "--provider", "fake", "--repo", str(non_repo)],
    )
    assert res_repo.exit_code == int(ExitCode.REPOSITORY_ERROR)

    # Invalid revision -> REPOSITORY_ERROR (3)
    res_rev = runner.invoke(
        app,
        ["review", "--base", "bad_rev_999", "--provider", "fake", "--repo", str(temp_git_repo)],
    )
    assert res_rev.exit_code == int(ExitCode.REPOSITORY_ERROR)

    # Exceeded token budget -> BUDGET_EXCEEDED (5)
    calc_file = temp_git_repo / "src" / "calc.py"
    calc_file.write_text("x = 1 / 0\n" * 40, encoding="utf-8")
    res_budget = runner.invoke(
        app,
        [
            "review",
            "--provider",
            "fake",
            "--max-tokens",
            "100",
            "--repo",
            str(temp_git_repo),
        ],
    )
    assert res_budget.exit_code == int(ExitCode.BUDGET_EXCEEDED)


def test_cli_review_context_options(temp_git_repo: Path) -> None:
    calc_file = temp_git_repo / "src" / "calc.py"
    calc_file.write_text("def run():\n    return 42\n", encoding="utf-8")
    res = runner.invoke(
        app,
        [
            "review",
            "--provider",
            "fake",
            "--context",
            "--context-tokens",
            "1000",
            "--context-files",
            "5",
            "--context-snippets",
            "10",
            "--repo",
            str(temp_git_repo),
        ],
    )
    assert res.exit_code == int(ExitCode.SUCCESS)


def test_cli_evaluate_help_exposes_max_elapsed_seconds() -> None:
    res = runner.invoke(app, ["evaluate", "--help"], env={"COLUMNS": "160"})
    assert res.exit_code == 0
    assert "--max-elapsed-seconds" in res.stdout
    assert "Maximum total execution time budget in seconds" in res.stdout


def test_cli_evaluate_max_elapsed_seconds_propagation_and_default(monkeypatch) -> None:
    captured_budgets = []

    import deicide.cli

    orig_evaluate_corpus = deicide.cli.evaluate_corpus

    def mock_evaluate_corpus(*args, **kwargs):
        captured_budgets.append(kwargs.get("budget"))
        return orig_evaluate_corpus(*args, **kwargs)

    monkeypatch.setattr(deicide.cli, "evaluate_corpus", mock_evaluate_corpus)

    # 1. Omitting the option preserves default (eval_budget is None, evaluate_corpus uses default 360.0)
    res_default = runner.invoke(app, ["evaluate", "--provider", "fake"])
    assert res_default.exit_code == int(ExitCode.SUCCESS)
    assert len(captured_budgets) == 1
    assert captured_budgets[0] is None

    # 2. Explicit --max-elapsed-seconds propagates to eval_budget and shared BudgetTracker
    res_override = runner.invoke(app, ["evaluate", "--provider", "fake", "--max-elapsed-seconds", "720"])
    assert res_override.exit_code == int(ExitCode.SUCCESS)
    assert len(captured_budgets) == 2
    assert captured_budgets[1] is not None
    assert captured_budgets[1].max_elapsed_seconds == 720.0

    # 3. Combined budget options propagate consistently without clamping max_elapsed_seconds
    res_combined = runner.invoke(
        app,
        [
            "evaluate",
            "--provider",
            "fake",
            "--timeout",
            "45.0",
            "--max-retries",
            "1",
            "--max-requests",
            "20",
            "--max-tokens",
            "50000",
            "--max-elapsed-seconds",
            "600.0",
        ],
    )
    assert res_combined.exit_code == int(ExitCode.SUCCESS)
    assert len(captured_budgets) == 3
    assert captured_budgets[2] is not None
    assert captured_budgets[2].request_timeout_seconds == 45.0
    assert captured_budgets[2].max_retries == 1
    assert captured_budgets[2].max_requests == 20
    assert captured_budgets[2].max_total_tokens == 50000
    assert captured_budgets[2].max_elapsed_seconds == 600.0


def test_cli_evaluate_max_elapsed_seconds_validation() -> None:
    # Negative value rejected
    res_neg = runner.invoke(app, ["evaluate", "--provider", "fake", "--max-elapsed-seconds", "-10"])
    assert res_neg.exit_code == int(ExitCode.CONFIGURATION_ERROR)
    assert "greater than zero" in res_neg.output

    # Zero rejected
    res_zero = runner.invoke(app, ["evaluate", "--provider", "fake", "--max-elapsed-seconds", "0"])
    assert res_zero.exit_code == int(ExitCode.CONFIGURATION_ERROR)
    assert "greater than zero" in res_zero.output

    # Non-numeric string rejected
    res_str = runner.invoke(app, ["evaluate", "--provider", "fake", "--max-elapsed-seconds", "not-a-number"])
    assert res_str.exit_code == int(ExitCode.CONFIGURATION_ERROR)
    assert "Invalid value for '--max-elapsed-seconds'" in res_str.output
    assert "not a valid" in res_str.output

    # Exceeding 1800s ceiling rejected
    res_ceil = runner.invoke(app, ["evaluate", "--provider", "fake", "--max-elapsed-seconds", "2000"])
    assert res_ceil.exit_code == int(ExitCode.CONFIGURATION_ERROR)
    assert "less than or equal to 1800" in res_ceil.output


def test_cli_deadline_options_validate_and_propagate(monkeypatch) -> None:
    captured_budgets = []

    import deicide.cli

    original = deicide.cli.evaluate_corpus

    def capture(*args, **kwargs):
        captured_budgets.append(kwargs.get("budget"))
        return original(*args, **kwargs)

    monkeypatch.setattr(deicide.cli, "evaluate_corpus", capture)
    success = runner.invoke(
        app,
        [
            "evaluate",
            "--provider",
            "fake",
            "--attempt-deadline",
            "6.5",
            "--case-deadline",
            "30",
        ],
    )
    assert success.exit_code == int(ExitCode.SUCCESS)
    assert captured_budgets[0].attempt_deadline_seconds == 6.5
    assert captured_budgets[0].case_deadline_seconds == 30.0

    for option in ("--attempt-deadline", "--case-deadline"):
        for invalid in ("0", "-1"):
            result = runner.invoke(app, ["evaluate", "--provider", "fake", option, invalid])
            assert result.exit_code == int(ExitCode.CONFIGURATION_ERROR)
            assert "greater than zero" in result.output


def test_cli_evaluate_tracker_receives_configured_max_elapsed(monkeypatch) -> None:
    """End-to-end verification that the active BudgetTracker receives the configured max_elapsed_seconds."""
    tracker_budgets = []

    import deicide.evaluation.runner

    orig_init = deicide.evaluation.runner.BudgetTracker.__init__

    def spy_init(self, budget, *args, **kwargs):
        tracker_budgets.append(budget)
        return orig_init(self, budget, *args, **kwargs)

    monkeypatch.setattr(deicide.evaluation.runner.BudgetTracker, "__init__", spy_init)

    # When explicit --max-elapsed-seconds is provided
    res = runner.invoke(app, ["evaluate", "--provider", "fake", "--max-elapsed-seconds", "540"])
    assert res.exit_code == int(ExitCode.SUCCESS)
    assert len(tracker_budgets) >= 1
    assert tracker_budgets[0].max_elapsed_seconds == 540.0

    # When omitted, tracker receives default 360.0
    tracker_budgets.clear()
    res_default = runner.invoke(app, ["evaluate", "--provider", "fake"])
    assert res_default.exit_code == int(ExitCode.SUCCESS)
    assert len(tracker_budgets) >= 1
    assert tracker_budgets[0].max_elapsed_seconds == 360.0
