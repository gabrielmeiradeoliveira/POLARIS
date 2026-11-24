import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from polaris_scanner.executor import run_analyzer_subprocess


class TestScannerExecutor(unittest.TestCase):
    def test_ok_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = run_analyzer_subprocess(
                [sys.executable, "-c", 'import json; print(json.dumps({"status": "COMPLETED"}))'],
                cwd=Path(tmp),
            )
            self.assertEqual(res.status, "OK")
            self.assertEqual(res.exit_code, 0)
            self.assertEqual(res.payload, {"status": "COMPLETED"})

    def test_timeout_handled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = run_analyzer_subprocess(
                [sys.executable, "-c", "import time; time.sleep(3)"],
                cwd=Path(tmp),
                timeout_seconds=1,
            )
            self.assertEqual(res.status, "TIMEOUT")
            self.assertIsNone(res.payload)

    def test_non_zero_exit_and_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res_err = run_analyzer_subprocess(
                [sys.executable, "-c", "import sys; sys.exit(3)"],
                cwd=Path(tmp),
            )
            self.assertEqual(res_err.status, "NON_ZERO_EXIT")
            self.assertEqual(res_err.exit_code, 3)

            res_bad_json = run_analyzer_subprocess(
                [sys.executable, "-c", "print('not-json')"],
                cwd=Path(tmp),
            )
            self.assertEqual(res_bad_json.status, "INVALID_JSON")

    def test_output_truncation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = run_analyzer_subprocess(
                [sys.executable, "-c", "print('x' * 500)"],
                cwd=Path(tmp),
                max_output_bytes=100,
            )
            self.assertTrue(res.truncated)
            self.assertLessEqual(len(res.stdout.encode("utf-8")), 100)


if __name__ == "__main__":
    unittest.main()
