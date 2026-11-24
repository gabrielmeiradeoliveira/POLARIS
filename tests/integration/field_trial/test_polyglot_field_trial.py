from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "legacy"))
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "terraform"))
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "html"))
sys.path.insert(0, str(REPO_ROOT / "analyzers" / "php"))

from polaris_scanner.cache import is_binary_bytes, is_minified_asset
from polaris_scanner.safe_reader import classify_file_scope, read_text_safe
from polaris_legacy_analyzer import analyze_legacy_content
from polaris_tf_analyzer import analyze_tf_content
from polaris_html_analyzer import analyze_frontend_content
from polaris_php_analyzer import analyze_php_content


def _scan_dir(root: Path) -> dict:
    t0 = time.perf_counter()
    errors = 0
    skipped = 0
    issues: list[dict] = []
    for p in root.rglob("*"):
        if not p.is_file() or any(part in {".git", ".venv", "__pycache__", "node_modules"} for part in p.parts):
            continue
        raw = p.read_bytes()
        if is_binary_bytes(raw) or is_minified_asset(p, raw):
            skipped += 1
            continue
        text, err = read_text_safe(p)
        if err or text is None:
            errors += 1
            continue
        rel = p.relative_to(root).as_posix()
        scope = classify_file_scope(rel)
        ext = p.suffix.lower()
        found: list[dict] = []
        if ext == ".tf":
            found = analyze_tf_content(text, rel)
        elif ext in (".tsx", ".jsx", ".html", ".htm"):
            found = analyze_frontend_content(text, rel)
        elif ext == ".php":
            found = analyze_php_content(text, rel)
        else:
            found = analyze_legacy_content(text, rel)
        for item in found:
            item["scope"] = scope
            issues.append(item)
    return {
        "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2),
        "errors": errors,
        "skipped": skipped,
        "issues": issues,
    }


class TestPolyglotFieldTrial(unittest.TestCase):
    def test_ascii_safe_hex_corpus_and_dogfooding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "legacy_cp1252.py").write_bytes(
                bytes.fromhex("2320436f6e666967757261e7e36f206c65676164610a70617373776f7264203d2022736563726574313233220a")
            )
            (root / "fake_binary.cs").write_bytes(bytes.fromhex("7f454c46020101000000000000000000"))
            (root / "minified_bundle.js").write_text("var a=1;" + ("b();" * 16667), encoding="utf-8")
            (root / "legacy_vuln.cs").write_text("var bf = new BinaryFormatter();\n", encoding="utf-8")
            (root / "legacy_vuln.php").write_text("<?php $h = md5($password); ?>\n", encoding="utf-8")
            (root / "legacy_vuln.tf").write_text('resource "aws_db_instance" "db" { publicly_accessible = true }\n', encoding="utf-8")
            (root / "App.tsx").write_text("export const X = ({ h }: any) => <div dangerouslySetInnerHTML={{ __html: h }} />;\n", encoding="utf-8")
            (root / "web.config").write_text('<add name="db" connectionString="Server=x;Password=Secret123;" />\n', encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "mock_secrets_test.py").write_text("x = 1\n", encoding="utf-8")

            res = _scan_dir(root)
            self.assertEqual(res["errors"], 0)
            self.assertEqual(res["skipped"], 2)
            self.assertGreaterEqual(len(res["issues"]), 5)

        dogfood = _scan_dir(REPO_ROOT / "src")
        self.assertEqual(dogfood["errors"], 0)


if __name__ == "__main__":
    unittest.main()
