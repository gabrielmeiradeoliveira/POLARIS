# POLARIS E2E Behavioral Delta A/B Report

## Executive summary

This single-run, 20-case synthetic E2E comparison is **partially valid**: all twelve positive
fixtures completed, but provider timeouts left two OFF and three ON negative fixtures incomplete.
Strictly scored completed results favour neither arm decisively. OFF found all 12 positive defects
but produced one false positive; ON missed fixture 05 but produced no completed-case false positive.

**Recommendation: PROMISING BUT INCONCLUSIVE.** Behavioral Delta must remain disabled by default.

## Configuration

Both arms used NVIDIA / `minimaxai/minimax-m3.1-flash`, E2E mode, production-parity mode,
2,000 supplementary-context tokens, a 500-token Delta reservation, timeout 40 seconds, one retry,
10 requests, 50,000 tokens, and 1,200 seconds per five-case batch. The only intentional arm
difference was `--no-behavioral-delta` versus `--behavioral-delta`. Batches ran OFF/ON, ON/OFF,
OFF/ON, ON/OFF. Each JSON file is a single canonical provider execution.

## Completion and metrics

| Metric | OFF | ON |
|---|---:|---:|
| Completed / failed cases | 18 / 2 | 17 / 3 |
| Strict TP / FP / FN | 12 / 1 / 0 | 11 / 0 / 1 |
| Strict precision | 92.31% | 100.00% |
| Strict recall | 100.00% | 91.67% |
| Strict F1 | 96.00% | 95.65% |
| Category mismatches | 0 | 0 |
| Positive cases detected | 12 / 12 | 11 / 12 |
| Completed negative cases with FP | 1 / 6 | 0 / 5 |
| Provider tokens | 37,973 | 38,412 |
| Total latency | 477,358 ms | 526,891 ms |

Diagnostic location-based metrics equal strict metrics here because neither arm produced a
category mismatch. Failures are excluded from TP/FP/FN rather than interpreted as misses.

## Paired results

| Cases | OFF | ON | Interpretation |
|---|---|---|---|
| 01–04 | TP | TP | detected by both |
| 05 | TP | FN | ON-only regression |
| 06–12 | TP | TP | detected by both |
| 13–15 | clean, no FP | clean, no FP | no measurable difference |
| 16 | FP | provider timeout | comparison unavailable; not evidence of an ON improvement |
| 17 | clean, no FP | clean, no FP | no measurable difference |
| 18–19 | provider timeout | provider timeout | unavailable in both arms |
| 20 | clean, no FP | clean, no FP | no measurable difference |

OFF exclusively detected fixture 05. No fixture was validly detected exclusively by ON.
OFF introduced one false positive on fixture 16; ON's corresponding result timed out, so it cannot
be credited with removing it.

## Infrastructure status

Timeouts occurred after the configured retry on OFF fixtures 18 and 19, and ON fixtures 16, 18,
and 19. They are reported as `error_category=timeout` in the canonical JSON files. No completed
case had a provider failure, and no infrastructure failure was scored as a model detection error.

## Validity threats

- Only 20 synthetic fixtures and a single run per arm; differences are not statistically significant.
- Provider/model nondeterminism remains possible despite temperature zero.
- Alternating batch order reduces but does not remove temporal/provider-load bias.
- The fixed 500-token Delta reservation preserves conventional-context parity, but constrains Delta.
- Strict category/location scoring can differ from semantic usefulness; no category mismatches occurred here.
- Incomplete negative cases prevent a complete false-positive comparison.

## Artifacts

Canonical results are `b01_off.json` through `b04_off.json` in this directory. The empty
`e2e_context_ab_20case_v1` directory is an aborted pre-entrypoint attempt and contains no provider
result; the v2 directory is authoritative. Historical benchmark directories were not modified.
