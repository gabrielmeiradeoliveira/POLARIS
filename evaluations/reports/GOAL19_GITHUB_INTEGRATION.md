# GOAL 19 — GitHub PR Review Integration

## Architecture

`polaris.integrations.github` is an isolated boundary around the public `AnalysisReport` and `Finding` contracts. It does not import the orchestrator, modules, parser, or provider implementations. `GitHubReviewAdapter` accepts an already-produced report, fetches PR file metadata through `GitHubClient`, maps findings, publishes through `SafePublisher`, and returns a deterministic `ReviewSummary`.

The package has no live HTTP transport. `GitHubTransport` is an injected protocol, which makes every operation testable with local scripted responses and prevents development-time API access. A future authenticated transport may implement the protocol without changing mapping or publication logic.

## Contracts and flow

1. `GitHubClient` reads PR metadata, changed files, and prior review comments with Link-header pagination.
2. Responses are strictly validated. HTTP 401, 403, 404, 429, 5xx, timeout, network, and malformed payloads become classified `GitHubIntegrationError` values.
3. `map_findings` translates stable `Finding.id` values into `MappedComment` records.
4. `SafePublisher` detects the hidden stable marker `<!-- polaris:finding:<id> -->`, performs dry-run by default, and uses one review-batch request only when `dry_run=False` is explicitly supplied.
5. `build_summary` reports files, findings, severity counts, valid/invalid locations, new/duplicate comments, operational errors, and status deterministically.

## Diff line mapping

Only exact added lines on the right side of a unified patch are review-comment targets. Renamed paths use the current GitHub path; a finding located at the previous path on an exact removed line maps to the left side. Context-only lines, missing patches, binary/unrepresented data, and findings outside changed lines are never forced into a location. They are retained as summary-only findings.

## Safety and publication

Dry-run is the constructor default. Real publication requires an explicit `dry_run=False` caller and sends one complete GitHub review request rather than one request per finding, avoiding a sequence of partially published inline comments. Failed batches record a structured error and claim no publication. No error or audit record contains the token. Retries are bounded and limited to timeout, network, rate-limit, and server failures.

The workflow is separate from existing workflows. It grants only `contents: read` and `pull-requests: read`, avoids `pull_request_target`, disables persisted checkout credentials, skips fork PRs, uses the fake provider, and never gives a token to a publication step. It is therefore intentionally a dry-run preparation workflow; publication is not activated.

## Offline testing

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_github_integration_goal19.py -q
.\.venv\Scripts\python.exe -m ruff check src/polaris/integrations/github tests/test_github_integration_goal19.py
```

The tests use only `ScriptedTransport` fixtures. They cover pagination, auth and authorization failures, 404/429/5xx/rate limits, timeouts, network and malformed payloads, multi-hunk patches, renames, removals, out-of-diff findings, deduplication, dry-run, simulated batching, partial publication failure, and token non-disclosure.

## Future integration and GOAL 18 dependency

The adapter depends only on the currently public, frozen `AnalysisReport.files_analyzed` and `AnalysisReport.findings` surfaces plus the public `Finding` location and stable ID fields. It therefore needs no GOAL 18 changes. If GOAL 18 intentionally changes those public contracts, a small adapter update is the only expected integration point; no engine files are modified by this goal.

To enable a trusted future publisher, implement `GitHubTransport` with an authenticated HTTP transport, pass a token only from a protected non-fork environment, and explicitly construct `SafePublisher(..., dry_run=False)`. Keep the Action default dry-run and retain review-batch semantics.
