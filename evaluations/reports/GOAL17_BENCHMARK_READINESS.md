# GOAL 17 Benchmark Readiness

## Offline A/B/C result

All arms used the same corpus, FakeProvider model, end-to-end production-parity
path, strict severity criterion, limits (100 requests, 10,000 estimated tokens,
45 s request/attempt, 90 s case, 300 s run), and no retries.

| Arm | Hybrid | Static relevance | Behavioral delta | TP / FP / FN | P / R / F1 | Completion | Tokens |
|---|---|---|---|---:|---|---:|---:|
| A | off | off | off | 4 / 0 / 0 | 1.0 / 1.0 / 1.0 | 1.0 | 6,920 |
| B | on | off | off | 4 / 0 / 0 | 1.0 / 1.0 / 1.0 | 1.0 | 5,700 |
| C | off | on | off | 4 / 0 / 0 | 1.0 / 1.0 / 1.0 | 1.0 | 6,920 |

Manifests: `goal17-offline-a-20261101`, `goal17-offline-b-20261101`, and
`goal17-offline-c-20261101`. These are FakeProvider controls, not NVIDIA accuracy.

## Unexecuted NVIDIA pilot

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'; $env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -m polaris evaluate --provider nvidia `
  --fixtures evaluations\fixtures\code_review_corpus.json --allow-external `
  --end-to-end --production-parity --strict-severity --no-behavioral-delta `
  --no-hybrid-static-selection --no-static-relevance-selection `
  --case-id pos_div_by_zero_unhandled_len --case-id pos_mutable_default_arg `
  --case-id neg_guarded_average --max-requests 3 --max-tokens 6000 `
  --timeout 45 --attempt-deadline 45 --case-deadline 90 --max-retries 0 `
  --max-elapsed-seconds 300 --history-dir evaluations\history `
  --history-run-id goal17-nvidia-pilot-YYYYMMDD --history-configuration A `
  --history-corpus-kind real --format json
```

GO checklist: explicit external authorization; disposable key; model availability;
no secrets in selected fixture text; unique run ID; acceptance of non-absolute
token accounting. NO-GO otherwise. The command was prepared but not executed;
6,000 estimated tokens is not an absolute hosted-provider cap.
