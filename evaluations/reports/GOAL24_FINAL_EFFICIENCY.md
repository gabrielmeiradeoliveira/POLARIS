# GOAL 24 Final Efficiency

## Controlled A/B measurement

Configuration: 40 GOAL23 development fixtures, controlled empty `FakeProvider`, end-to-end pipeline, identical fixture order and budgets. The only changed setting was behavioral-delta serialization.

| Configuration | Estimated prompt tokens | Completion tokens | TP / FP / FN | F1 |
| --- | ---: | ---: | ---: | ---: |
| Behavioral delta disabled | 33,115 | 40 | 18 / 0 / 2 | 0.9474 |
| Behavioral delta enabled | 35,060 | 40 | 18 / 0 / 2 | 0.9474 |

The enabled configuration added 1,945 estimated prompt tokens (5.87%) with no deterministic detection delta on this corpus. The regression test records the comparison and verifies that both usage values are estimates.

This supports the existing offline default of disabling behavioral deltas for deterministic-only evaluation. It does not establish that deltas lack value with a real provider or on a different corpus.

## Decision

These are heuristic prompt estimates, not billed provider tokens or API cost. A GOAL25 comparison must use equivalent prompts, fixed provider configuration, and separately report estimated versus provider-reported usage.
