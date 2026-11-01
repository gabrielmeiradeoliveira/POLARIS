# GOAL 08.2 — Hybrid Static Context Selection

## Scope and safety boundary

This change adds an opt-in, deterministic prompt-context optimization. It does
not introduce static bug findings, change matching, alter the evidence
validator, enable Behavioral Delta, or modify the frozen historical corpus,
ground truth, results, commits, or tags.

The original context behavior remains the default. The new control is disabled
unless explicitly enabled with `--hybrid-static-selection` or
`DEICIDE_HYBRID_STATIC_SELECTION_ENABLED=true`.

## Design

The existing AST/project-index/dependency-graph pipeline still selects
supplementary snippets. The hybrid layer runs at the final prompt-construction
boundary, where the primary changed-file context and the actual supplementary
serialization are both known:

```text
Git diff + numbered changed-file context
       + AST/dependency selected supplementary snippets
                         |
                         v
       exact overlap proof (opt-in only)
                         |
       suppress only proved changed_symbol duplicates
                         |
                         v
                 existing review prompt
```

`change_impact.py` models the exact-overlap proof. Every numbered source line
in a `changed_symbol` supplementary snippet must be contiguous, cover the
declared span, and have the exact same text as the line serialized into the
primary `context_snippets` payload. `context_relevance.py` then removes only
such snippets. The operation is conservative:

- A direct caller, callee, contract, inheritance, callback, state, or other
  non-`changed_symbol` snippet is retained.
- A missing file/line, differing source text, malformed numbering, incomplete
  span, or non-canonical supplementary serialization returns the original
  context unchanged.
- The diff, changed-file path, line locations, and primary numbered source
  context are never removed.
- No compact metadata is sent to the model. Selection metadata is local; its
  prompt cost is zero tokens.

## Implementation

New modules:

- `src/deicide/context/change_impact.py`
- `src/deicide/context/context_relevance.py`

Updated integration points:

- CLI review/evaluate flags and configuration parsing;
- `ContextSelectionLimits` and evaluation forwarding;
- code-review prompt construction, where filtering is applied;
- context public exports.

The new control is propagated through `DeicideConfig` to the existing context
limits. Behavioral Delta remains independently disabled by default.

## Tests and checks

New tests cover exact line-by-line proof, missing/mismatched/noncanonical
fallbacks, disabled-by-default behavior, retention of direct caller context,
and preservation of the original diff and changed-line locations in the final
prompt.

Executed after implementation:

```text
python -m pytest -p no:cacheprovider --basetemp C:\Users\gabri\AppData\Local\Temp\deicide-goal08-testing -q \
  tests\test_change_impact.py tests\test_hybrid_context.py \
  tests\test_config_and_validation.py tests\test_context_pipeline_integration.py \
  tests\test_production_parity_evaluation.py tests\test_cli_and_reporting.py \
  tests\test_evaluation_usage_accounting.py tests\test_end_to_end_context_oracles.py
```

Result: `59 passed`.

The full offline suite was subsequently run by the GOAL 08.3 verification and
passed (`287 passed`); its command and result are recorded in the A/B report.

## Limitations

This is intentionally the first, smallest hybrid slice. It suppresses only
proved duplicate changed-symbol context. It does not yet compact JSON, change
the fixed system prompt, summarize code, infer contracts beyond the existing
AST pipeline, or optimize indirect dependencies. The historical A/B result is
therefore useful for safety and token accounting, but does not establish LLM
quality equivalence; an authorized external A/B is still required for that.
