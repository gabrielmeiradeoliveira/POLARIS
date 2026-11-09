"""Security Advisory Providers, Caching & Offline Snapshots (GOAL 53 - Fase 6 & 7).

Provides an extensible interface for vulnerability advisories (OSV, GHSA, local snapshots)
with transparent provenance, offline fallback, cache timestamps, and zero unauthorized external calls.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from polaris.supply_chain.scanner import DEFAULT_LOCAL_ADVISORIES, Ecosystem, VulnerabilityAdvisory

logger = logging.getLogger(__name__)


class AdvisoryProvenance(BaseModel):
    """Metadata regarding where and when vulnerability advisories were acquired."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str
    source_name: str
    is_offline_snapshot: bool = True
    snapshot_version: str = "2026.11"
    last_synced: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    advisories_count: int = 0
    disclaimer: str = "DEFAULT_LOCAL_ADVISORIES is a curated offline snapshot and does not represent an exhaustive or live CVE database."


@runtime_checkable
class AdvisoryProvider(Protocol):
    """Port for vulnerability advisory data sources."""

    @property
    def source_id(self) -> str:
        ...

    def get_provenance(self) -> AdvisoryProvenance:
        ...

    def lookup_advisories(self, package_name: str, ecosystem: Ecosystem) -> list[VulnerabilityAdvisory]:
        ...


class LocalSnapshotAdvisoryProvider(AdvisoryProvider):
    """Default deterministic offline advisory provider backed by local curated snapshots."""

    def __init__(self, advisories: list[VulnerabilityAdvisory] | None = None) -> None:
        self._advisories = advisories or list(DEFAULT_LOCAL_ADVISORIES)
        self._index: dict[tuple[str, str], list[VulnerabilityAdvisory]] = {}
        for adv in self._advisories:
            key = (adv.package_name.lower(), adv.ecosystem.value.lower())
            self._index.setdefault(key, []).append(adv)

    @property
    def source_id(self) -> str:
        return "local_curated_snapshot"

    def get_provenance(self) -> AdvisoryProvenance:
        return AdvisoryProvenance(
            source_id=self.source_id,
            source_name="Polaris Local Advisory Database",
            is_offline_snapshot=True,
            snapshot_version="2026.11",
            advisories_count=len(self._advisories),
            disclaimer=(
                "Offline curated advisory snapshot. Live external network lookups (OSV/GHSA) "
                "require explicit opt-in policy flag and authorization."
            ),
        )

    def lookup_advisories(self, package_name: str, ecosystem: Ecosystem) -> list[VulnerabilityAdvisory]:
        key = (package_name.strip().lower(), ecosystem.value.lower())
        return self._index.get(key, [])
