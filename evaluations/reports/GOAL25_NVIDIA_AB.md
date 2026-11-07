# GOAL 25 NVIDIA A/B

## Frozen sample

The sample was frozen before the real A/B attempt. It has 12 fixtures: six positive and six negative cases, covering GOAL21, GOAL23, GOAL24 N1/N2/N3, and the post-slice set. Selection is defined by immutable case IDs in `evaluations.goal25_runner`; no historical benchmark or oracle was modified.

## Static-only baseline

| Metric | Static only |
| --- | ---: |
| TP | 6 |
| FP | 0 |
| FN | 0 |
| Precision | 1.0000 |
| Recall | 1.0000 |
| F1 | 1.0000 |
| Negative false-positive rate | 0.0000 |
| Completed cases | 12/12 |
| Prompt tokens | 10,314 (estimated) |
| Completion tokens | 12 (estimated) |
| Total tokens | 10,326 (estimated) |
| Total latency | 2 ms |

## NVIDIA arm: not scoreable

The authorized hybrid process was started once. It returned no telemetry payload or completed summary to the caller. Consequently, the number of submitted requests, provider-reported usage, per-case outcomes, failures, and latency cannot be verified. This is an observability failure, not a zero-result detection outcome.

No retry was made. Retrying could exceed the cumulative limits because the first process's consumption is unknown. Therefore this report does **not** claim NVIDIA TP/FP/FN, precision, recall, F1, false-positive rate, findings preserved/rejected, incremental gain, cost, or latency. The structured incident record is `evaluations/results/goal25/hybrid_execution_unverified.json`.

## Reproducibility condition

A future run requires a fresh, explicitly authorized budget allocation or provider-side usage reconciliation, plus the hardened metrics-only persistence path. It must reuse the same frozen sample or declare a new experiment rather than overwriting this result.
