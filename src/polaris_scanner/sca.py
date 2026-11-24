from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Dependency:
    ecosystem: str
    name: str
    version: str
    file_path: str
    line: int


@dataclass(frozen=True)
class ScaFinding:
    dependency: Dependency
    vuln_id: str
    severity: str
    fixed_version: str | None
    confidence: str = "HIGH"
    is_kev: bool = False
    epss_score: float = 0.0


def cvss_to_severity(score: float) -> str:
    if score >= 9.0:
        return "BLOCKER"
    if score >= 7.0:
        return "CRITICAL"
    if score >= 4.0:
        return "MAJOR"
    return "MINOR"


def parse_requirements_txt(file_path: str, content: str) -> list[Dependency]:
    deps: list[Dependency] = []
    for line_no, raw in enumerate(content.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)\s*==\s*([^\s;#]+)", line)
        if m:
            deps.append(Dependency("PyPI", m.group(1), m.group(2), file_path, line_no))
    return deps


def parse_package_json(file_path: str, content: str) -> list[Dependency]:
    deps: list[Dependency] = []
    data = json.loads(content)
    for section in ("dependencies", "devDependencies"):
        for name, ver in (data.get(section) or {}).items():
            deps.append(Dependency("npm", name, str(ver).lstrip("^~"), file_path, 1))
    return deps


def scan_dependencies_offline(deps: list[Dependency], offline_db: dict[str, list[dict]]) -> list[ScaFinding]:
    """Match dependencies against an offline OSV-style vulnerability dictionary."""
    findings: list[ScaFinding] = []
    for dep in deps:
        key = f"{dep.ecosystem}:{dep.name}"
        for vuln in offline_db.get(key, []):
            if dep.version in vuln.get("affected_versions", []):
                findings.append(
                    ScaFinding(
                        dependency=dep,
                        vuln_id=vuln["id"],
                        severity=cvss_to_severity(float(vuln.get("cvss", 7.5))),
                        fixed_version=vuln.get("fixed_version"),
                    )
                )
    return findings
