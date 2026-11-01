# Evaluation Validation History

`evaluations/history/manifests/` contains compact, append-only JSON manifests for benchmark runs. Each manifest has a run ID, UTC timestamp, Git commit, DEICIDE/provider/model metadata, configuration, corpus hash, operational limits, aggregate metrics, sanitized per-finding decisions, and integrity hashes.

Use the evaluation CLI with `--history-dir`, `--history-run-id`, `--history-configuration`, and `--history-corpus-kind` to create a manifest and immutable run-scoped trend reports. A duplicate run ID is rejected, and an existing run is never overwritten.

Only safe, reproducible manifests and small trend reports belong in version control. `evaluations/history/artifacts/` is ignored and is reserved for bulky or potentially sensitive local artifacts. Retain those artifacts only for the minimum period required by the approved evaluation protocol; remove them through the organization-approved retention process, never by rewriting history manifests.

Qualitative finding confidence (`HIGH`, `MEDIUM`, `LOW`) is recorded as a label, not a probability. Brier scores and reliability bins are available only when explicitly numeric probabilities and enough assessed samples are present. A confidence label never establishes code safety or the absence of vulnerabilities.
