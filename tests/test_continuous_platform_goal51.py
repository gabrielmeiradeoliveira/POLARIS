"""Comprehensive tests for GOAL 51: Polaris Continuous Quality Platform."""

from __future__ import annotations

import json
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from polaris.core.models import (
    AnalysisReport,
    Confidence,
    Finding,
    FindingCategory,
    LineRange,
    ProviderInfo,
    Severity,
    TokenUsage,
)
from polaris.integrations.github.app import verify_webhook_signature
from polaris.integrations.github.client import GitHubClient
from polaris.integrations.github.models import HttpResponse
from polaris.quality import addressed_gate_conditions, is_vulnerability_finding
from polaris.web.api import create_app
from polaris.web.store import WebStore
from polaris.web.worker import StaticAnalysisWorker


def _git(path: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=path, text=True).strip()


class StatefulGitHubTransport:
    """In-memory mock GitHub API transport supporting pagination, renames, archive, PRs, and SHA updates."""

    def __init__(self) -> None:
        self.repos_page_1: list[dict[str, Any]] = []
        self.repos_page_2: list[dict[str, Any]] = []
        self.branch_shas: dict[str, str] = {}
        self.open_prs: dict[str, list[dict[str, Any]]] = {}
        self.single_prs: dict[tuple[str, int], dict[str, Any]] = {}

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> HttpResponse:
        del method, headers, body, timeout_seconds
        if path == "/user":
            return HttpResponse(status_code=200, body='{"id":42,"login":"gabrielmeiradeoliveira"}')
        if path.startswith("/user/repos"):
            if "page=2" in path:
                return HttpResponse(status_code=200, body=json.dumps(self.repos_page_2))
            resp_headers: dict[str, str] = {}
            if self.repos_page_2:
                resp_headers["Link"] = (
                    '<https://api.github.com/user/repos?affiliation=owner,collaborator,organization_member'
                    '&per_page=100&page=2>; rel="next"'
                )
            return HttpResponse(status_code=200, body=json.dumps(self.repos_page_1), headers=resp_headers)
        if "/commits/" in path:
            # /repos/{owner}/{repo}/commits/{branch}
            parts = path.strip("/").split("/")
            full_name = f"{parts[1]}/{parts[2]}"
            sha = self.branch_shas.get(full_name, "a" * 40)
            return HttpResponse(status_code=200, body=json.dumps({"sha": sha}))
        if "/pulls" in path:
            parts = path.strip("/").split("/")
            full_name = f"{parts[1]}/{parts[2]}"
            if "?" in parts[3] or parts[3] == "pulls":
                prs = self.open_prs.get(full_name, [])
                return HttpResponse(status_code=200, body=json.dumps(prs))
            pr_num = int(parts[4])
            pr_data = self.single_prs.get((full_name, pr_num))
            if not pr_data:
                return HttpResponse(status_code=404, body='{"message":"Not Found"}')
            return HttpResponse(status_code=200, body=json.dumps(pr_data))
        return HttpResponse(status_code=404, body="{}")


def test_repository_autodiscovery_reconciliation_and_privacy_policy(tmp_path: Path) -> None:
    """Verify auto-discovery, pagination, new/renamed/archived/inaccessible states, and private repo protection."""
    transport = StatefulGitHubTransport()
    transport.repos_page_1 = [
        {
            "id": 101,
            "name": "AuthAPI",
            "full_name": "gabrielmeiradeoliveira/AuthAPI",
            "owner": {"login": "gabrielmeiradeoliveira"},
            "default_branch": "main",
            "language": "Python",
            "private": False,
            "archived": False,
        },
        {
            "id": 102,
            "name": "CorpSecret",
            "full_name": "gabrielmeiradeoliveira/CorpSecret",
            "owner": {"login": "gabrielmeiradeoliveira"},
            "default_branch": "main",
            "language": "Python",
            "private": True,
            "archived": False,
        },
    ]
    transport.repos_page_2 = [
        {
            "id": 103,
            "name": "LegacyTool",
            "full_name": "gabrielmeiradeoliveira/LegacyTool",
            "owner": {"login": "gabrielmeiradeoliveira"},
            "default_branch": "master",
            "language": "TypeScript",
            "private": False,
            "archived": True,
        }
    ]

    db_url = f"sqlite:///{tmp_path / 'discovery.sqlite3'}"
    gh_client = GitHubClient(transport, token="local-pat")
    client = TestClient(create_app(db_url, github_client=gh_client, initialize=True))

    # 1. Sync without auto-enqueuing jobs first so we can verify immediate NOT_ANALYZED state
    sync_res = client.post("/api/github/sync", json={"sync_prs": False, "enqueue_jobs": False})
    assert sync_res.status_code == 200
    body = sync_res.json()
    assert body["discovered_count"] == 3
    assert body["new_count"] == 3
    assert body["sync_mode"] == "pat_polling"

    repos_res = client.get("/api/repositories").json()
    assert repos_res["total"] == 3
    by_repo_id = {item["github_repository_id"]: item for item in repos_res["items"]}

    # Newly discovered repositories immediately show NOT_ANALYZED and never fabricate 0 findings
    auth_repo = by_repo_id[101]
    assert auth_repo["analysis_status"] == "NOT_ANALYZED"
    assert auth_repo["latest_grade"] is None
    assert auth_repo["vulnerability_count"] is None
    assert auth_repo["findings_count"] is None
    assert auth_repo["language"] == "Python"
    assert auth_repo["sync_status"] == "active"

    # Archived repository is marked archived
    assert by_repo_id[103]["is_archived"] is True
    assert by_repo_id[103]["sync_status"] == "archived"

    # 2. Subsequent sync: rename repo 101, add new repo 104, remove repo 103 (becomes inaccessible),
    # and enable enqueue_jobs (with non-inline worker so jobs stay queued and we can inspect scheduling policy)
    transport.repos_page_1 = [
        {
            "id": 101,
            "name": "AuthService",
            "full_name": "gabrielmeiradeoliveira/AuthService",
            "owner": {"login": "gabrielmeiradeoliveira"},
            "default_branch": "main",
            "language": "Python",
            "private": False,
            "archived": False,
        },
        {
            "id": 102,
            "name": "CorpSecret",
            "full_name": "gabrielmeiradeoliveira/CorpSecret",
            "owner": {"login": "gabrielmeiradeoliveira"},
            "default_branch": "main",
            "language": "Python",
            "private": True,
            "archived": False,
        },
        {
            "id": 104,
            "name": "ChatApp",
            "full_name": "gabrielmeiradeoliveira/ChatApp",
            "owner": {"login": "gabrielmeiradeoliveira"},
            "default_branch": "main",
            "language": "Go",
            "private": False,
            "archived": False,
        },
    ]
    transport.repos_page_2 = []
    transport.branch_shas["gabrielmeiradeoliveira/AuthService"] = "1" * 40
    transport.branch_shas["gabrielmeiradeoliveira/CorpSecret"] = "2" * 40
    transport.branch_shas["gabrielmeiradeoliveira/ChatApp"] = "4" * 40

    sync2 = client.post("/api/github/sync", json={"sync_prs": False, "enqueue_jobs": True}).json()
    assert sync2["new_count"] == 1
    assert sync2["renamed_count"] == 1
    assert sync2["inaccessible_count"] == 1
    # Only public active repos (101 and 104) should have initial analysis enqueued; private repo 102 is skipped!
    assert sync2["initial_jobs_enqueued"] == 2

    repos_after = {item["github_repository_id"]: item for item in client.get("/api/projects").json()}
    assert len(repos_after) == 4  # No duplicates created!
    assert repos_after[101]["name"] == "gabrielmeiradeoliveira/AuthService"
    assert repos_after[101]["analysis_status"] == "queued"
    assert repos_after[104]["analysis_status"] == "queued"
    # Private repository was NOT analyzed without authorization
    assert repos_after[102]["is_private"] is True
    assert repos_after[102]["analysis_status"] == "NOT_ANALYZED"
    # Removed repository is marked inaccessible
    assert repos_after[103]["sync_status"] == "inaccessible"

    # 3. Idempotent re-sync: syncing again with same SHAs must enqueue 0 duplicate jobs
    sync3 = client.post("/api/github/sync", json={"sync_prs": False, "enqueue_jobs": True}).json()
    assert sync3["initial_jobs_enqueued"] == 0


def test_automatic_pr_discovery_sha_change_and_end_to_end_analysis(monkeypatch, tmp_path: Path) -> None:
    """Verify automatic PR discovery, initial & PR analysis, SHA change re-scheduling, fork skip, and closed PRs."""
    repo_dir = tmp_path / "remote_repo"
    repo_dir.mkdir()
    _git(repo_dir, "init")
    _git(repo_dir, "config", "user.email", "dev@polaris.local")
    _git(repo_dir, "config", "user.name", "Polaris Dev")

    # Commit 1 (base_sha): clean code -> Grade A
    app_py = repo_dir / "app.py"
    app_py.write_text("def fetch_user(user_id: int) -> int:\n    return user_id + 1\n", encoding="utf-8")
    _git(repo_dir, "add", ".")
    _git(repo_dir, "commit", "-m", "base clean")
    base_sha = _git(repo_dir, "rev-parse", "HEAD")

    # Commit 2 (head_sha_v1): introduces SQL injection vulnerability + division by zero -> Grade F
    app_py.write_text(
        "def fetch_user(cursor, user_id: str) -> int:\n"
        "    cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')\n"
        "    return 100 / 0\n",
        encoding="utf-8",
    )
    _git(repo_dir, "add", ".")
    _git(repo_dir, "commit", "-m", "pr v1 vulnerability and bug")
    head_sha_v1 = _git(repo_dir, "rev-parse", "HEAD")

    # Commit 3 (head_sha_v2): fixes defects -> Grade A
    app_py.write_text(
        "def fetch_user(cursor, user_id: int) -> int:\n"
        "    return user_id + 2\n",
        encoding="utf-8",
    )
    _git(repo_dir, "add", ".")
    _git(repo_dir, "commit", "-m", "pr v2 fixed")
    head_sha_v2 = _git(repo_dir, "rev-parse", "HEAD")

    transport = StatefulGitHubTransport()
    transport.repos_page_1 = [
        {
            "id": 500,
            "name": "AuthAPI",
            "full_name": "gabrielmeiradeoliveira/AuthAPI",
            "owner": {"login": "gabrielmeiradeoliveira"},
            "default_branch": "main",
            "language": "Python",
            "private": False,
            "archived": False,
        }
    ]
    transport.branch_shas["gabrielmeiradeoliveira/AuthAPI"] = base_sha
    transport.open_prs["gabrielmeiradeoliveira/AuthAPI"] = [
        {
            "number": 12,
            "title": "Add user lookup endpoint",
            "body": "Implements lookup",
            "state": "open",
            "user": {"login": "alice"},
            "head": {
                "sha": head_sha_v1,
                "ref": "feat/user-lookup",
                "repo": {"fork": False, "full_name": "gabrielmeiradeoliveira/AuthAPI"},
            },
            "base": {
                "sha": base_sha,
                "ref": "main",
                "repo": {"fork": False, "full_name": "gabrielmeiradeoliveira/AuthAPI"},
            },
            "html_url": "https://github.com/gabrielmeiradeoliveira/AuthAPI/pull/12",
        },
        {
            "number": 15,
            "title": "Untrusted fork PR",
            "body": "From external fork",
            "state": "open",
            "user": {"login": "external-contributor"},
            "head": {
                "sha": head_sha_v1,
                "ref": "patch-1",
                "repo": {"fork": True, "full_name": "external/AuthAPI"},
            },
            "base": {
                "sha": base_sha,
                "ref": "main",
                "repo": {"fork": False, "full_name": "gabrielmeiradeoliveira/AuthAPI"},
            },
        },
    ]

    @contextmanager
    def local_checkout(owner: str, name: str, revision: str, token: str, **kwargs):
        del owner, name, token, kwargs
        with tempfile.TemporaryDirectory(prefix="polaris-g51-") as workspace:
            checkout = Path(workspace) / "repository"
            subprocess.run(
                ["git", "clone", "--no-checkout", str(repo_dir), str(checkout)], check=True, capture_output=True
            )
            subprocess.run(
                ["git", "-C", str(checkout), "checkout", "--detach", revision], check=True, capture_output=True
            )
            yield checkout

    monkeypatch.setattr("polaris.web.worker.checkout_github_repository", local_checkout)
    monkeypatch.setattr("polaris.web.worker.GitHubApiTransport", lambda: transport)
    monkeypatch.setenv("POLARIS_GITHUB_TOKEN", "local-pat-token")
    db_path = tmp_path / "g51-pr.sqlite3"
    monkeypatch.setenv("POLARIS_WEB_DATABASE", str(db_path))
    db_url = f"sqlite:///{db_path}"

    store = WebStore(db_url, initialize=True)
    worker = StaticAnalysisWorker(store)
    gh_client = GitHubClient(transport, token="local-pat-token")
    client = TestClient(create_app(db_url, worker=worker, github_client=gh_client, initialize=True))

    # 1. Trigger continuous sync: discovers repo 500, runs initial analysis on base_sha (Grade A),
    # discovers PR #12 and PR #15 (fork), runs analysis on PR #12 (A -> F), and skips fork PR #15!
    sync1 = client.post("/api/github/sync", json={"sync_prs": True, "enqueue_jobs": True}).json()
    assert sync1["discovered_count"] == 1
    assert sync1["prs_synced"] == 2
    assert sync1["initial_jobs_enqueued"] == 1
    assert sync1["pr_jobs_enqueued"] == 1  # Only non-fork PR #12 was enqueued!

    # Check Repository Dashboard metrics for AuthAPI (at base_sha -> Grade A, 0 findings, 0 vulnerabilities)
    projects = client.get("/api/projects").json()
    assert len(projects) == 1
    proj = projects[0]
    assert proj["analysis_status"] == "completed"
    assert proj["latest_grade"] == "A"
    assert proj["latest_score"] == 100.0
    assert proj["vulnerability_count"] == 0
    assert proj["findings_count"] == 0
    assert proj["last_analyzed_sha"] == base_sha
    assert proj["open_pr_count"] == 2

    # Check PR List: user sees Base Grade, Head Grade, Grade Change, New Crit/High, and Gate before opening details
    prs = client.get("/api/pull-requests").json()
    by_num = {pr["number"]: pr for pr in prs}
    pr12 = by_num[12]
    assert pr12["analysis_status"] == "completed"
    assert pr12["base_grade"] == "A"
    assert pr12["head_grade"] == "F"
    assert pr12["grade_delta"] == "A -> F"
    assert pr12["quality_gate_status"] == "FAILED"
    assert pr12["new_critical_count"] >= 1
    assert pr12["head_ref"] == "feat/user-lookup"
    assert pr12["base_ref"] == "main"
    assert pr12["author_login"] == "alice"

    # Fork PR #15 was discovered and persisted, but not auto-analyzed without authorization
    pr15 = by_num[15]
    assert pr15["is_fork"] is True
    assert pr15["analysis_status"] == "NOT_ANALYZED"

    # Check PR #12 Details: fix recommendations, safe code examples, addressed gate conditions, GitHub links
    pr12_detail = client.get(f"/api/pull-requests/{pr12['id']}").json()
    new_findings = pr12_detail["comparison"]["new_findings"]
    assert len(new_findings) >= 2
    sql_item = next(item for item in new_findings if "SQL" in item["finding"]["title"].upper())
    assert sql_item["is_vulnerability"] is True
    assert "minimum_grade" in sql_item["addressed_gate_conditions"]
    assert sql_item["github_blob_url"].startswith(
        f"https://github.com/gabrielmeiradeoliveira/AuthAPI/blob/{head_sha_v1}/app.py#L"
    )
    assert sql_item["safe_code_example"] is not None

    # 2. Idempotent sync: calling sync again with unchanged head_sha enqueues 0 jobs
    sync_dup = client.post("/api/github/sync", json={"sync_prs": True, "enqueue_jobs": True}).json()
    assert sync_dup["jobs_enqueued"] == 0

    # 3. Push new commit to PR #12 (head_sha_v2) and close PR #15
    transport.open_prs["gabrielmeiradeoliveira/AuthAPI"] = [
        {
            "number": 12,
            "title": "Add user lookup endpoint",
            "body": "Implements lookup safely",
            "state": "open",
            "user": {"login": "alice"},
            "head": {
                "sha": head_sha_v2,
                "ref": "feat/user-lookup",
                "repo": {"fork": False, "full_name": "gabrielmeiradeoliveira/AuthAPI"},
            },
            "base": {
                "sha": base_sha,
                "ref": "main",
                "repo": {"fork": False, "full_name": "gabrielmeiradeoliveira/AuthAPI"},
            },
        }
    ]
    sync_update = client.post("/api/github/sync", json={"sync_prs": True, "enqueue_jobs": True}).json()
    assert sync_update["pr_jobs_enqueued"] == 1

    prs_after = {pr["number"]: pr for pr in client.get("/api/pull-requests").json()}
    assert prs_after[12]["head_sha"] == head_sha_v2
    assert prs_after[12]["head_grade"] == "A"
    assert prs_after[12]["grade_delta"] == "A -> A"
    assert prs_after[12]["quality_gate_status"] == "PASSED"
    assert prs_after[15]["state"] == "closed"


def test_strict_repository_isolation_and_vulnerability_separation(tmp_path: Path) -> None:
    """Regression test for the AuthAPI/demo.py cross-project finding leak and vulnerability vs bug counts."""
    db_url = f"sqlite:///{tmp_path / 'isolation.sqlite3'}"
    store = WebStore(db_url, initialize=True)
    client = TestClient(create_app(db_url, initialize=True))

    # Project 1: SQL injection demo (has demo.py SQL injection + mutable default bug)
    demo_proj = store.create_project("SQL injection demo", str(tmp_path / "demo"))
    job = store.create_job(demo_proj["id"], "deadbeef1234", analysis_mode="project", head_sha="deadbeef1234")
    claim = store.claim_job(job["id"])
    assert claim is not None

    sql_finding = Finding(
        id="dcd-sql-demo1",
        module_id="code_review",
        category=FindingCategory.CORRECTNESS,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="demo.py",
        line_range=LineRange(start_line=2, end_line=2),
        title="[DET-SQL-INTERPOLATION] Unparameterized SQL string interpolation",
        description="Dynamic values are interpolated into a SQL string before execution.",
        evidence='cursor.execute(f"SELECT * FROM items WHERE name = \'{user_input}\'")',
        suggested_remediation="Pass SQL parameters separately from the query text.",
    )
    bug_finding = Finding(
        id="dcd-bug-demo2",
        module_id="code_review",
        category=FindingCategory.STATE_MUTATION,
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        file_path="demo.py",
        line_range=LineRange(start_line=6, end_line=6),
        title="[DET-MUTABLE-DEFAULT] Mutable default argument",
        description="A list default argument is mutated in the function body.",
        evidence="def collect(item, bucket=[]):",
        suggested_remediation="Default the parameter to None.",
    )
    assert is_vulnerability_finding(sql_finding) is True
    assert is_vulnerability_finding(bug_finding) is False

    report = AnalysisReport(
        repository_root=str(tmp_path / "demo"),
        target_description="HEAD",
        base_revision="deadbeef1234",
        files_analyzed=["demo.py"],
        modules_executed=["code_review"],
        findings=[sql_finding, bug_finding],
        provider=ProviderInfo(provider_name="fake", model_name="fake"),
        usage=TokenUsage(),
        status="completed",
    )
    assert store.complete(job["id"], claim["claim_token"], report, analyzed_sha="deadbeef1234")

    # Project 2: gabrielmeiradeoliveira/AuthAPI imported from GitHub with 0 runs (NOT_ANALYZED)
    auth_proj = store.import_github_project(
        {
            "id": 777,
            "name": "AuthAPI",
            "full_name": "gabrielmeiradeoliveira/AuthAPI",
            "owner": {"login": "gabrielmeiradeoliveira"},
            "default_branch": "main",
            "language": "Python",
        }
    )

    # Verify Project 1 separates 1 vulnerability and 1 correctness bug
    demo_detail = client.get(f"/api/projects/{demo_proj['id']}").json()
    assert demo_detail["vulnerability_count"] == 1
    assert demo_detail["bug_count"] == 1
    assert demo_detail["findings_count"] == 2
    assert len(demo_detail["latest_analysis"]["findings"]) == 2
    assert len( addressed_gate_conditions(sql_finding, demo_detail["latest_analysis"]["quality_gate"], classification="project")) >= 1

    # Verify Project 2 (AuthAPI) has strictly NO findings, NO latest_analysis, and NOT_ANALYZED status
    auth_detail = client.get(f"/api/projects/{auth_proj['id']}").json()
    assert auth_detail["analysis_status"] == "NOT_ANALYZED"
    assert auth_detail["latest_analysis"] is None
    assert auth_detail["analyses"] == []
    assert auth_detail["vulnerability_count"] is None
    assert auth_detail["findings_count"] is None

    # Verify Global Findings endpoint scopes findings strictly to their owning repository
    auth_findings = client.get(f"/api/findings?project_id={auth_proj['id']}").json()
    assert auth_findings == []
    all_findings = client.get("/api/findings").json()
    assert len(all_findings) == 2
    assert all(f["project_id"] == demo_proj["id"] and f["commit_sha"] == "deadbeef1234" for f in all_findings)


def test_webhook_pr_and_installation_repositories_synchronization(monkeypatch, tmp_path: Path) -> None:
    """Verify GitHub App webhook handles installation_repositories and pull_request events idempotently."""
    import hashlib
    import hmac

    secret = "webhook-test-secret"
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", secret)
    db_url = f"sqlite:///{tmp_path / 'webhook.sqlite3'}"
    client = TestClient(create_app(db_url, initialize=True))

    def _sign(body_bytes: bytes) -> str:
        digest = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    pr_event_payload = {
        "action": "opened",
        "number": 9,
        "repository": {
            "id": 888,
            "name": "PolarisRepo",
            "full_name": "acme/PolarisRepo",
            "owner": {"login": "acme"},
            "default_branch": "main",
            "language": "Python",
            "private": False,
        },
        "pull_request": {
            "number": 9,
            "title": "Fix edge case",
            "body": "Details",
            "state": "open",
            "user": {"login": "bob"},
            "head": {
                "sha": "c" * 40,
                "ref": "fix/edge",
                "repo": {"fork": False, "full_name": "acme/PolarisRepo"},
            },
            "base": {
                "sha": "d" * 40,
                "ref": "main",
                "repo": {"fork": False, "full_name": "acme/PolarisRepo"},
            },
        },
    }
    raw = json.dumps(pr_event_payload).encode("utf-8")
    sig = _sign(raw)
    assert verify_webhook_signature(raw, sig, secret)

    res = client.post(
        "/api/github/webhooks",
        content=raw,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Delivery": "deliv-pr-9",
            "X-GitHub-Event": "pull_request",
        },
    )
    assert res.status_code == 202
    assert res.json()["status"] == "accepted"

    prs = client.get("/api/pull-requests").json()
    assert len(prs) == 1
    assert prs[0]["number"] == 9
    assert prs[0]["head_sha"] == "c" * 40
    assert prs[0]["base_sha"] == "d" * 40
    assert prs[0]["latest_candidate_job_id"] is not None
