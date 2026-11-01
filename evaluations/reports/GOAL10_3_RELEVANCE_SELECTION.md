# GOAL 10.3 — Relevance Selection

## Policy

The experimental `--static-relevance-selection` policy is disabled by default.
It promotes already-proven direct callers and direct callees only when changed
lines overlap a local condition, return, raise, or exception-handler signal.
It never creates a finding and never drops a context candidate.

Priority order remains: diff/changed symbol, direct consumers, direct
callees/definitions, class context, and bounded transitive context. The static
policy adjusts only the already-proven direct relationships; unresolved,
dynamic, syntax-invalid, and complexity-limited cases retain the legacy order.

## Fallback

No static analysis result, no enclosing procedure, no changed control-flow
signal, or any unresolved relation leaves the legacy candidate order intact.
The independent GOAL 08 `--hybrid-static-selection` exact-overlap suppression
remains separately opt-in and disabled by default.
