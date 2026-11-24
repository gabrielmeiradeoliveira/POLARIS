from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "kotlin"))

from polaris_kotlin_analyzer import analyze_kotlin_content


class TestKotlinAnalyzer(unittest.TestCase):
    def test_positive_all_8_rules(self) -> None:
        kt = "\n".join([
            'val q = "SELECT * FROM users WHERE id = $userId"',
            "val hv = HostnameVerifier { _, _ -> true }",
            'const val apiKey = "sk_live_12345678"',
            "ObjectInputStream(stream).readObject()",
            "val len = name!!.length",
            "runBlocking { fetch() }",
            "GlobalScope.launch { work() }",
            "try { ok() } catch (e: Exception) {}",
        ])
        ids = {i["ruleId"].split(":")[1] for i in analyze_kotlin_content(kt)}
        expected = {
            "KT-SEC-001", "KT-SEC-002", "KT-SEC-003", "KT-SEC-004",
            "KT-REL-001", "KT-REL-002", "KT-REL-003", "KT-REL-004",
        }
        self.assertEqual(ids, expected)

    def test_negative_safe_kotlin(self) -> None:
        safe = "\n".join([
            'val len = name?.length ?: 0',
            'suspend fun fetch() { coroutineScope { launch { work() } } }',
        ])
        self.assertEqual(analyze_kotlin_content(safe), [])


if __name__ == "__main__":
    unittest.main()
