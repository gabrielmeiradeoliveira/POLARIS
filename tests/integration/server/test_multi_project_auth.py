from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from polaris_server.auth_jwt import create_jwt, generate_api_key, hash_api_key, verify_jwt


class TestMultiProjectAuth(unittest.TestCase):
    def test_jwt_roundtrip_and_tamper_rejected(self) -> None:
        tok = create_jwt({"sub": "admin@polaris.local", "role": "ADMIN"}, secret="s1")
        claims = verify_jwt(tok, secret="s1")
        self.assertIsNotNone(claims)
        self.assertEqual(claims["sub"], "admin@polaris.local")
        self.assertIsNone(verify_jwt(tok + "x", secret="s1"))

    def test_api_key_prefix_and_sha256(self) -> None:
        raw, prefix, digest = generate_api_key()
        self.assertTrue(raw.startswith("pls_live_"))
        self.assertEqual(len(prefix), 12)
        self.assertEqual(hash_api_key(raw), digest)


if __name__ == "__main__":
    unittest.main()
