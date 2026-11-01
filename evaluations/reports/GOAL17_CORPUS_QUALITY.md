# GOAL 17 Corpus Quality

## Selected A/B/C corpus

`evaluations/fixtures/code_review_corpus.json` SHA-256:
`e71a50d997302ce782c0eaec924cc1e2293df4f6cdb16d074c32939662c3f511`.

| Class | Cases | Verification |
|---|---:|---|
| Real verified defect introductions | 4 | `fully_verified` |
| Verified clean code / false-positive controls | 2 | `fully_verified` |
| Synthetic cases used in this A/B/C result | 0 | N/A |
| Inconclusive cases used in this A/B/C result | 0 | N/A |

The corpus is balanced enough to exercise detection and clean-negative behavior,
but six cases are not representative of production repositories. Frozen fixtures,
oracles, and historical manifests were not changed.

## Repository-wide fixture taxonomy

| Required class | Recorded source | Treatment |
|---|---|---|
| Verified real bugs | selected four defect introductions | Eligible for strict detection metrics |
| Verified bug fixes | `bug_introduction_benchmark.json` clean-fix case | Retained as a correction control, not a live defect positive |
| Correct code | selected two clean-negative controls | Eligible for false-positive measurement |
| Synthetic | behavioral/context benchmark fixtures | Kept separate as synthetic controls |
| Inconclusive | reference-modeled legacy cases | Not asserted clean or used as verified negatives |

## Additional inventory and limitations

- `real_world_verified_benchmark.json`: eight documented verified public-fix
  positives, SHA-256 `17019e5f994b1bfc4ba4afe62992cf69bd829f509db3e075cf68ba9615759096`;
  it has no negatives and cannot estimate precision alone.
- `behavioral_regression_benchmark.json` and `end_to_end_context_benchmark.json`
  are synthetic controls and must not be combined with real-provider claims.
- Existing clean-negative controls remain provenance-limited; no finding is not
  evidence by itself that an unverified case is truly clean.
