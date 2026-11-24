import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from polaris_server.config import ServerConfig


class TestServerConfig(unittest.TestCase):
    def test_valid_config(self):
        cfg = ServerConfig(pg_dsn="postgresql://u:p@127.0.0.1:5432/db", max_body_bytes=1024)
        self.assertEqual(cfg.max_body_bytes, 1024)

    def test_invalid_empty_dsn(self):
        with self.assertRaises(ValueError):
            ServerConfig(pg_dsn="   ")

    def test_invalid_max_body_bytes(self):
        with self.assertRaises(ValueError):
            ServerConfig(max_body_bytes=0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
