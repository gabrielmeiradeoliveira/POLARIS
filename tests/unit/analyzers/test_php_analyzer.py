from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "php"))

from polaris_php_analyzer import analyze_php_content


class TestPhpAnalyzer(unittest.TestCase):
    def test_positive_all_10_rules(self) -> None:
        php = "\n".join([
            '$pdo->query("SELECT * FROM u WHERE id=" . $id);',
            'echo $_GET["name"];',
            'eval($code);',
            'unserialize($_POST["data"]);',
            'include $page;',
            '$h = md5($password);',
            'extract($_POST);',
            'curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);',
            '$api_key = "sk_live_12345678";',
            'try { run(); } catch (Exception $e) {}',
        ])
        ids = {i["ruleId"].split(":")[1] for i in analyze_php_content(php)}
        expected = {f"PHP-SEC-00{i}" for i in range(1, 10)} | {"PHP-REL-001"}
        self.assertEqual(ids, expected)

    def test_negative_safe_php(self) -> None:
        safe = "\n".join([
            '$stmt = $pdo->prepare("SELECT * FROM u WHERE id = ?");',
            'echo htmlspecialchars($name, ENT_QUOTES);',
            '$hash = password_hash($password, PASSWORD_BCRYPT);',
        ])
        self.assertEqual(analyze_php_content(safe), [])


if __name__ == "__main__":
    unittest.main()
