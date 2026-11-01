# GOAL 18 Final — Accuracy Engine 2.0 & Production Readiness

## Scope and preserved state

The pre-edit worktree is recorded verbatim in
`.agents/task-baselines/goal18.git-status.txt`. Existing user changes and frozen
fixtures/manifests were preserved. No external API call, NVIDIA request, commit,
push, branch, or worktree was created.

## Problems identified

1. The intraprocedural CFG treated assignments from a single `if` branch as
   definitely available after the branch. This hid a real `UnboundLocalError`
   path and could also overstate relevance evidence.
2. `try/else` was not represented by the CFG, and bindings present only in an
   exception handler could be treated as available after the construct.
3. Behavioral Delta did not surface the specific contract change where an
   unconditional local initialization becomes conditional before a later use.

## Implemented improvements

- CFG data-flow now merges only bindings defined on every continuing branch.
  Branch-only and handler-only bindings are reported as `possible_unbound_local`.
- `try/else` is modeled as a distinct deterministic control-flow signal.
- Behavioral Delta adds `data_flow_contract_change`, narrowly requiring an
  equivalent former unconditional assignment, a new no-else condition, and a
  later use with no intervening reassignment.
- `CodeReviewModule` converts a proved changed-path unbound-local fact into an
  evidence-grounded `logic_error` candidate only when the responsible assignment
  is an added/modified line. Normal finding validation and deduplication remain
  authoritative.
- Added separate executable GOAL 18 corpus
  `goal18_data_flow_contract_corpus.json`: one introduced defect and one safe
  complete-branch negative case. Frozen corpora were not changed.

## Quantitative offline evidence

| Comparator / corpus | TP | FP | FN | Completion | Estimated tokens |
|---|---:|---:|---:|---:|---:|
| Pre-GOAL-18 module behavior, executable two-case corpus | 0 | 0 | 1 | 100% | 1,737 |
| Accuracy Engine 2.0, same corpus/criteria | 1 | 0 | 0 | 100% | 1,737 |

The pre-change comparator is an in-test reproduction of the former module path
with the new deterministic pass disabled; it is not presented as NVIDIA model
performance. Append-only synthetic manifests `goal18-baseline-20261101` and
`goal18-engine-20261101` reproduce the CLI evaluation contract (both current
validator configurations report 1 TP / 0 FP / 0 FN after the engine change).

For 100 same-process, same-input FakeProvider evaluations, the pre-data-flow
path took 171.87 ms and Accuracy Engine 2.0 took 232.85 ms. This records the
real cost of the extra AST pass; no percentage performance claim is made.

## Tests and integrity

- New static/CFG, behavioral-delta, deterministic finding, positive/negative
  corpus, and before/after regression tests were added.
- Targeted static/context, behavioral delta, provider-security, and corpus tests
  passed during implementation.
- Full pytest passed (346 tests); Ruff and `git diff --check` passed; full
  history-integrity verification passed for 11 manifests.

## Security and reliability

The implementation uses only local AST/context data; it neither changes provider
transport nor relaxes secret redaction, evidence validation, timeout, retry, or
token-budget controls. Incomplete or unassessed cases remain distinct from FNs.

## NVIDIA readiness

The GOAL 17 pilot remains the prepared protocol: `minimaxai/minimax-m3.1-flash`,
A/B/C, append-only history, and a three-request / 6,000-estimated-token /
300-second / no-retry pilot. No call was made. The token limit remains operational
and estimated, not a rigid provider-guaranteed ceiling.

## Limitations and next priorities

The new data-flow detector intentionally covers only a high-evidence local
pattern; it does not model dynamic dispatch, aliases, arbitrary loops, or all
interprocedural initialization contracts. Next, expand executable cross-file
authorization and resource-lifecycle controls, then collect separately authorized
real-provider results without mixing them with synthetic evidence.
