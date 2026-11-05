# GOAL 24 eligibility-inversion slice

## Authorized scope

- `src/polaris/modules/deterministic_rules.py`: add a bounded AST/diff rule for a parameter-bound conditional-expression polarity inversion.
- `tests/test_goal24_filter_regression.py`: add positive, negative, and semantic-equivalence regression coverage through the real deterministic-rule entry point.
- `tests/test_goal24_post_recovery_holdout.py`: make the frozen development-only holdout execution assert the observed score after the engine change, without changing its fixtures.
- `evaluations/reports/GOAL24_FINAL_ENGINEERING.md`, `evaluations/reports/GOAL24_FINAL_BENCHMARK.md`, and `evaluations/reports/GOAL24_FINAL_RELEASE.md`: record measured results and preserve the independent-evidence limitation.

## Root cause and expected behavior

The direction-labeled `h24-pos-eligibility-inversion` fixture reverses the condition of a conditional expression from `eligible` to `not eligible` while retaining both result branches. The current deterministic rules preserve and parse the before/after diff but have no rule that compares conditional-expression predicates, so the evaluator emits no candidate and scores a false negative.

The rule will report only when a changed conditional expression in a Python function changes a direct boolean parameter predicate to its direct negation (or the reverse) while both branches are structurally unchanged. It will emit a high-confidence `logic_error` on the changed after-expression. It will not report branch rewrites, distinct predicates, non-parameter predicates, double-negation equivalence, or unchanged expressions.

## Acceptance and verification

- The positive fixture produces `DET-CONDITIONAL-POLARITY-INVERTED`.
- Focused negative and metamorphic tests produce no finding.
- The frozen holdout improves from 5 TP / 0 FP / 1 FN to 6 TP / 0 FP / 0 FN; it remains development-only, not independent RC1 evidence.
- Run focused tests, GOAL24 tests, full pytest, Ruff, `git diff --check`, and both GOAL24 runners.

## Authorized post-slice corpus extension

The attached approval also authorizes preparation of a new corpus. The following design is frozen before its first engine execution; its scenarios and expected outcomes will not be changed based on benchmark results.

- Create `evaluations/fixtures/goal24_post_slice_holdout/__init__.py` and `catalog.py` with direction-labeled positive/negative causal scenarios spanning API validation, authorization, payments/idempotency, ETL data handling, cache consistency, concurrency/state ownership, return contracts, exception behavior, and data flow. Each positive has an executable before/after behavioral oracle, and each negative preserves the safe behavior through a distinct but semantics-preserving source change.
- Create `evaluations/goal24_post_slice_holdout_runner.py` to construct multi-file production-pipeline fixtures, hash all inputs, and execute through `evaluate_corpus` with controlled empty provider output.
- Create `tests/test_goal24_post_slice_holdout.py` to execute all causal oracles and ensure explicit directions, balanced labels, digest stability, and end-to-end runner operation. It will not assert a quality threshold before the frozen first measurement.
- Update `evaluations/reports/GOAL24_FINAL_BENCHMARK.md` and `GOAL24_FINAL_RELEASE.md` with the first measured results and provenance boundary.

This corpus will be internally authored after recovery and is therefore independent of the historical GOAL21/23 and previous GOAL24 development fixtures, but not external independent validation. It cannot alone satisfy the external-independence RC1 gate.

## Authorized deterministic correction scope

- `src/polaris/modules/deterministic_rules.py`: suppress `DET-IDEMPOTENCY-GUARD-REMOVED` when the after AST retains the same membership early-return guard before the matching set mutation; add a bounded typed-exception fallback rule only when a removed bare `raise` in an `except` handler becomes a literal fallback return in the same exception type.
- `tests/test_goal24_filter_regression.py`: add positive, negative, and semantic-refactor cases for both rules using the public deterministic-rule entry point.
- `evaluations/reports/GOAL24_FINAL_ENGINEERING.md` and `GOAL24_FINAL_RELEASE.md`: record development-corpus-based remediation and regression measurements, while preserving the frozen post-slice corpus evidence unchanged and explicitly not used for tuning.

Expected behavior: the multi-line idempotency refactor must emit no finding; a genuine removed replay guard must remain detectable; a typed changed handler that replaces re-raise with a literal fallback must be a high-confidence `error_handling` finding; propagated/re-raised and unrelated fallback handlers must remain clean.

## Explicitly authorized cross-file deterministic recovery

Production scope is limited to the existing review pipeline and deterministic rule engine:

- `src/polaris/modules/code_review.py`: pass the bounded review file/context collection into cross-file deterministic analysis without changing provider behavior or external interfaces.
- `src/polaris/modules/deterministic_rules.py`: derive evidence only from changed Python files and supplied bounded `FileContext` sources. Add conservative inter-file rules for changed module-level literal allowlist widening used by a changed caller, and for a changed caller replacing a same-parameter collection filter with an unambiguous local helper that returns the unfiltered parameter. Do not execute repository code or resolve dynamic imports.
- `tests/test_goal24_cross_file_rules.py`: direct positive, negative, ambiguous-resolution, and equivalence/refactor coverage using the production deterministic entry point.
- `evaluations/reports/GOAL24_FINAL_ENGINEERING.md`, `GOAL24_FINAL_BENCHMARK.md`, and `GOAL24_FINAL_RELEASE.md`: record only post-change measurements and retain corpus provenance/limitations.

Acceptance: cross-file candidates must point at changed after-lines; constant widening must require a changed literal collection plus a changed caller guard reference; collection-filter bypass must require a same-name, single unambiguous helper whose return is exactly `list(the_parameter)`; no candidate for local-only lookalikes, dynamic/ambiguous helper names, or equivalent filtering refactors. Frozen corpus files, hashes, labels, and oracles are not editable.
