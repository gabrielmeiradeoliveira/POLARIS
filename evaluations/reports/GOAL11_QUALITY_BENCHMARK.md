# GOAL 11 — Quality Benchmark

## Objective

Make offline quality measurements reproducible and operational failures visible without treating them as successful reviews.

## Evaluator audit and changes

`evaluate_corpus` already excluded non-completed cases from TP/FP/FN aggregation. This mission adds explicit `timeout_cases`, `error_cases`, `unassessed_cases`, and undefined-safe `f1_score` fields. It also fixes selection order: a `case_ids` batch is now bounded by `max_cases` rather than silently reverting to corpus order.

The evaluator uses one-to-one matching, validates file and changed-line location, reports category mismatches separately, and retains rejected-candidate diagnostics. Timeout or provider-error cases contribute neither credit nor findings.

## Complementary suite

`evaluations/fixtures/end_to_end_context_benchmark.json` is retained as the complementary 20-case suite rather than duplicated. It contains 12 defect introductions and 8 negative changes (clean fixes/equivalent changes), with exception, authorization, state, return-contract, concurrency, control-flow, and cross-file cases. Its tests include executable before/after oracles where applicable. It is synthetic/unverified and must not be represented as a real-world LLM-quality corpus.

## Offline A/B/C

All runs used the fake provider, the same 20 fixtures, no Behavioral Delta, unchanged matching, and the same token budget. Artifacts are in `evaluations/results/goal11_15_ab/`.

| Configuration | TP | FP | FN | Precision | Recall | F1 | Completion | Timeout/Error | Estimated tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A: optional selection off | 2 | 0 | 10 | 1.0000 | 0.1667 | 0.2858 | 20/20 | 0/0 | 17,166 |
| B: GOAL 08 hybrid opt-in | 2 | 0 | 10 | 1.0000 | 0.1667 | 0.2858 | 20/20 | 0/0 | 17,166 |
| C: GOAL 10 static relevance opt-in | 2 | 0 | 10 | 1.0000 | 0.1667 | 0.2858 | 20/20 | 0/0 | 17,166 |

All deltas are 0%. Latency is 0 ms because findings are fixture-backed/post-processing and the fake provider is deterministic. Cost is $0.00; provider usage is estimated. Detection precision/recall equal strict precision/recall because there were no category mismatches.

## Reproduction and limitations

Run the three commands recorded in `GOAL11_15_FINAL.md`. Real-provider execution was intentionally not performed. External validation must pre-register corpus, thresholds, provider/model, retries, budget, matching, and run order; report completed, timeout, error, skipped, accepted, and rejected findings separately.
