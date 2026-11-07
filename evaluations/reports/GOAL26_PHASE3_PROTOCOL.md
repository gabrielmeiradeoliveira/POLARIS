# GOAL 26 Phase 3 Paired Experiment Protocol

The campaign contains 20 frozen E2E cases in two arms, OFF and ON, for 40 initial executions. Retries are disabled. Both arms must use the provider, model, corpus hash, order, context limits, request timeout, quota scope, and token budget recorded in the campaign manifest.

The global ceiling is 100,000 tokens. The runner stops before an execution that would exceed that ceiling and preserves all prior records. A case is comparable only when both arms completed; timeout, quota exhaustion, deadline, interruption, or provider error excludes its pair from comparative TP/FP/FN metrics.

The prior campaign consumed 76,385 tokens across both arms. That is historical observation, not a completion guarantee. No real-provider execution is authorized by this protocol.
