# POLARIS — MASTER GOAL 31–40: CLEANUP MANIFEST
## Proposed File Categorization & Disposal Plan (Fase A Proposal)

This manifest outlines all detected files and directories in the repository classified into 5 strict tiers. In accordance with Fase A guidelines, **no deletions or destructive operations have taken place**. Execution requires explicit user approval (Fase B).

| Path | Size (bytes) | Status / Action | Purpose / Consumer | Risk & Verification |
| :--- | :--- | :--- | :--- | :--- |
| `evaluations/fixtures/end_to_end_context_benchmark.json` | 14,942 | **PROTECTED** | Frozen GOAL 27 benchmark dataset (SHA-256 verified) | Critical. Must never be altered or removed. |
| `evaluations/results/goal27_smoke_test/results.json` | 4,210 | **PROTECTED** | Frozen GOAL 27 benchmark baseline run result | Critical. Must never be altered or removed. |
| `evaluations/manifests/goal27-model-selection.json` | 1,840 | **PROTECTED** | Frozen GOAL 27 experiment configuration manifest | Critical. Must never be altered or removed. |
| `src/polaris/` (all submodules) | ~250 KB | **KEEP** | Core POLARIS production platform & GOAL 31-40 modules | High. Production code active in test suite. |
| `tests/` (all test suites) | ~180 KB | **KEEP** | 556 automated tests verifying entire platform | High. Core CI/CD validation barrier. |
| `evaluations/goal39_benchmark.py` | 15,200 | **KEEP** | Multi-domain evaluation benchmark runner (GOAL 39) | Medium. Primary empirical evaluation tool. |
| `src/deicide/` | 1,120 | **ARCHIVE** | Backward-compatibility forwarder to `polaris.cli:main` | Low. Can be removed if legacy aliasing is sunset. |
| `pytest_*.txt` (root test stdout dumps) | ~1.2 MB | **DELETE_CANDIDATE** | Ephemeral console output dumps from test runs | Zero. Disposable local execution logs. |
| `.pytest_temp/` | ~4 KB | **DELETE_CANDIDATE** | Temporary test run working directory | Zero. Regenerated automatically by pytest. |
| `demo-repo/` | ~8 KB | **DELETE_CANDIDATE** | Local exploratory repository fixture | Zero. Ephemeral scratch artifact. |
| `evaluations/fixtures/*_temp.json` | ~12 KB | **DELETE_CANDIDATE** | Intermediate slices used by audit scripts | Very Low. Subsets of `end_to_end_context_benchmark.json`. |

---

### Fase B Execution Proposal
Upon receiving explicit approval from the user:
1. Remove root `pytest_*.txt` logs.
2. Remove `.pytest_temp/` and `demo-repo/` local scratch folders.
3. Remove `evaluations/fixtures/*_temp.json`.
4. Run full test suite (`python -m pytest tests/`) to verify 556 passing tests with zero regressions.
