"""Application configuration and environment loading for POLARIS."""

from __future__ import annotations

import os
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from polaris.context.context_models import ContextSelectionLimits
from polaris.core.errors import (
    ConfigurationError,
    MissingCredentialsError,
    PolarisError,
    UnsupportedProviderError,
)
from polaris.core.models import ExecutionBudget
from polaris.quota.store import derive_quota_scope, get_default_usage_db_path, get_user_data_dir

SUPPORTED_PROVIDERS: frozenset[str] = frozenset({"fake", "nvidia"})
DEFAULT_NVIDIA_MODEL = "z-ai/glm-5.3-flash"
DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_FAKE_MODEL = "fake-deterministic-v1"

_PLACEHOLDER_KEYS: frozenset[str] = frozenset(
    {
        "SUA_CHAVE_NVIDIA",
        "your_nvidia_api_key_here",
    }
)

_POLARIS_INSTALL_ROOT = Path(__file__).resolve().parents[3]


def load_dotenv_file(dotenv_path: Path) -> dict[str, str]:
    """Parse a `.env` file into a dictionary without executing shell expressions."""
    if not dotenv_path.exists() or not dotenv_path.is_file():
        return {}

    parsed: dict[str, str] = {}
    try:
        content = dotenv_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, raw_val = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        val = raw_val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in {'"', "'"}:
            val = val[1:-1]
        elif " #" in val:
            val = val.split(" #", 1)[0].strip()

        parsed[key] = val

    return parsed


def resolve_api_key(
    process_env: Mapping[str, str],
    dotenv_env: Mapping[str, str],
    provider: str = "nvidia",
) -> SecretStr | None:
    """Resolve API credentials using strict 4-tier precedence for the active provider.

    For 'nvidia' (and default):
    1. Nonempty NVIDIA_API_KEY from the process environment.
    2. Nonempty POLARIS_API_KEY from the process environment.
    3. Nonempty NVIDIA_API_KEY from the trusted `.env`.
    4. Nonempty POLARIS_API_KEY from the trusted `.env`.

    An empty credential never overrides a nonempty credential.
    """
    primary_var = "NVIDIA_API_KEY"

    candidates = (
        process_env.get(primary_var),
        process_env.get("POLARIS_API_KEY"),
        dotenv_env.get(primary_var),
        dotenv_env.get("POLARIS_API_KEY"),
    )
    for raw in candidates:
        if raw is not None:
            cleaned = raw.strip()
            if cleaned and cleaned not in _PLACEHOLDER_KEYS:
                return SecretStr(cleaned)
    return None


def _load_trusted_dotenv(
    dotenv_path: Path | None,
    process_env: Mapping[str, str],
    *,
    use_default_locations: bool,
) -> dict[str, str]:
    """Load POLARIS's trusted `.env` without ever reading from an analyzed target repository."""
    if dotenv_path is not None:
        return load_dotenv_file(dotenv_path)

    env_file_override = process_env.get("POLARIS_ENV_FILE", "").strip()
    if env_file_override:
        return load_dotenv_file(Path(env_file_override).expanduser())

    if not use_default_locations:
        return {}

    merged: dict[str, str] = {}
    for candidate_dir in (get_user_data_dir(), _POLARIS_INSTALL_ROOT):
        candidate_env = candidate_dir / ".env"
        try:
            is_file = candidate_env.is_file()
        except OSError:
            is_file = False
        if is_file:
            for k, v in load_dotenv_file(candidate_env).items():
                if v.strip() or k not in merged:
                    merged[k] = v
    return merged


def _parse_positive_int(value: int | str | None, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ConfigurationError(f"{name} must be a positive integer.")
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            parsed = int(cleaned)
        except ValueError as exc:
            raise ConfigurationError(f"{name} must be a positive integer, got '{value}'.") from exc
    else:
        parsed = int(value)

    if parsed <= 0:
        raise ConfigurationError(f"{name} must be greater than zero, got {parsed}.")
    return parsed


def _parse_non_negative_int(value: int | str | None, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ConfigurationError(f"{name} must be a non-negative integer.")
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            parsed = int(cleaned)
        except ValueError as exc:
            raise ConfigurationError(f"{name} must be a non-negative integer, got '{value}'.") from exc
    else:
        parsed = int(value)

    if parsed < 0:
        raise ConfigurationError(f"{name} must be >= 0, got {parsed}.")
    return parsed


def _parse_positive_float(value: float | int | str | None, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ConfigurationError(f"{name} must be a positive number.")
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            parsed = float(cleaned)
        except ValueError as exc:
            raise ConfigurationError(f"{name} must be a positive number, got '{value}'.") from exc
    else:
        parsed = float(value)

    if parsed <= 0.0:
        raise ConfigurationError(f"{name} must be greater than zero, got {parsed}.")
    return parsed


def _parse_strict_bool(value: bool | str | None, name: str, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    cleaned = value.strip().lower()
    if not cleaned:
        return default
    if cleaned in {"1", "true", "yes", "on"}:
        return True
    if cleaned in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"Invalid boolean value '{value}' for {name}. Expected true/false or 1/0.")


class OutputFormat(StrEnum):
    """Supported CLI output formats."""

    TERMINAL = "terminal"
    JSON = "json"
    SARIF = "sarif"


class PolarisConfig(BaseModel):
    """Validated runtime configuration for a POLARIS execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repo_path: Path = Field(default_factory=Path.cwd)
    base_revision: str | None = Field(default=None)
    provider: str = Field(default="nvidia")
    model: str | None = Field(default=None)
    api_key: SecretStr | None = Field(default=None, repr=False)
    nvidia_base_url: str = Field(default=DEFAULT_NVIDIA_BASE_URL)
    allow_external_code: bool = Field(
        default=False,
        description="Explicit authorization to send repository diffs/context to an external provider.",
    )
    output_format: OutputFormat = Field(default=OutputFormat.TERMINAL)
    budget: ExecutionBudget = Field(default_factory=ExecutionBudget)
    quota_scope: str | None = Field(default=None)
    usage_db_path: Path | None = Field(default=None)
    context_enabled: bool = Field(default=True)
    behavioral_delta_enabled: bool = Field(default=False)
    hybrid_static_selection_enabled: bool = Field(default=False)
    static_relevance_selection_enabled: bool = Field(default=False)
    context_limits: ContextSelectionLimits = Field(default_factory=ContextSelectionLimits)

    def model_post_init(self, __context: object) -> None:
        """Keep direct config construction and context-pipeline limits consistent."""
        if (
            self.context_limits.hybrid_static_selection_enabled != self.hybrid_static_selection_enabled
            or self.context_limits.static_relevance_selection_enabled != self.static_relevance_selection_enabled
        ):
            object.__setattr__(
                self,
                "context_limits",
                self.context_limits.model_copy(
                    update={
                        "hybrid_static_selection_enabled": self.hybrid_static_selection_enabled,
                        "static_relevance_selection_enabled": self.static_relevance_selection_enabled,
                    }
                ),
            )

    @field_validator("provider")
    @classmethod
    def validate_provider_name(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_PROVIDERS:
            supported = ", ".join(sorted(SUPPORTED_PROVIDERS))
            msg = f"Unsupported provider '{value}'. Supported providers: {supported}."
            raise UnsupportedProviderError(msg)
        return normalized

    @field_validator("nvidia_base_url")
    @classmethod
    def validate_nvidia_base_url(cls, value: str) -> str:
        cleaned = value.strip().rstrip("/")
        if not cleaned.startswith("https://"):
            raise ConfigurationError(f"Invalid NVIDIA_BASE_URL '{value}': must start with 'https://'.")
        return cleaned

    @field_validator("base_revision")
    @classmethod
    def validate_base_revision(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ConfigurationError("Base revision cannot be empty or whitespace.")
        if cleaned.startswith("-"):
            raise ConfigurationError(f"Invalid base revision '{cleaned}': revisions may not start with '-'.")
        return cleaned

    @property
    def resolved_model(self) -> str:
        if self.model and self.model.strip():
            return self.model.strip()
        if self.provider == "fake":
            return DEFAULT_FAKE_MODEL
        return DEFAULT_NVIDIA_MODEL

    @property
    def resolved_quota_scope(self) -> str:
        raw_secret = self.api_key.get_secret_value() if self.api_key else None
        return derive_quota_scope(self.quota_scope, raw_secret)

    @property
    def resolved_usage_db_path(self) -> Path:
        if self.usage_db_path is not None:
            return self.usage_db_path.resolve()
        return get_default_usage_db_path()

    def validate_provider_credentials(self) -> None:
        """Ensure external providers have explicit credentials and configuration."""
        if self.provider == "fake":
            return
        key_var_hint = "NVIDIA_API_KEY"
        if self.api_key is None or not self.api_key.get_secret_value().strip():
            msg = (
                f"Missing API credentials for provider '{self.provider}'. "
                f"Set {key_var_hint} (or POLARIS_API_KEY) in your .env file or environment, "
                "or run with '--provider fake' for offline analysis."
            )
            raise MissingCredentialsError(msg)
        if not self.allow_external_code:
            msg = (
                f"External code transmission to provider '{self.provider}' is not enabled. "
                "Set POLARIS_ALLOW_EXTERNAL_CODE=1 (or pass --allow-external) along with your API key "
                "to authorize sending repository diffs to the external AI provider."
            )
            raise MissingCredentialsError(msg)

    @classmethod
    def from_env_and_args(
        cls,
        *,
        repo_path: Path | None = None,
        base_revision: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        output_format: OutputFormat | str = OutputFormat.TERMINAL,
        allow_external_code: bool | None = None,
        max_tokens: int | None = None,
        max_requests: int | None = None,
        max_retries: int | None = None,
        timeout_seconds: float | None = None,
        attempt_deadline_seconds: float | None = None,
        case_deadline_seconds: float | None = None,
        max_elapsed_seconds: float | None = None,
        max_files: int | None = None,
        rate_limit_rpm: int | None = None,
        rate_limit_tpm: int | None = None,
        rate_limit_rpd: int | None = None,
        quota_enabled: bool | None = None,
        quota_scope: str | None = None,
        usage_db_path: Path | None = None,
        nvidia_base_url: str | None = None,
        context_enabled: bool | None = None,
        behavioral_delta_enabled: bool | None = None,
        hybrid_static_selection_enabled: bool | None = None,
        static_relevance_selection_enabled: bool | None = None,
        context_max_files: int | None = None,
        context_max_snippets: int | None = None,
        context_max_snippet_lines: int | None = None,
        context_max_tokens: int | None = None,
        behavioral_delta_reserved_tokens: int | None = None,
        context_max_graph_depth: int | None = None,
        environ: dict[str, str] | None = None,
        dotenv_path: Path | None = None,
    ) -> PolarisConfig:
        """Build and validate configuration from CLI arguments, trusted `.env`, and environment variables.

        Never reads `.env` or configuration files from the target repository being analyzed.
        """
        target_repo = (repo_path or Path.cwd()).resolve()
        process_env: dict[str, str] = dict(os.environ) if environ is None else dict(environ)
        dotenv_env = _load_trusted_dotenv(
            dotenv_path,
            process_env,
            use_default_locations=(environ is None),
        )

        # Merge non-empty values for general settings (non-empty process_env overrides dotenv_env)
        env: dict[str, str] = {k: v for k, v in dotenv_env.items() if v is not None and v.strip() != ""}
        for k, v in process_env.items():
            if v is not None and v.strip() != "":
                env[k] = v

        env_provider = env.get("POLARIS_PROVIDER", "nvidia").strip().lower()
        resolved_provider = provider if provider is not None else env.get("POLARIS_PROVIDER", "nvidia")
        norm_provider = resolved_provider.strip().lower()

        if model is not None:
            resolved_model = model
        elif norm_provider != env_provider:
            resolved_model = None
        else:
            resolved_model = env.get("POLARIS_MODEL")

        secret_key = resolve_api_key(process_env, dotenv_env, provider=norm_provider)
        resolved_nvidia_url = (
            nvidia_base_url if nvidia_base_url is not None else env.get("NVIDIA_BASE_URL", DEFAULT_NVIDIA_BASE_URL)
        )

        if allow_external_code is not None:
            resolved_allow_external = allow_external_code
        elif "POLARIS_ALLOW_EXTERNAL_CODE" in env and env["POLARIS_ALLOW_EXTERNAL_CODE"].strip():
            resolved_allow_external = _parse_strict_bool(
                env["POLARIS_ALLOW_EXTERNAL_CODE"],
                "POLARIS_ALLOW_EXTERNAL_CODE",
                default=False,
            )
        else:
            resolved_allow_external = secret_key is not None

        try:
            fmt = (
                output_format
                if isinstance(output_format, OutputFormat)
                else OutputFormat(output_format.strip().lower())
            )
        except ValueError as exc:
            msg = f"Unsupported output format '{output_format}'. Use 'terminal' or 'json'."
            raise ConfigurationError(msg) from exc

        budget_kwargs: dict[str, int | float | bool | None] = {}

        parsed_max_tokens = _parse_positive_int(
            max_tokens if max_tokens is not None else env.get("POLARIS_MAX_TOKENS"),
            "POLARIS_MAX_TOKENS",
        )
        if parsed_max_tokens is not None:
            budget_kwargs["max_total_tokens"] = parsed_max_tokens

        parsed_max_requests = _parse_positive_int(
            max_requests if max_requests is not None else env.get("POLARIS_MAX_REQUESTS"),
            "POLARIS_MAX_REQUESTS",
        )
        if parsed_max_requests is not None:
            budget_kwargs["max_requests"] = parsed_max_requests

        parsed_max_retries = _parse_non_negative_int(
            max_retries if max_retries is not None else env.get("POLARIS_MAX_RETRIES"),
            "POLARIS_MAX_RETRIES",
        )
        if parsed_max_retries is not None:
            budget_kwargs["max_retries"] = parsed_max_retries

        parsed_max_elapsed = _parse_positive_float(
            max_elapsed_seconds
            if max_elapsed_seconds is not None
            else (env.get("POLARIS_MAX_ELAPSED_SECONDS") or env.get("POLARIS_MAX_ELAPSED")),
            "POLARIS_MAX_ELAPSED_SECONDS",
        )
        if parsed_max_elapsed is not None:
            budget_kwargs["max_elapsed_seconds"] = parsed_max_elapsed

        parsed_timeout = _parse_positive_float(
            timeout_seconds if timeout_seconds is not None else env.get("POLARIS_TIMEOUT_SECONDS"),
            "POLARIS_TIMEOUT_SECONDS",
        )
        if parsed_timeout is not None:
            budget_kwargs["request_timeout_seconds"] = parsed_timeout
            effective_attempts = 1 + (parsed_max_retries or 0)
            min_elapsed = min(1800.0, parsed_timeout * effective_attempts + 30.0)
            current_elapsed = budget_kwargs.get("max_elapsed_seconds", 360.0)
            if min_elapsed > current_elapsed:
                budget_kwargs["max_elapsed_seconds"] = min_elapsed

        parsed_attempt_deadline = _parse_positive_float(
            attempt_deadline_seconds if attempt_deadline_seconds is not None else env.get("POLARIS_ATTEMPT_DEADLINE_SECONDS"),
            "POLARIS_ATTEMPT_DEADLINE_SECONDS",
        )
        if parsed_attempt_deadline is not None:
            budget_kwargs["attempt_deadline_seconds"] = parsed_attempt_deadline

        parsed_case_deadline = _parse_positive_float(
            case_deadline_seconds if case_deadline_seconds is not None else env.get("POLARIS_CASE_DEADLINE_SECONDS"),
            "POLARIS_CASE_DEADLINE_SECONDS",
        )
        if parsed_case_deadline is not None:
            budget_kwargs["case_deadline_seconds"] = parsed_case_deadline

        parsed_max_files = _parse_positive_int(max_files, "max_files")
        if parsed_max_files is not None:
            budget_kwargs["max_files"] = parsed_max_files

        parsed_rpm = _parse_positive_int(
            rate_limit_rpm if rate_limit_rpm is not None else env.get("POLARIS_RATE_LIMIT_RPM"),
            "POLARIS_RATE_LIMIT_RPM",
        )
        if parsed_rpm is not None:
            budget_kwargs["rate_limit_rpm"] = parsed_rpm
        elif norm_provider == "nvidia":
            budget_kwargs["rate_limit_rpm"] = None

        parsed_tpm = _parse_positive_int(
            rate_limit_tpm if rate_limit_tpm is not None else env.get("POLARIS_RATE_LIMIT_TPM"),
            "POLARIS_RATE_LIMIT_TPM",
        )
        if parsed_tpm is not None:
            budget_kwargs["rate_limit_tpm"] = parsed_tpm
        elif norm_provider == "nvidia":
            budget_kwargs["rate_limit_tpm"] = None

        parsed_rpd = _parse_positive_int(
            rate_limit_rpd if rate_limit_rpd is not None else env.get("POLARIS_RATE_LIMIT_RPD"),
            "POLARIS_RATE_LIMIT_RPD",
        )
        if parsed_rpd is not None:
            budget_kwargs["rate_limit_rpd"] = parsed_rpd
        elif norm_provider == "nvidia":
            budget_kwargs["rate_limit_rpd"] = None

        resolved_quota_enabled = _parse_strict_bool(
            quota_enabled if quota_enabled is not None else env.get("POLARIS_QUOTA_ENABLED"),
            "POLARIS_QUOTA_ENABLED",
            default=True,
        )
        budget_kwargs["quota_enabled"] = resolved_quota_enabled

        resolved_scope = quota_scope if quota_scope is not None else env.get("POLARIS_QUOTA_SCOPE")
        resolved_db_path = (
            usage_db_path
            if usage_db_path is not None
            else (
                Path(env["POLARIS_USAGE_DB_PATH"].strip()).expanduser().resolve()
                if env.get("POLARIS_USAGE_DB_PATH", "").strip()
                else None
            )
        )

        resolved_context_enabled = _parse_strict_bool(
            context_enabled if context_enabled is not None else env.get("POLARIS_CONTEXT_ENABLED"),
            "POLARIS_CONTEXT_ENABLED",
            default=True,
        )

        resolved_behavioral_delta_enabled = _parse_strict_bool(
            behavioral_delta_enabled
            if behavioral_delta_enabled is not None
            else env.get("POLARIS_BEHAVIORAL_DELTA_ENABLED"),
            "POLARIS_BEHAVIORAL_DELTA_ENABLED",
            default=False,
        )

        resolved_hybrid_static_selection_enabled = _parse_strict_bool(
            hybrid_static_selection_enabled
            if hybrid_static_selection_enabled is not None
            else env.get("POLARIS_HYBRID_STATIC_SELECTION_ENABLED"),
            "POLARIS_HYBRID_STATIC_SELECTION_ENABLED",
            default=False,
        )
        resolved_static_relevance_selection_enabled = _parse_strict_bool(
            static_relevance_selection_enabled
            if static_relevance_selection_enabled is not None
            else env.get("POLARIS_STATIC_RELEVANCE_SELECTION_ENABLED"),
            "POLARIS_STATIC_RELEVANCE_SELECTION_ENABLED",
            default=False,
        )

        ctx_limits_kwargs: dict[str, int] = {}
        parsed_ctx_max_files = _parse_positive_int(
            context_max_files if context_max_files is not None else env.get("POLARIS_CONTEXT_MAX_FILES"),
            "POLARIS_CONTEXT_MAX_FILES",
        )
        if parsed_ctx_max_files is not None:
            ctx_limits_kwargs["max_context_files"] = parsed_ctx_max_files

        parsed_ctx_max_snippets = _parse_positive_int(
            context_max_snippets if context_max_snippets is not None else env.get("POLARIS_CONTEXT_MAX_SNIPPETS"),
            "POLARIS_CONTEXT_MAX_SNIPPETS",
        )
        if parsed_ctx_max_snippets is not None:
            ctx_limits_kwargs["max_snippets"] = parsed_ctx_max_snippets

        parsed_ctx_max_lines = _parse_positive_int(
            context_max_snippet_lines
            if context_max_snippet_lines is not None
            else env.get("POLARIS_CONTEXT_MAX_SNIPPET_LINES"),
            "POLARIS_CONTEXT_MAX_SNIPPET_LINES",
        )
        if parsed_ctx_max_lines is not None:
            ctx_limits_kwargs["max_snippet_lines"] = parsed_ctx_max_lines

        parsed_ctx_max_tokens = _parse_non_negative_int(
            context_max_tokens if context_max_tokens is not None else env.get("POLARIS_CONTEXT_MAX_TOKENS"),
            "POLARIS_CONTEXT_MAX_TOKENS",
        )
        if parsed_ctx_max_tokens is not None:
            ctx_limits_kwargs["max_context_tokens"] = parsed_ctx_max_tokens

        parsed_delta_reserved = _parse_non_negative_int(
            behavioral_delta_reserved_tokens
            if behavioral_delta_reserved_tokens is not None
            else env.get("POLARIS_BEHAVIORAL_DELTA_RESERVED_TOKENS"),
            "POLARIS_BEHAVIORAL_DELTA_RESERVED_TOKENS",
        )
        if parsed_delta_reserved is not None:
            ctx_limits_kwargs["behavioral_delta_reserved_tokens"] = parsed_delta_reserved

        parsed_ctx_depth = _parse_positive_int(
            context_max_graph_depth
            if context_max_graph_depth is not None
            else env.get("POLARIS_CONTEXT_MAX_GRAPH_DEPTH"),
            "POLARIS_CONTEXT_MAX_GRAPH_DEPTH",
        )
        if parsed_ctx_depth is not None:
            ctx_limits_kwargs["max_graph_depth"] = parsed_ctx_depth

        context_limits = ContextSelectionLimits(
            **ctx_limits_kwargs,
            hybrid_static_selection_enabled=resolved_hybrid_static_selection_enabled,
            static_relevance_selection_enabled=resolved_static_relevance_selection_enabled,
        )

        try:
            budget = ExecutionBudget(**budget_kwargs)  # type: ignore[arg-type]
            return cls(
                repo_path=target_repo,
                base_revision=base_revision,
                provider=resolved_provider,
                model=resolved_model,
                api_key=secret_key,
                nvidia_base_url=resolved_nvidia_url,
                allow_external_code=resolved_allow_external,
                output_format=fmt,
                budget=budget,
                quota_scope=resolved_scope,
                usage_db_path=resolved_db_path,
                context_enabled=resolved_context_enabled,
                behavioral_delta_enabled=resolved_behavioral_delta_enabled,
                hybrid_static_selection_enabled=resolved_hybrid_static_selection_enabled,
                static_relevance_selection_enabled=resolved_static_relevance_selection_enabled,
                context_limits=context_limits,
            )
        except PolarisError:
            raise
        except Exception as exc:
            raise ConfigurationError(f"Invalid configuration: {exc}") from exc
