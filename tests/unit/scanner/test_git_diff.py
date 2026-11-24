from __future__ import annotations

import unittest

from polaris_scanner.git_diff import parse_unified_diff

SAMPLE_DIFF = """diff --git a/src/app.py b/src/app.py
index 1111111..2222222 100644
--- a/src/app.py
+++ b/src/app.py
@@ -10,0 +11,3 @@ def foo():
+    x = 1
+    y = 2
+    z = 3
@@ -49 +52 @@ def bar():
-    old()
+    new()
"""


class TestGitDiffResolver(unittest.TestCase):
    def test_parse_unified_diff_lines(self) -> None:
        parsed = parse_unified_diff(SAMPLE_DIFF)
        self.assertEqual(parsed, {"src/app.py": {11, 12, 13, 52}})


if __name__ == "__main__":
    unittest.main()
