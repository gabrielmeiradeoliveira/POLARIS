import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "analyzers" / "python"))

from project_index import ProjectIndex  # noqa: E402


class TestProjectIndex(unittest.TestCase):
    def test_index_and_cache_key_invalidation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "helper.py").write_text("def sanitize(x):\n    return x\n", encoding="utf-8")
            (root / "app.py").write_text("import helper\ndef run():\n    return helper.sanitize('a')\n", encoding="utf-8")

            idx = ProjectIndex(root)
            idx.index_directory()
            self.assertIn("app.py", idx.modules)
            self.assertIn("helper.py", idx.modules)
            self.assertEqual(idx.modules["app.py"].functions, ["run"])
            self.assertEqual(idx.modules["app.py"].imports, ["helper"])

            key1 = idx.compute_cache_key("app.py")
            # Modify dependency helper.py -> cache key for app.py must change
            (root / "helper.py").write_text("def sanitize(x):\n    return x.strip()\n", encoding="utf-8")
            idx.index_file(root / "helper.py")
            key2 = idx.compute_cache_key("app.py")
            self.assertNotEqual(key1, key2)


if __name__ == "__main__":
    unittest.main()
