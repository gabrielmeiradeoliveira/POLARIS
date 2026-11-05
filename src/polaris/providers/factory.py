"""Factory for instantiating configured AI providers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polaris.core.errors import MissingCredentialsError, UnsupportedProviderError
from polaris.providers.base import LLMProvider
from polaris.providers.fake import FakeProvider
from polaris.providers.nvidia import NvidiaProvider
from polaris.quota.store import UsageStore

if TYPE_CHECKING:
    from polaris.core.config import PolarisConfig


def create_provider(
    config: PolarisConfig,
    usage_store: UsageStore | None = None,
) -> LLMProvider:
    """Instantiate an LLMProvider from a validated PolarisConfig."""
    provider_name = config.provider.strip().lower()
    if provider_name == "fake":
        return FakeProvider(model_name=config.resolved_model)

    if provider_name == "nvidia":
        config.validate_provider_credentials()
        if config.api_key is None:
            raise MissingCredentialsError("NVIDIA API key is required.")
        active_store = usage_store
        if active_store is None and config.budget.quota_enabled:
            active_store = UsageStore(
                db_path=config.resolved_usage_db_path,
                reservation_ttl_seconds=config.budget.reservation_ttl_seconds,
            )
        return NvidiaProvider(
            api_key=config.api_key,
            model_name=config.resolved_model,
            base_url=config.nvidia_base_url,
            timeout_seconds=config.budget.request_timeout_seconds,
            max_retries=config.budget.max_retries,
            budget=config.budget,
            usage_store=active_store,
            quota_scope=config.resolved_quota_scope,
        )

    raise UnsupportedProviderError(f"Unsupported provider '{config.provider}'. Supported providers: fake, nvidia.")
