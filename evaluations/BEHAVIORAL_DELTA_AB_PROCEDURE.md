# POLARIS Behavioral Delta Analysis A/B Evaluation Procedure

## 1. Overview and Objective

This document defines the reproducible, standardized protocol for conducting an empirical A/B evaluation of POLARIS's Behavioral Delta Analysis Engine. Historical 12-case artifacts remain unchanged; the production-ready protocol below uses the 20-case E2E corpus.

The goal is to measure whether deterministic Behavioral Delta Analysis improves code review accuracy (True Positives, Precision, Recall, False Positive Rate, and Severity Calibration) when reviewing code diffs with an LLM provider, compared to raw diff review without Behavioral Delta context.

Behavioral Delta is experimental and disabled by default. Both benchmark commands therefore set its state explicitly.

---

## 2. Experimental Controls & Invariants

To guarantee an unbiased comparison, both evaluation arms (**Arm A: Behavioral Delta OFF** and **Arm B: Behavioral Delta ON**) must execute under strictly identical parameters:

| Parameter | Value / Setting | Rationale |
|---|---|---|
| **Benchmark Suite** | `evaluations/fixtures/end_to_end_context_benchmark.json` | 20 executable cases (12 positive defects, 8 clean negatives) |
| **Provider** | `nvidia` | Production review provider |
| **Model** | `minimaxai/minimax-m3.1-flash` | Production baseline LLM |
| **Pipeline Mode** | `--end-to-end` | Runs full model inference + Finding Intelligence Engine |
| **Per-Request Timeout** | `--timeout 40.0` | Leaves bounded headroom for retry backoff |
| **Retry Limit** | `--max-retries 1` | Bounded retries on transient HTTP 429/500 errors |
| **Max Requests** | `--max-requests 10` | Five-case batch × at most 2 attempts per case |
| **Max Tokens** | `--max-tokens 50000` | Bounded token consumption ceiling |
| **Max Elapsed Time** | `--max-elapsed-seconds 1200` | Covers one five-case batch and bounded retry backoff |
| **Output Format** | `terminal` (for log review) & `json` (for programmatic analysis) | Dual artifact capture |
| **Temperature** | `0.0` (Enforced internally by `CodeReviewModule`) | Deterministic model decoding |

---

## 3. Pre-Flight Offline Verification

Before running live model evaluations, verify fixture integrity and command options using the offline `fake` provider:

```bash
# Verify Arm A (OFF) offline:
polaris evaluate \
  --fixtures evaluations/fixtures/behavioral_regression_benchmark.json \
  --provider fake \
  --no-behavioral-delta

# Verify Arm B (ON) offline:
polaris evaluate \
  --fixtures evaluations/fixtures/behavioral_regression_benchmark.json \
  --provider fake \
  --behavioral-delta
```

Expected offline result for both commands:
- `Dataset Size: 12 (positive=8, negative=4)`
- `TP=8, FP=0, FN=0`
- `Precision: 100.00%`
- `Recall: 100.00%`
- `False Positive Rate: 0.00%`

---

## 4. Historical 12-case commands (archived — do not execute)

## Production-parity batching

Run four deterministic five-case batches: 01–05 OFF then ON, 06–10 ON then OFF,
11–15 OFF then ON, and 16–20 ON then OFF. Each arm/batch has one canonical JSON command;
do not run a second terminal capture. Every command must add `--production-parity`,
`--context-tokens 2000`, `--behavioral-delta-reserved-tokens 500`, and exactly five repeated
`--case-id` options. The OFF command uses `--no-behavioral-delta`; ON uses
`--behavioral-delta`; all other parameters are identical. Store new results under
`evaluations/results/e2e_context_ab_20case_v1/` and retain historical reports unchanged.

The batch selectors are the case IDs in numeric order: `e2e-ctx-01-return-contract-multiple-callers`
through `e2e-ctx-05-null-plugin-result`; `e2e-ctx-06-page-boundary-callback` through
`e2e-ctx-10-unregisters-wrong-callback`; `e2e-ctx-11-permission-default-multiple-callers`
through `e2e-ctx-15-context-manager-retry`; and `e2e-ctx-16-narrow-exception-preserves-contract`
through `e2e-ctx-20-override-calls-super`. Each ID is supplied once with repeated `--case-id`.

> [!WARNING]
> Do NOT execute these live commands without explicit user permission and verified external API credentials.
> These commands make live network calls to the external provider.

### Step 1: Ensure Output Directories Exist

```bash
mkdir -p evaluations/results/behavioral_delta_ab_12case
```

### Step 2: Run Arm A — Behavioral Delta OFF

Execute the benchmark with Behavioral Delta Analysis explicitly disabled (`--no-behavioral-delta`):

```bash
# Terminal report capture:
polaris evaluate \
  --fixtures evaluations/fixtures/behavioral_regression_benchmark.json \
  --provider nvidia \
  --model minimaxai/minimax-m3.1-flash \
  --end-to-end \
  --no-behavioral-delta \
  --allow-external \
  --timeout 45.0 \
  --max-retries 1 \
  --max-requests 24 \
  --max-tokens 50000 \
  --max-elapsed-seconds 1800 \
  --detailed > evaluations/results/behavioral_delta_ab_12case/delta_off_terminal.txt

# Structured JSON capture:
polaris evaluate \
  --fixtures evaluations/fixtures/behavioral_regression_benchmark.json \
  --provider nvidia \
  --model minimaxai/minimax-m3.1-flash \
  --end-to-end \
  --no-behavioral-delta \
  --allow-external \
  --timeout 45.0 \
  --max-retries 1 \
  --max-requests 24 \
  --max-tokens 50000 \
  --max-elapsed-seconds 1800 \
  --format json > evaluations/results/behavioral_delta_ab_12case/delta_off.json
```

### Step 3: Run Arm B — Behavioral Delta ON

Execute the exact same benchmark with Behavioral Delta Analysis explicitly enabled (`--behavioral-delta`):

```bash
# Terminal report capture:
polaris evaluate \
  --fixtures evaluations/fixtures/behavioral_regression_benchmark.json \
  --provider nvidia \
  --model minimaxai/minimax-m3.1-flash \
  --end-to-end \
  --behavioral-delta \
  --allow-external \
  --timeout 45.0 \
  --max-retries 1 \
  --max-requests 24 \
  --max-tokens 50000 \
  --max-elapsed-seconds 1800 \
  --detailed > evaluations/results/behavioral_delta_ab_12case/delta_on_terminal.txt

# Structured JSON capture:
polaris evaluate \
  --fixtures evaluations/fixtures/behavioral_regression_benchmark.json \
  --provider nvidia \
  --model minimaxai/minimax-m3.1-flash \
  --end-to-end \
  --behavioral-delta \
  --allow-external \
  --timeout 45.0 \
  --max-retries 1 \
  --max-requests 24 \
  --max-tokens 50000 \
  --max-elapsed-seconds 1800 \
  --format json > evaluations/results/behavioral_delta_ab_12case/delta_on.json
```

---

## 5. Comparative Metric Analysis

Once both runs complete, evaluate the delta across the following dimensions:

| Metric | Delta OFF | Delta ON | Impact (ON - OFF) |
|---|---|---|---|
| **True Positives (TP)** | | | $\Delta \text{TP}$ |
| **False Positives (FP)** | | | $\Delta \text{FP}$ |
| **False Negatives (FN)** | | | $\Delta \text{FN}$ |
| **Precision** | | | $\Delta \text{Precision}$ |
| **Recall** | | | $\Delta \text{Recall}$ |
| **False Positive Rate** | | | $\Delta \text{FPR}$ |
| **Severity Mismatches** | | | $\Delta \text{Severity Mismatches}$ |
| **Total Prompt Tokens** | | | Token overhead of AST delta block |
| **Total Completion Tokens** | | | LLM reasoning token impact |
| **Average Latency (ms)** | | | Latency impact |

### Strict Matching and Detection Diagnostics

`TP`, `FP`, `FN`, precision, and recall remain strict rubric metrics. A strict match requires the expected file and line range plus a category listed in the fixture's `allowed_categories`.

JSON reports also expose diagnostic fields that do not change the strict metrics:

- `category_mismatch_detections`: validated findings at an expected source location whose category is not accepted by that fixture;
- `undetected_expected_defects`: expected defects with no location-matched validated finding;
- `detection_precision` and `detection_recall`: location-grounded diagnostic metrics that treat a category mismatch as a detected location, while retaining strict counts separately.

A location-matched category mismatch is not automatic proof of semantic equivalence. Curators must add a category to a fixture's `allowed_categories` only when it is a reviewed, acceptable classification of the intended defect. This preserves strict comparisons while making category-rubric failures auditable.

### Per-Case Differential Checklist

For each case `beh-regress-01` through `beh-regress-12`:
1. Did Delta ON detect a bug missed by Delta OFF?
2. Did Delta ON improve severity ranking (e.g. `medium` -> `high`)?
3. Did Delta ON prevent a false alarm on any of the 4 clean negative cases?
4. Did Delta ON increase prompt tokens without improving detection on subtle cases (e.g. Case 8)?

---

## 6. Archiving & Reporting Protocol

1. Retain both `delta_off.json` and `delta_on.json` in `evaluations/results/behavioral_delta_ab_12case/`.
2. Generate an analytical markdown comparison report at `evaluations/reports/behavioral_delta_ab_12case_report.md`.
3. Highlight cases where Behavioral Delta provided decisive guidance versus cases where textual reasoning dominated.
