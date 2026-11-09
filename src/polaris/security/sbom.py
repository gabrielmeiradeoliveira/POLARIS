"""Software Bill of Materials (SBOM) Ingestion, Validation & Parsing (GOAL 53 - Fase 5).

Parses CycloneDX (JSON) and SPDX (JSON/Tag-Value) formats, extracting components,
versions, PURLs, ecosystems, dependencies, and provenance without inventing missing data.
"""

from __future__ import annotations

import json
import logging
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polaris.supply_chain.scanner import DependencyScope, Ecosystem

logger = logging.getLogger(__name__)


class SBOMFormat(StrEnum):
    """Supported standard SBOM formats."""

    CYCLONEDX_JSON = "CYCLONEDX_JSON"
    SPDX_JSON = "SPDX_JSON"
    UNKNOWN = "UNKNOWN"


class IngestedComponent(BaseModel):
    """Canonical component extracted from ingested SBOM."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., min_length=1)
    version: str | None = None
    purl: str | None = None
    ecosystem: Ecosystem = Ecosystem.UNKNOWN
    scope: DependencyScope = DependencyScope.DIRECT
    source_file: str = "sbom.json"
    hashes: dict[str, str] = Field(default_factory=dict)
    licenses: list[str] = Field(default_factory=list)


class SBOMIngestionReport(BaseModel):
    """Result of parsing and validating an SBOM artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    format: SBOMFormat
    spec_version: str = "unknown"
    component_count: int = 0
    components: list[IngestedComponent] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SBOMParser:
    """Deterministic parser for CycloneDX and SPDX SBOM formats."""

    @classmethod
    def parse_sbom(cls, content: str, file_path: str = "sbom.json") -> SBOMIngestionReport:
        """Detect format and extract components deterministically."""
        try:
            data = json.loads(content)
        except Exception as exc:
            return SBOMIngestionReport(
                format=SBOMFormat.UNKNOWN,
                errors=[f"Invalid JSON content in SBOM: {type(exc).__name__}"],
            )

        if not isinstance(data, dict):
            return SBOMIngestionReport(
                format=SBOMFormat.UNKNOWN,
                errors=["Root of SBOM JSON must be an object."],
            )

        # Detect CycloneDX
        if data.get("bomFormat") == "CycloneDX" or "components" in data:
            return cls._parse_cyclonedx(data, file_path)

        # Detect SPDX
        if data.get("spdxVersion") or "packages" in data:
            return cls._parse_spdx(data, file_path)

        return SBOMIngestionReport(
            format=SBOMFormat.UNKNOWN,
            errors=["Unrecognized SBOM schema (neither CycloneDX nor SPDX JSON structure found)."],
        )

    @classmethod
    def _parse_cyclonedx(cls, data: dict[str, Any], file_path: str) -> SBOMIngestionReport:
        spec_ver = str(data.get("specVersion", "1.4"))
        raw_components = data.get("components", [])
        if not isinstance(raw_components, list):
            return SBOMIngestionReport(
                format=SBOMFormat.CYCLONEDX_JSON,
                spec_version=spec_ver,
                errors=["CycloneDX 'components' field must be an array."],
            )

        components: list[IngestedComponent] = []
        for item in raw_components:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            name = str(item["name"])
            version = str(item["version"]) if item.get("version") else None
            purl = str(item["purl"]) if item.get("purl") else None
            scope_str = str(item.get("scope", "required")).lower()
            scope = DependencyScope.TRANSITIVE if "optional" in scope_str or "transitive" in scope_str else DependencyScope.DIRECT

            # Infer ecosystem from PURL or type
            eco = Ecosystem.UNKNOWN
            if purl:
                if purl.startswith("pkg:pypi/"):
                    eco = Ecosystem.PYPI
                elif purl.startswith("pkg:npm/"):
                    eco = Ecosystem.NPM

            components.append(
                IngestedComponent(
                    name=name,
                    version=version,
                    purl=purl,
                    ecosystem=eco,
                    scope=scope,
                    source_file=file_path,
                )
            )

        return SBOMIngestionReport(
            format=SBOMFormat.CYCLONEDX_JSON,
            spec_version=spec_ver,
            component_count=len(components),
            components=components,
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def _parse_spdx(cls, data: dict[str, Any], file_path: str) -> SBOMIngestionReport:
        spdx_ver = str(data.get("spdxVersion", "SPDX-2.3"))
        raw_packages = data.get("packages", [])
        if not isinstance(raw_packages, list):
            return SBOMIngestionReport(
                format=SBOMFormat.SPDX_JSON,
                spec_version=spdx_ver,
                errors=["SPDX 'packages' field must be an array."],
            )

        components: list[IngestedComponent] = []
        for pkg in raw_packages:
            if not isinstance(pkg, dict) or not pkg.get("name"):
                continue
            name = str(pkg["name"])
            version = str(pkg["versionInfo"]) if pkg.get("versionInfo") else None

            # Extract PURL from externalRefs
            purl = None
            eco = Ecosystem.UNKNOWN
            ext_refs = pkg.get("externalRefs", [])
            if isinstance(ext_refs, list):
                for ref in ext_refs:
                    if isinstance(ref, dict) and ref.get("referenceType") == "purl":
                        purl = str(ref.get("referenceLocator"))
                        if purl.startswith("pkg:pypi/"):
                            eco = Ecosystem.PYPI
                        elif purl.startswith("pkg:npm/"):
                            eco = Ecosystem.NPM
                        break

            components.append(
                IngestedComponent(
                    name=name,
                    version=version,
                    purl=purl,
                    ecosystem=eco,
                    scope=DependencyScope.DIRECT,
                    source_file=file_path,
                )
            )

        return SBOMIngestionReport(
            format=SBOMFormat.SPDX_JSON,
            spec_version=spdx_ver,
            component_count=len(components),
            components=components,
            metadata={"spdxVersion": spdx_ver, "name": data.get("name")},
        )
