import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestScannerCLI(unittest.TestCase):
    def _run_cli(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        repo_root = Path(__file__).resolve().parents[3]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(repo_root / "src")
        return subprocess.run(
            [sys.executable, "-m", "polaris_scanner.cli", *args],
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            shell=False,
        )

    def test_version_and_help(self) -> None:
        res_ver = self._run_cli(["--version"])
        self.assertEqual(res_ver.returncode, 0)
        self.assertIn("polaris-scanner", res_ver.stdout)

        res_help = self._run_cli(["--help"])
        self.assertEqual(res_help.returncode, 0)

    def test_discover_and_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("print(1)\n", encoding="utf-8")
            out_file = root / "out" / "report.json"
            res = self._run_cli(["discover", "--target", str(root), "--project", "cli-test", "--output", str(out_file)])
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            report = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(report["projectKey"], "cli-test")
            self.assertEqual(report["totalFiles"], 1)

    def test_exit_codes_for_invalid_args_and_missing_target(self) -> None:
        res_bad = self._run_cli(["discover", "--languages", "invalidlang"])
        self.assertEqual(res_bad.returncode, 2)

        res_missing = self._run_cli(["discover", "--target", "Z:/nonexistent_polaris_dir_12345"])
        self.assertEqual(res_missing.returncode, 1)


if __name__ == "__main__":
    unittest.main()
