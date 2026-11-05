"""GitHub REST client logic over an injected transport; no network implementation is bundled."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from polaris.integrations.github.models import (
    ChangedFile,
    GitHubErrorCategory,
    GitHubIntegrationError,
    HttpResponse,
    PullRequestMetadata,
    body_as_object,
)
from polaris.integrations.github.transport import GitHubTransport

_LINK_NEXT = re.compile(r'<(?P<url>[^>]+)>;\s*rel="next"')
_SAFE_PART = re.compile(r"^[A-Za-z0-9_.-]+$")
_VALID_CHANGED_FILE_STATUSES = frozenset({"added", "modified", "removed", "renamed", "copied", "changed", "unchanged"})


class GitHubClient:
    """Small GitHub client with bounded retries and strict untrusted-response validation."""

    def __init__(
        self,
        transport: GitHubTransport,
        *,
        token: str | None = None,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._transport = transport
        self._token = token
        self._timeout_seconds = timeout_seconds
        self._max_retries = max(0, max_retries)
        self._sleep = sleep or (lambda _: None)

    @staticmethod
    def _validate_part(value: str, label: str) -> str:
        if not _SAFE_PART.fullmatch(value):
            raise ValueError(f"Invalid GitHub {label}.")
        return value

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _classify(self, response: HttpResponse) -> GitHubIntegrationError:
        status = response.status_code
        remaining = response.headers.get("X-RateLimit-Remaining", "")
        if status == 401:
            category = GitHubErrorCategory.AUTHENTICATION
        elif status == 403 and remaining == "0":
            category = GitHubErrorCategory.RATE_LIMIT
        elif status == 403:
            category = GitHubErrorCategory.AUTHORIZATION
        elif status == 404:
            category = GitHubErrorCategory.NOT_FOUND
        elif status == 429:
            category = GitHubErrorCategory.RATE_LIMIT
        elif status >= 500:
            category = GitHubErrorCategory.SERVER
        else:
            category = GitHubErrorCategory.HTTP
        return GitHubIntegrationError(category, f"GitHub request failed with HTTP {status}.", status)

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> HttpResponse:
        retries = 0
        serialized = json.dumps(body, sort_keys=True, separators=(",", ":")) if body is not None else None
        while True:
            try:
                response = self._transport.request(
                    method, path, headers=self._headers(), body=serialized, timeout_seconds=self._timeout_seconds
                )
            except TimeoutError:
                error = GitHubIntegrationError(GitHubErrorCategory.TIMEOUT, "GitHub request timed out.")
            except OSError:
                error = GitHubIntegrationError(GitHubErrorCategory.NETWORK, "GitHub network request failed.")
            else:
                if 200 <= response.status_code < 300:
                    return response
                error = self._classify(response)
            if (
                error.category
                not in {
                    GitHubErrorCategory.RATE_LIMIT,
                    GitHubErrorCategory.SERVER,
                    GitHubErrorCategory.NETWORK,
                    GitHubErrorCategory.TIMEOUT,
                }
                or retries >= self._max_retries
            ):
                raise error
            retries += 1
            self._sleep(float(retries))

    def _path(self, owner: str, repository: str, suffix: str) -> str:
        return f"/repos/{self._validate_part(owner, 'owner')}/{self._validate_part(repository, 'repository')}{suffix}"

    def authenticated_user(self) -> dict[str, Any]:
        payload = body_as_object(self._request("GET", "/user").body)
        if not isinstance(payload.get("id"), int) or not isinstance(payload.get("login"), str):
            raise GitHubIntegrationError(GitHubErrorCategory.INVALID_RESPONSE, "GitHub user response is invalid.")
        return payload

    def list_accessible_repositories(self) -> list[dict[str, Any]]:
        entries = self._list_pages("/user/repos?affiliation=owner,collaborator,organization_member&per_page=100&page=1")
        if not all(isinstance(entry, dict) for entry in entries):
            raise GitHubIntegrationError(GitHubErrorCategory.INVALID_RESPONSE, "GitHub repository response is invalid.")
        return entries

    def branch_sha(self, owner: str, repository: str, branch: str) -> str:
        payload = body_as_object(
            self._request(
                "GET", self._path(owner, repository, f"/commits/{self._validate_part(branch, 'branch')}")
            ).body
        )
        sha = payload.get("sha")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40,64}", sha):
            raise GitHubIntegrationError(GitHubErrorCategory.INVALID_RESPONSE, "GitHub commit response is invalid.")
        return sha

    @staticmethod
    def _parse_pr_payload(owner: str, repository: str, payload: dict[str, Any]) -> PullRequestMetadata:
        head = payload.get("head")
        base = payload.get("base")
        number = payload.get("number")
        if (
            not isinstance(head, dict)
            or not isinstance(base, dict)
            or not isinstance(head.get("sha"), str)
            or not isinstance(base.get("sha"), str)
            or not isinstance(number, int)
        ):
            raise GitHubIntegrationError(
                GitHubErrorCategory.INVALID_RESPONSE, "Pull request response lacks head/base SHA or number."
            )
        user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
        head_repo = head.get("repo") if isinstance(head.get("repo"), dict) else None
        base_repo = base.get("repo") if isinstance(base.get("repo"), dict) else None
        is_fork = bool(
            (head_repo and head_repo.get("fork"))
            or (
                head_repo
                and base_repo
                and head_repo.get("full_name")
                and base_repo.get("full_name")
                and head_repo.get("full_name") != base_repo.get("full_name")
            )
        )
        return PullRequestMetadata(
            owner=owner,
            repository=repository,
            number=number,
            title=str(payload.get("title", "")),
            state=str(payload.get("state", "open")),
            head_sha=head["sha"],
            base_sha=base["sha"],
            head_ref=str(head.get("ref", "")),
            base_ref=str(base.get("ref", "")),
            author_login=str(user.get("login", "")),
            is_fork=is_fork,
            merged=bool(payload.get("merged") or payload.get("merged_at")),
            html_url=str(payload.get("html_url", "")),
        )

    def get_pull_request(self, owner: str, repository: str, number: int) -> PullRequestMetadata:
        if number < 1:
            raise ValueError("Pull request number must be positive.")
        payload = body_as_object(self._request("GET", self._path(owner, repository, f"/pulls/{number}")).body)
        payload.setdefault("number", number)
        return self._parse_pr_payload(owner, repository, payload)

    def list_pull_requests(self, owner: str, repository: str, state: str = "open") -> list[PullRequestMetadata]:
        safe_state = state if state in {"open", "closed", "all"} else "open"
        path = self._path(owner, repository, f"/pulls?state={safe_state}&per_page=100&page=1")
        entries = self._list_pages(path)
        result: list[PullRequestMetadata] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise GitHubIntegrationError(
                    GitHubErrorCategory.INVALID_RESPONSE, "Pull request list contains an invalid entry."
                )
            result.append(self._parse_pr_payload(owner, repository, entry))
        return result

    def list_changed_files(self, pr: PullRequestMetadata) -> list[ChangedFile]:
        path = self._path(pr.owner, pr.repository, f"/pulls/{pr.number}/files?per_page=100&page=1")
        entries = self._list_pages(path)
        files: list[ChangedFile] = []
        for entry in entries:
            if (
                not isinstance(entry, dict)
                or not isinstance(entry.get("filename"), str)
                or not isinstance(entry.get("status"), str)
            ):
                raise GitHubIntegrationError(
                    GitHubErrorCategory.INVALID_RESPONSE, "Changed-file response contains an invalid entry."
                )
            if entry["status"] not in _VALID_CHANGED_FILE_STATUSES:
                raise GitHubIntegrationError(
                    GitHubErrorCategory.INVALID_RESPONSE, "Changed-file response contains an unsupported status."
                )
            patch = entry.get("patch")
            previous = entry.get("previous_filename")
            if (
                patch is not None
                and not isinstance(patch, str)
                or previous is not None
                and not isinstance(previous, str)
            ):
                raise GitHubIntegrationError(
                    GitHubErrorCategory.INVALID_RESPONSE, "Changed-file response has invalid patch fields."
                )
            files.append(
                ChangedFile(path=entry["filename"], status=entry["status"], patch=patch, previous_path=previous)
            )
        return files

    def _list_pages(self, path: str) -> list[Any]:
        collected: list[Any] = []
        current: str | None = path
        seen: set[str] = set()
        while current:
            if current in seen:
                raise GitHubIntegrationError(GitHubErrorCategory.INVALID_RESPONSE, "Pagination link loop detected.")
            seen.add(current)
            response = self._request("GET", current)
            try:
                payload = json.loads(response.body)
            except (TypeError, ValueError) as exc:
                raise GitHubIntegrationError(
                    GitHubErrorCategory.INVALID_RESPONSE, "GitHub returned invalid JSON."
                ) from exc
            if not isinstance(payload, list):
                raise GitHubIntegrationError(
                    GitHubErrorCategory.INVALID_RESPONSE, "GitHub paginated response must be a JSON array."
                )
            collected.extend(payload)
            match = _LINK_NEXT.search(response.headers.get("Link", ""))
            current = match.group("url") if match else None
            if current and current.startswith("https://api.github.com"):
                current = current[len("https://api.github.com") :]
            if current and not current.startswith("/"):
                raise GitHubIntegrationError(GitHubErrorCategory.INVALID_RESPONSE, "Unsafe pagination link returned.")
        return collected

    def list_review_comments(self, pr: PullRequestMetadata) -> list[dict[str, Any]]:
        entries = self._list_pages(
            self._path(pr.owner, pr.repository, f"/pulls/{pr.number}/comments?per_page=100&page=1")
        )
        if not all(isinstance(entry, dict) for entry in entries):
            raise GitHubIntegrationError(
                GitHubErrorCategory.INVALID_RESPONSE, "Review-comment response contains an invalid entry."
            )
        return entries

    def create_review(self, pr: PullRequestMetadata, body: str, comments: list[dict[str, Any]]) -> None:
        self._request(
            "POST",
            self._path(pr.owner, pr.repository, f"/pulls/{pr.number}/reviews"),
            {"commit_id": pr.head_sha, "body": body, "event": "COMMENT", "comments": comments},
        )
