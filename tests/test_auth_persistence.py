from __future__ import annotations

import os
import unittest

from polaris_server.auth_service import (
    UserCreateRequest,
    TokenCreateRequest,
    check_permission,
    create_token,
    create_user,
    get_audit_log,
    hash_password,
    revoke_token,
    verify_password,
)
from polaris_server.db import run_migrations


class TestAuthPersistence(unittest.TestCase):
    def test_password_hashing_and_verification(self) -> None:
        h = hash_password("StrongPass123!")
        self.assertTrue(verify_password("StrongPass123!", h))
        self.assertFalse(verify_password("WrongPass!", h))

    def test_rbac_permissions(self) -> None:
        self.assertTrue(check_permission("GLOBAL_ADMIN", "ADMIN_USERS"))
        self.assertFalse(check_permission("VIEWER", "ADMIN_USERS"))
        self.assertTrue(check_permission("ANALYZER", "ANALYZE"))

    @unittest.skipUnless(os.environ.get("POLARIS_TEST_PG") == "1", "Requires PostgreSQL outside sandbox")
    def test_auth_postgresql_roundtrip(self) -> None:
        run_migrations()
        uname = f"u_{os.getpid()}"
        res = create_user(UserCreateRequest(username=uname, password="Password123!", role="ANALYZER"))
        self.assertEqual(res["username"], uname)
        tok = create_token(TokenCreateRequest(name="ci", username=uname))
        rev = revoke_token(tok["token_id"])
        self.assertTrue(rev["revoked"])
        audit = get_audit_log()
        self.assertGreaterEqual(audit["total"], 3)


if __name__ == "__main__":
    unittest.main()
