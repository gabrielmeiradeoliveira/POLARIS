# GOAL 16.1 — Validation History & Confidence Calibration

## Implemented

- Added append-only, self-hashing benchmark manifests under a caller-selected `evaluations/history/` root.
- Captured UTC timestamp, run ID, local Git commit, POLARIS version, provider/model, A/B/C configuration label, corpus SHA-256, operational limits, and aggregate evaluation metrics.
- Persisted sanitized per-finding validation records with stable IDs, location/category, evidence/response excerpts, declared qualitative confidence, optional explicit numeric probability, outcome, verification method, decision reason, and UTC decision timestamp.
- Added provenance-separated real and synthetic trend summaries in immutable run-scoped Markdown and JSON reports.
- Added validation coverage, confirmed-rate-among-assessed, inconclusive counts, and guarded Brier/reliability calculations.

## Safety model

Manifests exclude raw case diagnostics, raw prompts, raw provider payloads, credentials, and bulky artifacts. The aggregate summary intentionally omits `case_results`; sanitized finding records are the only retained case-level data. Qualitative confidence is never mapped to a numeric probability. Calibration is unavailable unless assessed records contain explicitly numeric probabilities and meet the configured sample minimum.

## Usage

```powershell
polaris evaluate --provider fake --fixtures evaluations/fixtures/code_review_corpus.json `
  --history-dir evaluations/history --history-run-id offline-a-20261101 `
  --history-configuration A --history-corpus-kind synthetic
```

No external provider call is required by this workflow.

## Verification

Offline tests cover append-only persistence, duplicate run rejection, manifest tampering, sanitized persistence, metric calculations, calibration guards, real/synthetic separation, trend generation, and CLI integration.

## Limitations

The history records evaluation outcomes; it does not make a confidence score a security guarantee, prove absence of vulnerabilities, or establish real-model quality without an authorized external benchmark and independently assessed findings.
