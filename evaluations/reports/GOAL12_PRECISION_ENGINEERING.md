# GOAL 12 — Precision Engineering

## State and audit

The Finding Intelligence Engine already enforces repository-relative paths, changed-line overlap, bounds, evidence grounding, style-noise rejection, deterministic IDs, and deduplication. Existing diagnostics classify unsupported evidence, unsafe paths, missing files, unchanged files, unmapped lines, out-of-bounds locations, style noise, and weak evidence.

## Changes and trade-off

No new heuristic rejection rule was enabled. The audit found no evidence that a broader suppression policy would improve real precision without recall risk. Instead, evaluator output now exposes F1 and operational non-completion counts, preventing successful-looking aggregates from concealing timeouts/errors.

Weak or partial evidence remains represented by a confidence downgrade, preserving the public finding contract and allowing human investigation. Unsupported evidence remains rejected. This is the conservative compatible uncertainty representation.

## Regression coverage

The suite covers unsupported evidence, invalid/unchanged paths, lines outside the diff, duplicate findings, category mismatch, behavior-preserving changes, clean fixes, and truncated/context-dependent cases. New tests cover undefined F1 and stable `case_id` + `max_cases` selection.

## Result and limitation

The deterministic fake run has FP=0 and FN=10 on the synthetic complementary corpus; it proves validation plumbing only. It cannot establish real LLM precision or recall. No default precision behavior changed.
