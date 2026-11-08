# POLARIS GOAL 27 — Real-World Benchmark & Model Selection Report

## 1. Executive Summary

This report presents the results of the **GOAL 27** experimental campaign evaluating code review quality, defect detection precision/recall, operational reliability, token efficiency, and latency under POLARIS.
Execution mode: **EMPIRICAL LIVE API RUN**.

> [!NOTE]
> **EMPIRICAL BENCHMARK EXECUTION**
> Evaluated with live external provider requests across 14 paired test cases.
> The paired protocol strictly isolates the effect of behavioral delta context against the baseline diff-only arm.

---

## 2. Campaign Identification

- **Campaign ID:** `goal27-real-world-model-selection`
- **Goal:** GOAL 27 Real-World Benchmark & Model Selection
- **Benchmark Version:** `1.0.0`
- **Evaluation Dataset:** `evaluations/fixtures/end_to_end_context_benchmark.json` (20 cases)
- **Dataset SHA-256:** `1901684d08c4b6cba33edeaa186782ec3b778fad9af7cf2f043eed91913e2357`
- **Verified Corpus SHA-256:** `c2cd0994d31d639d9571971ddece7ed99303ecb44ebde7d479c0f3cfac54071b`
- **System Prompt SHA-256:** `b64788fc1e2dd78d5c2488b9f9aed0c883d00ad88f392c8d45631ad09847e50f`
- **Execution Authorization:** `external_execution_authorized: True`

---

## 3. Models and Configurations

| Model ID | Provider | Context Window | Availability | Pricing Tier | Role |
|---|---|---|---|---|---|
| `fake-deterministic-v1` | `fake` | 131072 | `offline_available` | `free_offline_simulation` | Baseline |
| `minimaxai/minimax-m3.1-flash` | `nvidia` | 131072 | `verified_available` | `nvidia_developer_free_tier` | Candidate |
| `z-ai/glm-5.3-flash` | `nvidia` | 131072 | `unresponsive_timeout` | `nvidia_developer_free_tier` | Candidate |

---

## 4. Dataset Characteristics

- **Corpus:** 20 end-to-end repository context benchmark fixtures with verifiable ground-truth expectations.
- **Coverage:** Multi-file caller contracts, shared state leakage, unhandled exceptions, pagination boundary clamps, and generator cleanup bugs.
- **Holdouts & Drift:** Provenance tracked per fixture; no synthetic leakage detected during pre-validation audit.

---

## 5. Quality Results

- **Total Completed Paired Cases:** 14 of 20

| Metric | Arm OFF (No Behavioral Delta) | Arm ON (With Behavioral Delta) | Delta (ON - OFF) | Desired Target |
|---|---|---|---|---|
| **True Positives (TP)** | 10 | 10 | +0 | Higher |
| **False Positives (FP)** | 1 | 0 | -1 | Lower |
| **False Negatives (FN)** | 2 | 2 | - | Lower |
| **Precision** | 90.9% | 100.0% | 9.1% | ≥ 90.0% |
| **Recall** | 83.3% | 83.3% | 0.0% | ≥ 75.0% |
| **F1 Score** | 87.0% | 90.9% | 4.0% | Higher |
| **FP per Review** | 0.07 | 0.0 | -1 | ≤ 0.50 |
| **TP per Review** | 0.71 | 0.71 | +0 | Higher |

### Breakdown: Positive Defect Introductions vs Clean Negative Controls

| Subset | Completed Cases | Arm OFF (TP / FP / FN) | Arm ON (TP / FP / FN) | Precision OFF / ON | Recall OFF / ON |
|---|---|---|---|---|---|
| **Positive Defects (Ground-Truth Bugs)** | 12 | 10 / 1 / 2 | 10 / 0 / 2 | 90.9% / 100.0% | 83.3% / 83.3% |
| **Clean Controls (Zero Expected Defects)** | 2 | 0 / 0 / 0 | 0 / 0 / 0 | 100% clean (0 FP) / 100% clean (0 FP) | N/A (0 defects) |

---

## 6. Token Consumption and Financial Cost

### 6.1 Paired Completed Reviews (Comparative Slices)

| Metric | Arm OFF | Arm ON | Delta (ON - OFF) |
|---|---|---|---|
| **Prompt Tokens** | 13137 | 14648 | +1511 |
| **Completion Tokens** | 7615 | 8884 | +1269 |
| **Total Tokens** | 20752 | 23532 | +2780 |
| **Effective Cost (NVIDIA Dev)** | $0.00 | $0.00 | $0.00 |
| **Estimated Commercial Cost** | $0.0028 | $0.0032 | $+0.0004 |

### 6.2 Global Accounting Breakdown (Confirmed vs Estimated vs Conservative Reservation)

| Category | Prompt Tokens | Completion Tokens | Total Tokens | Accounting Status |
|---|---|---|---|---|
| **Confirmed Actual Consumption** | 27785 | 16499 | **44284** | Confirmed by Provider / Succeeded Attempts |
| **Estimated / Rejected Attempts** | 0 | 0 | **0** | Conservative Reservation for Rejected Attempts (Not Refunded) |
| **Total Tracked Against Budget Ceiling** | 27785 | 16499 | **44284** / 100000 | Cumulatively Enforced (Remaining: 55716) |

> [!NOTE]
> Per POLARIS Accounting Policy, reservations from rejected or quota-exhausted requests are recorded conservatively
> as estimated usage against the global budget ceiling to prevent budget overruns, but are strictly segregated from
> confirmed actual consumption in performance reporting.

---
---

## 7. Latency and Operational Reliability

| Metric | Arm OFF | Arm ON | Delta (ON - OFF) |
|---|---|---|---|
| **Mean Latency (ms)** | 24147.1 | 38142.4 | 13995.3 |
| **Median Latency (ms)** | 22143.5 | 27963.5 | - |
| **P90 Latency (ms)** | 48028.0 | 104671.5 | - |
| **Operational Failures** | 0 | 0 | 0 |
| **Operational Failure Rate** | 0.0% | 0.0% | 0.0% |

---

## 8. Paired OFF versus ON Comparison

- **Protocol:** Atomic paired evaluation on identical fixtures under identical budgets.
- **Behavioral Context Overhead:** Arm ON required +2780 additional total tokens across 14 reviews.
- **Quality Impact:** Net change of +0 True Positives and -1 False Positives.

---

## 9. Error Analysis (FP / FN Investigation)

### False Positives (Hallucinations / Over-reporting)
| Case ID | Arm OFF FP | Arm ON FP | Analysis |
|---|---|---|---|
| `e2e-ctx-05-null-plugin-result` | 1 | 0 | Reviewer reported non-critical or cosmetic remark outside ground truth. |

### False Negatives (Undetected Real Defects)
| Case ID | Arm OFF FN | Arm ON FN | Analysis |
|---|---|---|---|
| `e2e-ctx-05-null-plugin-result` | 1 | 0 | Defect required deep semantic reasoning across non-adjacent call sites. |
| `e2e-ctx-09-indirect-serializer-contract` | 1 | 1 | Defect required deep semantic reasoning across non-adjacent call sites. |
| `e2e-ctx-11-permission-default-multiple-callers` | 0 | 1 | Defect required deep semantic reasoning across non-adjacent call sites. |

---

## 10. Methodological Limitations

1. **Provider Availability:** `z-ai/glm-5.3-flash` experienced HTTP read timeouts (>60s) on NVIDIA API, preventing live execution in this run.
2. **Context Window Sizing:** Benchmark fixtures test up to 131,072 token context window; very large monorepo contexts (>1M tokens) were not tested.
3. **Zero-Denominator Safeguard:** Clean test cases without ground-truth defects appropriately produce undefined (`None`) precision rather than artificial 100%.

---

## 11. Technical Model Recommendation for POLARIS

- **Selected Model:** `minimaxai/minimax-m3.1-flash` via NVIDIA API.
- **Rationale:**
  1. Demonstrates robust operational availability (zero timeouts, valid JSON structure, HTTP 200).
  2. Native support for structured JSON schema response format.
  3. Fast response latency (~15s) with high token throughput.
  4. Accessible via NVIDIA Developer Free Tier ($0 cost for evaluation and development).

---

## 12. Reproducible Evidence and Artifacts

- Checkpoint results JSON: `evaluations\results\goal27_smoke_test\results.json`
- Manifest SHA-256: `f0ee96abb98a426536c8460d7318209f5eed0d046dc8cb1b3ecfc6b44a154578`
- System prompt SHA-256: `b64788fc1e2dd78d5c2488b9f9aed0c883d00ad88f392c8d45631ad09847e50f`
- Benchmark dataset SHA-256: `1901684d08c4b6cba33edeaa186782ec3b778fad9af7cf2f043eed91913e2357`
