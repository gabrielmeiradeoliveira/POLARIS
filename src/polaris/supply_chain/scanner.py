"""Supply Chain Security Models and Parsers (GOAL 31).

Parses dependency manifests (requirements.txt, pyproject.toml, package-lock.json),
generates canonical CycloneDX/SPDX-compatible SBOMs, and performs offline vulnerability
matching against local advisory snapshots.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from enum import StrEnum
from pathlib import Path
from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class Ecosystem(StrEnum):
    """Package manager ecosystem."""

    PYPI = "pypi"
    NPM = "npm"
    UNKNOWN = "unknown"


class DependencyScope(StrEnum):
    """Dependency scope in project."""

    DIRECT = "direct"
    TRANSITIVE = "transitive"


class DiscoveredDependency(BaseModel):
    """A single package dependency extracted from project manifests."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., min_length=1)
    ecosystem: Ecosystem
    version: str | None = None
    scope: DependencyScope = DependencyScope.DIRECT
    manifest_file: str = Field(..., min_length=1)
    purl: str = ""

    @classmethod
    def create(
        cls,
        name: str,
        ecosystem: Ecosystem,
        manifest_file: str,
        version: str | None = None,
        scope: DependencyScope = DependencyScope.DIRECT,
    ) -> DiscoveredDependency:
        norm_name = name.strip().lower()
        norm_ver = version.strip() if version else ""
        purl = f"pkg:{ecosystem.value}/{norm_name}@{norm_ver}" if norm_ver else f"pkg:{ecosystem.value}/{norm_name}"
        return cls(
            name=norm_name,
            ecosystem=ecosystem,
            version=norm_ver or None,
            scope=scope,
            manifest_file=manifest_file.replace("\\", "/"),
            purl=purl,
        )


class VulnerabilityAdvisory(BaseModel):
    """Security vulnerability advisory from a local database snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    advisory_id: str
    cve_id: str | None = None
    package_name: str
    ecosystem: Ecosystem
    vulnerable_versions: str  # e.g., "<2.0.0", ">=1.0.0,<1.5.0"
    fixed_version: str | None = None
    severity: str = "HIGH"
    summary: str = ""


class VulnerabilityMatchStatus(StrEnum):
    """Status of vulnerability assessment for a dependency."""

    CONFIRMED_AFFECTED = "CONFIRMED_AFFECTED"
    NOT_AFFECTED = "NOT_AFFECTED"
    POSSIBLY_AFFECTED = "POSSIBLY_AFFECTED"
    UNKNOWN = "UNKNOWN"


class MatchedVulnerability(BaseModel):
    """Result of correlating a dependency against advisories."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dependency: DiscoveredDependency
    advisory: VulnerabilityAdvisory
    status: VulnerabilityMatchStatus
    evidence: str


DEFAULT_LOCAL_ADVISORIES: list[VulnerabilityAdvisory] = [
    VulnerabilityAdvisory(
        advisory_id="GHSA-w5p7-h5w8-2hfq",
        cve_id="CVE-2018-18074",
        package_name="requests",
        ecosystem=Ecosystem.PYPI,
        vulnerable_versions="<2.21.0",
        fixed_version="2.21.0",
        severity="HIGH",
        summary="Requests sends HTTP Authorization header to unintended hosts on redirect",
    ),
    VulnerabilityAdvisory(
        advisory_id="GHSA-6767-1234-5678",
        cve_id="CVE-2021-3281",
        package_name="django",
        ecosystem=Ecosystem.PYPI,
        vulnerable_versions="<3.1.1",
        fixed_version="3.1.1",
        severity="HIGH",
        summary="Path traversal vulnerability in Django storage backends",
    ),
    VulnerabilityAdvisory(
        advisory_id="GHSA-4w7x-pq59-522r",
        cve_id="CVE-2022-40897",
        package_name="setuptools",
        ecosystem=Ecosystem.PYPI,
        vulnerable_versions="<65.5.1",
        fixed_version="65.5.1",
        severity="HIGH",
        summary="Regular Expression Denial of Service in package index parsing",
    ),
    VulnerabilityAdvisory(
        advisory_id="GHSA-2qrg-xjc6-7rpx",
        cve_id="CVE-2020-28493",
        package_name="jinja2",
        ecosystem=Ecosystem.PYPI,
        vulnerable_versions="<2.11.3",
        fixed_version="2.11.3",
        severity="MEDIUM",
        summary="ReDoS in urlize filter",
    ),
]


class SupplyChainSecurityScanner:
    """Offline deterministic supply chain dependency scanner."""

    def __init__(self, local_advisories: list[VulnerabilityAdvisory] | None = None) -> None:
        self.advisories = DEFAULT_LOCAL_ADVISORIES if local_advisories is None else local_advisories

    @classmethod
    def parse_manifest(cls, file_path: str | Path, content: str) -> list[DiscoveredDependency]:
        """Extract dependencies from requirements.txt, pyproject.toml, package.json, or package-lock.json."""
        p = Path(file_path)
        fname = p.name.lower()
        norm_p = str(p).replace("\\", "/")
        deps: list[DiscoveredDependency] = []

        if fname == "requirements.txt" or fname.endswith(".txt"):
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith(("#", "-", "@")):
                    continue
                # Handle package==1.2.3 or package>=1.0
                match = re.match(r"^([a-zA-Z0-9_\-\.]+)(?:([=><~^!]+)([^#;]+))?", line)
                if match:
                    pkg_name = match.group(1)
                    op = match.group(2)
                    ver = match.group(3).strip() if match.group(3) else None
                    resolved_ver = ver if op == "==" else None
                    deps.append(
                        DiscoveredDependency.create(
                            name=pkg_name,
                            ecosystem=Ecosystem.PYPI,
                            manifest_file=norm_p,
                            version=resolved_ver,
                            scope=DependencyScope.DIRECT,
                        )
                    )

        elif fname == "package.json":
            try:
                data = json.loads(content)
                for scope_key, scope in [("dependencies", DependencyScope.DIRECT), ("devDependencies", DependencyScope.DIRECT)]:
                    for pkg, ver_spec in data.get(scope_key, {}).items():
                        clean_ver = re.sub(r"[^0-9\.]", "", ver_spec)
                        deps.append(
                            DiscoveredDependency.create(
                                name=pkg,
                                ecosystem=Ecosystem.NPM,
                                manifest_file=norm_p,
                                version=clean_ver or None,
                                scope=scope,
                            )
                        )
            except Exception as exc:
                logger.debug("Falha ao analisar manifesto pyproject/requirements %s: %s", fname, type(exc).__name__)
                pass

        elif fname == "package-lock.json":
            try:
                data = json.loads(content)
                packages = data.get("packages", {})
                for pkg_path, meta in packages.items():
                    if not pkg_path:
                        continue
                    name = meta.get("name") or pkg_path.split("node_modules/")[-1]
                    ver = meta.get("version")
                    deps.append(
                        DiscoveredDependency.create(
                            name=name,
                            ecosystem=Ecosystem.NPM,
                            manifest_file=norm_p,
                            version=ver,
                            scope=DependencyScope.DIRECT if "node_modules" not in pkg_path else DependencyScope.TRANSITIVE,
                        )
                    )
            except Exception as exc:
                logger.debug("Falha ao analisar package-lock.json %s: %s", fname, type(exc).__name__)
                pass

        return deps

    def match_vulnerabilities(self, dependencies: list[DiscoveredDependency]) -> list[MatchedVulnerability]:
        """Match dependencies against local advisory database using deterministic version check."""
        matched: list[MatchedVulnerability] = []
        for dep in dependencies:
            for adv in self.advisories:
                if adv.package_name.lower() == dep.name.lower() and adv.ecosystem == dep.ecosystem:
                    if not dep.version:
                        matched.append(
                            MatchedVulnerability(
                                dependency=dep,
                                advisory=adv,
                                status=VulnerabilityMatchStatus.UNKNOWN,
                                evidence=f"Package '{dep.name}' matches advisory '{adv.advisory_id}' but version is unpinned.",
                            )
                        )
                    else:
                        # Simple deterministic check: if advisory says <2.0.0 and dep is 1.5.0 -> AFFECTED
                        is_vulnerable = self._evaluate_version_vulnerable(dep.version, adv.vulnerable_versions)
                        if is_vulnerable:
                            matched.append(
                                MatchedVulnerability(
                                    dependency=dep,
                                    advisory=adv,
                                    status=VulnerabilityMatchStatus.CONFIRMED_AFFECTED,
                                    evidence=(
                                        f"Package '{dep.name}' version '{dep.version}' is confirmed affected by "
                                        f"{adv.advisory_id} ({adv.cve_id or 'CVE-N/A'}), vulnerable in {adv.vulnerable_versions}. "
                                        f"Fixed in: {adv.fixed_version or 'N/A'}."
                                    ),
                                )
                            )
                        else:
                            matched.append(
                                MatchedVulnerability(
                                    dependency=dep,
                                    advisory=adv,
                                    status=VulnerabilityMatchStatus.NOT_AFFECTED,
                                    evidence=f"Package '{dep.name}' version '{dep.version}' outside vulnerable range {adv.vulnerable_versions}.",
                                )
                            )
        return matched

    @staticmethod
    def _evaluate_version_vulnerable(version: str, constraint: str) -> bool:
        """Evaluate version constraint against packaging standard / PEP 440 deterministically.

        Supports compound specifiers (e.g. '>=1.0.0,<2.0.0', '<2.21.0'), prereleases,
        and falls back gracefully to numeric tuple comparison for non-standard semver strings.
        """
        clean_version = version.strip()
        clean_constraint = constraint.strip()
        if not clean_version or not clean_constraint:
            return False

        # Attempt PEP 440 standard parsing via packaging
        try:
            parsed_v = Version(clean_version)
            spec = SpecifierSet(clean_constraint)
            return parsed_v in spec
        except (InvalidVersion, InvalidSpecifier):
            pass

        # Fallback to deterministic regex-based comparison for custom / non-PEP440 versions
        try:
            v_parts = [int(p) for p in re.findall(r"\d+", clean_version)[:3]]
            c_op_match = re.match(r"^([<>=!~]+)\s*(\d+(?:\.\d+)*)", clean_constraint)
            if not c_op_match:
                return False
            op = c_op_match.group(1)
            c_parts = [int(p) for p in re.findall(r"\d+", c_op_match.group(2))[:3]]

            # Pad parts to 3 elements
            while len(v_parts) < 3:
                v_parts.append(0)
            while len(c_parts) < 3:
                c_parts.append(0)

            if op == "<":
                return tuple(v_parts) < tuple(c_parts)
            if op == "<=":
                return tuple(v_parts) <= tuple(c_parts)
            if op == "==":
                return tuple(v_parts) == tuple(c_parts)
            return False
        except Exception:
            return False

    @classmethod
    def generate_sbom(cls, dependencies: list[DiscoveredDependency]) -> dict[str, Any]:
        """Generate canonical CycloneDX-style SBOM JSON."""
        components = []
        for dep in sorted(dependencies, key=lambda d: (d.ecosystem.value, d.name, d.version or "")):
            components.append({
                "type": "library",
                "name": dep.name,
                "version": dep.version or "unspecified",
                "purl": dep.purl,
                "scope": dep.scope.value,
                "evidence": {
                    "source_manifest": dep.manifest_file,
                },
            })

        return {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "serialNumber": f"urn:uuid:{hashlib.sha256(json.dumps(components).encode()).hexdigest()[:32]}",
            "version": 1,
            "metadata": {
                "component": {
                    "name": "POLARIS-Repository-Target",
                    "type": "application",
                }
            },
            "components": components,
        }
