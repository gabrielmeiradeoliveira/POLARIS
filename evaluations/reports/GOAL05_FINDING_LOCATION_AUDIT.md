# GOAL 05 — Finding Location Integrity Audit

## Scope and safeguards

This audit was performed entirely offline against the saved fixture and saved NVIDIA pilot result. It made no provider calls, did not rerun the NVIDIA benchmark, alter prompts, models, timeouts, ground truth, production validation rules, or historical result files, and did not recalculate official metrics.

## Reproducible evidence

The audited fixture is `rw-urllib3-port-zero` in `evaluations/fixtures/real_world_verified_benchmark.json`.

Relevant reconstructed source states:

```text
BEFORE, line 6: if self.port is not None:
AFTER,  line 6: if self.port:
AFTER,  line 7: return f"{self.host}:{self.port}"
```

The materialized AFTER source has eight lines:

```text
1 class Url:
2     @property
3     def netloc(self):
4         if self.host is None:
5             return None
6         if self.port:
7             return f"{self.host}:{self.port}"
8         return self.host
```

Before this correction, the fixture declared the compact diff as `@@ -1,3 +1,3 @@` even though its body contained only the line-6 replacement and line-7 context. `parse_unified_diff` consequently recorded added line `{1}` and context line `{2}`. The context sent to the model correctly numbered `if self.port:` as line 6, but the same prompt advertised `added_lines: [1]` and hunk coordinates `new_start: 1`, `new_count: 3`.

The captured NVIDIA candidate was:

```json
{
  "category": "boundary_condition",
  "severity": "medium",
  "confidence": "high",
  "file_path": "src/urllib3/util/url.py",
  "start_line": 6,
  "end_line": 6,
  "title": "Explicit port 0 is omitted from the netloc",
  "evidence": "if self.port:"
}
```

An offline replay through `FindingIntelligenceEngine.process_candidates` before the correction produced zero findings, one rejection, and `FINDING_REJECTED_UNMAPPED_LINE`; the parsed added-line set was `[1]` while the candidate location was 6.

## Finding path and rejection cause

`evaluate_case` parses `fixture.diff_text` using `parse_unified_diff`, builds full numbered fixture contexts, and passes candidates to `FindingIntelligenceEngine.process_candidates`. Its evidence-validation stage calls `validate_and_assess_candidates` in `src/polaris/intelligence/evidence_validator.py`.

That function constructs `LineRange(6, 6)` and invokes `FileDiff.has_changed_overlap` in `src/polaris/git/models.py`. Before the correction, the parsed added-line set was `{1}`. The declared hunk range was 1–3 and its two-line adjacency allowance does not reach line 6. Rejection was therefore mechanically consistent with the malformed parsed diff, but not with the materialized source or the candidate's evidence.

## Minimal correction

Only the target fixture hunk header was changed:

```diff
-@@ -1,3 +1,3 @@
+@@ -6,2 +6,2 @@
```

No hunk body, AFTER source, expected finding, candidate, provider configuration, validator, or saved NVIDIA result was changed. The corrected hunk maps the replacement to new-file line 6 and its context to line 7.

## Classification

**B. Reconstruction defect.**

The model identified the semantic issue and cited the actual changed line in the materialized file. The internal fixture reconstruction supplied incompatible diff coordinates, causing the legitimate finding to be discarded.

## Regression protection and verification

Before the correction, an offline assertion using the captured candidate and the real `FindingIntelligenceEngine` validation path failed with:

```text
AssertionError: {'findings': 0, 'rejected': 1,
'warnings': ['FINDING_REJECTED_UNMAPPED_LINE']}
```

`tests/test_real_world_verified_benchmark.py::test_real_world_port_zero_captured_candidate_survives_production_validation` reproduces the same candidate through `evaluate_case` and the production intelligence pipeline. It requires one true positive and no rejected candidate after correction.

Post-correction offline replay produced hunk `(old_start=6, old_count=2, new_start=6, new_count=2)`, added lines `[6]`, context lines `[7]`, a positive changed-line overlap for line 6, one accepted finding, and zero rejections.

Executed checks:

- The focused regression test passed: `pytest -p no:cacheprovider --basetemp .pytest-goal05-run tests/test_real_world_verified_benchmark.py::test_real_world_port_zero_captured_candidate_survives_production_validation -q`.
- The complete real-world fixture test module passed: `pytest -p no:cacheprovider --basetemp .pytest-goal05-suite tests/test_real_world_verified_benchmark.py -q` (`4 passed`).
- The wider offline suite was run with a workspace-local temporary directory. It had two unrelated failures: `tests/test_cli_and_reporting.py::test_cli_error_exit_codes` and `tests/test_git_integration.py::test_detect_valid_and_invalid_repository`. Both expect a directory below the workspace to be outside Git, but Git resolves the workspace repository as its parent; no unrelated test or production code was changed.
- `git diff --check` exited successfully with no whitespace errors. It emitted only existing line-ending warnings for pre-existing modified tracked files.

## Diagnostic audit of the remaining corpus hunks

The audit compared each hunk header and body against its fixture AFTER source without modifying it. All eight compact historical hunks have at least one structural inconsistency: a header count that does not equal the supplied compact hunk body, a line that does not map to the stated AFTER coordinate, or both.

| Case | Diagnostic result |
| --- | --- |
| `rw-requests-2023-proxy-authorization` | Count and AFTER-coordinate mismatch |
| `rw-requests-jsondecodeerror-pickle` | Count mismatch |
| `rw-requests-super-len-unicode` | Count mismatch |
| `rw-urllib3-cookie-cross-origin` | Count and AFTER-coordinate mismatch |
| `rw-urllib3-proxy-redirect-origin` | Count and AFTER-coordinate mismatch |
| `rw-urllib3-port-zero` | Count and AFTER-coordinate mismatch; corrected in this task |
| `rw-urllib3-invalid-timeout-error` | Count and AFTER-coordinate mismatch |
| `rw-werkzeug-debugger-trusted-host` | AFTER-coordinate mismatch |

This is a diagnostic observation, not a claim that every other case affected a score. No other fixture was changed because that exceeds this task's authorization.

## Limitations and recommendation

The corpus deliberately stores compact historical excerpts rather than complete checkouts. Its diff headers must still be internally consistent whenever their line coordinates drive model instructions or validator decisions. Before the next external experiment, perform a separately approved fixture-integrity pass that verifies, for every hunk, header counts and every added/context line against `file_contents`; repair cases individually with regression tests. Do not retroactively alter already-recorded experiment metrics.
