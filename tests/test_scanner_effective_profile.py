import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from polaris_scanner.cli import fetch_effective_profile  # noqa: E402


class TestScannerEffectiveProfile(unittest.TestCase):
    def test_fetch_effective_profile_success(self):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"projectKey":"p1","profileHash":"abc123","enabledRules":["PY-SYN-001"],"disabledRules":["SQL-SYN-001"],"parameters":{}}'
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            data = fetch_effective_profile("http://127.0.0.1:8001", "p1")
            self.assertEqual(data["profileHash"], "abc123")
            self.assertEqual(data["disabledRules"], ["SQL-SYN-001"])

    def test_fetch_effective_profile_invalid_contract_raises(self):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"invalid": true}'
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(RuntimeError):
                fetch_effective_profile("http://127.0.0.1:8001", "p1")

    def test_fetch_effective_profile_network_error_raises(self):
        with patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
            with self.assertRaises(RuntimeError):
                fetch_effective_profile("http://127.0.0.1:8001", "p1")
