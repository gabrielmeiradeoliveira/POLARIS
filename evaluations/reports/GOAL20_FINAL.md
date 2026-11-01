# Goal 20 — End-to-End GitHub PR Review & Release Hardening

## Scope and result

Goal 20 is complete as an offline, fixture-driven vertical slice. No GitHub,
NVIDIA, or other external service was contacted; no credentials were read; no
review comment or repository change was published.

The new `GitHubPullRequestReview` bridge fetches PR metadata and changed files
through the existing injected `GitHubClient`, reconstructs a bounded unified
diff from available patches, runs the existing `CodeReviewModule` and
`FindingIntelligenceEngine`, maps validated findings with the existing strict
diff mapper, and invokes the existing `SafePublisher` in dry-run mode. It
returns the normal `AnalysisReport` plus the structured `ReviewSummary`.

`deicide github review --repo OWNER/REPO --pr NUMBER --fixture FIXTURE.json
--dry-run` is now an offline-only command. Its local fixture transport accepts
only read-like fixture responses, the command accepts only the `fake` provider,
and it has no token option or HTTP implementation. JSON output contains both
the analysis report and review summary. Configuration, malformed fixture, GitHub
payload, budget, and provider errors exit without publication.

## Evidence-backed validation

| Check | Result |
| --- | --- |
| Focused GitHub integration + Goal 20 E2E tests | 22 passed |
| Full discovered pytest suite | passed (exit 0; 22.0 s) |
| Ruff lint (`src`, `tests`) | passed |
| Changed-path formatting | passed |
| `git diff --check` | passed |
| Network/publish audit | no HTTP transport; fixture transport rejects non-GET; Goal 20 CLI constructs only dry-run publisher |

The repository-wide formatter check remains non-clean because of pre-existing
formatting drift in unrelated context, evaluation, provider, and legacy-test
files. This task did not reformat or otherwise change those files.

The E2E tests exercise actual production components rather than a mocked review
pipeline: injected transport -> `GitHubClient` -> PR patch conversion ->
`CodeReviewModule` -> `FindingIntelligenceEngine` -> `GitHubReviewAdapter` ->
`SafePublisher` -> `ReviewSummary`.

They cover a renamed file with a concrete division-by-zero defect, a clean
change, a missing/truncated patch, duplicate marker detection, exhausted token
budget, CLI JSON output, and rejection of the external NVIDIA provider. All
transport observations are GET-only. The budget-exhaustion test confirms that
publication preparation is not reached after analysis fails.

## Small-sample E2E metrics

These figures are smoke-test measurements, not a benchmark claim:

| Layer | Positive | Clean negative | TP | FP | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Engine detection | 1 | 1 | 1 | 0 | 0 | 1.00 | 1.00 |
| Diff mapping | 1 located finding | — | 1 | 0 | 0 | 1.00 | 1.00 |
| Comment preparation | 1 dry-run proposal | — | 1 | 0 | 0 | 1.00 | 1.00 |

The missing-patch scenario is deliberately excluded from these rates because
the correct outcome is `incomplete`, not a detection decision. No simulated
comment is treated as a published comment.

## Safety and release review

- The integration still has an explicit `SafePublisher(dry_run=True)` default;
  Goal 20 adds no CLI path that can disable it.
- Existing strict mapping permits comments only at exact added or removed diff
  lines; rename origins, multi-hunks, absent patches, and non-locatable findings
  remain summary-only or dry-run-only.
- The fixture transport validates its root shape, uses no network library, and
  returns `405` for any non-GET request.
- The workflow uses `pull_request`, never `pull_request_target`, has read-only
  `contents` and `pull-requests` permissions, disables persisted checkout
  credentials, skips fork PRs, and runs the fake provider. Its invalid
  `--base-revision` option was corrected to `--base`.
- The reusable workflow input no longer suggests that publication is available.
- Historical fixtures, manifests, result directories, scratch data, and the
  user-owned `AGENTS.md`, `calculator.py`, and `context_test.py` changes were
  not altered by this task.

## Remaining release limitation

There is intentionally no real GitHub HTTP transport or credential wiring.
That means live GitHub publication remains unavailable until a separately
authorized, security-reviewed integration is introduced. This is the expected
safe state for the offline Goal 20 scope.
