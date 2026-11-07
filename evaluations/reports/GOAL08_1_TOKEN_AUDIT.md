# GOAL 08.1 — Token Consumption Audit

## Scope and frozen baseline

This audit is read-only with respect to review behavior. It uses the frozen
historical corpus from `polaris-historical-introducing-v1.0.0`:

- evaluated payload commit: `52618449b4db2c07860f711330d3cf510daf463d`;
- manifest commit: `9ad591cf02efff5cb10fe217955bab3a18ef484c`;
- corpus SHA-256:
  `17019e5f994b1bfc4ba4afe62992cf69bd829f509db3e075cf68ba9615759096`.

No provider request, prompt, finding validator, fixture, ground truth, or
historical result was changed.

## Pipeline map

1. `GitAnalyzer` parses diffs and retrieves bounded changed-file source
   context.
2. `PythonAstAnalyzer`, the project index, and the dependency graph identify
   changed symbols and rank supplementary snippets.
3. `Behavioral Delta` can serialize AST observations, but was disabled for this
   baseline.
4. `CodeReviewModule` serializes file metadata, hunks, and changed-file context
   into JSON, then appends supplementary snippets and optional diagnostics.
5. `ProviderRequest` estimates prompt tokens, `BudgetTracker` reserves attempts,
   and the provider reports actual usage when available.
6. Finding intelligence validates evidence, deduplicates, normalizes severity,
   and reporting emits terminal or JSON output. These later stages do not add
   model-input tokens.

## Measurement method and limitation

The installed environment has neither `tiktoken` nor `transformers`; the NVIDIA
provider does not expose a local tokenizer. All input counts therefore use the
existing deterministic estimator `ceil(len(text) / 4)` from
`polaris.core.models.estimate_token_count`. These are comparable local budget
estimates, not provider-billed tokens.

Each of the eight fixtures was materialized with production-parity context,
`max_context_tokens=2000`, `max_total_tokens=100000`, and Behavioral Delta
disabled. The real `CodeReviewModule._build_user_prompt()` output was measured.
No LLM was invoked. Output tokens are consequently not measured; the request
reserves up to 4,096 output tokens, while actual completion usage must remain a
provider-reported field in any external experiment.

## Reproducible baseline

| Case | System | Diff and changed-context JSON | Supplementary section | Total prompt | Selected snippets |
| --- | ---: | ---: | ---: | ---: | ---: |
| rw-requests-2023-proxy-authorization | 577 | 495 | 387 | 1,511 | 1 |
| rw-requests-jsondecodeerror-pickle | 577 | 315 | 244 | 1,188 | 1 |
| rw-requests-super-len-unicode | 577 | 277 | 222 | 1,127 | 1 |
| rw-urllib3-cookie-cross-origin | 577 | 225 | 205 | 1,059 | 1 |
| rw-urllib3-proxy-redirect-origin | 577 | 452 | 276 | 1,357 | 1 |
| rw-urllib3-port-zero | 577 | 251 | 235 | 1,115 | 1 |
| rw-urllib3-invalid-timeout-error | 577 | 329 | 285 | 1,243 | 1 |
| rw-werkzeug-debugger-trusted-host | 577 | 291 | 279 | 1,199 | 1 |
| **Total** | **4,616** | **2,635** | **2,133** | **9,799** | **8** |

The user-level fixed instructions and XML/JSON section wrappers account for
415 estimated tokens in total. The supplementary raw snippet content accounts
for 1,237 estimated tokens; its wrappers, explanatory prose, and metadata
account for the remaining 896 supplementary-section tokens. Behavioral Delta,
diagnostic sections, omissions, and retries contributed zero tokens in this
controlled baseline.

## Findings

### Confirmed duplication

For every historical fixture, production context selection chose one snippet
with relationship `changed_symbol` in the same changed file already emitted as
`context_snippets` in the primary JSON payload. The selected spans are:

| Case family | Selected relationship | Selected source span |
| --- | --- | --- |
| requests proxy authorization | changed_symbol | `requests/sessions.py:1-18` |
| requests JSON decode | changed_symbol | `src/requests/exceptions.py:1-6` |
| requests Unicode length | changed_symbol | `src/requests/utils.py:1-8` |
| urllib3 cookie redirect | changed_symbol | `src/urllib3/util/retry.py:1-3` |
| urllib3 proxy redirect | changed_symbol | `src/urllib3/poolmanager.py:1-7` |
| urllib3 port zero | changed_symbol | `src/urllib3/util/url.py:1-8` |
| urllib3 timeout | changed_symbol | `src/urllib3/connectionpool.py:1-9` |
| Werkzeug host validation | changed_symbol | `src/werkzeug/debug/__init__.py:1-7` |

This duplicate supplementary section is 2,133 / 9,799 = **21.77%** of the
estimated total prompt input for the corpus. It is the strongest confirmed
token-reduction opportunity, but must be removed only when the exact selected
source range is already represented in changed-file context.

### Other opportunities

- The system prompt is 577 tokens per request (4,616 corpus total). It is a
  fixed safety and output-contract cost; compressing it risks instruction
  quality and is not a first optimization target.
- JSON keys, line maps, XML delimiters, and explanatory section prose create
  structural overhead. They are useful for evidence mapping and prompt-injection
  containment, so compact representation must preserve paths, line numbers,
  provenance, and trust boundaries.
- The current static ranker already enforces token, file, snippet, graph-depth,
  and omission limits. No fixture approached the 2,000-token supplementary
  budget, so this corpus alone cannot demonstrate budget-pressure behavior.

## Risks and guardrails for optimization

- A changed-symbol snippet is not always duplicate: a production diff may carry
  only a narrow hunk while the selected symbol supplies necessary surrounding
  contract or control-flow context.
- Direct callers, callees, inheritance relations, callbacks, shared state, and
  exception contracts must never be discarded merely because their file is not
  changed.
- Static analysis must be advisory. Ambiguous parsing, dynamic dispatch, or an
  incomplete index must preserve baseline context and report a fallback.
- Estimated savings must not be reported as billed-provider savings without a
  live provider usage response.

## Recommended next step

Implement an opt-in hybrid context mode that classifies source as essential,
relevant, or optional. Its first deterministic optimization should suppress
only exact changed-symbol overlap, while retaining all indirect dependency
context and falling back to the baseline selector whenever overlap proof is
incomplete.
