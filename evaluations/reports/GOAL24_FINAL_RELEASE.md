# GOAL 24 Final RC1 Release Decision

## Decision: NO-GO

The recovery materially improved the GOAL23 development corpus: 5 TP / 2 FP / 15 FN (F1 0.3704) became 18 TP / 0 FP / 2 FN (F1 0.9474). A causal runner executes the 60-case GOAL24 catalog and reports N1/N2/N3 breakdowns. N1 has direct guards, N2 helper-normalized flow, and N3 policy/repository object flow; all remain one validation-contract family and therefore do not prove independent generalization.

RC1 is still not approved. There is no independent, direction-validated post-recovery holdout: the 33-case legacy corpus samples fixes while omitting explicit change type, and the separate six-case legacy review corpus also omits change-direction metadata. The local fixture-side GitHub resilience matrix is complete, but secret minimization remains intentionally lexical and no real-provider token efficiency baseline is available. These are evidence gaps, not test failures hidden by the release report.

A causal, direction-labeled 12-case post-recovery corpus exists, but its former holdout result was withdrawn after a later GOAL23-derived pagination rule overlapped one of its families. It is now development-only and is explicitly not treated as independent evidence.

The bounded eligibility-inversion recovery now detects the remaining known development false negative. The unchanged 12-case digest scores 6 TP / 0 FP / 0 FN, but this remains development-only evidence and does not change the RC1 decision.

The newly frozen post-slice corpus provides a less favorable but more diverse internal check: 18 causal cases across nine families yielded 6 TP / 1 FP / 3 FN (precision 0.8571, recall 0.6667, F1 0.7500, negative FP rate 0.1111). Its digest is `9ed882edf8a5af28fe76046b1f3dd6282b2ccd46b8d2ac0234211eee7eddae20`. The score fails every numeric RC1 quality threshold; no changes were made after its first execution. It is internally authored and therefore does not replace an external independent corpus.

After the separately approved bounded guard-refactor and typed-exception correction, the same unchanged corpus measured 7 TP / 0 FP / 2 FN (precision 1.0000, recall 0.7778, F1 0.8750, negative FP rate 0.0000). These point estimates meet the numeric thresholds, but the corpus remains internally authored and cannot satisfy the independent-evidence requirement; the RC1 decision is still NO-GO.

After the bounded cross-file analysis recovery, the same frozen corpus measured 8 TP / 0 FP / 1 FN (precision 1.0000, recall 0.8889, F1 0.9412, negative FP rate 0.0000). The remaining miss lacks a changed caller guard, and the engine retains its changed-line evidence invariant rather than reporting an otherwise-unreviewable policy-only change. Numeric results are favorable but internally authored; RC1 remains NO-GO pending eligible independent evidence and GOAL25 real-provider validation.

Current frozen regression measurements are GOAL21: 13 TP / 1 FP / 2 FN (F1 0.8966), and GOAL23 development: 19 TP / 0 FP / 1 FN (F1 0.9744). GOAL23 is not independent release evidence because it informed recovery work.

## Gate audit

| Gate | Evidence | Status |
| --- | --- | --- |
| Frozen GOAL21 regression | 13 TP / 1 FP / 2 FN, F1 0.8966 | Pass |
| GOAL23 development | 18 TP / 0 FP / 2 FN, F1 0.9474 | Development-only pass |
| GOAL24 causal execution | 60 cases; N1/N2/N3 separately measured | Pass, development-only |
| Independent direction-valid post-recovery corpus | None available offline; legacy corpora lack valid change direction | Blocked |
| Full regression, lint, diff integrity | Full pytest, Ruff, `git diff --check` passed | Pass |
| Provider/parser/path security | Controlled offline tests passed; lexical redaction tested | Partial |
| GitHub dry-run | Fixture matrix complete, GET-only, no publication | Offline pass |
| Real-provider token efficiency | Not authorized until GOAL25 | Deferred |

## Required follow-up

1. Replace template N2/N3 cases with independently executable multi-component contracts and freeze their outcomes before tuning.
2. Build semantic analyses for the historical holdout's missing framework, lifecycle, sanitization, and interprocedural classes.
3. Expand lexical secret minimization only with evidence-backed patterns; preserve its current documented boundary.
4. Perform the separately authorized real-provider validation in GOAL 25.

## GOAL25 readiness

The offline controls needed for a real-provider run are present: explicit provider budget accounting, safe prompt boundaries with synthetic-secret redaction, strict output validation, deterministic fallback coverage for controlled failures, frozen corpus digests, and an offline GitHub dry-run path. NVIDIA configuration, credentials, and every network request remain deliberately out of scope for GOAL24.
