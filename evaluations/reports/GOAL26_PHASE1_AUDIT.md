# GOAL 26 Phase 1 Evaluation Integrity Audit

## Scope

This audit freezes reproducibility metadata for the 20-case synthetic end-to-end context corpus and the scored, provenance-backed real-world corpus. It does not measure provider quality, change production analysis, or authorize external requests.

## Ground-truth correction

`rw-urllib3-proxy-redirect-origin` previously declared lines `1-5`. The unified diff adds the causal condition at line `2` and the dependent header-selection condition at line `5`; the corrected envelope is `2-5`. The fixture diff, finding category, severity, evidence, and matching logic are unchanged.

The raw SHA-256 before this correction was `d372f6de7ad7a29acc78c8b6cc93b015db89fd4d0d601dcf1951093da5f645d5`. The corrected corpus SHA-256 is `c2cd0994d31d639d9571971ddece7ed99303ecb44ebde7d479c0f3cfac54071b`.

## Reproducibility evidence

`evaluations/manifests/goal26-phase1-evaluation.json` records the base commit, raw corpus hashes, stable E2E case order, and the exact offline FakeProvider runner configuration. `tests/test_goal26_phase1_integrity.py` recomputes both hashes and checks the recorded ordering; a changed corpus therefore fails the integrity control until the manifest is deliberately regenerated and reviewed.

All 20 E2E cases already have before/after executable contracts in `tests/test_end_to_end_context_oracles.py`. The new location control requires each positive expected-finding boundary to be an added diff line. Fixture provenance, descriptions, expected evidence, and oracle content remain outside model prompts.

## Limits

Passing integrity and oracle tests establishes fixture consistency and repeatability, not precision, recall, latency, token cost, or real-provider quality. Historical manifests and result directories are intentionally untouched; the new manifest is a separate record and does not revise prior metrics.
