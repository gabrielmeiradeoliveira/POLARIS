# GOAL 06 — Real-World Corpus Integrity

## Executive summary

The corpus began with eight structurally inconsistent compact diffs. Six approved header/count corrections plus the prior GOAL 05 port-zero correction now independently round-trip against materialized AFTER files. `rw-urllib3-proxy-redirect-origin` remains **BLOCKED**: its hunk body uses method indentation while the materialized excerpt is a top-level function, so header-only changes cannot make it valid without altering source content.

## Inventory and outcome

| Case | Project | File | Hunks | Status |
| --- | --- | --- | ---: | --- |
| `rw-requests-2023-proxy-authorization` | requests | `requests/sessions.py` | 1 | valid after header correction |
| `rw-requests-jsondecodeerror-pickle` | requests | `src/requests/exceptions.py` | 1 | valid after header correction |
| `rw-requests-super-len-unicode` | requests | `src/requests/utils.py` | 1 | valid after header correction |
| `rw-urllib3-cookie-cross-origin` | urllib3 | `src/urllib3/util/retry.py` | 1 | valid after header correction |
| `rw-urllib3-proxy-redirect-origin` | urllib3 | `src/urllib3/poolmanager.py` | 1 | blocked; body/AFTER indentation mismatch |
| `rw-urllib3-port-zero` | urllib3 | `src/urllib3/util/url.py` | 1 | valid; GOAL 05 correction retained |
| `rw-urllib3-invalid-timeout-error` | urllib3 | `src/urllib3/connectionpool.py` | 1 | valid after header correction |
| `rw-werkzeug-debugger-trusted-host` | Werkzeug | `src/werkzeug/debug/__init__.py` | 1 | valid after header correction |

## Corrections and semantic integrity

Only diff headers/counts changed. No hunk body, `file_contents`, expected finding, category, evidence, provider setting, production validator, or saved NVIDIA result changed. The independent validator reconstructs BEFORE by reversing each hunk against materialized AFTER, reapplies the hunk, and requires byte-line equivalence with AFTER. This proves structural correspondence for the seven valid fixtures, but not full executable reproduction of historical upstream repositories.

The blocked proxy case declares `13/8` lines while its body has `9/5`; even with corrected counts, its first new line has eight spaces whereas materialized AFTER line 2 has four. It was intentionally left unchanged.

## Automated guardrail

`src/polaris/evaluation/fixture_integrity.py` independently parses hunk bodies without reusing POLARIS's production diff parser. It checks declared counts, materialized new-side coordinates, reverse reconstruction, forward application, and malformed input. `tests/test_real_world_fixture_integrity.py` covers all eight fixtures and negative malformed-count/coordinate cases. The GOAL 05 regression remains in `tests/test_real_world_verified_benchmark.py`.

## Tests

- External-temp focused run: `pytest -p no:cacheprovider --basetemp $env:TEMP\polaris-goal06-pytest-179308 tests/test_real_world_fixture_integrity.py tests/test_real_world_verified_benchmark.py -q` — `7 passed`.
- External-temp full offline suite: `pytest -p no:cacheprovider --basetemp $env:TEMP\polaris-goal06-full-179308 -q` — passed, 100%.
- `git diff --check` — no whitespace errors; only pre-existing line-ending warnings.

No external provider calls, NVIDIA benchmarks, historical-metric recalculation, or commits occurred.

## Recommendation for GOAL 07

**PARTIAL: do not start a new external evaluation yet.** Obtain explicit approval to repair or replace the proxy-redirect materialized excerpt/body consistently, then require the integrity validator to pass every fixture before an external experiment.
