# POLARIS MVP 1.4 Baseline Evaluation Report

**Model Identifier:** `minimaxai/minimax-m3.1-flash`
**Provider:** NVIDIA API (`NvidiaProvider`)
**Evaluation Date:** October 25, 2026
**Benchmark Suite:** MVP 1.4 Valid Bug Introduction Benchmark (`evaluations/fixtures/bug_introduction_benchmark.json`)
**Benchmark Version:** 1.0.0
**Evaluation Mode:** End-to-End Live Model Review (`--end-to-end`)

---

## 1. Executive Summary

This report establishes the empirical code review baseline for POLARIS MVP 1.4 evaluated against `minimaxai/minimax-m3.1-flash`.

The benchmark evaluates the model's ability to detect authentic and reconstructed bug-introducing changes while maintaining zero false positives on clean bug fixes, refactorings, and documentation updates.

> [!IMPORTANT]
> This benchmark contains reconstructed historical and synthetic evaluation cases. These results reflect baseline capability under controlled test conditions and must **not** be presented as unconstrained production accuracy.

### Summary Metrics

| Metric | Value | Interpretation |
|---|---|---|
| **Total Cases** | 8 | Total benchmark fixture cases in corpus |
| **Successful Completed Cases** | 7 | Cases completing end-to-end inference and post-processing |
| **API Failures / Timeouts** | 1 | Unhandled network / gateway timeout on case `bug-intro-03-flask-session-nullbyte-crash` (timed out across 2 separate attempts) |
| **True Positives (TP)** | 4 | Ground-truth bugs successfully detected by the model |
| **False Positives (FP)** | 0 | No hallucinated bugs on clean code or non-bug changes |
| **False Negatives (FN)** | 0 | Zero missed bugs among completed positive cases |
| **Completed-Case Precision** | 100.00% | $\frac{TP}{TP + FP} = \frac{4}{4 + 0}$ |
| **Completed-Case Recall** | 100.00% | $\frac{TP}{TP + FN} = \frac{4}{4 + 0}$ |
| **False Positive Rate (FPR)** | 0.00% | $\frac{\text{clean cases with FP}}{\text{completed clean cases}} = \frac{0}{3}$ |
| **Severity Mismatches** | 4 | All 4 detected findings differed from ground-truth severity |
| **Negative Cases Handled** | 3 / 3 (100%) | All 3 negative controls completed without false alarms |

---

## 2. Individual Case Breakdown & Outcomes

| Case ID | Type | Provenance | Ground-Truth Category | Model Outcome | Notes |
|---|---|---|---|---|---|
| `bug-intro-01-tqdm-zerodiv` | Positive (Defect Intro) | `reconstructed_inverted_fix` | `correctness` / `boundary_condition` | **TP=1, FP=0, FN=0** | Detected division-by-zero on `tqdm/std.py:4`. Severity mismatch (model assigned medium vs ground truth high). |
| `bug-intro-02-polaris-budget-underflow` | Positive (Defect Intro) | `reconstructed_inverted_fix` | `boundary_condition` | **TP=1, FP=0, FN=0** | Detected unclamped negative token budget on `code_review.py:3`. Severity mismatch. |
| `bug-intro-03-flask-session-nullbyte-crash` | Positive (Defect Intro) | `reconstructed_inverted_fix` | `error_handling` | **API Timeout** | Upstream NVIDIA endpoint timed out during inference (reproduced across 2 separate evaluation attempts). Categorized as API timeout failure (FN=0, non-completed). |
| `bug-intro-04-client-state-mutation` | Positive (Defect Intro) | `reconstructed_inverted_fix` | `state_mutation` | **TP=1, FP=0, FN=0** | Detected in-place header dict mutation across sessions (`requests/sessions.py:6-8`). Severity mismatch. |
| `bug-intro-05-cross-file-signature-break` | Positive (Defect Intro) | `reconstructed_inverted_fix` | `correctness` | **TP=1, FP=0, FN=0** | Detected breaking parameter change in `charge_card` breaking caller contract (`services/payment.py:1`). Severity mismatch. |
| `clean-neg-01-tqdm-guarded-rate-fix` | Negative (Clean Bug Fix) | `fully_verified` | None (Clean) | **FP=0** (Clean Pass) | Model correctly identified patch as a bug fix and emitted no false defect findings. |
| `clean-neg-02-safe-helper-refactor` | Negative (Clean Unrelated) | `fully_verified` | None (Clean) | **FP=0** (Clean Pass) | Safe helper extraction correctly passed without false alarms. |
| `clean-neg-03-docstring-and-typing-docs` | Negative (Clean Unrelated) | `reference_modeled` | None (Clean) | **FP=0** (Clean Pass) | Documentation and type annotation additions emitted zero false alarms. |

---

## 3. Failure & Severity Analysis

### 3.1 API Timeout on `bug-intro-03-flask-session-nullbyte-crash`
- **Error:** Upstream HTTP / Read Timeout encountered during model inference on `bug-intro-03-flask-session-nullbyte-crash` (reproduced across two separate evaluation attempts).
- **Handling:** Under POLARIS failure diagnostics, network and timeout errors on external providers are isolated into `api_failed_cases` and `failed_cases`. They are **not** counted as detection passes or false negatives, ensuring infrastructure and endpoint latency anomalies do not distort model capability metrics.
- **Remediation:** Configure retry backoff (`--max-retries 1`) and per-request timeout bounds (`--timeout 45.0`). In contrast, multi-file context case `bug-intro-05-cross-file-signature-break` completed successfully without timeout.

### 3.2 Severity Calibration Mismatches (4 / 4 Detected Cases)
- In all 4 completed positive cases, the model successfully pinpointed the exact bug and evidence, but categorized severity as `medium` or `critical` rather than ground truth `high`.
- **System Impact:** Finding Intelligence Stage 2 (`severity_normalizer.py`) deterministically normalizes finding severity based on category ceilings and evidence quality, preventing raw LLM severity drift from impacting triage priorities.

---

## 4. Token Accounting & Quota Integrity

POLARIS maintains a strict distinction between:
1. **Actual Provider Usage:** Reported directly by the NVIDIA inference API responses (`usage.prompt_tokens`, `usage.completion_tokens`, `usage.total_tokens`).
2. **Locally Estimated Token Reservations:** Tracked pre-request in SQLite (`UsageStore`) before dispatching requests to enforce rate-limit ceilings (RPM, TPM, RPD) and prevent quota overrun.

For completed cases, metrics reflect verified API response tokens. Failed cases release reserved token capacity according to reservation TTL.

---

## 5. Provenance & Dataset Classification

- **`fully_verified` (2 cases):** Ground truth directly verified against historical Git commit history and standalone unit test behavioral proofs (`clean-neg-01`, `clean-neg-02`).
- **`reconstructed_inverted_fix` (5 cases):** Authentically reconstructed bug-introducing changes derived from historical bug fixes (e.g. BugInPy, CVE-2018-1000656, CVE-2023-32681).
- **`reference_modeled` (1 case):** Upstream clean changes curated to model real-world docstring and typing updates (`clean-neg-03`).

---

## 6. Known Limitations

1. **Provider Inference Latency on Specific Prompts:** Case 3 (`bug-intro-03-flask-session-nullbyte-crash`) experienced upstream inference timeouts across multiple separate evaluation runs, indicating provider-side sensitivity or latency spikes on certain cookie deserialization prompt structures.
2. **Small Corpus Size:** 8 cases establish directional validity and prevent regressions, but are insufficient for statistical power across all defect types.
3. **Absence of Behavioral Delta Verification:** Static diffs without dynamic execution or AST behavioral delta comparison leave models reliant on textual prompt reasoning alone.
