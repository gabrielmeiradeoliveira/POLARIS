from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileCoverage:
    covered_lines: set[int]
    uncovered_lines: set[int]

    @property
    def lines_to_cover(self) -> int:
        return len(self.covered_lines) + len(self.uncovered_lines)

    @property
    def line_coverage(self) -> float:
        total = self.lines_to_cover
        return round((len(self.covered_lines) / total) * 100.0, 2) if total > 0 else 100.0


def parse_coverage_xml(xml_path: Path) -> dict[str, FileCoverage]:
    """Parse Cobertura XML, OpenCover XML, or JaCoCo XML into {file_path: FileCoverage}."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    result: dict[str, FileCoverage] = {}

    def _add(fname: str, line_no: int, covered: bool) -> None:
        fc = result.setdefault(fname, FileCoverage(set(), set()))
        if covered:
            fc.covered_lines.add(line_no)
            fc.uncovered_lines.discard(line_no)
        elif line_no not in fc.covered_lines:
            fc.uncovered_lines.add(line_no)

    if root.tag == "coverage":  # Cobertura
        for cls in root.findall(".//class"):
            fname = cls.attrib.get("filename", "")
            for line in cls.findall("./lines/line"):
                _add(fname, int(line.attrib["number"]), int(line.attrib.get("hits", "0")) > 0)
    elif root.tag == "CoverageSession":  # OpenCover
        files_map = {f.attrib["uid"]: f.attrib["fullPath"] for f in root.findall(".//File") if "uid" in f.attrib}
        for sp in root.findall(".//SequencePoint"):
            fname = files_map.get(sp.attrib.get("fileid", ""), "")
            if fname:
                _add(fname, int(sp.attrib["sl"]), int(sp.attrib.get("vc", "0")) > 0)
    elif root.tag == "report":  # JaCoCo
        for pkg in root.findall("./package"):
            pkg_name = pkg.attrib.get("name", "")
            for sf in pkg.findall("./sourcefile"):
                fname = f"{pkg_name}/{sf.attrib['name']}".lstrip("/")
                for line in sf.findall("./line"):
                    _add(fname, int(line.attrib["nr"]), int(line.attrib.get("ci", "0")) > 0)
    return result


def compute_new_coverage(coverage_map: dict[str, FileCoverage], changed_lines: dict[str, set[int]]) -> float:
    """Compute coverage percentage exclusively over added/modified executable lines."""
    covered = 0
    total = 0
    for path, lines in changed_lines.items():
        fc = coverage_map.get(path)
        if not fc:
            continue
        for ln in lines:
            if ln in fc.covered_lines:
                covered += 1
                total += 1
            elif ln in fc.uncovered_lines:
                total += 1
    return round((covered / total) * 100.0, 2) if total > 0 else 100.0
