# GOAL 25 NVIDIA Preflight

Status: completed before the A/B run. This document contains metrics and configuration identifiers only; it contains no source, prompt, response body, credential, or endpoint authorization value.

## Fixed configuration

- Provider: NVIDIA.
- Model: `minimaxai/minimax-m3.1-flash`.
- Base endpoint family: NVIDIA Integrate API.
- Timeout: 90 seconds.
- Global execution ceilings: 60 requests, 50,000 input tokens, 20,000 output tokens, 8,000 input tokens/request, and 2,000 output tokens/request.
- Retry ceiling: two attempts per scenario including the initial attempt.
- A/B-specific ceiling: 12 additional NVIDIA requests. The frozen 12-case sample therefore disables retries rather than silently exceeding this narrower cap.
- Concurrency: sequential (one active request).

## Offline validation

The GOAL25 runner tests passed: 3 tests before telemetry hardening and 4 tests after it. They verify the frozen balanced sample, the global and A/B-specific budget ceilings, metrics-only serialization, and rejection of unsafe result fields. Provider reliability and quota tests also passed (36 tests), including separate input/output cap reservation and missing-usage failure handling.

## Minimal provider health request

One bounded NVIDIA health request was completed before the A/B attempt. It did not transmit repository source or a benchmark fixture.

| Metric | Observed |
| --- | ---: |
| Attempts | 1 |
| Reported input tokens | 186 |
| Reported output tokens | 128 |
| Reported total tokens | 314 |
| Usage reported by provider | yes |
| Request timeout ceiling | 90 s |

This request is counted as preflight consumption in the experiment record. Its 314 reported tokens are below every individual and cumulative ceiling.

## Preflight limitation

The first real hybrid process later returned no verifiable telemetry payload. The runner has now been hardened to persist only metrics-only completed results and to enforce the 12-request A/B cap, but no real run was repeated because the earlier process's request/token consumption cannot be reconstructed safely.
