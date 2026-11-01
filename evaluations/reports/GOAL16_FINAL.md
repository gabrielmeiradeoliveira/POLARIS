# GOAL 16 Final — Offline Preparation

## State

`GOAL16_OFFLINE_PREPARED_AWAITING_EXTERNAL_AUTHORIZATION`

The real NVIDIA benchmark was intentionally not executed. Offline preparation,
controlled FakeProvider A/B/C runs, append-only synthetic history persistence,
corpus audit, and the frozen external protocol are complete. This is not an
MVP 2.0 release declaration.

## Deliverables

- Corpus audit with the preserved local-change baseline and immutable corpus
  checks.
- Frozen A/B/C protocol, real-run command, limits, matching rules, and failure
  treatment.
- Offline-readiness evidence with clear FakeProvider limitations.
- Three new manifests and six run-scoped trend reports under
  `evaluations/history/`.

## Proposed NVIDIA budget

Each arm is capped at 24 requests, 50,000 tokens, 45-second request/attempt
limits, a 90-second case deadline, one retry, and 1,800 seconds elapsed time.
Across A/B/C the ceiling is 72 requests and 150,000 tokens, excluding a
separately authorized clean-negative evaluation. No currency estimate is made
without current account-specific NVIDIA pricing.
