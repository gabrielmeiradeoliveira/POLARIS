# GOAL 24 Final Benchmark

## Causal runner execution

`evaluations.goal24_runner.run_goal24_catalog` executes every scenario through the production evaluation pipeline with controlled empty provider output, after the catalog's causal before/after oracle tests. The catalog SHA-256 is `9db44b7571bcc638793fc0934965f16bceb2a607cc793608d8b0c007eae57d31`.

| Group | Cases | TP | FP | FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| All declared levels | 60 | 30 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| N1 | 12 | 6 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| N2 | 24 | 12 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| N3 | 24 | 12 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |

## Validity limitation

N1 uses a direct guard; N2 routes the value through a normalization helper; N3 crosses policy and repository objects before the guard. The runner now confirms that bounded local alias flow detects the N2/N3 guard removal without regressing GOAL21 or GOAL23. However, all scenarios still exercise the same validation-contract family, so the perfect score is not independent generalization or broad complexity evidence. A 33-case legacy real-world corpus scored 0 TP / 0 FP / 22 FN end-to-end, but it is not release eligible: its positive diffs sample fixes and omit explicit change-direction metadata, so it cannot measure defect-introduction recall.

## Withdrawn post-recovery holdout

`goal24_holdout` was a separate, direction-labeled, causally executable 12-case corpus created after an earlier recovery phase. Its SHA-256 is `c73bb6fc1b86a244062487ab4488b9a17ec1ebd3d29c24d465aed59b810544e2`.

| Cases | TP | FP | FN | Precision | Recall | F1 | Negative FP rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 12 | 4 | 0 | 2 | 1.0000 | 0.6667 | 0.8000 | 0.0000 |

This result is withdrawn from holdout evidence. A later general pagination rule was developed from GOAL23 and overlaps the holdout's pagination family; retaining it as a frozen post-recovery score would be misleading. The corpus remains useful as a development regression fixture, but it is agent-authored and not a replacement for independently authored or external validation.

## Eligibility-inversion development regression

The previously missed `h24-pos-eligibility-inversion` development case now has a deterministic candidate. The current frozen-corpus execution is 6 TP / 0 FP / 0 FN (precision 1.0000, recall 1.0000, F1 1.0000, negative FP rate 0.0000; 12 cases). The corpus digest remains `c73bb6fc1b86a244062487ab4488b9a17ec1ebd3d29c24d465aed59b810544e2`; no fixture or oracle was changed.

This result validates the implemented regression fix, not generalization and not the RC1 independent-quality gate.

## Frozen post-slice corpus

The post-slice corpus was designed and hashed before its first engine execution. It contains 18 direction-labeled causal cases (9 defect introductions and 9 clean changes) across API bounds, multi-file authorization, payment replay, ETL contracts, cache invalidation, lock ordering, return contracts, exception behavior, and multi-file tenant data flow. Its frozen SHA-256 is `9ed882edf8a5af28fe76046b1f3dd6282b2ccd46b8d2ac0234211eee7eddae20`.

The first and only post-freeze result is 6 TP / 1 FP / 3 FN: precision 0.8571, recall 0.6667, F1 0.7500, negative FP rate 0.1111, completion 1.0000, and 14,003 estimated tokens. The misses are authorization scope, exception swallowing, and cross-file tenant data flow; the false positive is a semantics-preserving multi-line idempotency refactor. No scenario, expected result, or deterministic rule was changed after this run.

This is internally authored post-slice evidence, independent of the historical and prior GOAL24 development fixtures but not external independent validation. It fails the RC1 thresholds and must not be used to tune further rules.

The separately approved idempotency-refactor and typed-exception correction was then observed against the unchanged digest: 7 TP / 0 FP / 2 FN (precision 1.0000, recall 0.7778, F1 0.8750, negative FP rate 0.0000). The corpus content, labels, oracles, and digest were not modified. The remaining misses are authorization scope and cross-file tenant data flow; this does not establish independent generalization.

The bounded cross-file pass then measured 8 TP / 0 FP / 1 FN (precision 1.0000, recall 0.8889, F1 0.9412, negative FP rate 0.0000) against the same digest. It detected the tenant-flow bypass but intentionally did not report an allowlist widening without a changed caller guard. This is a conservative evidence-boundary tradeoff, not a reason to weaken the changed-line invariant.
