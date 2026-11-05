# GOAL 16 Corpus Audit

## Pre-edit Git baseline

Purpose: verbatim `git status --short --branch` captured immediately before the
reconstructed GOAL 16 artifacts were created.

```text
## feature/nvidia-benchmark...origin/feature/review-accuracy
 M AGENTS.md
 M calculator.py
 D context_test.py
?? .agents/task-baselines/
?? .agents/workflows/orchestration-matrix.md
?? .pytest-goal11-15-final/
?? .pytest-goal11-15-final2/
?? .pytest-goal11-15-metrics/
?? .pytest-goal11-15-release/
?? .pytest-goal11-15-targeted/
?? .pytest-goal11-15-timing/
?? .pytest-goal11-15/
?? .pytest-goal16-1-compat/
?? .pytest-goal16-1-final/
?? .pytest-goal16-1-full/
?? .pytest-goal16-1-history-final/
?? .pytest-goal16-1-release/
?? .pytest-goal16-1-schema/
?? .pytest-goal16-1/
?? evaluations/fixtures/bug_intro_03_temp.json
?? evaluations/fixtures/bug_intro_04_05_temp.json
?? evaluations/fixtures/clean_negatives_temp.json
?? evaluations/reports/baseline_mvp1_4_minimax_m3_1_flash.md
?? evaluations/results/
?? scratch/
```

## Corpus inventory

| Fixture | Cases | Live-suitable | Role | SHA-256 |
|---|---:|---:|---|---|
| `real_world_verified_benchmark.json` | 8 | 8 | Documented public-fix positive corpus selected for the future real run | `17019e5f994b1bfc4ba4afe62992cf69bd829f509db3e075cf68ba9615759096` |
| `end_to_end_context_benchmark.json` | 20 | 20 | Synthetic end-to-end control corpus | `1901684d08c4b6cba33edeaa186782ec3b778fad9af7cf2f043eed91913e2357` |
| `live_nvidia_baseline_cases.json` | 5 | 1 | Legacy mixed baseline; not selected | `3c412fd1cba8f656d34d00cb19b0eba2350a915e80b18035325bb42f72c9bf9d` |

The selected corpus contains eight positive, `documented_verified` cases and
no clean negatives. It can measure recall and strict finding matching but
cannot independently estimate false-positive rate or precision. Any release
claim against the precision/F1 targets requires a separately frozen,
representative real clean-negative corpus and its SHA-256 before an external
run. Synthetic negatives must remain separate from real-model results.

## Evaluation and production paths

`polaris review` analyzes a Git repository; `polaris evaluate
--production-parity` materializes fixture sources and reuses production context
preparation. Both share configuration, provider construction, budgets,
selection flags, Finding Intelligence, and failure diagnostics. Evaluation adds
fixture loading, oracle matching, per-case aggregation, and history writing;
it cannot recreate a source repository's complete history or unrelated files.

Strict matching uses the existing location/category matching and
`--strict-severity`. Category mismatches, failures, timeouts, skipped cases,
and unassessed cases remain separately reported rather than being converted
into invented findings.

## Existing history

The three pre-existing Goal 16.1 manifests were integrity-checked before this
work and were not modified:

| Run ID | Manifest SHA-256 |
|---|---|
| `goal16-1-offline-20261101` | `522570706b716968c755ffcd1914232a31566fdfc2978796833ec8f4fabe3871` |
| `goal16-1-offline-20261101-v2` | `73178d014746eb4363c5938aaa5759135c793d96793f65dc7e032c68880ff791` |
| `goal16-1-offline-20261101-v3` | `d453a7c07df9e347bc96b713ecf3c9c840411cf3c739f24ee8d061a0c9f840c5` |
