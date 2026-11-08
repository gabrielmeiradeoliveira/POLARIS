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
        for sid in sorted(self._scanners):
            scanner = self._scanners[sid]
            try:
                results.extend(scanner.scan_file(file_path, content))
            except Exception as exc:
                # Fault isolation: an individual scanner failure does not abort the pipeline
                logger.warning("Scanner %s falhou na análise de arquivo: %s", scanner.name, type(exc).__name__)
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
