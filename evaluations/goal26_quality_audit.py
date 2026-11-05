"""Read-only inventory and comparability guards for GOAL 26 Phase 2."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Campaign:
    path: Path
    corpus: str | None
    provider: str | None
    model: str | None
    configuration: str
    status: str | None
    tp: int
    fp: int
    fn: int

    @property
    def comparable_key(self) -> tuple[str | None, str | None, str | None, str]:
        return self.corpus, self.provider, self.model, self.configuration


def _campaign(path: Path, payload: dict[str, Any]) -> Campaign | None:
    summary = payload.get("summary", payload)
    if not isinstance(summary, dict) or not {"true_positives", "false_positives", "false_negatives"} <= summary.keys():
        return None
    config = payload.get("configuration", payload.get("run_metadata", {}))
    if not isinstance(config, dict):
        config = {}
    corpus = payload.get("corpus_sha256") or config.get("corpus_sha256") or config.get("fixtures")
    provider = payload.get("provider") or config.get("provider")
    model = payload.get("model") or config.get("model")
    stable_config = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return Campaign(
        path=path,
        corpus=str(corpus) if corpus is not None else None,
        provider=str(provider) if provider is not None else None,
        model=str(model) if model is not None else None,
        configuration=stable_config,
        status=summary.get("status"),
        tp=int(summary["true_positives"]),
        fp=int(summary["false_positives"]),
        fn=int(summary["false_negatives"]),
    )


def inventory(root: Path) -> list[Campaign]:
    campaigns: list[Campaign] = []
    for path in sorted(root.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            campaign = _campaign(path, payload)
            if campaign:
                campaigns.append(campaign)
    return campaigns


def comparable_groups(campaigns: list[Campaign]) -> dict[tuple[str | None, str | None, str | None, str], list[Campaign]]:
    groups: dict[tuple[str | None, str | None, str | None, str], list[Campaign]] = defaultdict(list)
    for campaign in campaigns:
        groups[campaign.comparable_key].append(campaign)
    return dict(groups)


def aggregate(campaigns: list[Campaign]) -> tuple[int, int, int]:
    """Aggregate only a caller-vetted, exactly comparable group."""
    if len({campaign.comparable_key for campaign in campaigns}) > 1:
        raise ValueError("Cannot aggregate incompatible campaigns")
    return sum(c.tp for c in campaigns), sum(c.fp for c in campaigns), sum(c.fn for c in campaigns)
