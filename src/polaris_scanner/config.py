from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

SUPPORTED_LANGUAGES = ("python", "csharp", "java", "sql")
VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
DEFAULT_EXCLUSIONS = (".git", ".venv", "node_modules", "bin", "obj", "target", "build", "dist")


class ConfigValidationError(ValueError):
    """Raised when scanner configuration is invalid."""


@dataclass(frozen=True)
class ScannerConfig:
    """Typed configuration for the POLARIS scanner."""

    target_dir: Path
    project_key: str
    branch: str = "main"
    exclusions: tuple[str, ...] = DEFAULT_EXCLUSIONS
    languages: tuple[str, ...] = SUPPORTED_LANGUAGES
    max_file_bytes: int = 1 * 1024 * 1024
    max_files: int = 10000
    max_total_bytes: int = 100 * 1024 * 1024
    timeout_seconds: int = 60
    output_path: Path | None = None
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        if not self.project_key or not self.project_key.strip():
            raise ConfigValidationError("project_key must be a non-empty string")
        if self.max_file_bytes <= 0:
            raise ConfigValidationError("max_file_bytes must be positive")
        if self.max_files <= 0:
            raise ConfigValidationError("max_files must be positive")
        if self.max_total_bytes <= 0:
            raise ConfigValidationError("max_total_bytes must be positive")
        if self.timeout_seconds <= 0:
            raise ConfigValidationError("timeout_seconds must be positive")
        if self.log_level.upper() not in VALID_LOG_LEVELS:
            raise ConfigValidationError(f"log_level must be one of {VALID_LOG_LEVELS}")
        for lang in self.languages:
            if lang not in SUPPORTED_LANGUAGES:
                raise ConfigValidationError(f"Unsupported language '{lang}'. Supported: {SUPPORTED_LANGUAGES}")


def _load_config_file(target_dir: Path, config_file: Path | None = None) -> dict[str, Any]:
    candidates = [config_file] if config_file else [target_dir / "polaris.json", target_dir / ".polaris.json"]
    for path in candidates:
        if path and path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ConfigValidationError(f"Config file {path} must contain a JSON object")
                return data
            except json.JSONDecodeError as exc:
                raise ConfigValidationError(f"Invalid JSON in config file {path}: {exc}") from exc
    return {}


def load_scanner_config(
    *,
    target_dir: Path,
    cli_overrides: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
    config_file: Path | None = None,
) -> ScannerConfig:
    """Load ScannerConfig with precedence: CLI > env > config_file > defaults."""
    env_map = env if env is not None else os.environ
    cli = dict(cli_overrides or {})
    file_cfg = _load_config_file(target_dir, config_file)

    def pick(key: str, env_key: str, default: Any) -> Any:
        if key in cli and cli[key] is not None:
            return cli[key]
        if env_key in env_map and env_map[env_key] != "":
            return env_map[env_key]
        if key in file_cfg and file_cfg[key] is not None:
            return file_cfg[key]
        return default

    project_key = str(pick("project_key", "POLARIS_PROJECT_KEY", target_dir.name or "default-project"))
    branch = str(pick("branch", "POLARIS_BRANCH", "main"))

    raw_exclusions = pick("exclusions", "POLARIS_EXCLUSIONS", DEFAULT_EXCLUSIONS)
    if isinstance(raw_exclusions, str):
        exclusions = tuple(x.strip() for x in raw_exclusions.split(",") if x.strip())
    else:
        exclusions = tuple(str(x).strip() for x in raw_exclusions if str(x).strip())

    raw_languages = pick("languages", "POLARIS_LANGUAGES", SUPPORTED_LANGUAGES)
    if isinstance(raw_languages, str):
        languages = tuple(x.strip().lower() for x in raw_languages.split(",") if x.strip())
    else:
        languages = tuple(str(x).strip().lower() for x in raw_languages if str(x).strip())

    max_file_bytes = int(pick("max_file_bytes", "POLARIS_MAX_FILE_BYTES", 1 * 1024 * 1024))
    max_files = int(pick("max_files", "POLARIS_MAX_FILES", 10000))
    max_total_bytes = int(pick("max_total_bytes", "POLARIS_MAX_TOTAL_BYTES", 100 * 1024 * 1024))
    timeout_seconds = int(pick("timeout_seconds", "POLARIS_TIMEOUT_SECONDS", 60))
    raw_output = pick("output_path", "POLARIS_OUTPUT_PATH", None)
    output_path = Path(raw_output) if raw_output else None
    log_level = str(pick("log_level", "POLARIS_LOG_LEVEL", "INFO")).upper()

    return ScannerConfig(
        target_dir=target_dir.resolve(),
        project_key=project_key,
        branch=branch,
        exclusions=exclusions,
        languages=languages,
        max_file_bytes=max_file_bytes,
        max_files=max_files,
        max_total_bytes=max_total_bytes,
        timeout_seconds=timeout_seconds,
        output_path=output_path,
        log_level=log_level,
    )
