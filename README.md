# POLARIS

## Local dashboard (MVP)

Run the complete local dashboard with PostgreSQL using Docker Compose:

```bash
cp .env.example .env # set POSTGRES_PASSWORD and POLARIS_REPOSITORIES_PATH
docker compose up --build -d
```

Open `http://127.0.0.1:3000`. PostgreSQL is internal-only; API and worker read only
the explicit `/repositories` bind mount. The worker runs static analysis with the fake
provider and never executes analyzed repositories or calls NVIDIA.

```bash
docker compose logs -f
docker compose down
docker compose down -v # removes the PostgreSQL data volume
```

**POLARIS** is an open-source, human-controlled, modular AI software assurance and code intelligence platform. Its local CLI engine inspects Git changes, retrieves bounded surrounding context, identifies concrete correctness bugs, validates findings against actual changed lines and source evidence, deduplicates overlapping reports, enforces persistent API rate and daily quotas, and outputs terminal or machine-readable JSON reports.

---

## Architecture & Workflow

```text
Git Repository
      |
      v
Detect Changes (GitAnalyzer)
      |
      v
Extract Diff & Line Mapping (DiffBundle)
      |
      v
Retrieve Bounded Source Context (FileContext)
      |
      v
Atomic Quota & Budget Reservation (BudgetTracker + SQLite UsageStore)
      |
      v
AI Code Review Module (module_id: "code_review")
      |
      v
Reconcile Actual Token Usage & Retries
      |
      v
Validate Findings (Schema, Changed Lines, Verbatim Evidence)
      |
      v
Deduplicate Findings (Stable IDs & Overlap Resolution)
      |
      v
Terminal / JSON Report
```

### Core Components (`src/polaris/`)

- **`polaris.core`**: Configuration (`PolarisConfig`), per-analysis and persistent execution budgets (`ExecutionBudget`, `BudgetTracker`), shared schemas (`Finding`, `CandidateFinding`, `AnalysisReport`), validation and deduplication (`validation.py`), module registry (`ModuleRegistry`), and stateless orchestration (`AnalysisOrchestrator`).
- **`polaris.quota`**: Provider-independent SQLite usage ledger (`UsageStore`, `QuotaSnapshot`, `RequestStatus`), atomic `BEGIN IMMEDIATE` request reservations, stale reservation expiration, rolling 60-second (`RPM`/`TPM`) and UTC daily (`RPD`) quota windows, and API key scope isolation.
- **`polaris.git`**: Safe read-only Git repository detection, diff extraction, unified diff hunk/line mapping, and bounded working-tree context retrieval (`GitAnalyzer`) with path traversal and symlink-escape protection.
- **`polaris.context`**: Deterministic repository context engine (MVP 1.2) featuring secure Python AST symbol extraction (`PythonAstAnalyzer`), cross-file import and call-site dependency indexing (`DependencyGraph`), depth-based context ranking, token-budgeted snippet slicing, and deletion-only diff symbol recovery.
- **`polaris.intelligence`**: Deterministic Finding Intelligence Engine (MVP 1.3) post-processing pipeline featuring evidence grounding and AST symbol verification (`EvidenceValidator`), semantic deduplication with collision prevention (`SemanticDeduplicator`), category-based severity ceilings and confidence normalization (`SeverityNormalizer`), and multi-key deterministic prioritization (`FindingPrioritizer`). Operates 100% locally with zero additional LLM requests.
- **`polaris.providers`**: Provider-neutral `LLMProvider` protocol, deterministic offline `FakeProvider`, and production-grade `NvidiaProvider` (using Python's standard library `urllib.request`, per-attempt quota reservation, bounded retries, `Retry-After` handling, request timeouts, and token usage reconciliation).
- **`polaris.modules.code_review`**: First analysis module (`module_id = "code_review"`), decoupled from provisional mythological display names. Focuses strictly on functional correctness bugs rather than stylistic nitpicks.
- **`polaris.reporting`**: Human-readable terminal formatters and strict machine-readable JSON formatters for both review reports and usage/quota snapshots.
- **`polaris.evaluation`**: Offline evaluation runner (`evaluate_corpus`) measuring True Positives, False Positives, False Negatives, Precision, Recall, False Positive Rate, Latency, and Token Consumption across synthetic fixtures (`code_review_corpus.json`, `finding_intelligence_corpus.json`) and authentic Python benchmark cases (`real_world_benchmark.json`).

---

## Installation

Requires **Python 3.12+**:

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

pip install -e ".[dev]"
```

---

## Configuration

POLARIS is configured via CLI flags, environment variables, or a `.env` file in the POLARIS application directory. **POLARIS never reads `.env` or configuration files from a repository being analyzed.**

Copy `.env.example` to `.env` and configure your provider, model, API key, and quota limits:

```dotenv
POLARIS_PROVIDER=nvidia
POLARIS_MODEL=z-ai/glm-5.3-flash

POLARIS_MAX_REQUESTS=3
POLARIS_MAX_TOKENS=8000

POLARIS_QUOTA_ENABLED=true
POLARIS_QUOTA_SCOPE=nvidia-glm

NVIDIA_API_KEY=your_nvidia_api_key_here
POLARIS_ALLOW_EXTERNAL_CODE=1
```

| Environment Variable | Default | Description |
|---|---|---|
| `POLARIS_PROVIDER` | `nvidia` | AI provider (`nvidia` or `fake`). |
| `POLARIS_MODEL` | `z-ai/glm-5.3-flash` (or `fake-deterministic-v1`) | Model name override. |
| `POLARIS_MAX_REQUESTS` | `3` | Maximum API request attempts allowed per analysis run. |
| `POLARIS_MAX_TOKENS` | `8000` | Maximum total tokens allowed per analysis run. |
| `POLARIS_MAX_RETRIES` | `0` | Maximum automatic retries on transient HTTP 429/5xx or timeout (`0` = 1 initial attempt, no automatic retries). |
| `POLARIS_RATE_LIMIT_RPM` | *None* | Persistent requests-per-minute limit (rolling 60s window). |
| `POLARIS_RATE_LIMIT_TPM` | *None* | Persistent input-tokens-per-minute limit (rolling 60s window). |
| `POLARIS_RATE_LIMIT_RPD` | *None* | Persistent requests-per-day limit (UTC calendar day). |
| `POLARIS_QUOTA_ENABLED` | `true` | Enable persistent SQLite quota enforcement (`true`/`false`). |
| `POLARIS_QUOTA_SCOPE` | Key SHA-256 fingerprint | Optional shared quota bucket name across keys in the same project. |
| `POLARIS_USAGE_DB_PATH` | OS user data dir | Optional custom path for the SQLite usage database. |
| `NVIDIA_API_KEY` / `POLARIS_API_KEY` | *None* | API key for NVIDIA API (resolved with precedence: process `NVIDIA_API_KEY` > process `POLARIS_API_KEY` > trusted `.env` `NVIDIA_API_KEY` > trusted `.env` `POLARIS_API_KEY`). |
| `POLARIS_ALLOW_EXTERNAL_CODE` | `0` | Explicit authorization to send repository diffs to an external AI provider (`1` to authorize). |
| `POLARIS_TIMEOUT_SECONDS` | `60.0` | Per-request HTTP socket timeout in seconds passed directly to the HTTP transport (`--timeout` on CLI). |
| `POLARIS_CONTEXT_ENABLED` | `true` | Enable or disable AST-based cross-file context engine (`--context` / `--no-context`). |
| `POLARIS_CONTEXT_MAX_TOKENS` | `2000` | Maximum token budget allocated for supplementary repository context (`--context-tokens`). |
| `POLARIS_CONTEXT_MAX_FILES` | `8` | Maximum number of supplementary context files to select (`--context-files`). |
| `POLARIS_CONTEXT_MAX_SNIPPETS` | `16` | Maximum number of supplementary code snippets to select (`--context-snippets`). |
| `POLARIS_CONTEXT_MAX_SNIPPET_LINES` | `60` | Maximum line count per sliced snippet before truncation (`60`). |
| `POLARIS_CONTEXT_MAX_GRAPH_DEPTH` | `2` | Maximum traversal depth in the dependency graph (`2`). |
| `POLARIS_HYBRID_STATIC_SELECTION_ENABLED` | `false` | Opt in to exact supplementary-context duplicate suppression. |
| `POLARIS_STATIC_RELEVANCE_SELECTION_ENABLED` | `false` | Opt in to CFG/data-flow-informed ranking of proven direct context. |

---

## Persistent Quota & Usage Tracking

- **Database Location**: Stored outside analyzed repositories in the OS user data directory:
  - **Windows**: `%LOCALAPPDATA%\polaris\usage.sqlite3`
  - **macOS**: `~/Library/Application Support/polaris/usage.sqlite3`
  - **Linux**: `${XDG_DATA_HOME:-~/.local/share}/polaris/usage.sqlite3`
- **Privacy**: The SQLite ledger stores only `provider`, `model`, `quota_scope` (a non-reversible truncated SHA-256 hash when derived from an API key), UTC timestamps, request lifecycle status, and token counts. **API keys, prompts, diffs, filenames, source code, and model responses are never stored.**
- **Window Calculations & Quota Limitations**:
  - **Daily Window (`RPD`)**: Calculated per UTC calendar day (`00:00:00Z` through `23:59:59Z`). Note that a provider's server-side daily quota may reset on a different timezone (such as Pacific Time) or rolling window.
  - **Per-Minute Windows (`RPM` & `TPM`)**: Calculated over a rolling 60-second window (`[now_utc - 60s, now_utc]`).
  - **Local Estimation**: Usage tracked in SQLite reflects requests initiated by this local POLARIS installation. Requests made by other tools using the same API key/project are not visible locally.
  - **Uncertain Network Failures & Retries**: Every retry that reaches the provider reserves and consumes an attempt. Network timeouts or connection failures where it is unknown whether the provider received the request are recorded as `uncertain` and conservatively retained against quota rather than refunded. A stale local reservation is likewise transitioned to `uncertain`; it is never automatically refunded.

---

## Context Engine (MVP 1.2)

POLARIS MVP 1.2 introduces an autonomous, deterministic, AST-powered repository context engine. When reviewing code changes, the engine maps modified lines to syntactic symbols, traces cross-file references across the repository, deterministically ranks relevant context, and fits extracted snippets into a strict token budget alongside the diff.

### Capabilities

1. **Python AST Symbol Extraction**:
   - Parses modified and repository Python files using the standard library `ast` module.
   - Extracts top-level and nested classes, methods, synchronous functions, and `async def` coroutines.
   - Accurately tracks exact line spans (`start_line`, `end_line`), parent scopes, and qualified names (e.g., `Class.method`).
2. **Cross-File Dependency Discovery**:
   - Bounded discovery of repository Python files with symlink-escape and size protections.
   - Discovers import statements (`import foo`, `from foo.bar import baz, qux as q`).
   - Identifies intra-file and cross-file call sites, resolving them against the indexed module symbol table.
   - Distinguishes confirmed `RESOLVED` relationships from `AMBIGUOUS` or `UNRESOLVED` references, never fabricating hallucinated graph targets.
3. **Deterministic Ranking**:
   - Scores candidate contexts using deterministic priority ordering: direct callers/callees > imported definitions > class-associated methods > module-level definitions > transitive dependencies.
   - Breaks ties deterministically by relationship depth, file path, and start line, avoiding non-deterministic hashing or ordering.
4. **Token-Budgeted Snippet Selection**:
   - Slices exact source code ranges with safety boundaries (`max_snippet_lines`, `max_context_files`, `max_snippets`).
   - Dynamically checks available token headroom against the overall run budget and baseline prompt tokens.
   - Omitted candidates are explicitly recorded with reasons (e.g., `token_budget_exceeded`, `file_limit_exceeded`, `duplicate`).
5. **Deletion-Only Diff Detection**:
   - Accurately maps symbol boundaries in diff hunks where code was purely deleted (`-` lines without `+` lines).
   - Recovers caller and dependent context even when functions, methods, or entire files are deleted.

### CLI Options

The Context Engine is enabled by default and can be configured or disabled via CLI options:

- `--context` / `--no-context`: Enable or disable the AST cross-file context engine (default: enabled).
- `--context-tokens <int>`: Set the maximum token budget allocated for supplementary repository context (default: 2000).
- `--context-files <int>`: Set the maximum number of supplementary context files to select (default: 8).
- `--context-snippets <int>`: Set the maximum number of supplementary code snippets to select (default: 16).
- `--hybrid-static-selection` / `--no-hybrid-static-selection`: Enable exact supplementary-context duplicate suppression (default: disabled).
- `--static-relevance-selection` / `--no-static-relevance-selection`: Enable bounded CFG/data-flow-informed ranking of proven direct context (default: disabled).

### Known MVP 1.2 Limitations

- **Python Only**: The AST parser and dependency graph currently support Python source files (`.py`). Multi-language AST support is planned for future MVPs.
- **Static Resolution Only**: Symbol resolution relies on deterministic static analysis. Dynamic runtime behaviors (such as `getattr()`, `importlib`, dynamic `*args` / `**kwargs` dispatch, or monkey-patching) are not dynamically executed.
- **Single-Repository Boundary**: Context extraction is strictly bounded to the target Git repository root. External third-party packages in virtual environments or system paths are omitted from snippet extraction.

---

## Finding Intelligence Engine (MVP 1.3)

POLARIS MVP 1.3 introduces a deterministic post-processing pipeline that transforms raw candidate findings into reliable, evidence-grounded review reports. The engine runs entirely locally, requiring **zero additional LLM calls and zero extra token expenditure**.

```text
Raw Candidate Findings (from LLM or analysis module)
                   |
                   v
1. Evidence Validation & Grounding (EvidenceValidator)
   - Verifies lines against diff additions & deletions
   - Grounds referenced symbols against AST index
   - Downgrades confidence on partial evidence without dropping legitimate bugs
   - Rejects hallucinated code and ungrounded claims
                   |
                   v
2. Semantic Deduplication (SemanticDeduplicator)
   - Detects overlapping or adjacent findings
   - Computes title token Jaccard similarity and category compatibility
   - Enforces anti-collision guards: preserves distinct bugs on adjacent lines
   - Merges redundant reports while preserving strongest evidence and remediation
                   |
                   v
3. Severity Normalization (SeverityNormalizer)
   - Enforces deterministic category-based severity ceilings
   - Caps severity on low-confidence or partial evidence
   - Eliminates model severity inflation (e.g. style nitpicks labeled critical)
                   |
                   v
4. Deterministic Prioritization (FindingPrioritizer)
   - Multi-key sort: Severity -> Confidence -> File Path -> Line -> Finding ID
   - Stable SHA-256 finding identifiers
                   |
                   v
Final Validated Findings (AnalysisReport)
```

### Key Capabilities

1. **Evidence Validation & Grounding (`EvidenceValidator`)**:
   - Cross-checks finding line numbers against unified diff hunks (including deletion-only hunks).
   - Validates that code identifiers, function calls, and classes cited in evidence actually exist in the AST symbol index or extracted context snippets.
   - Categorizes evidence strength into `STRONG`, `PARTIAL`, or `NONE`.
   - Partial or imprecise citations have their confidence downgraded rather than prematurely discarding genuine bugs.

2. **Semantic Deduplication (`SemanticDeduplicator`)**:
   - Compares candidate findings using spatial proximity (`tolerance=1`), category compatibility, and Jaccard similarity of normalized title keywords.
   - Anti-collision protection (`_is_distinct_issue`): Prevents distinct bugs on adjacent lines (such as a hardcoded credential on line 10 and an unclosed file on line 11) from being mistakenly merged.

3. **Severity & Confidence Normalization (`SeverityNormalizer`)**:
   - Establishes deterministic ceiling rules per category (e.g., `boundary_condition` capped at `HIGH`, `error_handling` capped at `HIGH` for high confidence, `style` capped at `INFO`).
   - Normalizes inflated severities produced by generative models without suppressing the underlying finding.

4. **Deterministic Prioritization (`FindingPrioritizer`)**:
   - Sorts findings predictably across repeated runs:
     $$\text{Severity Rank} \downarrow \;\to\; \text{Confidence Rank} \downarrow \;\to\; \text{File Path} \uparrow \;\to\; \text{Start Line} \uparrow \;\to\; \text{Deterministic ID} \uparrow$$
   - Emits consistent `dcd-<sha256[:12]>` fingerprints.

---

## Evaluation Benchmark & Methodology

POLARIS includes an evidence-based quality evaluation framework (`polaris evaluate`) to measure detection accuracy, false alarm rejection, and deduplication effectiveness across curated and real-world test cases.

### Evaluation Corpora

1. **Curated Regression Corpus (`evaluations/fixtures/finding_intelligence_corpus.json`)**:
   - 10 synthetic fixtures testing specific edge cases: hallucinated symbols, semantic duplicates, adjacent distinct bugs, deletion diffs, severity normalization, supplementary context grounding, and ambiguous evidence.
2. **Real-World Benchmark Corpus (`evaluations/fixtures/real_world_benchmark.json`)**:
   - 33 independently labeled cases across 11 major Python repositories (`psf/requests`, `urllib3/urllib3`, `python/cpython`, `pallets/flask`, `pallets/werkzeug`, `pallets/jinja`, `tiangolo/fastapi`, `psf/black`, `pytest-dev/pytest`, `tqdm/tqdm`, and local `POLARIS` history).
   - Contains **22 positive (buggy) cases** and **11 negative (clean) cases**.

### Benchmark Provenance Classification

- **Fully Verified (23 cases)**:
  - 20 authentic open-source security fixes and bugs verified against official CVE advisories, GitHub issue trackers, or the BugsInPy benchmark dataset.
  - 3 local POLARIS cases verified against repository git history (`a76d89b`, `ae580a6`, `cfc826d`).
- **Partially Verified / Reference-Modeled (10 cases)**:
  - 10 clean negative examples modeling real-world refactorings, typing annotations, docstrings, and constant definitions from upstream repositories (without full local clones of historical dependency trees).
- **Unverified / Fabricated (0 cases)**: Zero cases contain fabricated bugs or synthetic inventions.

### Benchmark Modes & Separation of Metrics

The evaluation framework explicitly distinguishes three measurement tiers:

1. **Candidate-Finding Post-Processing Evaluation (Default)**:
   - Evaluates how effectively the post-processing engine filters, deduplicates, and normalizes pre-generated candidate findings against known ground truth.
   - On the 33-case real-world benchmark, the Finding Intelligence Engine achieves:
     - **Precision**: 95.65% (22 TP, 1 FP on clean code with verbatim quote)
     - **Recall**: 100.00% (22 / 22 ground-truth bugs detected)
     - **Legitimate Findings Rejected**: 0
     - **Severity Mismatches**: 1 (detected bug had `HIGH` normalized severity vs. `MEDIUM` expected)
   - > [!IMPORTANT]
     > **These metrics measure post-processing filtering performance on candidate findings, NOT autonomous end-to-end bug detection from raw source code.** Post-processing takes candidate findings generated by human reviewers or models and verifies them deterministically.

2. **Strict Severity Calibration (`--strict-severity`)**:
   - Enforces exact severity equality between actual and expected findings.
   - If a detected bug has a different severity than ground truth, it is treated as unmatched under strict mode.
   - Under `--strict-severity`, the Finding Intelligence Engine achieves **91.30% precision** and **95.45% recall** (outperforming the legacy Baseline Validator's 86.96% precision and 90.91% recall due to category ceiling normalization).

3. **End-to-End Evaluation with FakeProvider (`--end-to-end`)**:
   - Runs the complete pipeline (diff parsing -> AST context retrieval -> provider -> post-processing).
   - When run with the offline `FakeProvider`, the benchmark reports **0.00% Recall** (0 / 22 bugs detected) and **0.00% Precision**.
   - This honestly reflects that `FakeProvider` is a deterministic regex test double that cannot detect complex semantic vulnerabilities.

4. **Genuine LLM-Powered Bug Detection (Unbenchmarked in MVP 1.3)**:
   - Autonomous bug detection using frontier LLM providers (e.g. NVIDIA Nemotron, DeepSeek, GLM) requires live network API execution and token expenditure.
   - Live model benchmarks will be published as separate provider capability evaluations in future milestones.

### Metric Definitions

- **Precision**: $\frac{\text{TP}}{\text{TP} + \text{FP}}$ when $\text{TP} + \text{FP} > 0$, otherwise $0.0\%$ (zero predictions never report 100% precision).
- **Recall**: $\frac{\text{TP}}{\text{TP} + \text{FN}}$ when $\text{TP} + \text{FN} > 0$, otherwise $1.0$.
- **False Positive Rate (Clean Cases)**: Fraction of negative cases producing at least one false positive ($\frac{\text{Clean Cases with FP}}{\text{Total Clean Cases}}$).
- **Legitimate Findings Rejected**: Count of ground-truth bugs where a candidate finding was present but discarded by validation.
- **Severity Mismatches**: Detected bugs where file, lines, and category matched, but severity differed from ground truth.

### CLI Evaluation Options

- `polaris evaluate`: Evaluates the default corpus using the Finding Intelligence Engine.
- `polaris evaluate --baseline`: Compares against the legacy pre-MVP 1.3 baseline validator.
- `polaris evaluate --strict-severity`: Enforces strict severity equality.
- `polaris evaluate --end-to-end` (`--e2e`): Runs the full end-to-end review pipeline with the configured provider.
- `polaris evaluate --provider <name>`: Selects AI provider (`fake` or `nvidia`).
- `polaris evaluate --allow-external`: Explicitly authorizes transmitting evaluation fixtures to an external provider (required for `nvidia`).
- `polaris evaluate --max-cases <int>`: Limits evaluation to the first $N$ benchmark cases.
- `polaris evaluate --max-requests <int>`: Enforces a cumulative API request ceiling across the benchmark run.
- `polaris evaluate --max-tokens <int>`: Enforces a cumulative token ceiling across the benchmark run.
- `polaris evaluate --fixtures <path>`: Specifies a custom fixtures JSON file.
- `polaris evaluate --format json`: Outputs structured machine-readable evaluation metrics.
- `polaris evaluate --history-dir <path> --history-run-id <id>`: Appends a sanitized, integrity-checked validation manifest and run-scoped trend reports.

### Validation History

History manifests preserve aggregate metrics and sanitized finding decisions while separating real and synthetic corpora. Qualitative confidence remains a label; Brier scores and reliability curves require explicitly numeric probabilities and enough assessed samples. See [evaluation history](evaluations/history/README.md) for retention and artifact policy.

---

## Usage

### 1. Show CLI help

```bash
polaris --help
```

### 2. Inspect persistent API usage and remaining quota (`polaris usage`)

```bash
# Human-readable terminal report:
polaris usage

# Machine-readable JSON report:
polaris usage --format json
```

### 3. Analyze local uncommitted changes (`polaris review`)

By default, `polaris review` inspects all local uncommitted changes in the current Git repository, including **both staged and unstaged changes**:

```bash
# Offline deterministic review (no API key required; isolated from external quota):
polaris review --provider fake

# Real review using NVIDIA (requires NVIDIA_API_KEY and explicit external authorization):
polaris review --provider nvidia --allow-external
```

### 4. Configure AST context selection

By default, cross-file AST context discovery is automatically performed. You can tune context limits or disable context extraction entirely:

```bash
# Review with customized context token and snippet limits:
polaris review --provider fake --context-tokens 1500 --context-files 4 --context-snippets 8

# Review with AST context engine disabled (diff only):
polaris review --provider fake --no-context
```

### 5. Compare against a specific Git revision (`--base`)

```bash
polaris review --base HEAD~1 --provider fake
```

### 6. Structured JSON output (`--format json`)

```bash
polaris review --provider fake --format json
```

### 7. Run the evaluation benchmark (`polaris evaluate`)

```bash
# Evaluate candidate findings on the default curated corpus:
polaris evaluate

# Compare Finding Intelligence against the legacy pre-MVP 1.3 baseline validator:
polaris evaluate --baseline

# Evaluate with strict severity calibration (exact severity equality required):
polaris evaluate --strict-severity

# Evaluate on the 33-case real-world open-source benchmark:
polaris evaluate --fixtures evaluations/fixtures/real_world_benchmark.json

# Run the full end-to-end pipeline (AST context + provider + post-processing):
polaris evaluate --end-to-end --provider fake

# Evaluate a bounded slice of benchmark cases with safety budget limits:
polaris evaluate --fixtures evaluations/fixtures/real_world_benchmark.json --max-cases 5 --max-requests 5

# Benchmark real NVIDIA LLM bug-detection accuracy with explicit external authorization:
polaris evaluate --fixtures evaluations/fixtures/real_world_benchmark.json --provider nvidia --allow-external --max-cases 5 --max-requests 5

# Export evaluation metrics in machine-readable JSON format:
polaris evaluate --fixtures evaluations/fixtures/real_world_benchmark.json --format json
```

---

## Process Exit Codes

| Exit Code | Meaning |
|---|---|
| `0` | Command completed successfully |
| `1` | Unexpected internal error |
| `2` | Configuration error (missing credentials, unsupported provider, invalid flags/limits) |
| `3` | Repository or Git error (not a Git repository, invalid revision) |
| `4` | AI provider failure or exhausted rate-limit retries |
| `5` | Execution budget or persistent API quota (`RPD`/`RPM`/`TPM`) exceeded |
| `6` | Security or trust boundary violation (path traversal, symlink escape) |

## Polaris GitHub App (offline-ready)

Create a GitHub App with Metadata read, Contents read, Pull requests read, and Checks write. Configure its webhook for `POST /api/github/webhooks` and set `GITHUB_WEBHOOK_SECRET`; requests without a valid `X-Hub-Signature-256` are rejected before JSON decoding. Set `GITHUB_APP_ID` and mount its PEM key outside the image at `GITHUB_APP_PRIVATE_KEY_PATH`. Installation tokens are short-lived and never stored in PostgreSQL.

For local development or isolated staging only, set `POLARIS_ADMIN_TOKEN` in the API environment and send it as `X-Polaris-Admin-Token` for policy changes. Production requires OAuth/SSO and RBAC before exposing administrative routes. Configure `Polaris / Quality Gate` as a required GitHub Ruleset check manually after staging validation; Polaris never edits Rulesets.

Staging validation: use a disposable organization, publicly reachable HTTPS webhook URL, test App key and webhook secret, then install on one disposable repository. Exercise installation sync, a PR baseline/head analysis, a stale-SHA retry, and a failed/incomplete run. Do not use company repositories or enable merge blocking during this validation.

### Local GitHub PAT

For local development only, set `POLARIS_GITHUB_TOKEN` in `.env`. Polaris validates it server-side with `GET /user` and discovers repositories through `GET /user/repos`; the token is never sent to the browser, logged, or persisted. A classic token needs repository read access for private repositories. SSO, expired tokens, missing permissions, and rate limits are returned as explicit API errors. No GitHub Check or Ruleset is published in PAT mode.

The Compose worker uses a 512 MiB `noexec,nosuid` tmpfs for temporary Git checkouts. This is a hard Docker-managed bound for local staging; deployments without tmpfs must provide an equivalent filesystem or volume quota before enabling PAT analysis.
