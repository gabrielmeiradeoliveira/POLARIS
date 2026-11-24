import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from analyzers import analyze_python
from scanner import scan_directory, submit_report
from server import create_server


class TestPolarisPoc(unittest.TestCase):
    def test_python_parse_error_not_treated_as_clean(self):
        res = analyze_python(Path("bad.py"), "bad.py", "def broken(:\n")
        self.assertEqual(res["state"], "PARSE_ERROR")

    def test_vertical_integration_end_to_end(self):
        samples_dir = Path(__file__).parent / "samples"
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "polaris_test.db"
            srv, conn = create_server(db_path, port=0)
            port = srv.server_address[1]
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
            try:
                base_url = f"http://127.0.0.1:{port}"
                with urllib.request.urlopen(f"{base_url}/api/v1/health") as r:
                    health = json.loads(r.read().decode("utf-8"))
                    self.assertEqual(health["status"], "UP")

                report = scan_directory(samples_dir, project_key="demo-polaris")
                self.assertEqual(len(report["files"]), 4)
                self.assertEqual(len(report["issues"]), 4)

                resp = submit_report(base_url, report)
                self.assertEqual(resp["persistedIssues"], 4)

                with urllib.request.urlopen(f"{base_url}/api/v1/projects/demo-polaris/summary") as r:
                    summary = json.loads(r.read().decode("utf-8"))
                    self.assertEqual(summary["totalFiles"], 4)
                    self.assertEqual(summary["totalIssues"], 4)
                    self.assertGreater(summary["totalLoc"], 0)

                with urllib.request.urlopen(f"{base_url}/") as r:
                    html = r.read().decode("utf-8")
                    self.assertIn("POLARIS 2.0 PoC", html)
            finally:
                srv.shutdown()
                srv.server_close()
                conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
