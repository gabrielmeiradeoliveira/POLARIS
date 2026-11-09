# POLARIS GOAL 27 — Benchmark Datasets Audit Report

## 1. Executive Summary

This audit inspects all evaluation fixtures and datasets in the POLARIS repository to establish
a verified, uncompromised benchmark for model selection and paired A/B evaluation (GOAL 27).

**Total Fixture Corpora Audited:** 11
**Audit Standard:** Strict ground-truth verification (requiring explicit commit IDs, CVEs/PR references, or documented behavioral proofs).

---

## 2. Dataset Inventory

| Dataset | Type | Total Cases | Positives | Negatives | Ground Truth Verified | Insufficient Evidence | SHA-256 (64 hex) |
|---|---|---|---|---|---|---|---|
| `behavioral_regression_benchmark.json` | behavioral_regression | 12 | 8 | 4 | 12 | 0 | `1f35841ddf04cfd347536cd2703dce9b4671fb6b727ee5ccda1724f44dcf6453` |
| `bug_introduction_benchmark.json` | bug_introduction | 8 | 5 | 3 | 8 | 0 | `f16864193db2eb4e26e82688c81b96d953ca675903728da105c48492c4468a94` |
| `code_review_corpus.json` | curated_benchmark | 6 | 4 | 2 | 1 | 5 | `e71a50d997302ce782c0eaec924cc1e2293df4f6cdb16d074c32939662c3f511` |
| `end_to_end_context_benchmark.json` | context_ab_benchmark | 20 | 12 | 8 | 20 | 0 | `1901684d08c4b6cba33edeaa186782ec3b778fad9af7cf2f043eed91913e2357` |
| `finding_intelligence_corpus.json` | synthetic | 10 | 7 | 3 | 1 | 9 | `c4908653215062bc18e8f69dbd43f19e4f3fdba6af0d47f2b608fc9f73dcc204` |
| `goal18_data_flow_contract_corpus.json` | synthetic | 2 | 1 | 1 | 2 | 0 | `f5e8ace37a5104a33d2c6981ed18748064ea5080f847cac4127e93fc6d171ccb` |
| `goal21_adversarial/scenarios.json` | holdout_adversarial | 30 | 0 | 30 | 30 | 0 | `f0ca25d5929982d8a477ded40f689e32806c5f12cdffb3054ed30fccccec8001` |
| `goal23_real_world/cases.json` | real_world | 40 | 0 | 40 | 40 | 0 | `2494f9d42e8d0235264adcd649f6d5e370b8442387bcab0529ee9b6db30d4c18` |
| `live_nvidia_baseline_cases.json` | real_world | 5 | 4 | 1 | 5 | 0 | `d4d6caa11660f41b136ed0b0ba480d50dd9c1c9644a0d4339c660b7426eaa28b` |
| `real_world_benchmark.json` | real_world | 33 | 22 | 11 | 33 | 0 | `243bd568eee37fd8d20d3c8135a2676443549b3cc64f2ea6c767c99f64423a04` |
| `real_world_verified_benchmark.json` | real_world | 8 | 8 | 0 | 8 | 0 | `c2cd0994d31d639d9571971ddece7ed99303ecb44ebde7d479c0f3cfac54071b` |

---

## 3. Dataset Classification & Detailed Findings

### 3.1 Real-World Verified Benchmark (`real_world_verified_benchmark.json`)
- **Status:** Highest confidence real-world ground truth.
- **Cases:** 8 cases across mature open-source projects (`psf/requests`, `urllib3/urllib3`, `pallets/werkzeug`).
- **Validation:** Each case contains exact `commit_id`, `fix_commit_id`, `independent_evidence` (CVE / GitHub issue links), and regression test assertions.
- **Role in GOAL 27:** Serves as the primary real-world benchmark for absolute bug detection accuracy and false negative accounting.

### 3.2 Paired Context A/B Benchmark (`end_to_end_context_benchmark.json`)
- **Status:** Frozen paired evaluation corpus.
- **Cases:** 20 balanced cases (12 positive defect introduction cases, 8 clean negative controls).
- **Validation:** Ground truth covers cross-file contracts (caller/callee signatures, resource lifecycles, callback propagation).
- **Role in GOAL 27:** Serves as the frozen dataset for paired OFF vs ON comparisons under identical limits.

### 3.3 General Real-World Benchmark (`real_world_benchmark.json`)
- **Status:** Broad real-world evaluation.
- **Cases:** 33 cases (22 positive defects, 11 clean refactorings).
- **Validation:** Covers `psf/requests`, `urllib3`, `cpython`, and `pallets/flask`.

### 3.4 Holdouts and Adversarial Corpora
- `goal21_adversarial/scenarios.json`: 30 clean/adversarial cases with 0 expected defects to measure false positive rejection under malicious or tricky patterns.
- `goal24_holdout`: Isolated holdout catalog designed to detect overfitting.

---

## 4. Cross-Dataset Leakage & Overlap Analysis

Cross-dataset ID and diff overlap audit:

| Dataset A | Dataset B | Shared Cases | Shared Case IDs |
|---|---|---|---|
| `code_review_corpus.json` | `goal21_adversarial/scenarios.json` | 1 | `neg_guarded_average` |
| `live_nvidia_baseline_cases.json` | `real_world_benchmark.json` | 5 | `real-cpython-01-urlsplit-whitespace-bypass`, `real-flask-01-null-byte-session-dos`, `real-polaris-03-clean-readme-docs`, `real-requests-01-proxy-leak` (+1 more) |

---

## 5. Model Selection Recommendation for GOAL 27

1. **Primary Evaluation Corpus:** `end_to_end_context_benchmark.json` (20 cases, SHA-256 `1901684d08c4b6cba33edeaa186782ec3b778fad9af7cf2f043eed91913e2357`) for paired OFF/ON comparison, combined with `real_world_verified_benchmark.json` for independent verification.
2. **Candidate Models for Comparison:**
   - Baseline (Offline deterministic): `fake-deterministic-v1`
   - Candidate A: `minimaxai/minimax-m3.1-flash` (tested in GOAL 26)
   - Candidate B: `z-ai/glm-5.3-flash` (POLARIS default NVIDIA model)
3. **Protocol Integrity:** Strict atomic pair execution, immutable manifests, and zero-leakage holdout retention.
