# GOAL 21 — Security & Adversarial Benchmark

## Scope and reproducibility

This benchmark is intentionally independent of production code and GOAL 20. Its 30 scenario manifest is at `evaluations/fixtures/goal21_adversarial/scenarios.json`; the integrity, oracle, and offline-evaluation harness is `tests/test_goal21_adversarial.py`.

Every scenario contains local synthetic Python `before` and `after` code, an expected defect or verified clean change, location, POLARIS category, justified severity, behaviour explanation, and declarative oracle. The fixture material contains no credentials, private code, network access, subprocess use, or destructive operation.

Run the reproducible offline validation with:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .pytest-goal21-adversarial tests/test_goal21_adversarial.py -q
.\.venv\Scripts\python.exe -m ruff check tests/test_goal21_adversarial.py
```

## Corpus

There are 15 positive defect introductions and 15 negative changes. Twenty-nine scenarios have executable before/after oracles. The deadlock-order case is deliberately structural-only: executing competing lock acquisition would make the test potentially hang, so its limitation is explicit rather than hidden.

| Coverage area | Positive | Negative / preserving counterpart |
| --- | ---: | ---: |
| Authorization bypass | 1 | 1 |
| SQL interpolation / parameter binding | 1 | 1 |
| Path traversal | 1 | 1 |
| Sensitive output | 1 | 1 |
| Race / stale version | 1 | 1 |
| Deadlock lock ordering | 1 | 0 |
| Resource lifetime | 1 | 1 |
| Exception masking | 1 | 1 |
| Conditional initialization | 1 | 1 |
| Cross-file-style return contract | 1 | 2 |
| Input mutation / mutable defaults | 2 | 2 |
| Boundary behaviour | 2 | 2 |

The resource oracle replaces `open` with a local fake handle and checks closure directly; it does not touch real files beyond pytest-managed temporary fixtures. Other applicable oracles execute the before and after functions, checking exceptions, return values, output exposure, traversal containment, stale-version rejection, mutation, and default-state isolation.

## Offline evaluation results

The observed run used `evaluate_corpus(..., provider=FakeProvider(), force_end_to_end=True, behavioral_delta_enabled=False)`. This is an offline simulated-provider pipeline, not evidence of an external model or a pure static-analysis detector.

| Metric | Result |
| --- | ---: |
| Dataset / positive / negative | 30 / 15 / 15 |
| True positives | 3 |
| False positives | 1 |
| False negatives | 12 |
| Precision | 0.7500 |
| Recall | 0.2000 |
| F1 | 0.3158 |
| Negative-case false-positive rate | 0.0000 |
| Static-engine-only detections observed | 0 |
| FakeProvider deterministic-heuristic detections | 3 |
| Undetected expected defects | 12 |
| Inconclusive cases | 0 |

The three matched findings were unclosed-resource handling, mutable default state, and unguarded average. The conditional-initialization case produced one wrong-category finding, counted as a false positive and false negative under the strict expected-category ground truth. No negative case produced a finding, so the negative false-positive rate is zero in this small corpus.

| Positive category | TP / cases |
| --- | ---: |
| Resource management | 1 / 2 |
| State mutation | 1 / 2 |
| Boundary condition | 1 / 2 |
| Logic error | 0 / 2 |
| Concurrency | 0 / 2 |
| Error handling | 0 / 2 |
| Type mismatch | 0 / 2 |
| Null handling | 0 / 1 |

## Main gaps and prioritized opportunities

1. **Authorization, SQL, traversal, and data exposure** — high impact, 4/4 missed; deterministic taint/source-sink rules are feasible for constrained Python frameworks, while realistic coverage needs framework and interprocedural context.
2. **Concurrency and deadlocks** — high impact, 2/2 missed; lock-order graphs and stale-version patterns are partly deterministic but need cross-function and cross-file context. Dynamic schedule exploration is more expensive and should remain bounded.
3. **Return contracts and cross-file dependencies** — high impact, 2/2 missed; infer type/nullable contracts from callers and annotations deterministically, then use LLM interpretation only for ambiguous semantic contracts.
4. **Control-flow initialization and off-by-one logic** — medium/high impact, 2/2 missed (with one category false positive); CFG and definite-assignment analysis can cover many cases deterministically without LLMs.
5. **Exception and sensitive-data semantics** — medium impact, 2/2 missed; broad exception analysis and configurable sensitive-source/redaction rules are deterministic starting points, with LLM support useful for business-specific logging context.

## Methodological limits

The corpus is deliberately small, synthetic, and executable; it is not a prevalence estimate for production projects. The `FakeProvider` has deterministic pattern heuristics, so its three matches must not be described as general LLM performance or static-engine performance. A finding supplied by a provider is only counted when the existing evaluator validates its location and category against the fixture ground truth. Metrics are therefore reproducible for this codebase/version, not a release-quality claim.
