# GOAL 09–10 — Offline Completion Report

## 1. Timeout diagnosis

GOAL 08 observed seven timeout cases in each arm, with failed attempts taking
approximately the configured 40 seconds. This proves an opaque transport wait,
not a connect-only, read-only, queueing, billing, or provider-side cause.

## 2. Provider improvements

The provider path carries structured failure categories, HTTP status,
privacy-preserving attempt hashes, transport duration, configured timeout, and
termination reason. Runner results expose a compatible broad status plus an
explicit operational state.

## 3. Deadlines and retries

Retries are bounded by `max_retries`, request/token budgets, elapsed budget,
and Retry-After. Optional attempt and case deadlines are disabled by default.
The synchronous standard-library transport supports cooperative boundaries, not
forced cancellation of an implementation that ignores its socket timeout.

## 4–9. Static-engine architecture, AST, CFG, data flow, relevance, fallbacks

`PythonStaticAnalyzer` uses only `ast`, produces structural facts and bounded
intraprocedural CFG/data-flow evidence, and never emits findings. CFG coverage
includes sequence, conditions, loops, early returns, break, continue,
try/except/finally, raise, and potentially unreachable local statements.
Def-use facts are `proven` only for known local
definitions and `possible` otherwise. The independent opt-in
`--static-relevance-selection` promotes only proven direct callers/callees of
changed control-flow or error-handling symbols. Syntax errors, dynamic behavior,
complexity limits, and unresolved links preserve legacy ranking.
Later lexical local assignments are also represented as
`possible_use_before_assignment`, without generating a finding.

## 10–11. Token benchmark and validation

Offline A/B/C using the six-case `code_review_corpus.json` and FakeProvider
completed all cases with 4 TP, 0 FP, 0 FN, and 5,171 prompt tokens in each arm.
This corpus selects no cross-file context, so it demonstrates compatibility but
not the experimental 15–25% saving target. The full offline suite passed:
`305 passed in 19.75s`.

## 12–13. Tests and regression correction

Targeted provider, context, static-analysis, CLI, quota, and corpus-integrity
tests are included in the full-suite result. A regression in repository
boundary validation was corrected: a child directory of a Git worktree is no
longer silently treated as an independent review target.

## 14–15. Technical and operational limits

The static engine is Python-only and intraprocedural. Dynamic dispatch,
reflection, monkey-patching, and exact alias/value propagation remain unknown.
The NVIDIA external benchmark was deliberately not run; simulated reliability
does not prove NVIDIA completion-rate improvement.

## 16. Flags and defaults

`--hybrid-static-selection` and `--static-relevance-selection` are both
disabled by default. `--attempt-deadline` and `--case-deadline` are optional
and disabled by default. Existing default review behavior remains unchanged.

## 17. Principal files changed or added

Provider/reliability changes are in `providers/base.py`, `providers/nvidia.py`,
core configuration/models, CLI/evaluation paths, and deterministic tests.
Static-engine additions are `context/static_analysis.py`,
`context/static_relevance.py`, context-pipeline integration, and
`tests/test_static_analysis.py`. GOAL reports are under `evaluations/reports/`.

## 18–19. Commit and Git state

No local commit was created. The environment explicitly denies creation of
`.git/index.lock`, including after verification that no stale lock exists.
All verified changes are preserved in the worktree; existing unrelated changes
were not reset, removed, or overwritten.

## 20. External pending work

The NVIDIA benchmark remains pending explicit future authorization and an
environment capable of external execution. It must preserve the frozen corpus
hash `17019e5f994b1bfc4ba4afe62992cf69bd829f509db3e075cf68ba9615759096`.
