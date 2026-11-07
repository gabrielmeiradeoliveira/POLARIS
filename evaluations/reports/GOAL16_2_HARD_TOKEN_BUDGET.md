# GOAL 16.2 — Hard Token Budget Enforcement

## Pre-edit Git baseline

```text
## feature/nvidia-benchmark...origin/feature/nvidia-benchmark [ahead 3]
 M AGENTS.md
 M calculator.py
 D context_test.py
?? .agents/task-baselines/
?? .agents/workflows/orchestration-matrix.md
?? evaluations/fixtures/bug_intro_03_temp.json
?? evaluations/fixtures/bug_intro_04_05_temp.json
?? evaluations/fixtures/clean_negatives_temp.json
?? evaluations/reports/baseline_mvp1_4_minimax_m3_1_flash.md
?? evaluations/results/
?? scratch/
```

The pre-existing changes above are outside GOAL 16.2 and are preserved.

## Root cause

Before this change, the NVIDIA adapter reserved only locally estimated prompt
tokens. It sent the module's fixed 4,096-token completion allowance and added
provider-reported completion usage only after the response. Consequently, a
completion could cross `max_total_tokens` after it had already been generated.

## Reservation policy

Before every NVIDIA attempt, POLARIS now calculates:

`remaining = max_total_tokens - recorded_total_tokens`

It requires capacity for the estimated prompt, a conservative 256-token
tokenizer-variance margin, and the protocol minimum completion of 64 tokens.
The outgoing `max_tokens` is the smaller of the requested model cap and the
remaining reservable output. The same calculation runs for retries after their
conservative prompt charge. The non-bound provider path, including
FakeProvider through `CodeReviewModule`, uses the same output-cap calculation.

Actual provider usage still reconciles into metrics and persistent quota
records. If reported usage exceeds the reservation, the overage is recorded
and the run stops before another attempt.

## Residual limitation

No local character-based token estimator can prove an absolute provider-token
ceiling when the provider may tokenize a prompt differently by an unbounded
amount. The 256-token margin materially reduces the risk but does not make a
strict external 6,000-token guarantee. A true hard guarantee would require
authoritative preflight tokenization from the selected provider, or a provider
contract that enforces a total input-plus-output cap.

## Pilot decision

`NO-GO` for a pilot advertised as a strict three-request, 6,000-token ceiling.
The new policy prevents avoidable output over-allocation and blocks insufficient
budget before transport, but the residual provider-tokenizer variance means an
external provider can still report more prompt tokens than the local estimate
plus margin. No NVIDIA request was made during GOAL 16.2.
