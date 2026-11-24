import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from polaris_scanner.config import ConfigValidationError, load_scanner_config


class TestScannerConfig(unittest.TestCase):
    def test_precedence_cli_over_env_over_file_over_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "polaris.json").write_text(
                json.dumps({"project_key": "from-file", "branch": "file-branch", "timeout_seconds": 30}),
                encoding="utf-8",
            )
            cfg = load_scanner_config(
                target_dir=root,
                env={"POLARIS_PROJECT_KEY": "from-env", "POLARIS_TIMEOUT_SECONDS": "45"},
                cli_overrides={"project_key": "from-cli"},
            )
            self.assertEqual(cfg.project_key, "from-cli")
            self.assertEqual(cfg.timeout_seconds, 45)
            self.assertEqual(cfg.branch, "file-branch")
            self.assertEqual(cfg.log_level, "INFO")

    def test_invalid_language_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ConfigValidationError):
                load_scanner_config(target_dir=Path(tmp), cli_overrides={"languages": "python,ruby"})

    def test_invalid_limits_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ConfigValidationError):
                load_scanner_config(target_dir=Path(tmp), cli_overrides={"timeout_seconds": 0})


if __name__ == "__main__":
    unittest.main()
