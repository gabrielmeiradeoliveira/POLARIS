from __future__ import annotations

import gzip
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from polaris_scanner.exporters.sarif import export_sarif_2_1_0
from polaris_scanner.exporters.sbom import export_cyclonedx_1_5
from polaris_scanner.sca import Dependency
from polaris_server.aspm import detect_toxic_combinations, verify_hmac_signature
from polaris_server.ingestion import decode_gzip_json_stream, iter_chunks


class TestLowSpecAndASPM(unittest.TestCase):
    def test_streaming_ingestion_and_chunking(self) -> None:
        payload = {"issues": [{"id": i} for i in range(1200)]}
        gz = gzip.compress(json.dumps(payload).encode("utf-8"))
        decoded = decode_gzip_json_stream(gz)
        chunks = list(iter_chunks(decoded["issues"], chunk_size=500))
        self.assertEqual([len(c) for c in chunks], [500, 500, 200])

    def test_aspm_toxic_combinations_and_hmac(self) -> None:
        issues = [
            {"ruleId": "api:NO_AUTH_ROUTE", "severity": "MAJOR", "confidence": "HIGH"},
            {"ruleId": "python:PY-SEC-001", "severity": "CRITICAL", "confidence": "HIGH"},
        ]
        paths = detect_toxic_combinations(issues)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].id, "aspm:EXPOSED_CRITICAL_ENDPOINT")
        self.assertFalse(verify_hmac_signature(b"{}", "deadbeef", "secret"))

    def test_sarif_and_sbom_exporters(self) -> None:
        sarif = export_sarif_2_1_0({"analyzer": {"id": "polaris", "version": "2.7.0"}, "issues": []})
        self.assertEqual(sarif["version"], "2.1.0")
        sbom = export_cyclonedx_1_5([Dependency("PyPI", "fastapi", "0.163.1", "requirements.txt", 1)])
        self.assertEqual(sbom["bomFormat"], "CycloneDX")
        self.assertEqual(sbom["specVersion"], "1.5")


if __name__ == "__main__":
    unittest.main()
