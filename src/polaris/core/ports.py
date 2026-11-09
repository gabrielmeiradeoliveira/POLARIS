"""Clean Architecture Port definitions for POLARIS.

Defines the stable abstractions (Ports) decoupling core domain and use-case
workflows from concrete external adapters, runners, and storage mechanisms.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from polaris.core.models import BudgetTracker, CandidateFinding
from polaris.core.registry import ScannerResult
from polaris.git.models import DiffBundle, FileContext
from polaris.providers.base import LLMProvider


@runtime_checkable
class CodeReviewPort(Protocol):
    """Port for code change review engines."""

    def review_changes(
        self,
        diff_bundle: DiffBundle,
        contexts: dict[str, FileContext],
        provider: LLMProvider,
        tracker: BudgetTracker,
    ) -> list[CandidateFinding]:
        """Execute review logic across diff bundle and contextual sources."""
        ...


@runtime_checkable
class SecurityScannerPort(Protocol):
    """Port for deterministic file and configuration vulnerability scanners."""

    @property
    def scanner_id(self) -> str:
        """Technical identifier."""
        ...

    def scan_file(self, file_path: str, content: str) -> list[ScannerResult]:
        """Execute scan and return structured findings."""
        ...


@runtime_checkable
class EvidenceStoragePort(Protocol):
    """Port for persisting and retrieving unified evidence."""

    def record_evidence(self, item: dict[str, object]) -> str:
        """Persist an evidence entry and return its ID."""
        ...
