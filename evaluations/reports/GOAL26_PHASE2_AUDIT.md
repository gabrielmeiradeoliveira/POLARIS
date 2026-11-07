# GOAL 26 Phase 2 Detection Quality Audit

## Confirmed evidence

The repository contains eleven append-only history manifests and several archived result campaigns. Their TP/FP/FN values are evidence for their own recorded corpus and configuration only. The audit helper groups campaigns by corpus identifier, provider, model, and complete serialized configuration; it rejects aggregation across different groups.

The archived 20-case E2E A/B report records OFF as 12 TP, 1 FP, 0 FN and ON as 11 TP, 0 FP, 1 FN, with two and three failed executions respectively. This is exploratory evidence only: provider non-determinism and unequal operational failures prevent a causal claim about Behavioral Delta.

## Hypotheses to test before engine changes

1. Failed provider executions may bias apparent ON/OFF detection differences.
2. Context-budget reservation may reduce available conventional context in some configurations.
3. Category and location diagnostics should be analyzed per fixture before changing normalizers or matching.

## Limits and priorities

No historical campaign is rewritten or silently re-scored. The available records do not establish a controlled real-provider comparison because configurations and operational outcomes differ. First priority is a frozen, repeated paired experiment with identical corpus, model, budget, retry policy, and recorded failure states; only then should an engine change be proposed.
