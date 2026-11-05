# GOAL 09.3 — Benchmark Stability

## Status: PARTIAL — external authorization required

The offline phase is complete. No external provider call was made in this
phase, so this report does not claim an external stability improvement.

## Frozen inputs observed for this phase

- Corpus: `evaluations/fixtures/real_world_verified_benchmark.json`
- Corpus SHA-256:
  `17019e5f994b1bfc4ba4afe62992cf69bd829f509db3e075cf68ba9615759096`
- Cases: the eight `rw-*` historical fixtures in manifest order
- Evaluator-component manifest SHA-256:
  `0866649967db6b8565fbc4dfce658ecb1cab481699d6526a93a7e7dbebe9c05d`

The evaluator manifest is the SHA-256 of UTF-8, newline-terminated lines
`<relative path> <file SHA-256>` in this exact order:

```text
src/polaris/providers/base.py babfb48d74a65175dca81d91bef899d8bc6a3ac0ae3c06096ec80d657732af92
src/polaris/providers/nvidia.py 5c44c41c535784843456c8865da2538b9a911a964548963c5f177119ffd645ba
src/polaris/core/models.py be6cdb8a2de53d6000ef7a4cc30538a88259742058f4dd555f1e3220f729d072
src/polaris/core/config.py b4c08edc187d3493ea715e7972d620ebde943ad7e8cfeb7c644e785be56704c5
src/polaris/evaluation/models.py 4240dba92c8c3e6f95c69ed5f99873dd585169cc6dc07e5c9f1f0d2e72393637
src/polaris/evaluation/runner.py b92f2a733cc537d76a546d684f30de135f24ed6f36b1a3275846b051d98a7f4f
src/polaris/cli.py b67c663c4ebfc2728be9b32d320d93ffbbe69f023d77da27032e636a0be60a9e
```

## Offline evidence

The complete suite used an external temporary directory and passed:

```text
299 passed in 17.63s
```

The reliability regressions deterministically simulate timeout, HTTP failure,
Retry-After, retry, elapsed-budget, telemetry-redaction, and deadline paths.
They include an explicit local baseline-versus-reliability comparison: with a
non-binding deadline, matching/status/TP/FP outcomes are identical and only
the configured timeout supplied to the fake transport changes. A local timeout
still makes exactly two attempts under `max_retries=1` and ends as
`provider_timeout`. The standard transport's response context also exits on a
simulated read timeout. These tests show that result accounting distinguishes
provider failures from matching outcomes; they are not evidence that NVIDIA
will complete more requests.

## Required external checkpoint

An external campaign needs a new, explicit authorization identifying the
provider/model, the eight-case corpus transmission, timeout/retry/deadline
values, token/request/elapsed budgets, and the result-output location. The
GOAL 08 authorization does not authorize this campaign.

If authorized, compare the previous operational configuration against a
reliability-controlled configuration without changing corpus, prompts,
matching, Behavioral Delta, or hybrid-selection defaults. Preserve per-case
records and report completed, timeout, rate-limited, connection, HTTP,
invalid-response, budget-exhausted, and evaluation-error counts separately.
Provider failures must not be recalculated as false negatives.

The comparison can support a stability conclusion only if the two runs use the
same corpus hash, evaluator manifest, provider/model, matching policy, and
explicitly recorded budgets. Results remain inconclusive if completion is too
low or provider failures dominate.
