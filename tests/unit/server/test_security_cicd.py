from __future__ import annotations

import unittest

from fastapi import HTTPException

from polaris_server.auth_service import (
    TokenCreateRequest,
    UserCreateRequest,
    check_permission,
    create_token,
    create_user,
    get_audit_log,
    hash_password,
    revoke_token,
    verify_password,
)
from polaris_server.webhooks_service import WebhookCreateRequest, create_webhook, sign_webhook_payload, validate_webhook_url


class TestSecurityAndCICD(unittest.TestCase):
    def test_webhook_ssrf_and_hmac(self) -> None:
        with self.assertRaises(ValueError):
            validate_webhook_url("http://127.0.0.1:8000/hook")
        with self.assertRaises(ValueError):
            validate_webhook_url("http://169.254.169.254/latest/meta-data")
        self.assertEqual(validate_webhook_url("https://ci.example.com/polaris"), "https://ci.example.com/polaris")
        sig = sign_webhook_payload("secret", b'{"status":"PASSED"}')
        self.assertEqual(len(sig), 64)
        wh = create_webhook(WebhookCreateRequest(name="CI", url="https://ci.example.com/polaris"))
        self.assertEqual(wh["name"], "CI")

    def test_auth_passwords_tokens_rbac_and_audit(self) -> None:
        h = hash_password("StrongPass123!")
        self.assertTrue(verify_password("StrongPass123!", h))
        self.assertFalse(verify_password("WrongPass", h))

        self.assertTrue(check_permission("GLOBAL_ADMIN", "ADMIN_USERS"))
        self.assertFalse(check_permission("VIEWER", "ADMIN_USERS"))

        u = create_user(UserCreateRequest(username="alice", password="StrongPass123!", role="PROJECT_ADMIN"))
        self.assertEqual(u["username"], "alice")

        tok = create_token(TokenCreateRequest(name="ci-token", username="alice"))
        self.assertTrue(tok["token"].startswith("pol_"))
        rev = revoke_token(tok["token_id"])
        self.assertTrue(rev["revoked"])
        self.assertGreaterEqual(get_audit_log()["total"], 2)

        with self.assertRaises(HTTPException):
            create_user(UserCreateRequest(username="bob", password="StrongPass123!", role="INVALID_ROLE"))


if __name__ == "__main__":
    unittest.main()
