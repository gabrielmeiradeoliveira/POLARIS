"""Behavioral Delta 3.0 (Consolidated into polaris.context.behavioral_delta).

Retained as a backwards-compatible entrypoint. All logic is now consolidated in
`polaris.context.behavioral_delta.BehavioralDelta3`.
"""

from __future__ import annotations

from polaris.context.behavioral_delta import (
    BehavioralChange,
    BehavioralDelta3,
    SemanticChangeCategory,
)

__all__ = [
    "BehavioralChange",
    "BehavioralDelta3",
    "SemanticChangeCategory",
]
