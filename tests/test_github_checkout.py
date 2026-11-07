from __future__ import annotations

import base64
import subprocess
from pathlib import Path

import pytest

from polaris.integrations.github.checkout import GitHubCheckoutError, checkout_github_repository


def test_checkout_rejects_untrusted_repository_parts() -> None:
    with (
        pytest.raises(GitHubCheckoutError, match="owner"),
        checkout_github_repository("evil/../../x", "repo", "a" * 40, "token"),
    ):
        pass
    with (
        pytest.raises(GitHubCheckoutError, match="revision"),
        checkout_github_repository("acme", "repo", "main", "token"),
    ):
        pass


def test_checkout_cleans_workspace(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def run(command, **kwargs):
        calls.append(command)
        if "clone" in command:
            Path(command[-1]).mkdir()
            (Path(command[-1]) / "file.py").write_text("pass\n")
        return None

    monkeypatch.setattr("polaris.integrations.github.checkout.subprocess.run", run)
    with checkout_github_repository("acme", "repo", "a" * 40, "token") as path:
        assert path.exists()
    assert not path.exists()
    assert "core.hooksPath=/dev/null" in calls[0]


def test_checkout_uses_basic_x_access_token_auth_not_bearer(monkeypatch) -> None:
    """Regression test: GitHub Git Smart HTTP rejects AUTHORIZATION: bearer <PAT> and requires Basic x-access-token."""
    calls: list[tuple[list[str], dict[str, str]]] = []
    secret_pat = "ghp_SyntheticSecretTokenForTestOnly123456"

    def run(command, **kwargs):
        calls.append((command, kwargs["env"]))
        if "clone" in command:
            Path(command[-1]).mkdir()
            (Path(command[-1]) / "app.cs").write_text("namespace StoreApi {}\n", encoding="utf-8")
        return None

    monkeypatch.setattr("polaris.integrations.github.checkout.subprocess.run", run)
    sha = "0c64a77bffcf8c1e76756214c54045421351cf5a"
    with checkout_github_repository("gabrielmeiradeoliveira", "StoreApi", sha, secret_pat) as repo_dir:
        assert (repo_dir / "app.cs").is_file()

    assert len(calls) == 2
    clone_cmd, clone_env = calls[0]
    checkout_cmd, _ = calls[1]
    expected_b64 = base64.b64encode(f"x-access-token:{secret_pat}".encode()).decode("ascii")

    assert clone_env["GIT_TERMINAL_PROMPT"] == "0"
    assert clone_env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert clone_env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
    assert clone_env["GIT_CONFIG_VALUE_0"] == f"AUTHORIZATION: basic {expected_b64}"
    assert "bearer" not in clone_env["GIT_CONFIG_VALUE_0"].lower()
    assert secret_pat not in " ".join(clone_cmd)
    assert "core.hooksPath=/dev/null" in clone_cmd
    assert "protocol.file.allow=never" in clone_cmd
    assert "core.hooksPath=/dev/null" in checkout_cmd
    assert "protocol.file.allow=never" in checkout_cmd


def test_checkout_classifies_auth_failure_without_exposing_token(monkeypatch) -> None:
    """Regression test for git exit code 128 ('could not read Username') without leaking credentials."""
    secret_pat = "ghp_NeverLeakThisTokenInErrorMessages999"
    encoded = base64.b64encode(f"x-access-token:{secret_pat}".encode()).decode("ascii")

    def fail_clone(command, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=128,
            cmd=command,
            stderr="Cloning into '/tmp/polaris-github-xyz/repository'...\n"
            "fatal: could not read Username for 'https://github.com': terminal prompts disabled\n",
        )

    monkeypatch.setattr("polaris.integrations.github.checkout.subprocess.run", fail_clone)
    with (
        pytest.raises(GitHubCheckoutError) as exc_info,
        checkout_github_repository("gabrielmeiradeoliveira", "StoreApi", "a" * 40, secret_pat),
    ):
        pass

    message = str(exc_info.value)
    assert "Authorized repository checkout failed" in message
    assert "git clone: Git HTTP authentication rejected by remote" in message
    assert secret_pat not in message
    assert encoded not in message


def test_checkout_classifies_missing_sha_and_repo_not_found_and_timeout(monkeypatch) -> None:
    secret_pat = "ghp_AnotherSecretTokenValue1234567890"

    # 1. Missing commit SHA during git checkout stage
    def fail_on_checkout(command, **kwargs):
        if "clone" in command:
            Path(command[-1]).mkdir()
            return None
        raise subprocess.CalledProcessError(
            returncode=128,
            cmd=command,
            stderr="fatal: reference is not a tree: " + ("b" * 40) + "\n",
        )

    monkeypatch.setattr("polaris.integrations.github.checkout.subprocess.run", fail_on_checkout)
    with (
        pytest.raises(GitHubCheckoutError) as sha_exc,
        checkout_github_repository("acme", "repo", "b" * 40, secret_pat),
    ):
        pass
    assert "git checkout: target commit SHA not found in repository" in str(sha_exc.value)
    assert secret_pat not in str(sha_exc.value)

    # 2. Repository not found (404)
    def fail_not_found(command, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=128,
            cmd=command,
            stderr="remote: Repository not found.\nfatal: repository 'https://github.com/acme/missing.git/' not found\n",
        )

    monkeypatch.setattr("polaris.integrations.github.checkout.subprocess.run", fail_not_found)
    with (
        pytest.raises(GitHubCheckoutError) as nf_exc,
        checkout_github_repository("acme", "missing", "b" * 40, secret_pat),
    ):
        pass
    assert "git clone: remote repository not found or inaccessible" in str(nf_exc.value)
    assert secret_pat not in str(nf_exc.value)

    # 3. Timeout
    def fail_timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(cmd=command, timeout=60)

    monkeypatch.setattr("polaris.integrations.github.checkout.subprocess.run", fail_timeout)
    with (
        pytest.raises(GitHubCheckoutError) as to_exc,
        checkout_github_repository("acme", "slow", "b" * 40, secret_pat),
    ):
        pass
    assert "git clone timed out after 60s" in str(to_exc.value)
    assert secret_pat not in str(to_exc.value)
