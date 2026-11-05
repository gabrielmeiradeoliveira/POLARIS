# GOAL 16 NVIDIA Experiment Protocol

## Authorization boundary

This protocol is frozen before external calls. Its real-run command must not
be executed without a separate explicit authorization because it sends fixture
code to NVIDIA and may consume credits.

## Registered experiment

| Item | Frozen value |
|---|---|
| Repository commit evaluated | `7bf19d038703fe27e1857814d370e6b5556a841c` |
| POLARIS version | `0.1.0` |
| Provider / exact model | `nvidia` / `minimaxai/minimax-m3.1-flash` |
| Positive corpus / SHA-256 | `real_world_verified_benchmark.json` / `17019e5f994b1bfc4ba4afe62992cf69bd829f509db3e075cf68ba9615759096` |
| Evaluation mode | `--end-to-end --production-parity --strict-severity` |
| Behavioral Delta | Disabled in every arm |
| Temperature | 0.0 in `CodeReviewModule` |
| Retry policy | At most one retry for timeout, 429, 502, 503, or 504 |
| Deadlines | 45 s request and attempt, 90 s case, 1,800 s arm elapsed ceiling |
| Per-arm limits | 24 requests, 50,000 total tokens |
| Persistence | Unique append-only run ID and run-scoped trend reports |

| Arm | Hybrid selection | Static relevance | Behavioral Delta |
|---|---|---|---|
| A — baseline | disabled | disabled | disabled |
| B — hybrid | enabled | disabled | disabled |
| C — relevance | disabled | enabled | disabled |

The primary metrics are strict precision, recall, F1, and completion rate.
Initial targets are 90%, 80%, 85%, and 95% respectively. They are
experimental gates, not a release declaration; the selected positive-only
corpus cannot prove precision or F1 representativeness.

Failures, timeouts, budget exhaustion, skipped, and unassessed cases are
preserved as such. They are not false negatives. A stopped run is retained;
any replacement gets a new run ID and is reported separately.

## Offline A/B/C command

This command was executed with unique A/B/C run IDs and their respective
selection flags, always with `--history-corpus-kind synthetic`.

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -m polaris evaluate `
  --provider fake --model fake-deterministic-v1 `
  --fixtures evaluations\fixtures\real_world_verified_benchmark.json `
  --end-to-end --production-parity --strict-severity --no-behavioral-delta `
  --no-hybrid-static-selection --no-static-relevance-selection `
  --max-requests 24 --max-tokens 50000 --timeout 45 --attempt-deadline 45 `
  --case-deadline 90 --max-retries 1 --max-elapsed-seconds 1800 `
  --history-dir evaluations\history --history-run-id goal16-offline-a-20261101 `
  --history-configuration A --history-corpus-kind synthetic --format json
```

## Future real command — do not execute now

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -m polaris evaluate `
  --provider nvidia --model minimaxai/minimax-m3.1-flash `
  --fixtures evaluations\fixtures\real_world_verified_benchmark.json `
  --allow-external --end-to-end --production-parity --strict-severity `
  --no-behavioral-delta --no-hybrid-static-selection --no-static-relevance-selection `
  --max-requests 24 --max-tokens 50000 --timeout 45 --attempt-deadline 45 `
  --case-deadline 90 --max-retries 1 --max-elapsed-seconds 1800 `
  --history-dir evaluations\history --history-run-id goal16-nvidia-a-YYYYMMDD `
  --history-configuration A --history-corpus-kind real --format json
```

For Arm B use `--hybrid-static-selection --no-static-relevance-selection`; for
Arm C use `--no-hybrid-static-selection --static-relevance-selection`.
