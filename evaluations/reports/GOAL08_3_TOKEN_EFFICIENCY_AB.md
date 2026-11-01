# GOAL 08.3 — Offline Token Efficiency A/B

## Status

The offline comparison and an authorized external NVIDIA A/B run were
completed. The external run is operationally valid but insufficient to compare
detection quality because seven of eight cases timed out in each arm. It does
not establish quality equivalence or superiority.

## Reproducible setup

- Corpus: `evaluations/fixtures/real_world_verified_benchmark.json`
- Frozen corpus SHA-256: `17019e5f994b1bfc4ba4afe62992cf69bd829f509db3e075cf68ba9615759096`
- Cases: the eight `rw-*` historical introducing fixtures
- Behavioral Delta: disabled in both arms
- Context budget: 2,000 estimated tokens per case
- Token method: DEICIDE's existing `ceil(characters / 4)` estimator. A real
  tokenizer was unavailable in the audited environment.
- Arm A: existing context behavior, hybrid static selection disabled
- Arm B: identical context preparation, hybrid static selection enabled

For each fixture, the production-parity evaluator materialized the AFTER
source in an external temporary directory, constructed the same review prompt
for each arm, and counted `SYSTEM_PROMPT + user prompt`. The only intended
difference was final supplementary-context suppression.

## Results

| Case | A input tokens | B input tokens | Saved | Suppressed snippet |
| --- | ---: | ---: | ---: | --- |
| rw-requests-2023-proxy-authorization | 1511 | 1124 | 387 | requests/sessions.py:1-18 |
| rw-requests-jsondecodeerror-pickle | 1188 | 944 | 244 | src/requests/exceptions.py:1-6 |
| rw-requests-super-len-unicode | 1127 | 905 | 222 | src/requests/utils.py:1-8 |
| rw-urllib3-cookie-cross-origin | 1059 | 854 | 205 | src/urllib3/util/retry.py:1-3 |
| rw-urllib3-proxy-redirect-origin | 1357 | 1081 | 276 | src/urllib3/poolmanager.py:1-7 |
| rw-urllib3-port-zero | 1115 | 880 | 235 | src/urllib3/util/url.py:1-8 |
| rw-urllib3-invalid-timeout-error | 1243 | 958 | 285 | src/urllib3/connectionpool.py:1-9 |
| rw-werkzeug-debugger-trusted-host | 1199 | 920 | 279 | src/werkzeug/debug/__init__.py:1-7 |
| **Total** | **9799** | **7666** | **2133** | **8 of 8** |

Input-token reduction: **21.77%** (`2133 / 9799`). The local selection
metadata is not inserted into the model prompt, so its measured prompt cost is
**0 tokens**. Supplementary-context-only savings were 1,237 estimated tokens;
the remaining measured reduction is the supplementary wrapper and formatting
that disappear when the section becomes empty.

No fallback was triggered on these eight fixtures because each removed snippet
met the exact numbered-line and source-text proof. Unit tests exercise the
fallback paths for text mismatch, missing primary lines, incomplete spans, and
noncanonical serialization.

## Preservation checks

- All eight expected finding file paths remained present in the optimized
  prompt.
- The target changed-line spans remained in the primary diff/context payload.
- The eight historical `expected_findings[].evidence` strings were not literal
  prompt text in either arm: they describe later fixing commits and tests, and
  are intentionally corpus metadata excluded from model input. This is a
  pre-existing baseline property, not an optimization regression.
- Direct/indirect context is retained unless it is a proved `changed_symbol`
  duplicate. Tests explicitly retain a direct caller.

## Offline regression verification

```text
python -m pytest -o addopts= -p no:cacheprovider --basetemp C:\Users\gabri\AppData\Local\Temp\deicide-goal08-full -rA
```

Result: `287 passed in 18.67s`.

Fixture integrity is covered by the complete suite, including the historical
round-trip tests. No corpus, ground truth, validator, historical result, or
matching rule was edited.

## Recommendation

Keep hybrid static selection **opt-in and disabled by default**. The offline
result is safe under the tested proof rule and provides measurable savings, but
falls below the GOAL's experimental 25–40% input-token target. It also cannot
establish detection-quality equivalence. The authorized external A/B recorded
below also had insufficient completion, so a future authorized rerun with the
same controls and materially higher completion is required before considering
default activation.

## Authorized external A/B run

### Pre-transmission safety gate

The same eight materialized production-parity prompts from both arms were
checked before transmission. The static scan found zero matches for private
key blocks, AWS access keys, GitHub tokens, bearer tokens, or credential
assignment patterns. The corpus remains the manifest's minimized,
documented-historical-excerpt corpus; its SHA-256 was rechecked before the
run. The resulting artifacts contain sanitized provider errors and hash-only
observability. They contain no credentials, authorization headers, prompts,
raw model responses, or provider error bodies.

### Fixed configuration

- Provider/model: NVIDIA / `minimaxai/minimax-m3.1-flash`
- Corpus: the same eight manifest case IDs, in manifest order
- End-to-end and production-parity: enabled
- Behavioral Delta: disabled
- Matching: manifest defaults (exact file path, overlapping location, primary
  or allowed alternative category, non-strict severity)
- Context budget: 2,000 estimated tokens
- Per-arm budget: 16 attempts, 100,000 tokens, 40-second request timeout,
  one retry, 720 seconds elapsed time
- Arm A: hybrid selection disabled; Arm B: hybrid selection enabled

Results are stored separately in
`evaluations/results/goal08_3_external_ab_20261031T163715/baseline/` and
`evaluations/results/goal08_3_external_ab_20261031T163715/hybrid_opt_in/`.

### External results

| Metric | A: baseline | B: hybrid opt-in |
| --- | ---: | ---: |
| Completed cases | 1 / 8 | 1 / 8 |
| Provider failures / timeouts | 7 / 7 | 7 / 7 |
| Attempts (including retries) | 15 | 15 |
| Retries | 7 | 7 |
| Budget-exhausted cases | 0 | 0 |
| TP / FP / FN among completed cases | 0 / 0 / 1 | 1 / 0 / 0 |
| Prompt tokens (provider-estimated) | 18,402 | 14,539 |
| Completion tokens (provider-estimated) | 202 | 487 |
| Total tokens (provider-estimated) | 18,604 | 15,026 |
| Aggregate latency | 587,676 ms | 593,258 ms |

Observed external prompt-token reduction was **20.99%**
(`3,863 / 18,402`). This is consistent in direction with the offline 21.77%
result, but the request-level totals include retries and different successful
cases. Total-token reduction (19.23%) is not a quality or cost comparison,
because output lengths differ.

The baseline completed only `rw-urllib3-invalid-timeout-error`, which was
missed. The optimized arm completed only `rw-requests-super-len-unicode`,
which was detected. The other seven cases in each arm were recorded as
provider timeouts, not false negatives, exactly as required by the failure
policy. There are no negative controls in this eight-case corpus, so no
external false-positive rate can be measured here.

### External limitations and decision

The 87.5% timeout rate in both arms is an infrastructure/result-completeness
failure. Since the completed case differs by arm, the TP/FN figures cannot be
attributed to the hybrid selection strategy. The experiment demonstrates that
the opt-in path can be exercised against the authorized provider under the
fixed configuration and still reduces input tokens, but it provides no
reliable quality comparison. Keep the flag disabled by default. A future
authorized rerun would need materially higher completion before it could
support a quality decision.

This run intentionally used the GOAL 08.2 worktree rather than the historical
payload commit, because the experiment compares its new opt-in behavior. That
means the evaluator-component hashes in the frozen GOAL 07.2 manifest do not
describe this worktree verbatim. With the flag disabled, the prompt-level
baseline behavior was regression-tested offline; nevertheless, this is a
separate reproducibility limitation from the immutable historical release.
