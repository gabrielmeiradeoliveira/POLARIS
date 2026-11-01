# GOAL 14 — Pipeline Optimization

## Measured offline path

The A/B/C fixture-backed runs report 17,166 estimated tokens, 0 ms provider latency, and 20/20 completed cases for every configuration. This path exercises parsing, token accounting, finding validation, matching, and reporting; it does not invoke external transport or a real LLM.

## Instrumentation

`AnalysisReport.stage_timings_ms` now separates diff reading, changed-file context reading, context preparation, per-module analysis (including the simulated provider), and finding validation. `ContextSummary.stage_timings_ms` separately records AST parsing, optional CFG/data-flow analysis, project indexing, dependency-graph construction, Behavioral Delta analysis, context selection, and total context preparation time. These fields are included in the JSON report and have zero-impact defaults for compatibility.

The context pipeline uses bounded project indexing, AST reuse within preparation, explicit context/token allowances, conservative duplicate removal, and safe fallbacks. Provider attempt telemetry separately records transport duration and retry information when a provider is used.

## Decision

No new persistent cache or aggressive early exit was added. The measured fake path showed no configuration delta, and introducing caching without a demonstrated bottleneck would risk stale-source behavior. The added summary counters make any future timeout/error and unassessed workload visible.

## Benchmark and limitations

The existing 30-file cyclic-import performance test verifies project indexing plus dependency-graph construction completes below one second. Integration coverage verifies the newly exposed timing stages with a two-file cross-file review. The fake A/B/C corpus validates deterministic token accounting, but it is not a representative provider-latency benchmark. Memory remains intentionally unreported because the standard-library implementation has no reliable cross-platform RSS collector; no claim of latency improvement is made.
