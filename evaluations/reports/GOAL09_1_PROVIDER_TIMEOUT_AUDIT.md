# GOAL 09.1 — Provider Timeout Root Cause Audit

## Scope and evidence boundary

This is a read-only audit of the provider path and existing GOAL 04/08
artifacts. No external request was issued, no historical result was modified,
and no provider cause is asserted beyond the available evidence.

The frozen historical corpus remains unchanged:
`evaluations/fixtures/real_world_verified_benchmark.json`, SHA-256
`17019e5f994b1bfc4ba4afe62992cf69bd829f509db3e075cf68ba9615759096`.

## Request lifecycle

```text
CodeReviewModule builds system + user prompt
        |
        v
ProviderRequest estimates input tokens
        |
        v
BudgetTracker.reserve_attempt() checks elapsed/request/token budget
and persists an attempt reservation when a UsageStore is attached
        |
        v
NvidiaProvider builds JSON payload and HTTPS urllib Request
        |
        v
urllib.request.urlopen(..., timeout=request_timeout_seconds)
        |
        +-- HTTP response -> body read -> JSON/schema parse -> usage reconcile
        |
        +-- 429/5xx/URLError/Timeout/OSError -> failure reservation -> bounded retry
        |
        v
ProviderAttempt records aggregate attempt latency, hashes, category/status/usage
        |
        v
Evaluation runner categorizes exception, records case latency, then validates
findings and computes matching metrics only for completed cases
```

## Observed GOAL 08 timeline

The authorized external A/B used 40 seconds per request, one retry, and a
720-second per-arm elapsed budget. Each arm made 15 attempts: one successful
attempt and seven cases with two attempts each.

| Observation | Baseline | Hybrid opt-in |
| --- | ---: | ---: |
| Completed cases | 1 | 1 |
| Timeout cases | 7 | 7 |
| Attempts | 15 | 15 |
| Retry attempts | 7 | 7 |
| Timeout-attempt latency | 40.28–41.32 s | 40.27–41.42 s |
| Successful-attempt latency | 16.15 s | 21.68 s |
| Budget exhaustion | 0 | 0 |

The repeated approximately-40-second attempt durations prove that the
configured value was applied to the observed failed attempts. They do not
identify whether the wait occurred during TCP/TLS connection, first byte, or
body read.

GOAL 04 provides a different failure mode: Windows socket error 10013 before
connection establishment. Provider attempt telemetry classified that event as
`connection_error`, while the legacy case-level text classifier labeled the
generic wrapper as `timeout`. GOAL 08 later received two valid model responses,
so its repeated timeout pattern is not evidence of the same pre-connection
socket block.

## What is measured today

| Stage | Current evidence |
| --- | --- |
| Prompt/context preparation | Included only in case-level `latency_ms`; no separate timer. |
| Budget reservation | Attempt count/tokens are recorded; no duration. |
| Connection, TLS, first byte | Not separately measured. |
| Response-body receipt | Not separately measured. |
| Parse/validation | Included only in case-level duration; no separate timer. |
| Whole attempt | `ProviderAttempt.latency_ms`. |
| Whole case | `CaseEvaluationResult.latency_ms`. |
| Usage | Provider usage when returned; local estimates for failed/usage-less responses. |

`urllib.request.urlopen` receives the single configured `timeout` argument.
The current adapter therefore has no distinct connection timeout, read timeout,
first-byte timer, or hard wall-clock deadline for the full attempt. Python's
socket timeout is passed through; phase attribution is unavailable in the
present telemetry.

## Failure classification and accounting

- HTTP 429 is rate-limited; 502/503/504 are server errors; other 4xx/5xx are
  client/server errors as applicable.
- `URLError`, `TimeoutError`, and `OSError` are classified by exception type
  and message text as `timeout` or `connection_error` in the provider.
- Invalid JSON/envelope/content becomes a provider error and is later detected
  by runner text classification as `invalid_response` where recognizable.
- The runner currently emits broad status `failed` and a separate
  `error_category`; it does not expose the unambiguous provider-state names
  requested by GOAL 09.
- Failed and uncertain attempts conservatively consume estimated input-token
  usage. Successful responses reconcile provider-reported usage when supplied.
  Failed-request estimates are reservations, not evidence of provider billing.

## Retry and deadline findings

Retries are limited by `max_retries`, total request budget, and token checks at
reservation. Retry-eligible statuses are 429, 502/503/504, and network/timeout
exceptions. Backoff is exponential (1 s, then powers of two) and honors a
bounded `Retry-After` up to 60 s. It has no jitter.

A timeout is treated as ambiguous: its reservation is recorded as `UNCERTAIN`,
but the same request is retried. This is appropriately conservative for quota
accounting, but it cannot prove provider-side idempotency and may duplicate
provider work or billing. The GOAL 08 result demonstrates the practical cost:
each failed case consumed two near-40-second waits.

`max_elapsed_seconds` is checked before an attempt reservation and after a
successful usage reconciliation. `fail_attempt()` does not check elapsed time,
and there is no per-case deadline. Consequently, a failed attempt or backoff
does not itself terminate a case because of a case deadline; the next
reservation normally catches a passed global deadline. This is a bounded but
coarse control.

## Supported hypotheses

1. **The GOAL 08 failures occurred during or before HTTP response completion.**
   Each affected attempt reached the configured 40-second socket timeout and
   no HTTP status or response hash was recorded.
2. **They are not proven to be connect-only failures.** GOAL 08 had successful
   NVIDIA responses, unlike the GOAL 04 Windows-10013 pre-connect pilot.
3. **The current observability cannot distinguish connection, TLS, first-byte,
   or read-body delay.** No phase timer exists.
4. **Case-level error labels can lose provider precision.** The provider's
   generic `network/timeout` wrapper causes the runner's message-based
   classifier to prefer `timeout`.

## Unverified hypotheses

- NVIDIA queueing, model inference latency, regional routing, TLS stalls, and
  response streaming behavior are not observable with the present transport.
- Provider-side processing or billing after a client timeout is unknown.
- A larger per-attempt timeout would improve completion; GOAL 08 does not test
  that counterfactual and it must not be assumed.

## Operational risks

- Retrying an ambiguous timeout may create duplicate provider work/cost.
- A single opaque timeout hides the transport phase that needs remediation.
- Persisting unredacted HTTP error excerpts in default evaluation output is a
  privacy risk; GOAL 08's external runner sanitized them before persistence.
- Completion-rate metrics are invalid when provider failures dominate and must
  remain distinct from false negatives.

## Proposed GOAL 09.2 implementation

Implement a provider-neutral, opt-in-safe observability extension and a
conservative deadline policy:

1. Extend attempt telemetry with optional phase durations and an explicit
   termination reason. Populate only data the transport can know; leave unknown
   phase fields null.
2. Preserve the single socket timeout for backward compatibility, add an
   optional attempt deadline and case deadline, and enforce elapsed checks on
   failed attempts/backoff boundaries. Do not silently raise defaults.
3. Carry structured provider error category/status into runner results instead
   of reconstructing it primarily from error strings; retain current `failed`
   status for compatibility while exposing an unambiguous operational state.
4. Add deterministic transport-mock tests for timeouts, HTTP errors,
   Retry-After, deadline termination, retry accounting, and secret-free
   telemetry.
5. Keep Behavioral Delta and Hybrid Static Selection disabled by default;
   neither is part of provider reliability behavior.

## Exact proposed file scope for GOAL 09.2

Modify:

- `src/deicide/providers/base.py`
- `src/deicide/providers/nvidia.py`
- `src/deicide/core/models.py`
- `src/deicide/core/config.py`
- `src/deicide/cli.py`
- `src/deicide/evaluation/models.py`
- `src/deicide/evaluation/runner.py`
- `tests/test_nvidia_failure_diagnostics.py`
- `tests/test_evaluation_observability.py`
- `tests/test_quota_and_usage.py`
- `tests/test_review_accuracy_baseline.py`
- `tests/test_config_and_validation.py`
- `tests/test_cli_and_reporting.py`

Create:

- `tests/test_provider_reliability.py`
- `evaluations/reports/GOAL09_2_PROVIDER_RELIABILITY.md`
- `evaluations/reports/GOAL09_3_STABILITY_BENCHMARK.md`

No provider, runner, quota, prompt, validator, corpus, ground truth, or
historical-result file will be changed without the next explicit approval.
