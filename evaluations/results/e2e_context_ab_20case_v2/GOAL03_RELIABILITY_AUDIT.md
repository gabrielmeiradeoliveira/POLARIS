# GOAL 03 — Detection Reliability & Generalization Audit

## Status

Complete. No additional NVIDIA calls were made.

## Independent reconstruction

Canonical JSON files contain exactly 20 unique IDs per arm. Recalculation confirms OFF: 18
completed, 2 failed, TP/FP/FN 12/1/0, precision 12/13 (92.31%), recall 12/12 (100%), F1 96.00%.
ON: 17 completed, 3 failed, TP/FP/FN 11/0/1, precision 100%, recall 11/12 (91.67%), F1 95.65%.
Category mismatches are zero. Canonical batch totals remain 37,973 OFF and 38,412 ON tokens,
with 477,358 ms and 526,891 ms aggregate latency respectively.

Paired completed cases are 01–15, 17, and 20, except that fixture 05 is TP OFF/FN ON and
fixture 16 cannot be compared because ON timed out. Fixtures 18–19 timed out in both arms.
Timeouts are excluded from detection metrics.

## Fixture 05

Verified facts: OFF emitted one `null_handling` candidate, validated at `plugins/custom.py:4` and
strictly matched the expected defect. ON completed successfully but emitted zero candidates;
there were no rejected candidates, category mismatches, line mismatches, or budget interruption.
ON recorded 54,674 ms and estimated token usage; OFF recorded 32,220 ms and provider-reported
usage. The canonical artifacts do not retain raw provider text or serialized prompt blocks.

Conclusion: matching and validation did not cause the miss. Provider output absence is verified.
Whether Delta context representation, prompt interference, or model nondeterminism caused that
absence is an unresolved hypothesis; this single run cannot distinguish them. No fixture-specific
rule or detection change is justified.

## Timeout classification

Fixtures 18 and 19 timed out after one retry in both arms. Fixture 16 timed out after one retry
only ON. Each error is serialized as `error_category=timeout` with the provider message
`network/timeout error after 1 retries`. Durations near 81.5 seconds are consistent with two
40-second client transport attempts plus small overhead. This supports client timeout/retry
exhaustion against provider latency; it does not prove a local provider defect, rate-limit event,
or global-budget exhaustion. No HTTP status or Retry-After was present.

## Reliability correction

`CaseEvaluationResult.usage` previously referenced the shared tracker's cumulative usage, making
per-case token comparisons misleading. Evaluation now stores the incremental usage delta for each
case while `EvaluationSummary.usage` remains aggregate. This changes diagnostics only: budgets,
provider behavior, matching, and historical canonical JSON artifacts are unchanged.

## Generalization limitations

- Twenty synthetic, compact Python fixtures are not representative of repository-scale reviews.
- Repeated contract, nullable return, callback, and state patterns can reward pattern recognition.
- Dependency graphs are deliberately small and complete within `file_contents`.
- Location matching permits adjacent lines, appropriate for hunk movement but not proof of semantic equivalence.
- Fixed Delta reservation improves arm parity but may underrepresent Delta in larger repositories.
- Raw provider prompts/responses were not persisted, limiting post-hoc causal attribution.

## GOAL 04 recommendation

Prioritize a broader, versioned corpus of real multi-file changes and optional privacy-safe prompt
fingerprints/response hashes for forensic reproducibility. Repeat the A/B with independent runs,
counterbalanced order, and a timeout policy experiment. Do not enable Delta by default based on
these results.
