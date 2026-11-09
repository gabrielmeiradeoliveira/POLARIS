# POLARIS GOAL 27 — Experimental Campaign Readiness & Pre-Validation Report

## 1. Executive Summary

This report documents the offline pre-validation of the experimental evaluation pipeline for **GOAL 27**.
It verifies that all datasets, manifests, prompts, serialization protocols, token reservations,
and paired OFF/ON comparison mechanisms operate deterministically and without errors before any external API calls.

> [!IMPORTANT]
> **SIMULATED PRE-VALIDATION ONLY**
> The metrics presented below were generated using offline deterministic mock execution (`FakeProvider`).
> They validate protocol integrity, atomic pair enforcement, and metric computation pipelines.
> They do **not** reflect actual LLM code review capability or empirical model performance.

---

## 2. Campaign Specification

- **Campaign ID:** `goal27-real-world-model-selection`
- **Benchmark Version:** `1.0.0`
- **Dataset:** `evaluations/fixtures/end_to_end_context_benchmark.json` (20 cases)
- **Dataset SHA-256:** `1901684d08c4b6cba33edeaa186782ec3b778fad9af7cf2f043eed91913e2357`
- **System Prompt SHA-256:** `b64788fc1e2dd78d5c2488b9f9aed0c883d00ad88f392c8d45631ad09847e50f`
- **Target Model Candidates:**
  - `fake-deterministic-v1` (Provider: `fake`, Context: 131072, Tier: `free_offline_simulation`)
  - `minimaxai/minimax-m3.1-flash` (Provider: `nvidia`, Context: 131072, Tier: `nvidia_developer_free_tier`)
  - `z-ai/glm-5.3-flash` (Provider: `nvidia`, Context: 131072, Tier: `nvidia_developer_free_tier`)

---

## 3. Protocol & Pre-Validation Verification

| Check | Verified State | Proof / Guarantee |
|---|---|---|
| **Manifest Integrity** | PASS | Exact prompt SHA-256 and dataset SHA-256 verified |
| **Atomic Pair Admission** | PASS | No partial OFF/ON pair admitted without complete budget |
| **In-Flight Safety** | PASS | Atomic checkpoint writing with `.tmp` replacement and in-flight markers |
| **Checkpoint Resume** | PASS | Checkpoint state validated; replay of completed pairs strictly prevented |
| **Zero Denominator Handling** | PASS | Safe `None` returned for empty TP+FP / TP+FN; no artificial 100% |
| **External Code Egress Control** | BLOCKED | `external_execution_authorized: false` strictly enforced until user approval |

---

## 4. Offline Mock Execution Results (Simulated Baseline)

- **Total Completed Paired Cases:** 20 of 20

| Metric | Arm OFF (No Behavioral Delta) | Arm ON (With Behavioral Delta) | Delta (ON - OFF) |
|---|---|---|---|
| **True Positives (TP)** | 3 | 3 | +0 |
| **False Positives (FP)** | 0 | 0 | +0 |
| **False Negatives (FN)** | 9 | 9 | - |
| **Precision** | 1.0 | 1.0 | 0.0 |
| **Recall** | 0.25 | 0.25 | 0.0 |
| **F1 Score** | 0.4 | 0.4 | 0.0 |
| **Total Tokens** | 17166 | 18735 | +1569 |
| **Mean Latency (ms)** | 0.15 | 1.5 | 1.35 |
| **Operational Failure Rate** | 0.0% | 0.0% | 0.0% |

---

## 5. Model Selection Readiness & Next Steps

The evaluation harness is fully pre-flighted, resilient against process or permission interruptions, and verified offline.

> [!IMPORTANT]
> Per POLARIS Safety & Security Policy, **no external network requests or paid model invocations will be dispatched without explicit user authorization**.
> To proceed to Phase 5 (Smoke Test / Pilot / Benchmark Principal with NVIDIA API), provide explicit approval.
