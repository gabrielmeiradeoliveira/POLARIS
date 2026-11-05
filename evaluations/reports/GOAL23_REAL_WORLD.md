# GOAL 23 — Realistic Python Generalization Benchmark

## Methodology and provenance

This is an original, synthetic-but-realistic corpus inspired by common Python application layers. It is **not** represented as a collection of defects extracted from named third-party projects. Every case was authored independently of POLARIS findings and is stored in `evaluations/fixtures/goal23_real_world/cases.json`.

The corpus was prepared against reference commit `e78778f` on the active workspace. GOAL 22 was modifying the engine concurrently, so any runtime result below is a provisional diagnostic, not a stable baseline or a comparison with GOAL 22. The fixture corpus must not be changed in response to these results.

Each case includes a stable identifier, domain/category, severity, primary file and modified line, before/after source, impact, local reproduction condition, and a behavioral oracle. Four positive and four negative cases include compiled dependent-module source, covering distributed contract changes rather than only single-function patterns.

## Corpus coverage

The corpus contains 40 independent cases: 20 positive regressions and 20 negative, contract-preserving changes. It covers these required domains:

| Domain | Positive | Negative |
| --- | ---: | ---: |
| REST input validation | 1 | 1 |
| Pagination and limits | 1 | 1 |
| Business services | 2 | 2 |
| Repositories / persistence | 2 | 2 |
| Authorization / permissions | 2 | 2 |
| Error handling | 2 | 2 |
| Cache / invalidation | 2 | 2 |
| Shared state / concurrency | 1 | 1 |
| Async-processing semantics | 2 | 2 |
| Serialization / deserialization | 2 | 2 |
| Module contracts | 2 | 2 |
| Resource cleanup | 1 | 1 |

The examples cover tenant isolation, idempotency, authorization ownership, privilege defaults, stale cache invalidation, cancellation reporting, retry limits, compatibility of numeric/nullable contracts, response status mapping, and cleanup. None were copied from GOAL 21.

## Executable oracles

All 40 cases have a local executable oracle. Positive cases execute both versions and demonstrate either an introduced exception/incorrect return, a lost authorization/visibility constraint, a duplicated idempotent effect, stale cache retention, shared mutable state, or skipped cleanup. Negative cases execute the same relevant contract against both versions and require matching behavior.

No network, external process, external provider, or real service/database operation is used. The test executes only static fixture code from this corpus in an isolated namespace. Resource cleanup uses an in-memory fake session.

## Offline evaluation

Command/configuration used for the provisional run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -c "from tests.test_goal23_real_world import _cases, _fixture; from polaris.evaluation.runner import evaluate_corpus; from polaris.providers.fake import FakeProvider; evaluate_corpus([_fixture(c) for c in _cases()], provider=FakeProvider(), force_end_to_end=True, behavioral_delta_enabled=False)"
```

| Metric | Provisional FakeProvider pipeline result |
| --- | ---: |
| Dataset / positive / negative | 40 / 20 / 20 |
| TP / FP / FN | 5 / 2 / 15 |
| Precision / recall / F1 | 0.7143 / 0.2500 / 0.3704 |
| Negative-case false-positive rate | 0.1000 |
| Completion rate | 1.0000 |
| Mean scenario time | 0.0 ms (below millisecond reporting resolution) |
| Deterministic-engine-only detections measured | Not established |
| Simulated-response-attributable detections | 5 validated matches in this run |
| Inconclusive / unassessed | 0 / 0 |

The five matches are attributed to the offline `FakeProvider` deterministic heuristics running through the public evaluation pipeline. They are not claims about a general LLM, projects in the wild, or a deterministic static engine. The metric is retained to make the current configuration reproducible only; the required comparative run should occur after GOAL 22 stabilizes with a separately recorded engine revision.

## Reproduction and acceptance criteria

Run the self-contained checks:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .pytest-goal23-real-world tests/test_goal23_real_world.py -q
.\.venv\Scripts\python.exe -m ruff check tests/test_goal23_real_world.py
```

External validation should require: independent reviewer confirmation of the before/after behavioral claims; a pinned post-GOAL-22 commit/configuration; no fixture changes after evaluator results are observed; per-case diagnostics; and a separate record for deterministic analysis versus provider-simulated results. A realistic-project precision claim requires a provenance-backed external corpus, not these fixtures alone.

## Methodological limits and overfitting risks

The cases are intentionally focused executable micro-scenarios, so they do not estimate production prevalence, exploitability, latency, or framework-specific behavior. Their source is more realistic than a syntax-only suite but remains synthetic. The public evaluation adapts each primary changed module to an `EvaluationFixture`; related-module material is compiled and oracle-documented but is not a full package installation.

Overfitting risks include adding simple pattern detectors for known source snippets, treating FakeProvider outputs as independent evidence, and modifying fixtures after seeing current scores. Mitigations are stable IDs, behavior-oracle tests, balanced negatives, distributed-contract cases, documented provenance limits, and deferral of the GOAL 22 comparison.
