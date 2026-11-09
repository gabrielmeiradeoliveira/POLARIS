"""Security Scanner Protocols, Status Models, and Metadata Contracts (GOAL 53 - Architecture V2).

Defines the formal typed contracts for security domain scanners, execution states,
coverage accounting, and scanner capabilities.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class ScannerExecutionStatus(StrEnum):
    """Execution status for specialized security scanners."""

    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    SKIPPED = "SKIPPED"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


class ScannerReportParseError(Exception):
    """Raised when a security report (SARIF/JSON) contains corrupt or unparsable payload."""

    def __init__(self, message: str, file_path: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.file_path = file_path


class SecurityDomain(StrEnum):
    """Taxonomy of security inspection domains in POLARIS."""

    CONTAINER = "CONTAINER"
    SUPPLY_CHAIN = "SUPPLY_CHAIN"
    SECRETS = "SECRETS"
    IAC = "IAC"
    CODE_INTELLIGENCE = "CODE_INTELLIGENCE"
    IMAGE_VULNERABILITY = "IMAGE_VULNERABILITY"


class ScannerMetadata(BaseModel):
    """Formal declared identity and capabilities of a security scanner."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scanner_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    version: str = "2.0.0"
    domain: SecurityDomain
    supported_file_patterns: list[str] = Field(default_factory=list)
    description: str = ""
    external_dependencies: list[str] = Field(default_factory=list)
    is_optional: bool = False


class ScannerExecutionReport(BaseModel):
    """Audit report for an individual scanner's execution lifecycle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scanner_id: str
    status: ScannerExecutionStatus
    duration_ms: float = 0.0
    files_evaluated: list[str] = Field(default_factory=list)
    effective_coverage_pct: float = 100.0
    error_message: str | None = None
    data_source: str = "local_deterministic"
    data_timestamp: str | None = None


@runtime_checkable
class SecurityScannerV2(Protocol):
    """Port interface for POLARIS Security Architecture V2 scanners."""

    @property
    def metadata(self) -> ScannerMetadata:
        """Declared metadata, domain, and file pattern capabilities."""
        ...

    def is_available(self) -> bool:
        """Check if scanner runtime dependencies and environment prerequisites are met."""
        ...

    def scan_file(self, file_path: str, content: str) -> list[Any]:
        """Scan individual file content and return typed domain findings."""
        ...
