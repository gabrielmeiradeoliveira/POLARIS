"""Provider-independent contracts for LLM interactions."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from polaris.core.models import TokenUsage, estimate_token_count


class ProviderRequest(BaseModel):
    """Provider-neutral request payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    system_prompt: str
    user_prompt: str
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=4096, ge=64, le=32768)
    response_json: bool = True

    @property
    def estimated_prompt_tokens(self) -> int:
        return estimate_token_count(self.system_prompt) + estimate_token_count(self.user_prompt)


class ProviderFailureCategory(StrEnum):
    """Stable provider-neutral operational failure categories."""

    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    CLIENT_ERROR = "client_error"
    CONNECTION_ERROR = "connection_error"
    INVALID_RESPONSE = "invalid_response"
    PROVIDER_ERROR = "provider_error"


class ProviderAttempt(BaseModel):
    """Privacy-preserving metadata for one provider request attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attempt_number: int = Field(..., ge=1)
    latency_ms: int | None = Field(default=None, ge=0)
    prompt_hash: str | None = Field(default=None, min_length=64, max_length=64)
    response_hash: str | None = Field(default=None, min_length=64, max_length=64)
    retry_reason: str | None = None
    error_category: ProviderFailureCategory | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    usage: TokenUsage | None = None
    transport_duration_ms: int | None = Field(default=None, ge=0)
    configured_attempt_timeout_seconds: float | None = Field(default=None, gt=0.0)
    termination_reason: str | None = None


class ProviderResponse(BaseModel):
    """Provider-neutral response payload with token usage and retry metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    content: str
    model_name: str
    usage: TokenUsage
    retries_performed: int = Field(default=0, ge=0)


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol implemented by all AI provider adapters."""

    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    def generate(self, request: ProviderRequest) -> ProviderResponse: ...
