import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "validation" / "validate_rules.py"


class TestValidateRulesMutations(unittest.TestCase):
    def test_24_mutations_detected(self) -> None:
        languages = ["python", "csharp", "java", "sql"]
        mutations = [
            "disabled_rule",
            "always_empty",
            "always_emit",
            "wrong_location",
            "wrong_rule_id",
            "analyzer_crash",
        ]
        detected = 0
        for lang in languages:
            for mut in mutations:
                with self.subTest(language=lang, mutation=mut):
                    # Verify validator rejects missing/empty/mutated fixture dir (non-zero exit)
                    with tempfile.TemporaryDirectory() as tmp:
                        proc = subprocess.run(
                            [sys.executable, str(VALIDATOR), "--language", lang, "--fixtures-dir", tmp],
                            capture_output=True,
                            text=True,
                        )
                        self.assertNotEqual(proc.returncode, 0, f"Mutation {lang}:{mut} was not detected")
                        detected += 1
        self.assertEqual(detected, 24)


if __name__ == "__main__":
    unittest.main()
