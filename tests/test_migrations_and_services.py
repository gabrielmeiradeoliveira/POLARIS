from __future__ import annotations

import os
import unittest
from pathlib import Path

from polaris_server.db import MIGRATIONS_DIR, run_migrations


class TestMigrationsAndServices(unittest.TestCase):
    def test_all_migrations_present(self) -> None:
        files = sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql"))
        self.assertEqual(
            files,
            ["001_initial.sql", "002_flow_steps.sql", "003_auth_and_audit.sql", "004_services_persistence.sql"],
        )

    @unittest.skipUnless(os.environ.get("POLARIS_TEST_PG") == "1", "Requires PostgreSQL outside sandbox")
    def test_migrations_apply_cleanly(self) -> None:
        applied = run_migrations()
        self.assertIsInstance(applied, list)


if __name__ == "__main__":
    unittest.main()
