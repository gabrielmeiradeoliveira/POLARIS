# GOAL 17 Accuracy Engineering

## Reproducible improvements

The budget-cutoff regression was corrected so later fixtures become explicit
unassessed cases rather than absent rows. Operational interruption is not an FN.

Strict TP/FP/FN require file, tolerant line location, permitted category, and,
when enabled, exact severity. Location-only category diagnostics remain separately
reported as detection precision/recall; severity and category mismatches do not
improve strict metrics.

## Precision safeguards retained

- deterministic evidence and source-location validation;
- one-to-one matching and semantic deduplication;
- conservative severity normalization;
- clean-negative controls;
- preserved selectable baseline.

No offline A/B/C false positive or false negative was reproducible in this
deterministic six-case control, so no fixture-specific rule tuning was performed.
Wilson 95% intervals are unavailable below 20 observations by design.
