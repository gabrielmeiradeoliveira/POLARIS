from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "html"))

from polaris_html_analyzer import analyze_frontend_content


class TestFrontendAnalyzer(unittest.TestCase):
    def test_positive_all_10_rules(self) -> None:
        code = "\n".join([
            '<div dangerouslySetInnerHTML={{ __html: x }} />',
            '<a href="javascript:alert(1)">x</a>',
            '<a href="https://x.com" target="_blank">x</a>',
            'eval(userInput);',
            'localStorage.setItem("auth_token", tok);',
            '<script src="https://cdn.example.com/a.js"></script>',
            '<iframe src="https://example.com"></iframe>',
            'useEffect(() => { setCount(1) });',
            'items.map((x, idx) => <li key={idx}>{x}</li>);',
            '<input type="password" name="pw" />',
        ])
        ids = {i["ruleId"].split(":")[1] for i in analyze_frontend_content(code, "App.tsx")}
        expected = {
            "FE-SEC-001", "FE-SEC-002", "FE-SEC-003", "FE-SEC-004", "FE-SEC-005",
            "FE-SEC-006", "FE-SEC-007", "FE-REL-001", "FE-REL-002", "FE-REL-003",
        }
        self.assertEqual(ids, expected)

    def test_negative_safe_frontend(self) -> None:
        safe = "\n".join([
            '<div>{text}</div>',
            '<a href="/home" target="_blank" rel="noopener noreferrer">Home</a>',
            '<script src="https://cdn.example.com/a.js" integrity="sha384-abc"></script>',
            '<iframe src="/embed" sandbox="allow-scripts"></iframe>',
            '<input type="password" autocomplete="current-password" />',
        ])
        self.assertEqual(analyze_frontend_content(safe, "index.html"), [])


if __name__ == "__main__":
    unittest.main()
