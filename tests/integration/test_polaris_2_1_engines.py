from __future__ import annotations

import ast
import importlib.util
import sys
import unittest
from pathlib import Path

from polaris_scanner.incremental_cache import IncrementalCache
from polaris_scanner.project_manifest import discover_project_manifest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestPolaris21Engines(unittest.TestCase):
    def test_project_manifest_and_incremental_cache(self) -> None:
        manifest = discover_project_manifest(ROOT / "src", "polaris-self", "anl-21", mode="PROJECT")
        self.assertGreater(len(manifest.source_files), 5)
        self.assertTrue(all(len(h) == 64 for h in manifest.file_hashes.values()))

        cache = IncrementalCache("2.1.0", "prof-hash-1")
        cache.put("a.py", "h1", [{"ruleId": "PY-SYN-001"}])
        self.assertEqual(cache.get("a.py", "h1"), [{"ruleId": "PY-SYN-001"}])
        self.assertIsNone(cache.get("a.py", "h2"))

    def test_python_taint_engine_vulnerable_vs_sanitized(self) -> None:
        taint_mod = _load("polaris_py_taint", ROOT / "analyzers" / "python" / "taint_engine.py")
        vuln_code = (
            "def handler(request, cursor):\n"
            "    uid = request.args.get('id')\n"
            "    q = f'SELECT * FROM users WHERE id = {uid}'\n"
            "    cursor.execute(q)\n"
        )
        findings = taint_mod.analyze_python_taint(ast.parse(vuln_code))
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].cwe, "CWE-89")
        self.assertEqual(findings[0].flow_steps[0]["kind"], "SOURCE")
        self.assertEqual(findings[0].flow_steps[-1]["kind"], "SINK")

        safe_code = (
            "def handler_safe(request, cursor):\n"
            "    uid = int(request.args.get('id'))\n"
            "    q = f'SELECT * FROM users WHERE id = {uid}'\n"
            "    cursor.execute(q)\n"
        )
        self.assertEqual(len(taint_mod.analyze_python_taint(ast.parse(safe_code))), 0)

    def test_sql_semantic_schema_and_lineage(self) -> None:
        sql_sem = _load("polaris_sql_sem", ROOT / "analyzers" / "sql" / "semantic_engine.py")
        schema = {"users": ["id", "name", "email"]}
        res = sql_sem.resolve_sql_semantics("SELECT u.id, u.missing_col FROM users u", schema, dialect="postgres")
        self.assertEqual(res["aliases"]["u"], "users")
        self.assertIn("u.missing_col", res["unknown_columns"])
        self.assertEqual(res["lineage"], [{"column": "id", "source_table": "users"}])


if __name__ == "__main__":
    unittest.main()
