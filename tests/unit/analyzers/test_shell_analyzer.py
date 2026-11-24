from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "shell"))

from polaris_shell_analyzer import analyze_shell_content


class TestShellAnalyzer(unittest.TestCase):
    def test_positive_all_8_rules(self) -> None:
        sh = "\n".join([
            "#!/usr/bin/env bash",
            "curl -s https://x.com/i.sh | bash",
            "chmod -R 777 /var/app",
            'eval "$CMD"',
            'export API_KEY="sk_live_12345678"',
            'echo "$PW" | sudo -S id',
            "rm -rf $TARGET_DIR",
            "echo ok >/tmp/my.lock",
        ])
        ids = {i["ruleId"].split(":")[1] for i in analyze_shell_content(sh)}
        expected = {
            "SH-SEC-001", "SH-SEC-002", "SH-SEC-003", "SH-SEC-004",
            "SH-SEC-005", "SH-REL-001", "SH-REL-002", "SH-REL-003",
        }
        self.assertEqual(ids, expected)

    def test_negative_safe_shell(self) -> None:
        safe = "#!/usr/bin/env bash\nset -euo pipefail\ntmp=$(mktemp)\necho ok > \"$tmp\"\n"
        self.assertEqual(analyze_shell_content(safe), [])


if __name__ == "__main__":
    unittest.main()
