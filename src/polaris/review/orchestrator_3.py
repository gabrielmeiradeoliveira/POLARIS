"""Hybrid Orchestrator 3.0 (Consolidated into polaris.review.engine).

Retained as a backwards-compatible entrypoint. All logic is now consolidated in
`polaris.review.engine.HybridReviewOrchestrator`.
"""

from __future__ import annotations

from polaris.review.engine import HybridOrchestrator3, HybridReviewOrchestrator

__all__ = ["HybridOrchestrator3", "HybridReviewOrchestrator"]
