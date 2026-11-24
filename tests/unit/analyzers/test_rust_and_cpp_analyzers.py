from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "rust"))
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "cpp"))

from polaris_rust_analyzer import analyze_rust_content
from polaris_cpp_analyzer import analyze_cpp_content


class TestRustAndCppAnalyzers(unittest.TestCase):
    def test_rust_all_5_rules_and_safe(self) -> None:
        rs = "\n".join([
            "unsafe { ptr.read(); }",
            "let x: u32 = std::mem::transmute(y);",
            'Command::new("sh").arg("-c").arg(cmd);',
            "let v = opt.unwrap();",
            'let w = opt.expect("boom");',
        ])
        ids = {i["ruleId"].split(":")[1] for i in analyze_rust_content(rs, "main.rs")}
        self.assertEqual(ids, {"RS-SEC-001", "RS-SEC-002", "RS-SEC-003", "RS-REL-001", "RS-REL-002"})
        safe_rs = "// SAFETY: valid aligned pointer\nunsafe { ptr.read(); }\n"
        self.assertEqual(analyze_rust_content(safe_rs, "main.rs"), [])

    def test_cpp_all_5_rules_and_safe(self) -> None:
        cpp = "\n".join([
            "strcpy(dst, src);",
            "system(cmd);",
            "printf(user_input);",
            "int r = rand();",
            "void* p = malloc(16);",
        ])
        ids = {i["ruleId"].split(":")[1] for i in analyze_cpp_content(cpp, "main.c")}
        self.assertEqual(ids, {"CPP-SEC-001", "CPP-SEC-002", "CPP-SEC-003", "CPP-SEC-004", "CPP-REL-001"})
        safe_cpp = 'printf("%s", msg);\nvoid* p = malloc(16); free(p);\n'
        self.assertEqual(analyze_cpp_content(safe_cpp, "main.c"), [])


if __name__ == "__main__":
    unittest.main()
