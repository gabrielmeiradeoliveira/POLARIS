from __future__ import annotations

import os
import unittest

from polaris_server.db import get_connection, run_migrations
from polaris_server.gates_service import GateCreateRequest, create_gate, list_gates
from polaris_server.git_branch_service import list_branches, list_pull_requests, register_branch, register_pull_request
from polaris_server.history_service import get_project_history, record_snapshot
from polaris_server.issues_service import upsert_issue_occurrence
from polaris_server.metrics_service import get_project_metrics, store_project_metrics
from polaris_server.profiles_service import ProfileCreateRequest, create_profile, list_profiles
from polaris_server.webhooks_service import WebhookCreateRequest, create_webhook, list_webhooks


@unittest.skipUnless(os.environ.get("POLARIS_TEST_PG") == "1", "Requires PostgreSQL outside sandbox")
class TestServicesPostgreSQL(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        run_migrations()
        cls.project_key = f"pg_test_{os.getpid()}"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO projects (project_key, name) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
                    (cls.project_key, "PG Test Project"),
                )
            conn.commit()

    def test_01_history_and_metrics_roundtrip(self) -> None:
        aid = f"anl_{os.getpid()}"
        record_snapshot(self.project_key, aid, branch="main", quality_gate_status="PASSED", metrics={"total_files": 5})
        hist = get_project_history(self.project_key)
        self.assertGreaterEqual(hist["total"], 1)
        store_project_metrics(self.project_key, {"issues_total": 2, "technical_debt_minutes": 15}, analysis_id=aid)
        m = get_project_metrics(self.project_key)
        self.assertEqual(m["issues_total"], 2)

    def test_02_issues_roundtrip(self) -> None:
        aid = f"anl_{os.getpid()}"
        rec = upsert_issue_occurrence(
            self.project_key, "PY-REL-002", "MINOR", "python", "a.py", 10, "Broad except", "fp1234567890abcd", analysis_id=aid
        )
        self.assertEqual(rec.project_key, self.project_key)

    def test_03_profiles_and_gates_roundtrip(self) -> None:
        pname = f"Custom_{os.getpid()}"
        p = create_profile(ProfileCreateRequest(name=pname, language="python"))
        self.assertTrue(any(x["profile_id"] == p["profile_id"] for x in list_profiles("python")["items"]))
        gname = f"Gate_{os.getpid()}"
        g = create_gate(GateCreateRequest(name=gname, conditions=[{"metric": "issues_total", "operator": "GT", "threshold": 10}]))
        self.assertTrue(any(x["gate_id"] == g["gate_id"] for x in list_gates()["items"]))

    def test_04_branches_prs_and_webhooks_roundtrip(self) -> None:
        register_branch(self.project_key, "main", is_main=True, last_commit="abc123")
        self.assertGreaterEqual(list_branches(self.project_key)["total"], 1)
        register_pull_request(self.project_key, "pr-1", "feat/x", "main", "def456")
        self.assertGreaterEqual(list_pull_requests(self.project_key)["total"], 1)
        wh = create_webhook(WebhookCreateRequest(name="ci", url="https://example.com/hook", project_key=self.project_key))
        self.assertTrue(any(x["webhook_id"] == wh["webhook_id"] for x in list_webhooks()["items"]))


if __name__ == "__main__":
    unittest.main()
