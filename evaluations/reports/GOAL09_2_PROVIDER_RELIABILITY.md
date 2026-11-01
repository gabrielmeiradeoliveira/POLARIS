# GOAL 09.2 — Provider Reliability Implementation

## Status

Implemented offline only. No provider request, benchmark run, corpus edit,
ground-truth edit, historical-result edit, commit, or tag was made.

## Implemented controls

- Provider attempts now retain a structured failure category, HTTP status when
  available, retry count, configured attempt timeout, termination reason, and
  hash-only prompt/response identifiers.
- `transport_duration_ms` measures the transport invocation only. The existing
  `latency_ms` remains the full attempt duration and can include retry backoff.
- Provider failure bodies are redacted before error persistence. Provider error
  classification is propagated to evaluation results rather than reconstructed
  primarily from error text.
- Evaluation results retain the compatible broad `status` and add an
  `operational_state` such as `provider_timeout`, `provider_rate_limited`,
  `provider_connection_error`, `provider_invalid_response`,
  `provider_http_error`, `budget_exhausted`, `evaluation_error`, or `skipped`.
- Optional `attempt_deadline_seconds` and `case_deadline_seconds` are available
  through configuration, environment, and CLI. They are disabled by default.
  Attempt deadlines cap the timeout passed to the synchronous transport; case
  deadlines are checked at safe pre/post-call boundaries. They are cooperative
  elapsed-time controls, not forcible interruption of a blocked transport.
- Retries remain bounded by the existing request/token budgets and
  `max_retries`. The default retry behavior is unchanged: zero retries and no
  jitter. `Retry-After` is retained exactly within its existing bound.

Behavioral Delta and hybrid static selection remain disabled by default. No
static rule creates findings.

## Validation

- Focused provider/evaluation/CLI regression set after the review corrections:
  `31 passed`; the final provider-reliability audit subset passed `10` tests.
- Broader targeted reliability set before those corrections: `71 passed`.
- Complete offline suite, with a temporary directory outside the repository:
  `299 passed in 17.63s`.
- `git diff --check` completed without whitespace errors. Git emitted existing
  CRLF normalization warnings only.

The focused tests cover timeout and HTTP classification, exact Retry-After,
retry accounting, deadline/budget termination, redacted telemetry, transport
duration excluding backoff, skipped operational state, and CLI/configuration
propagation. A local `urlopen` fake also proves that the standard-library
transport exits its response context when a response read raises a timeout;
this is resource cleanup, not forced cancellation.

## Known limits

The standard-library synchronous transport cannot expose separate TCP, TLS,
time-to-first-byte, and body-read timers, nor can these controls cancel a
transport implementation that ignores its timeout argument. Those facts are
explicitly represented as unavailable rather than inferred. A provider-side
timeout remains ambiguous for billing and idempotency.

An unrelated GOAL 08.2 concern remains outside this approved scope: suppressed
context metadata can still be present in an internal validation path even when
it was removed from the LLM prompt. It was not changed here.
