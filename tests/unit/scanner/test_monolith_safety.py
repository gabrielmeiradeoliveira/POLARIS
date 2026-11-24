from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from polaris_scanner.cache import IncrementalScanCache, compute_bytes_sha256, is_binary_bytes, is_minified_asset
from polaris_scanner.secrets import scan_secrets


class TestMonolithSafety(unittest.TestCase):
    def test_backend_long_line_is_not_skipped_and_detects_secret(self) -> None:
        long_padding = "x" * 5000
        py_content = f"DATA = '{long_padding}'\nTOKEN = 'AKIAIOSFODNN7EXAMPLE'\n"
        py_path = Path("backend_monolith.py")
        self.assertFalse(is_binary_bytes(py_content.encode("utf-8")))
        self.assertFalse(is_minified_asset(py_path, py_content.encode("utf-8")))
        findings = scan_secrets(str(py_path), py_content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].kind, "AWS_ACCESS_KEY")

    def test_minified_js_and_binary_discarded(self) -> None:
        min_js = Path("app.min.js")
        self.assertTrue(is_minified_asset(min_js, b"var a=1;"))
        self.assertTrue(is_binary_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00"))

    def test_json_gz_cache_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / ".polaris" / "cache.json.gz"
            sha = compute_bytes_sha256(b"print(1)")
            with IncrementalScanCache(cache_path) as cache:
                cache.put(
                    file_path="a.py",
                    file_sha256=sha,
                    rule_profile_hash="p1",
                    worker_version="2.6.1",
                    issues=[{"ruleId": "python:PY-001", "confidence": "HIGH"}],
                )
                cache.commit()
            self.assertTrue(cache_path.exists())
            with IncrementalScanCache(cache_path) as cache2:
                hit = cache2.get(file_sha256=sha, rule_profile_hash="p1", worker_version="2.6.1")
                self.assertIsNotNone(hit)
                self.assertEqual(len(hit.issues), 1)


if __name__ == "__main__":
    unittest.main()
