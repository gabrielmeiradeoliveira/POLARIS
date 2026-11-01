# GOAL 17 Technical Audit

## Scope and evidence

The production orchestrator, fixture runner, NVIDIA adapter, intelligence pipeline,
and append-only history were inspected. The pre-edit status is preserved verbatim
in `.agents/task-baselines/goal17.git-status.txt`; pre-existing changes were not modified.

## Findings and corrections

1. A budget-stopped corpus retained the triggering case but silently omitted all
   later fixtures. `evaluate_corpus` now records each later fixture as
   `unassessed` with `not_attempted_budget_exhausted`; no such case adds an FN.
2. Evaluation summaries now expose completion rate and 95% Wilson intervals for
   strict and location-detection precision/recall when the denominator is at
   least 20. Smaller samples expose `null`, rather than unjustified certainty.
3. Reading legacy sealed history broke after new optional summary fields were
   introduced: Pydantic defaults altered the reserialized hash. Schema 1.2 now
   seals new manifests; legacy validation accepts only documented prior shapes.

## Existing controls confirmed

- NVIDIA attempts reserve input, safety margin, and output before transport;
  retries re-reserve and respect request/elapsed limits.
- Provider errors are categorized, secrets are redacted, and observability stores
  hashes rather than prompt/response bodies.
- Finding matching is one-to-one; category mismatch, severity mismatch,
  duplicate reduction, operational failure, and detection metrics remain distinct.

No speculative refactor was made.
