"""Module and Scanner registration with typed contracts for POLARIS analysis."""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from polaris.core.errors import ConfigurationError
from polaris.core.models import BudgetTracker, CandidateFinding
from polaris.git.models import DiffBundle, FileContext
from polaris.providers.base import LLMProvider

logger = logging.getLogger(__name__)


@runtime_checkable
class AnalysisModule(Protocol):
    """Typed contract implemented by every POLARIS analysis module."""

    @property
    def module_id(self) -> str:
        """Stable technical identifier (e.g., 'code_review')."""
        ...

    @property
    def description(self) -> str:
        """Human-readable summary of the module's responsibility."""
        ...

    def analyze(
        self,
        diff_bundle: DiffBundle,
        contexts: dict[str, FileContext],
        provider: LLMProvider,
        tracker: BudgetTracker,
    ) -> list[CandidateFinding]:
        """Execute analysis on the diff and bounded context, returning candidate findings."""
        ...


class ScannerResult(BaseModel):
    """Typed deterministic scanner result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scanner_id: str
    rule_id: str
    file_path: str
    line: int
    title: str
    description: str
    severity: str
    confidence: str = "high"
    remediation: str = ""


@runtime_checkable
class BaseScanner(Protocol):
    """Typed port for deterministic static and configuration security scanners."""

    @property
    def scanner_id(self) -> str:
        """Unique identifier (e.g., 'container_security', 'supply_chain')."""
        ...

    def scan_file(self, file_path: str, content: str) -> list[ScannerResult]:
        """Execute deterministic scan over file content returning typed findings."""
        ...


class ScannerRegistry:
    """Registry managing available deterministic scanners."""

    def __init__(self) -> None:
        self._scanners: dict[str, BaseScanner] = {}

    def register(self, scanner: BaseScanner) -> None:
        sid = scanner.scanner_id.strip()
        if not sid:
            raise ConfigurationError("Scanner identifier cannot be empty.")
        if sid in self._scanners:
            raise ConfigurationError(f"Scanner '{sid}' is already registered.")
        self._scanners[sid] = scanner

    def get(self, scanner_id: str) -> BaseScanner:
        if scanner_id not in self._scanners:
            available = ", ".join(sorted(self._scanners)) or "none"
            raise ConfigurationError(f"Unknown scanner '{scanner_id}'. Available: {available}.")
        return self._scanners[scanner_id]

    def list_scanners(self) -> list[BaseScanner]:
        return [self._scanners[k] for k in sorted(self._scanners)]

    def run_scanners_on_file(self, file_path: str, content: str) -> list[ScannerResult]:
        """Execute all registered scanners in deterministic alphabetical order."""
        results: list[ScannerResult] = []
        from polaris.security.contracts import ScannerReportParseError

        for sid in sorted(self._scanners):
            scanner = self._scanners[sid]
            try:
                results.extend(scanner.scan_file(file_path, content))
            except ScannerReportParseError:
                # Do not swallow corrupt security reports silently; propagate to caller
                raise
            except Exception as exc:
                # Fault isolation: an individual scanner failure does not abort the pipeline
                logger.warning("Scanner %s falhou na análise de arquivo: %s", getattr(scanner, "scanner_id", "unknown"), type(exc).__name__)
                continue
        return results


class ModuleRegistry:
    """Registry managing available POLARIS analysis modules by technical `module_id`."""

    def __init__(self) -> None:
        self._modules: dict[str, AnalysisModule] = {}

    def register(self, module: AnalysisModule) -> None:
        module_id = module.module_id.strip()
        if not module_id:
            raise ConfigurationError("Module technical identifier cannot be empty.")
        if module_id in self._modules:
            raise ConfigurationError(f"Module '{module_id}' is already registered.")
        self._modules[module_id] = module

    def get(self, module_id: str) -> AnalysisModule:
        if module_id not in self._modules:
            available = ", ".join(sorted(self._modules)) or "none"
            raise ConfigurationError(f"Unknown analysis module '{module_id}'. Registered modules: {available}.")
        return self._modules[module_id]

    def list_modules(self) -> list[AnalysisModule]:
        return [self._modules[k] for k in sorted(self._modules)]


def build_default_scanner_registry() -> ScannerRegistry:
    """Build and populate a ScannerRegistry with default deterministic security scanners."""
    from polaris.container.scanner import ContainerSecurityScanner
    from polaris.security.docker_scout import DockerScoutAdapter
    from polaris.security.iac import IaCSecurityScanner
    from polaris.security.sbom import SBOMParser
    from polaris.security.secrets import SecretDetectionScanner
    from polaris.supply_chain.scanner import DiscoveredDependency, SupplyChainSecurityScanner

    registry = ScannerRegistry()

    class _ContainerScannerAdapter:
        @property
        def scanner_id(self) -> str:
            return "container_security"

        def scan_file(self, file_path: str, content: str) -> list[ScannerResult]:
            norm = file_path.replace("\\", "/").lower()
            name = norm.split("/")[-1]
            if not (name == "dockerfile" or name.startswith("dockerfile.") or name.endswith(".dockerfile")):
                return []
            findings = ContainerSecurityScanner.analyze_dockerfile(content, file_path=file_path)
            return [
                ScannerResult(
                    scanner_id=self.scanner_id,
                    rule_id=f.defect_type.value,
                    file_path=file_path,
                    line=f.line,
                    title=f.defect_type.value.replace("_", " ").title(),
                    description=f.instruction,
                    severity=f.severity,
                    confidence="high",
                    remediation=f.remediation,
                )
                for f in findings
            ]

    class _SupplyChainScannerAdapter:
        def __init__(self) -> None:
            self._scanner = SupplyChainSecurityScanner()

        @property
        def scanner_id(self) -> str:
            return "supply_chain"

        def scan_file(self, file_path: str, content: str) -> list[ScannerResult]:
            norm = file_path.replace("\\", "/").lower()
            name = norm.split("/")[-1]
            manifest_names = {"requirements.txt", "pyproject.toml", "package.json", "package-lock.json"}
            results: list[ScannerResult] = []

            # Check if standard manifest
            if name in manifest_names or name.endswith(".txt"):
                deps = SupplyChainSecurityScanner.parse_manifest(file_path, content)
                matches = self._scanner.match_vulnerabilities(deps)
                for m in matches:
                    if m.status.value in ("CONFIRMED_AFFECTED", "POSSIBLY_AFFECTED"):
                        cve = m.advisory.cve_id or m.advisory.advisory_id
                        results.append(
                            ScannerResult(
                                scanner_id=self.scanner_id,
                                rule_id=cve,
                                file_path=file_path,
                                line=1,
                                title=f"Vulnerable dependency '{m.dependency.name}' ({cve})",
                                description=m.evidence,
                                severity=m.advisory.severity,
                                confidence="high",
                                remediation=f"Upgrade '{m.dependency.name}' to {m.advisory.fixed_version or 'latest'}.",
                            )
                        )

            # Check if SBOM artifact (CycloneDX or SPDX JSON)
            if norm.endswith(".json") and ("sbom" in norm or "cyclonedx" in norm or "spdx" in norm):
                sbom_rep = SBOMParser.parse_sbom(content, file_path=file_path)
                if sbom_rep.components:
                    deps = [
                        DiscoveredDependency.create(c.name, c.ecosystem, file_path, c.version, purl=c.purl or "")
                        for c in sbom_rep.components
                    ]
                    matches = self._scanner.match_vulnerabilities(deps)
                    for m in matches:
                        if m.status.value in ("CONFIRMED_AFFECTED", "POSSIBLY_AFFECTED"):
                            cve = m.advisory.cve_id or m.advisory.advisory_id
                            results.append(
                                ScannerResult(
                                    scanner_id=self.scanner_id,
                                    rule_id=cve,
                                    file_path=file_path,
                                    line=1,
                                    title=f"Vulnerable SBOM component '{m.dependency.name}' ({cve})",
                                    description=f"[SBOM Ingested] {m.evidence}",
                                    severity=m.advisory.severity,
                                    confidence="high",
                                    remediation=f"Upgrade SBOM component '{m.dependency.name}' to {m.advisory.fixed_version or 'latest'}.",
                                )
                            )
            return results

    class _SecretScannerAdapter:
        def __init__(self) -> None:
            self._scanner = SecretDetectionScanner()

        @property
        def scanner_id(self) -> str:
            return "secret_detection"

        def scan_file(self, file_path: str, content: str) -> list[ScannerResult]:
            findings = self._scanner.scan_file(file_path, content)
            return [
                ScannerResult(
                    scanner_id=self.scanner_id,
                    rule_id=f.rule_or_cve,
                    file_path=file_path,
                    line=f.line,
                    title=f.title,
                    description=f.evidence_text,
                    severity=f.severity,
                    confidence=f.confidence.lower(),
                    remediation=f.remediation_hint,
                )
                for f in findings
            ]

    class _IaCScannerAdapter:
        def __init__(self) -> None:
            self._scanner = IaCSecurityScanner()

        @property
        def scanner_id(self) -> str:
            return "iac_security"

        def scan_file(self, file_path: str, content: str) -> list[ScannerResult]:
            findings = self._scanner.scan_file(file_path, content)
            return [
                ScannerResult(
                    scanner_id=self.scanner_id,
                    rule_id=f.rule_or_cve,
                    file_path=file_path,
                    line=f.line,
                    title=f.title,
                    description=f.evidence_text,
                    severity=f.severity,
                    confidence=f.confidence.lower(),
                    remediation=f.remediation_hint,
                )
                for f in findings
            ]

    class _DockerScoutScannerAdapter:
        def __init__(self) -> None:
            self._adapter = DockerScoutAdapter()

        @property
        def scanner_id(self) -> str:
            return "docker_scout"

        def scan_file(self, file_path: str, content: str) -> list[ScannerResult]:
            findings = self._adapter.scan_file(file_path, content)
            return [
                ScannerResult(
                    scanner_id=self.scanner_id,
                    rule_id=f.rule_or_cve,
                    file_path=file_path,
                    line=f.line,
                    title=f.title,
                    description=f.evidence_text,
                    severity=f.severity,
                    confidence=f.confidence.lower(),
                    remediation=f.remediation_hint,
                )
                for f in findings
            ]

    registry.register(_ContainerScannerAdapter())
    registry.register(_SupplyChainScannerAdapter())
    registry.register(_SecretScannerAdapter())
    registry.register(_IaCScannerAdapter())
    registry.register(_DockerScoutScannerAdapter())
    return registry
