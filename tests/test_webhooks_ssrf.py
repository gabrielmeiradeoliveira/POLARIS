import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from polaris_server.webhooks_service import validate_webhook_url  # noqa: E402


class TestWebhooksSSRF(unittest.TestCase):
    def test_blocks_loopback_and_private_ips(self):
        for bad in ("http://127.0.0.1:8000/hook", "http://localhost/hook", "http://10.0.0.1/hook", "http://192.168.1.10/hook", "file:///etc/passwd"):
            with self.assertRaises(ValueError):
                validate_webhook_url(bad)

    def test_allows_public_https_url(self):
        self.assertEqual(validate_webhook_url("https://hooks.example.com/polaris"), "https://hooks.example.com/polaris")
