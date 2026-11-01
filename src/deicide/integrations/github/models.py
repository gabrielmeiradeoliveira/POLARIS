"""Typed, provider-independent contracts for GitHub pull-request review."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GitHubErrorCategory(StrEnum):
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NOT_FOUND = "not_found"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    NETWORK = "network"
    SERVER = "server"
    INVALID_RESPONSE = "invalid_response"
    HTTP = "http"


class GitHubIntegrationError(RuntimeError):
    """A classified GitHub API failure that never includes credentials."""

    def __init__(self, category: GitHubErrorCategory, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.status_code = status_code


class HttpResponse(BaseModel):
    """Minimal transport response, supplied by an injected transport."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status_code: int = Field(ge=100, le=599)
    headers: dict[str, str] = Field(default_factory=dict)
    body: str = ""


class PullRequestMetadata(BaseModel):
    """The stable PR details needed to analyze and publish one review."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    owner: str = Field(min_length=1)
    repository: str = Field(min_length=1)
    number: int = Field(ge=1)
    title: str = ""
    state: str = "open"
    head_sha: str = Field(min_length=1)
    base_sha: str = Field(min_length=1)


class ChangedFile(BaseModel):
    """GitHub changed-file data, retaining optional patch and rename origin."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    status: str = Field(min_length=1)
    patch: str | None = None
    previous_path: str | None = None

    @field_validator("path", "previous_path")
    @classmethod
    def normalize_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.replace("\\", "/").lstrip("./")
        if not cleaned or ".." in cleaned.split("/"):
            raise ValueError("GitHub file paths must be repository-relative")
        return cleaned


class DiffPosition(BaseModel):
    """A valid GitHub review-comment location on either side of a patch."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    line: int = Field(ge=1)
    side: str = Field(pattern="^(LEFT|RIGHT)$")


class MappedComment(BaseModel):
    """A DEICIDE finding rendered as a safely placeable PR comment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str = Field(min_length=1)
    body: str = Field(min_length=1)
    position: DiffPosition | None = None
    reason: str | None = None


class PublishOperation(BaseModel):
    """Structured audit record for a proposed or attempted review operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str | None = None
    action: str
    status: str
    detail: str = ""


class ReviewSummary(BaseModel):
    """Deterministic execution outcome, deliberately free of token values."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    files_analyzed: int = Field(ge=0)
    findings: int = Field(ge=0)
    severities: dict[str, int] = Field(default_factory=dict)
    findings_with_valid_location: int = Field(ge=0)
    findings_without_valid_location: int = Field(ge=0)
    new_comments: int = Field(ge=0)
    duplicate_comments: int = Field(ge=0)
    operational_errors: list[str] = Field(default_factory=list)
    status: str


def body_as_object(payload: str) -> dict[str, Any]:
    """Validate a decoded JSON object without trusting arbitrary API data."""
    import json

    try:
        parsed = json.loads(payload)
    except (TypeError, ValueError) as exc:
        raise GitHubIntegrationError(GitHubErrorCategory.INVALID_RESPONSE, "GitHub returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise GitHubIntegrationError(GitHubErrorCategory.INVALID_RESPONSE, "GitHub response must be a JSON object.")
    return parsed
