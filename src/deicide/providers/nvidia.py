"""NVIDIA NIM (OpenAI-compatible chat completions) REST API adapter using the standard library."""

from __future__ import annotations

import email.utils
import hashlib
import json
import random
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import SecretStr

from deicide.core.errors import (
    BudgetExceededError,
    ConfigurationError,
    MissingCredentialsError,
    ProviderError,
    QuotaExhaustedError,
    RateLimitError,
)
from deicide.core.models import BudgetTracker, ExecutionBudget, TokenUsage
from deicide.providers.base import (
    ProviderRequest,
    ProviderResponse,
    ProviderAttempt,
    ProviderFailureCategory,
    estimate_token_count,
)
from deicide.quota.store import RequestStatus, UsageStore

DEFAULT_NVIDIA_MODEL = "z-ai/glm-5.3-flash"
DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
MAX_RETRY_WAIT_SECONDS = 60.0


def _redact_secret(text: str, secret: str) -> str:
    """Ensure API key never appears in error messages or logs."""
    if not secret or not text:
        return text
    return text.replace(secret, "[REDACTED]")


def _extract_header_case_insensitive(
    headers: dict[str, str] | Any | None,
    target_name: str,
) -> str | None:
    if headers is None:
        return None
    target_lower = target_name.lower()
    if hasattr(headers, "items"):
        for k, v in headers.items():
            if str(k).lower() == target_lower:
                return str(v)
    return None


class NvidiaProvider:
    """Provider adapter for NVIDIA NIM chat/completions API."""

    def __init__(
        self,
        api_key: SecretStr,
        model_name: str = DEFAULT_NVIDIA_MODEL,
        base_url: str = DEFAULT_NVIDIA_BASE_URL,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        initial_backoff_seconds: float = 1.0,
        jitter_ratio: float = 0.0,
        sleep_fn: Callable[[float], None] = time.sleep,
        random_fn: Callable[[], float] = random.random,
        transport_fn: Callable[[urllib.request.Request, float], tuple[int, dict[str, str], str]] | None = None,
        *,
        budget: ExecutionBudget | None = None,
        usage_store: UsageStore | None = None,
        quota_scope: str = "default",
    ) -> None:
        raw_key = api_key.get_secret_value().strip() if api_key else ""
        if not raw_key:
            raise MissingCredentialsError(
                "NvidiaProvider requires a non-empty API key (NVIDIA_API_KEY or DEICIDE_API_KEY)."
            )
        cleaned_base = base_url.strip().rstrip("/") if base_url else DEFAULT_NVIDIA_BASE_URL
        if not cleaned_base.startswith("https://"):
            raise ConfigurationError(f"Invalid NVIDIA_BASE_URL '{base_url}': URL must start with 'https://'.")

        self._api_key = api_key
        self._model_name = model_name.strip() or DEFAULT_NVIDIA_MODEL
        self.base_url = cleaned_base
        self.timeout_seconds = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else (budget.request_timeout_seconds if budget is not None else 60.0)
        )
        self.max_retries = (
            int(max_retries) if max_retries is not None else (budget.max_retries if budget is not None else 0)
        )
        self.initial_backoff_seconds = initial_backoff_seconds
        self.jitter_ratio = max(0.0, min(float(jitter_ratio), 1.0))
        self._sleep = sleep_fn
        self._random = random_fn
        self._transport_fn = transport_fn or self._default_transport
        self.budget = budget
        self.usage_store = usage_store
        self.quota_scope = quota_scope
        self._bound_tracker: BudgetTracker | None = None
        self.last_attempts: list[ProviderAttempt] = []

    @property
    def provider_name(self) -> str:
        return "nvidia"

    @property
    def model_name(self) -> str:
        return self._model_name

    def bind_tracker(self, tracker: BudgetTracker | None) -> None:
        """Bind an active BudgetTracker for per-attempt reservation and reconciliation."""
        self._bound_tracker = tracker

    @staticmethod
    def _default_transport(
        req: urllib.request.Request,
        timeout: float,
    ) -> tuple[int, dict[str, str], str]:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            status = int(getattr(resp, "status", 200))
            headers = {k.lower(): v for k, v in resp.headers.items()}
            body = resp.read().decode("utf-8", errors="replace")
            return status, headers, body

    def _build_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _build_payload(self, request: ProviderRequest) -> bytes:
        body: dict[str, Any] = {
            "model": self._model_name,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
        }
        return json.dumps(body).encode("utf-8")

    def _resolve_active_tracker(self) -> BudgetTracker | None:
        if self._bound_tracker is not None:
            return self._bound_tracker
        if self.usage_store is not None or self.budget is not None:
            effective_budget = self.budget or ExecutionBudget(
                request_timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
            )
            return BudgetTracker(
                effective_budget,
                usage_store=self.usage_store,
                provider_name="nvidia",
                model_name=self._model_name,
                quota_scope=self.quota_scope,
            )
        return None

    def _can_attempt_retry(self, attempt: int, tracker: BudgetTracker | None) -> bool:
        if attempt >= self.max_retries:
            return False
        return not (tracker is not None and tracker.requests_made >= tracker.budget.max_requests)

    def _record_boundary(self, tracker: BudgetTracker | None) -> None:
        """Enforce elapsed-time budget at failed-attempt and backoff boundaries."""
        if tracker is not None:
            tracker.check_elapsed_time()

    @staticmethod
    def _annotate_failure(exc: Exception, category: ProviderFailureCategory, status: int | None, retries: int) -> Exception:
        setattr(exc, "failure_category", category.value)
        setattr(exc, "http_status", status)
        setattr(exc, "retries_attempted", retries)
        return exc

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        secret = self._api_key.get_secret_value()
        url = self._build_url()
        payload_bytes = self._build_payload(request)
        estimated_in = request.estimated_prompt_tokens
        active_tracker = self._resolve_active_tracker()
        prompt_hash = hashlib.sha256(
            f"{request.system_prompt}\x00{request.user_prompt}".encode("utf-8")
        ).hexdigest()
        self.last_attempts = []

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {secret}",
        }

        retries = 0
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            if not url.startswith("https://"):
                raise ProviderError("NVIDIA API URL must use https:// scheme.")

            reservation_id: str | None = None
            attempt_started = time.perf_counter_ns()
            configured_attempt_timeout: float | None = None
            transport_duration_ms: int | None = None
            response_hash: str | None = None
            attempt_usage: TokenUsage | None = None
            retry_reason: str | None = None
            error_category: str | None = None
            http_status: int | None = None
            if active_tracker is not None:
                reservation_id = active_tracker.reserve_attempt(
                    estimated_in,
                    provider_name="nvidia",
                    model_name=self._model_name,
                    is_retry=(attempt > 0),
                )

            http_req = urllib.request.Request(  # noqa: S310
                url=url,
                data=payload_bytes,
                headers=headers,
                method="POST",
            )
            try:
                attempt_timeout = self.timeout_seconds
                if self.budget is not None and self.budget.attempt_deadline_seconds is not None:
                    attempt_timeout = min(attempt_timeout, self.budget.attempt_deadline_seconds)
                configured_attempt_timeout = attempt_timeout
                transport_started = time.perf_counter_ns()
                try:
                    status, resp_headers, resp_body = self._transport_fn(http_req, attempt_timeout)
                finally:
                    transport_duration_ms = max(0, int((time.perf_counter_ns() - transport_started) / 1_000_000))
                retry_after_val = _extract_header_case_insensitive(resp_headers, "Retry-After")

                if status == 429:
                    http_status = status
                    error_category = ProviderFailureCategory.RATE_LIMIT
                    retry_reason = "HTTP 429" if self._can_attempt_retry(attempt, active_tracker) else None
                    if active_tracker is not None:
                        active_tracker.fail_attempt(
                            reservation_id,
                            status=RequestStatus.RATE_LIMITED,
                            estimated_prompt_tokens=estimated_in,
                        )
                    if self._can_attempt_retry(attempt, active_tracker):
                        delay = self._compute_backoff(attempt, retry_after_val)
                        retries += 1
                        self._record_boundary(active_tracker)
                        self._sleep(delay)
                        self._record_boundary(active_tracker)
                        continue
                    raise self._annotate_failure(
                        RateLimitError(f"NVIDIA API rate limit exceeded (HTTP 429) after {retries} retries."),
                        ProviderFailureCategory.RATE_LIMIT,
                        status,
                        retries,
                    )

                if status in {502, 503, 504}:
                    http_status = status
                    error_category = ProviderFailureCategory.SERVER_ERROR
                    retry_reason = f"HTTP {status}" if self._can_attempt_retry(attempt, active_tracker) else None
                    if active_tracker is not None:
                        active_tracker.fail_attempt(
                            reservation_id,
                            status=RequestStatus.FAILED,
                            estimated_prompt_tokens=estimated_in,
                        )
                    if self._can_attempt_retry(attempt, active_tracker):
                        delay = self._compute_backoff(attempt, retry_after_val)
                        retries += 1
                        self._record_boundary(active_tracker)
                        self._sleep(delay)
                        self._record_boundary(active_tracker)
                        continue
                    raise self._annotate_failure(
                        ProviderError(f"NVIDIA API server error (HTTP {status}) after {retries} retries."),
                        ProviderFailureCategory.SERVER_ERROR,
                        status,
                        retries,
                    )

                if status >= 400:
                    http_status = status
                    error_category = (
                        ProviderFailureCategory.SERVER_ERROR if status >= 500 else ProviderFailureCategory.CLIENT_ERROR
                    )
                    if active_tracker is not None:
                        active_tracker.fail_attempt(
                            reservation_id,
                            status=RequestStatus.FAILED,
                            estimated_prompt_tokens=estimated_in,
                        )
                    raise self._annotate_failure(
                        ProviderError(f"NVIDIA API returned HTTP {status}. [REDACTED]"),
                        error_category,
                        status,
                        retries,
                    )

                try:
                    parsed_resp = self._parse_response(resp_body, request, retries)
                except Exception:
                    error_category = ProviderFailureCategory.INVALID_RESPONSE
                    if active_tracker is not None:
                        active_tracker.fail_attempt(
                            reservation_id,
                            status=RequestStatus.FAILED,
                            estimated_prompt_tokens=estimated_in,
                        )
                    raise

                if active_tracker is not None:
                    active_tracker.complete_attempt(reservation_id, parsed_resp.usage)
                response_hash = hashlib.sha256(parsed_resp.content.encode("utf-8")).hexdigest()
                attempt_usage = parsed_resp.usage
                return parsed_resp

            except urllib.error.HTTPError as exc:
                code = exc.code
                http_status = code
                error_category = ProviderFailureCategory.RATE_LIMIT if code == 429 else (ProviderFailureCategory.SERVER_ERROR if code >= 500 else ProviderFailureCategory.CLIENT_ERROR)
                retry_after_header = _extract_header_case_insensitive(exc.headers, "Retry-After")
                rec_status = RequestStatus.RATE_LIMITED if code == 429 else RequestStatus.FAILED
                if active_tracker is not None:
                    active_tracker.fail_attempt(
                        reservation_id,
                        status=rec_status,
                        estimated_prompt_tokens=estimated_in,
                    )

                if code in {429, 502, 503, 504} and self._can_attempt_retry(attempt, active_tracker):
                    retry_reason = f"HTTP {code}"
                    delay = self._compute_backoff(attempt, retry_after_header)
                    retries += 1
                    self._record_boundary(active_tracker)
                    self._sleep(delay)
                    self._record_boundary(active_tracker)
                    last_error = exc
                    continue

                if code == 429:
                    raise self._annotate_failure(RateLimitError(f"NVIDIA API rate limit exceeded (HTTP 429) after {retries} retries."), ProviderFailureCategory.RATE_LIMIT, code, retries) from exc

                raise self._annotate_failure(
                    ProviderError(f"NVIDIA API request failed with HTTP {code}. [REDACTED]"),
                    error_category,
                    code,
                    retries,
                ) from exc

            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                error_category = ProviderFailureCategory.TIMEOUT if isinstance(exc, TimeoutError) or "timed out" in str(exc).lower() else ProviderFailureCategory.CONNECTION_ERROR
                if active_tracker is not None:
                    active_tracker.fail_attempt(
                        reservation_id,
                        status=RequestStatus.UNCERTAIN,
                        estimated_prompt_tokens=estimated_in,
                    )
                if self._can_attempt_retry(attempt, active_tracker):
                    retry_reason = error_category
                    delay = self._compute_backoff(attempt, None)
                    retries += 1
                    self._record_boundary(active_tracker)
                    self._sleep(delay)
                    self._record_boundary(active_tracker)
                    last_error = exc
                    continue
                raise self._annotate_failure(
                    ProviderError(f"NVIDIA API network/timeout error after {retries} retries."),
                    error_category,
                    None,
                    retries,
                ) from exc
            except ProviderError as exc:
                raise self._annotate_failure(
                    exc,
                    error_category or ProviderFailureCategory.PROVIDER_ERROR,
                    http_status,
                    retries,
                ) from exc
            except (QuotaExhaustedError, BudgetExceededError):
                raise
            except Exception as exc:
                error_category = ProviderFailureCategory.PROVIDER_ERROR
                if active_tracker is not None:
                    active_tracker.fail_attempt(
                        reservation_id,
                        status=RequestStatus.FAILED,
                        estimated_prompt_tokens=estimated_in,
                    )
                raise ProviderError("Unexpected NVIDIA provider failure.") from exc
            finally:
                self.last_attempts.append(
                    ProviderAttempt(
                        attempt_number=attempt + 1,
                        latency_ms=max(0, int((time.perf_counter_ns() - attempt_started) / 1_000_000)),
                        prompt_hash=prompt_hash,
                        response_hash=response_hash,
                        retry_reason=retry_reason,
                        error_category=error_category,
                        http_status=http_status,
                        usage=attempt_usage,
                        transport_duration_ms=transport_duration_ms,
                        configured_attempt_timeout_seconds=configured_attempt_timeout,
                        termination_reason=(
                            "completed" if response_hash is not None else (error_category.value if error_category else None)
                        ),
                    )
                )

        raise ProviderError(f"NVIDIA API request failed after {retries} retries.")

    def _compute_backoff(self, attempt: int, retry_after: str | None) -> float:
        if retry_after and retry_after.strip():
            cleaned = retry_after.strip()
            try:
                parsed = float(cleaned)
                if parsed > MAX_RETRY_WAIT_SECONDS:
                    raise RateLimitError(
                        f"Provider requested Retry-After of {parsed:.1f}s, exceeding maximum "
                        f"retry wait ceiling ({MAX_RETRY_WAIT_SECONDS:.1f}s)."
                    )
                if parsed > 0:
                    return parsed
            except ValueError:
                try:
                    dt = email.utils.parsedate_to_datetime(cleaned)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)
                    delta = (dt - datetime.now(tz=UTC)).total_seconds()
                    if delta > MAX_RETRY_WAIT_SECONDS:
                        raise RateLimitError(
                            f"Provider requested Retry-After until {cleaned} ({delta:.1f}s), "
                            f"exceeding maximum retry wait ceiling ({MAX_RETRY_WAIT_SECONDS:.1f}s)."
                        )
                    if delta > 0:
                        return float(delta)
                except RateLimitError:
                    raise
                except (TypeError, ValueError, OverflowError):
                    return float(self.initial_backoff_seconds * (2**attempt))
        base = float(self.initial_backoff_seconds * (2**attempt))
        return min(MAX_RETRY_WAIT_SECONDS, base * (1.0 + self.jitter_ratio * self._random()))

    def _parse_response(
        self,
        raw_body: str,
        request: ProviderRequest,
        retries: int,
    ) -> ProviderResponse:
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise ProviderError("NVIDIA API returned invalid JSON envelope.") from exc

        if not isinstance(data, dict):
            raise ProviderError("NVIDIA API response root must be a JSON object.")

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError("NVIDIA API response contained no choices.")

        first = choices[0]
        message = first.get("message") if isinstance(first, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("NVIDIA API choice message content was empty.")

        combined_text = content.strip()

        usage_meta = data.get("usage")
        if isinstance(usage_meta, dict) and "prompt_tokens" in usage_meta:
            prompt_tokens = int(usage_meta.get("prompt_tokens", 0))
            completion_tokens = int(usage_meta.get("completion_tokens", 0))
            total_tokens = int(usage_meta.get("total_tokens", prompt_tokens + completion_tokens))
            usage = TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                is_estimated=False,
            )
        else:
            prompt_tokens = request.estimated_prompt_tokens
            completion_tokens = estimate_token_count(combined_text)
            usage = TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                is_estimated=True,
            )

        return ProviderResponse(
            content=combined_text,
            model_name=self._model_name,
            usage=usage,
            retries_performed=retries,
        )
