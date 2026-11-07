# GOAL 24 Final Engineering Recovery

## Scope and method

This offline recovery used the frozen GOAL 23 corpus with `evaluate_corpus`, an empty-response `FakeProvider`, end-to-end processing enabled, and behavioral delta disabled. The provider contributes no findings, so these are measurements of the local deterministic engine and validation pipeline, not LLM quality.

The initial reproduced GOAL 23 result was 5 TP, 2 FP, and 15 FN. Investigation grouped false negatives by missing structural signals and identified both false positives as authorization-guard refactors being mistaken for guard removal.

## Implemented recovery

- Added detection for a conditional collection visibility filter replaced by `list(input)`.
- Tightened permission-guard removal to require that the post-change source has no remaining `PermissionError` guard.
- Added narrow structural detections for role allowlist widening, removed validation/idempotency/cache/resource guards, composite-key collapse, least-privilege default escalation, weakened required-field access, numeric return stringification, optional-value truthiness, sensitive redirect-header removal, HTTPS proxy authorization guards, trusted-host policy, redirect Host stripping, and exception serialization hooks.
- Extended removed-validation analysis with bounded intra-procedural aliases from one-argument helper calls, covering normalization and wrapper flow without speculative inter-file inference.
- Added an end-to-end causal GOAL24 runner with a frozen catalog digest and per-level scorecards.

## Frozen post-change measurement

| Corpus | Cases | TP | FP | FN | Precision | Recall | F1 | Negative FP rate | Completion |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GOAL 21 frozen adversarial regression | 30 | 13 | 1 | 2 | 0.9286 | 0.8667 | 0.8966 | 0.0000 | 1.0000 |
| GOAL 23 development corpus | 40 | 18 | 0 | 2 | 1.0000 | 0.9000 | 0.9474 | 0.0000 | 1.0000 |
| Documented real-world development corpus | 8 | 6 | 0 | 2 | 1.0000 | 0.7500 | 0.8571 | N/A | 1.0000 |
| Legacy real-world corpus (not release eligible) | 33 | 0 | 0 | 22 | N/A | 0.0000 | N/A | 0.0000 | 1.0000 |

GOAL23 improved by +13 TP, -2 FP, -13 FN, and +0.5770 F1 from the reproduced baseline. It is development evidence because it informed the changes. The legacy 33-case corpus is not valid release evidence: sampled positive diffs add fixes while its fixtures omit `change_type`, causing the model to default them to defect introductions. Its 0/22 end-to-end result must not be interpreted as missed vulnerable code.

## Eligibility-inversion recovery slice

The direction-labeled post-recovery development fixture `h24-pos-eligibility-inversion` changed a conditional-expression predicate from `eligible` to `not eligible` while retaining the same result branches. The evaluation pipeline retained its diff, source location, category, and causal oracle, but the deterministic engine had no before/after predicate-polarity comparison and therefore produced no candidate.

`DET-CONDITIONAL-POLARITY-INVERTED` now reports only a direct function-parameter predicate whose polarity flips exactly once in a changed conditional return while both branch ASTs remain identical. It deliberately excludes branch rewrites, non-parameter predicates, and double-negation forms. The focused regression, negative, and metamorphic checks passed.

Re-running the frozen digest `c73bb6fc1b86a244062487ab4488b9a17ec1ebd3d29c24d465aed59b810544e2` after this change yielded 6 TP / 0 FP / 0 FN (precision 1.0000, recall 1.0000, F1 1.0000, negative FP rate 0.0000). This is a development regression result only: the corpus is agent-authored and previously contaminated by a GOAL23-derived pagination rule, so it is not independent RC1 evidence.

## Guard-refactor and typed-exception recovery

The idempotency detector had treated a one-line guard rewritten into an equivalent multi-line guard as removed. It now confirms that the same membership early return still precedes the matching set mutation before emitting. A second narrow rule identifies only a typed exception handler where a removed bare re-raise becomes an added literal fallback return. Focused positive, negative, and metamorphic tests pass.

The unchanged post-slice digest was remeasured after the approved correction as a regression observation: 7 TP / 0 FP / 2 FN (precision 1.0000, recall 0.7778, F1 0.8750, negative FP rate 0.0000). Authorization scope and cross-file tenant data flow remain missed. This internal corpus remains frozen and is not a valid independent RC1 quality gate.

## Bounded cross-file deterministic recovery

The engine now derives two conservative relationships from the supplied, bounded review contexts without executing code: a changed literal allowlist widening is reported only with a changed permission-style caller guard using that exact global name; a changed caller bypassing a same-parameter collection filter is reported only when a single unambiguous helper returns exactly `list(the_parameter)`. Dynamic imports, unresolved names, and ambiguous helpers are deliberately excluded. Focused positive, negative, ambiguity, and refactor coverage passes.

The frozen post-slice digest remained `9ed882edf8a5af28fe76046b1f3dd6282b2ccd46b8d2ac0234211eee7eddae20`; post-change observation yielded 8 TP / 0 FP / 1 FN (precision 1.0000, recall 0.8889, F1 0.9412, negative FP rate 0.0000). The remaining authorization-scope miss intentionally lacks a changed caller guard, which is required for an evidence-backed review finding. This corpus remains internally authored and was not modified.

The frozen GOAL21 regression remained 13 TP / 1 FP / 2 FN (F1 0.8966). The GOAL23 development measurement improved to 19 TP / 0 FP / 1 FN (precision 1.0000, recall 0.9500, F1 0.9744); it remains development evidence and is not an independent release gate.

## Verification

Focused deterministic, causal-runner, catalog, and real-world corpus tests passed. The final `pytest -p no:cacheprovider --basetemp .pytest-goal24-final-suite2 -q` suite, `ruff check src tests evaluations`, and `git diff --check` all passed. No network provider or GitHub operation occurred.

## Pipeline audit

| Stage | Current implementation | Contract / control | Residual limitation |
| --- | --- | --- | --- |
| Diff ingestion | `git.analyzer.parse_unified_diff` | Parsed `FileDiff` with changed-line locations | Partial/deleted patches have incomplete after-context. |
| Context and AST | `context.python_ast`, `context.static_analysis`, `context.pipeline` | Bounded `FileContext`, AST/static facts, token limits | Python-only analysis. |
| Deterministic review | `modules.deterministic_rules`, `CodeReviewModule._static_data_flow_candidates` | `CandidateFinding` with changed-path evidence | Rule coverage is incomplete for broad framework semantics. |
| Behavioral delta | `context.behavioral_delta.analyze_behavioral_deltas` | Optional serialized deltas under explicit token allowance | Disabled in deterministic A/B when it adds cost without signal. |
| Provider boundary | `CodeReviewModule.analyze` | Strict JSON parsing, prompt redaction, budget tracking, static fallback only for opt-in controlled providers | No real-provider result in GOAL24. |
| Validation and deduplication | `FindingIntelligenceEngine.process_candidates` | Repository-relative path, evidence, location, and duplicate validation | Evidence can be insufficient for interprocedural bugs. |
| GitHub dry-run | `GitHubPullRequestReview`, `SafePublisher` | Fixture transport, mapping, GET-only dry run | No live GitHub validation in this goal. |

## GOAL25 handoff

GOAL25 must keep the frozen GOAL21/GOAL23, GOAL24 catalog digest, and post-recovery holdout digest unchanged; use an explicitly configured NVIDIA model and budget; record provider-reported versus estimated token use and latency; compare deterministic-only with deterministic-plus-provider findings; re-run parser/redaction/path/invalid-output controls; and report incremental TP/FP/FN by N1/N2/N3 without treating `FakeProvider` as model-quality evidence.
