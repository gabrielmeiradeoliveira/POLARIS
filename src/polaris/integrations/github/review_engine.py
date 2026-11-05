"""Offline PR-to-DEICIDE bridge reusing the standard review module and validation pipeline."""

from __future__ import annotations

import time

from deicide.core.models import AnalysisReport, BudgetTracker, ExecutionBudget, ProviderInfo
from deicide.git.analyzer import parse_unified_diff
from deicide.git.models import ContextSnippet, DiffBundle, FileContext
from deicide.integrations.github.adapter import GitHubReviewAdapter
from deicide.integrations.github.client import GitHubClient
from deicide.integrations.github.models import ChangedFile, ReviewSummary
from deicide.integrations.github.publishing import SafePublisher
from deicide.intelligence.pipeline import FindingIntelligenceEngine
from deicide.modules.code_review import CodeReviewModule
from deicide.providers.base import LLMProvider


def _unified_diff(files: list[ChangedFile]) -> str:
    """Convert GitHub patch fragments into the standard parser's unified format."""
    blocks: list[str] = []
    for item in files:
        if not item.patch:
            continue
        old_path = item.previous_path or item.path
        blocks.extend(
            [
                f"diff --git a/{old_path} b/{item.path}",
                f"--- a/{old_path}",
                f"+++ b/{item.path}",
                item.patch,
            ]
        )
    return "\n".join(blocks) + ("\n" if blocks else "")


def _contexts(bundle: DiffBundle) -> dict[str, FileContext]:
    """Build bounded patch-only source context; missing content is never invented."""
    contexts: dict[str, FileContext] = {}
    for file_diff in bundle.files:
        numbered: dict[int, str] = {}
        for hunk in file_diff.hunks:
            line = hunk.new_start
            for raw in hunk.lines:
                if (raw.startswith("+") and not raw.startswith("+++")) or raw.startswith(" "):
                    numbered[line] = raw[1:]
                    line += 1
        snippets = (
            [ContextSnippet(start_line=min(numbered), end_line=max(numbered), lines=numbered)] if numbered else []
        )
        contexts[file_diff.new_path] = FileContext(
            file_path=file_diff.new_path,
            total_lines=max(numbered, default=0),
            snippets=snippets,
            truncated=True,
        )
    return contexts


class GitHubPullRequestReview:
    """End-to-end offline PR review with injectable GitHub transport and provider."""

    def __init__(
        self,
        client: GitHubClient,
        provider: LLMProvider,
        *,
        publisher: SafePublisher | None = None,
        budget: ExecutionBudget | None = None,
    ) -> None:
        self._client = client
        self._provider = provider
        self._publisher = publisher or SafePublisher(client, dry_run=True)
        self._budget = budget or ExecutionBudget(max_requests=10, max_total_tokens=20_000)

    def review(self, owner: str, repository: str, number: int) -> tuple[AnalysisReport, ReviewSummary]:
        """Fetch a PR through the injected client, analyze its patches, and dry-run publish."""
        started = time.perf_counter_ns()
        pr = self._client.get_pull_request(owner, repository, number)
        files = self._client.list_changed_files(pr)
        bundle = DiffBundle(
            repository_root=f"github:{owner}/{repository}",
            base_revision=pr.base_sha,
            target_description=f"github-pr:{owner}/{repository}#{number}",
            files=parse_unified_diff(_unified_diff(files)),
            truncated=any(item.patch is None for item in files),
        )
        contexts = _contexts(bundle)
        tracker = BudgetTracker(
            self._budget,
            provider_name=self._provider.provider_name,
            model_name=self._provider.model_name,
        )
        module = CodeReviewModule()
        candidates = module.analyze(bundle, contexts, self._provider, tracker)
        intelligence = FindingIntelligenceEngine().process_candidates(module.module_id, candidates, bundle, contexts)
        report = AnalysisReport(
            repository_root=bundle.repository_root,
            base_revision=pr.base_sha,
            target_description=bundle.target_description,
            modules_executed=[module.module_id],
            provider=ProviderInfo(
                provider_name=self._provider.provider_name,
                model_name=self._provider.model_name,
                requests_made=tracker.requests_made,
                retries_performed=tracker.retries_performed,
            ),
            usage=tracker.usage,
            duration_ms=max(0, int((time.perf_counter_ns() - started) / 1_000_000)),
            stage_timings_ms={},
            files_analyzed=[item.path for item in files],
            findings=intelligence.findings,
            rejected_findings_count=intelligence.rejected_count,
            deduplicated_findings_count=intelligence.deduplicated_count,
            warnings=[*tracker.warnings, *intelligence.warnings],
            status="incomplete" if bundle.truncated else "empty_diff" if not bundle.files else "completed",
        )
        summary = GitHubReviewAdapter(self._client, self._publisher).review_with_files(pr, report, files)
        return report, summary
