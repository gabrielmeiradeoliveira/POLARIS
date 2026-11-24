from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from polaris_scanner.coverage_parser import compute_new_coverage, parse_coverage_xml
from polaris_scanner.cpd import detect_duplicates


class TestCpdAndCoverage(unittest.TestCase):
    def test_cpd_detects_duplicated_block(self) -> None:
        block = "\n".join([f"    value_{i} = compute_item(input_a, {i}) + offset_{i}" for i in range(20)])
        res = detect_duplicates(
            {"a.py": f"def f1():\n{block}\n", "b.py": f"def f2():\n{block}\n"},
            min_lines=10,
            min_tokens=100,
        )
        self.assertGreaterEqual(res.duplicated_blocks, 1)
        self.assertGreater(res.duplicated_lines, 0)
        self.assertGreater(res.duplicated_lines_density, 0.0)

    def test_coverage_cobertura_and_new_coverage(self) -> None:
        xml = """<coverage><packages><package><classes>
        <class filename="src/app.py"><lines>
          <line number="10" hits="1"/>
          <line number="11" hits="0"/>
        </lines></class></classes></package></packages></coverage>"""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cov.xml"
            p.write_text(xml, encoding="utf-8")
            cov = parse_coverage_xml(p)
            self.assertEqual(cov["src/app.py"].line_coverage, 50.0)
            self.assertEqual(compute_new_coverage(cov, {"src/app.py": {10, 11}}), 50.0)


if __name__ == "__main__":
    unittest.main()
