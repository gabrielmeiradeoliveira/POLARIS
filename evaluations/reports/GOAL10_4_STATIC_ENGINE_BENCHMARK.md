# GOAL 10.4 — Static Engine Offline Benchmark

## Method

On 2026-10-31, all arms used `evaluations/fixtures/code_review_corpus.json`,
the offline FakeProvider, end-to-end evaluation, and the same case limit of 10
(the corpus contains six cases). No external provider request was issued.

| Arm | Flag | Cases | TP / FP / FN | Prompt tokens | Result |
| --- | --- | ---: | ---: | ---: | --- |
| A baseline | none | 6 | 4 / 0 / 0 | 5,171 | completed |
| B GOAL 08 | `--hybrid-static-selection` | 6 | 4 / 0 / 0 | 5,171 | completed |
| C GOAL 10 | `--static-relevance-selection` | 6 | 4 / 0 / 0 | 5,171 | completed |

## Interpretation

The corpus has no selected cross-file context candidates for these cases, so
there is no opportunity for either optional selector to change prompt tokens.
The run proves compatibility for this fixture; it does **not** demonstrate the
experimental 15–25% additional saving target. A larger fixture set with
resolved direct consumers and constrained context budgets is required before
claiming token savings or detection-quality improvement.

The fake provider's deterministic detections are an offline compatibility
signal only, not evidence of frontier-model review quality.
