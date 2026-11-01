# GOAL 22 - Deterministic Detection Engine Expansion

## Executive result

GOAL 22 adds a bounded, AST-backed deterministic rule layer to the existing
`CodeReviewModule`. It emits ordinary `CandidateFinding` records and therefore
continues through the existing Finding Intelligence validation, normalization,
deduplication, CLI, and Goal 20 GitHub dry-run mapping paths. It neither
executes reviewed code nor makes network calls.

The frozen Goal 21 corpus SHA-256 remained
`A57EE9FE0900978CF4928D72211B1CA5AE05BD765494E8ED6D20A1D06279D84E` before and
after this work.

## Baseline and after measurement

The documented pre-change full offline FakeProvider pipeline measured 3 TP,
1 FP, 12 FN: precision 0.7500, recall 0.2000, F1 0.3158, and zero negative
case FPs. It had no observed deterministic-only detections.

The same immutable 30-scenario harness after the change measured 13 TP, 1 FP,
2 FN: precision 0.9286, recall 0.8667, F1 0.8966, zero negative-case FPs,
and 0 ms reported aggregate evaluator latency (small local synthetic inputs;
not a production performance claim). The same values were observed with a
scripted empty FakeProvider response, proving these are deterministic-engine
findings rather than provider heuristics. The normal FakeProvider added no
extra matched detection on this corpus. The remaining FP is a category
mismatch; no negative scenario produced a finding.

## Implemented rules

`deterministic_rules.py` contributes stable rule identifiers:

- `DET-AUTH-GUARD-REMOVED`: removed PermissionError authorization guard.
- `DET-SQL-INTERPOLATION`: runtime data interpolated into SQL syntax.
- `DET-PATH-CONTAINMENT-REMOVED`: removed resolved-path containment guard.
- `DET-SENSITIVE-OUTPUT`: formatted secret-like parameter reaches output.
- `DET-STALE-VERSION-GUARD-REMOVED` and `DET-LOCK-ORDER-REMOVED`: removed
  stale-version and canonical-order concurrency protections.
- `DET-RESOURCE-NO-CLOSE`, `DET-BROAD-EXCEPT-DEFAULT`, `DET-INDEX-LEN`, and
  `DET-UNGARDED-LEN-DIVISION`.
- `DET-INPUT-MUTATION`, `DET-MUTABLE-DEFAULT`, and `DET-RETURN-CONTRACT`.

Each rule requires parseable Python, bounded complete context, and a changed
or hunk-local source location. Ambiguous security and concurrency patterns also
require explicit removed safeguard evidence from the diff; clean counterparts
in the corpus remain unreported.

## Architecture, safety, and compatibility

The rule layer is called beside the existing CFG/data-flow candidate extractor;
it is not a second findings pipeline. Candidate IDs remain stable only after
the existing evidence validator constructs findings. Context and GitHub
integration remain unchanged and no real provider, GitHub API, credentials, or
publication path was invoked.

## Validation

- Goal 21 corpus/oracles, static-analysis tests, and Goal 20 GitHub E2E tests:
  22 passed.
- Ruff lint passed for the changed modules.
- `git diff --check` passed.
- Full pytest suite passed (final offline run: approximately 21 seconds).

## Remaining limits and recommendation

The rules are intentionally syntax/structure bounded: they do not prove
framework-specific authorization, general taint propagation, lock schedules,
or arbitrary interprocedural contracts. The Goal 21 result is synthetic and
must not be interpreted as production prevalence. One positive case remains a
category mismatch. GO for a controlled external pilot only with dry-run output,
human review, and continued precision monitoring; no live publishing should be
enabled from this work.
