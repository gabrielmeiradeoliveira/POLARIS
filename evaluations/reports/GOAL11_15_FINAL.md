# GOAL 11–15 Final Report

## Execution summary

- GOAL 11: COMPLETE — evaluator audit, explicit operational counts, F1, reproducible offline A/B/C.
- GOAL 12: COMPLETE — conservative validation audit and regression coverage; no unjustified suppression enabled.
- GOAL 13: COMPLETE — verified existing opt-in, bounded cross-file slice and its safeguards.
- GOAL 14: COMPLETE — bounded stage-level timing instrumentation, existing safe performance controls, and offline benchmark coverage.
- GOAL 15: COMPLETE — release documentation/audit, full offline tests, Ruff, and frozen-corpus integrity verification passed.

## Commands

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -m pytest --basetemp .pytest-goal11-15 -q
.\.venv\Scripts\ruff.exe check src tests
.\.venv\Scripts\python.exe -m polaris evaluate --provider fake --fixtures evaluations\fixtures\end_to_end_context_benchmark.json --no-behavioral-delta --no-hybrid-static-selection --no-static-relevance-selection --observability-file evaluations\results\goal11_15_ab\A_baseline.json
```

Repeat the last command with `--hybrid-static-selection` for B and `--static-relevance-selection` for C.

## External protocol

Before a permitted real-provider run, freeze a representative versioned corpus and SHA-256, provider/model, request/retry/deadline/token budget, selection flags, matching rules, and primary success thresholds. Stratify by positive/negative/security/concurrency/cross-file cases. Report strict and detection metrics, completed/timeout/error/skipped cases, accepted/rejected candidates, per-case latency, reported versus estimated tokens, and cost basis. Do not change metrics or matching after observing outputs.

## Final verdict

`MVP_2_0_OFFLINE_RELEASE_CANDIDATE`

The offline evaluation/control work is reproducible, the frozen corpus is intact, and the full offline test, lint, and diff-integrity gates pass. Real LLM quality remains unproven because external provider calls were intentionally not authorized. The sole release blocker is the pre-registered external validation protocol; until it runs, this must not be classified as `MVP_2_0_RELEASE_READY`.
