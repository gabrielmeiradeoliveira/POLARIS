# GOAL 24 Token Efficiency

The current review path is diff-first and reserves output tokens through `BudgetTracker`; context selection, truncation, and estimated usage remain observable in `ContextSummary`. The provider-failure fallback avoids a retry loop and preserves deterministic findings without any new token use.

No before/after token-economy percentage is asserted in this pass because no controlled equivalent-context experiment was run. Estimated tokens must not be presented as billed usage. A post-GOAL-22 experiment should compare preserved evidence, selected context, estimated tokens, latency, and degradation cases.
