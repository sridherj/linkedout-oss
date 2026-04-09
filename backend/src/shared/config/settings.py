# SPDX-License-Identifier: Apache-2.0
"""LinkedOut OSS unified settings.

Resolution order (highest priority wins):
    1. Environment variables (``LINKEDOUT_`` prefix, or standard names)
    2. ``.env`` file (if present in project root)
    3. ``secrets.yaml`` — API keys / credentials
    4. ``config.yaml`` — human-readable user config
    5. Code defaults
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from pydantic import AliasChoices, BaseModel, Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.config.yaml_sources import YamlConfigSource, YamlSecretsSource

_DATA_DIR_SUBDIRS = (
    'config',
    'db',
    'crawled',
    'uploads',
    'logs',
    'queries',
    'reports',
    'metrics',
    'seed',
    'state',
)


class ScoringConfig(BaseModel):
    """Affinity scoring weights and thresholds."""

    weight_career_overlap: float = 0.40
    weight_external_contact: float = 0.25
    weight_embedding_similarity: float = 0.15
    weight_source_count: float = 0.10
    weight_recency: float = 0.10
    dunbar_inner_circle: int = 15
    dunbar_active: int = 50
    dunbar_familiar: int = 150
    seniority_boosts: dict[str, float] = {
        'founder': 3.0,
        'c_suite': 2.5,
        'vp': 2.0,
        'director': 1.8,
        'manager': 1.5,
        'lead': 1.3,
        'senior': 1.1,
        'mid': 1.0,
        'junior': 0.9,
        'intern': 0.7,
    }
    external_contact_scores: dict[str, float] = {'phone': 1.0, 'email': 0.7}
    career_normalization_months: int = 36
    recency_thresholds: list[list[int | float]] = [
        [12, 1.0],
        [36, 0.7],
        [60, 0.4],
    ]


class EnrichmentConfig(BaseModel):
    """Apify enrichment pipeline settings."""

    apify_base_url: str = 'https://api.apify.com/v2'
    cost_per_profile_usd: float = 0.004
    cache_ttl_days: int = 90
    sync_timeout_seconds: int = 60
    async_start_timeout_seconds: int = 30
    run_poll_timeout_seconds: int = 300
    run_poll_interval_seconds: int = 5
    fetch_results_timeout_seconds: int = 30
    key_validation_timeout_seconds: int = 15


class LLMConfig(BaseModel):
    """LLM model selection, retry, and rate-limit settings."""

    provider: str = 'openai'
    model: str = 'gpt-5.2-2025-12-11'
    search_model: str = 'gpt-5.4-mini'
    timeout_seconds: float = 120.0
    retry_max_attempts: int = 3
    retry_min_wait: float = 2.0
    retry_max_wait: float = 30.0
    rate_limit_rpm: int = 60
    prompt_cache_ttl_seconds: int = 300
    summarize_beyond_n_turns: int = 4


class EmbeddingConfig(BaseModel):
    """Embedding model and batch processing settings."""

    provider: str = 'openai'
    model: str = 'text-embedding-3-small'
    dimensions: int = 1536
    chunk_size: int = 5000
    batch_timeout_seconds: int = 7200
    batch_poll_interval_seconds: int = 30

    @field_validator('provider')
    @classmethod
    def _validate_provider(cls, v: str) -> str:
        allowed = ('openai', 'local')
        if v not in allowed:
            raise ValueError(
                f"embedding provider must be 'openai' or 'local', got '{v}'.\n\n"
                'Set it in one of:\n'
                '  1. ~/linkedout-data/config/config.yaml  →  embedding_provider: openai\n'
                '  2. Environment variable                 →  export LINKEDOUT_EMBEDDING__PROVIDER=openai',
            )
        return v


class ExternalAPIConfig(BaseModel):
    """Default retry/timeout for external API calls (Apify, etc.)."""

    retry_max_attempts: int = 3
    timeout_seconds: float = 30.0


class LinkedOutSettings(BaseSettings):
    """Single pydantic-settings class for the entire LinkedOut backend."""

    model_config = SettingsConfigDict(
        env_prefix='LINKEDOUT_',
        env_nested_delimiter='__',
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
        case_sensitive=False,
    )

    # ── Core ────────────────────────────────────────────────
    database_url: str = Field(
        default='postgresql://linkedout:linkedout@localhost:5432/linkedout',
        validation_alias=AliasChoices('DATABASE_URL', 'database_url'),
    )
    data_dir: str = Field(default='~/linkedout-data')
    environment: str = Field(default='local')
    debug: bool = Field(default=False)
    demo_mode: bool = Field(default=False)

    # ── Server ──────────────────────────────────────────────
    backend_host: str = Field(default='localhost')
    backend_port: int = Field(default=8001)
    backend_url: str = Field(default='')
    cors_origins: str = Field(default='')

    # ── LLM ────────────────────────────────────────────────
    llm: LLMConfig = LLMConfig()
    llm_api_key: str | None = Field(default=None)
    llm_api_base: str | None = Field(default=None)
    llm_api_version: str | None = Field(default=None)
    prompts_directory: str = Field(default='prompts')
    prompt_from_local_file: bool = Field(default=False)

    # ── Embeddings ──────────────────────────────────────────
    embedding: EmbeddingConfig = EmbeddingConfig()

    # ── External API Defaults ──────────────────────────────
    external_api: ExternalAPIConfig = ExternalAPIConfig()

    # ── API Keys (industry-standard names, no prefix) ───────
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices('OPENAI_API_KEY', 'openai_api_key'),
    )
    apify_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices('APIFY_API_KEY', 'apify_api_key'),
    )
    # Multiple keys for round-robin rotation (spreads Apify rate limits across accounts).
    # Comma-separated in env: APIFY_API_KEYS=key1,key2,key3
    # Or as a YAML list in secrets.yaml under apify_api_keys.
    apify_api_keys: str = Field(
        default='',
        validation_alias=AliasChoices('APIFY_API_KEYS', 'apify_api_keys'),
    )

    def get_apify_api_keys(self) -> list[str]:
        """Parse apify_api_keys into a list (comma-separated string or YAML list)."""
        if not self.apify_api_keys:
            return []
        return [k.strip() for k in self.apify_api_keys.split(',') if k.strip()]

    # ── Logging & Observability ─────────────────────────────
    log_level: str = Field(default='INFO')
    log_format: str = Field(default='human')
    log_dir: str = Field(default='')
    log_rotation: str = Field(default='50 MB')
    log_retention: str = Field(default='30 days')
    metrics_dir: str = Field(default='')
    db_echo_log: bool = Field(default=False)

    # ── Pagination ─────────────────────────────────────────
    default_page_size: int = Field(default=20)

    # ── Langfuse (industry-standard names, no prefix) ───────
    langfuse_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices('LANGFUSE_ENABLED', 'langfuse_enabled'),
    )
    langfuse_public_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices('LANGFUSE_PUBLIC_KEY', 'langfuse_public_key'),
    )
    langfuse_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices('LANGFUSE_SECRET_KEY', 'langfuse_secret_key'),
    )
    langfuse_host: str | None = Field(
        default=None,
        validation_alias=AliasChoices('LANGFUSE_HOST', 'langfuse_host'),
    )

    # ── Upgrade ─────────────────────────────────────────────
    # When true, silently upgrade on skill invocation when an update is available.
    # Logs to ~/linkedout-data/logs/cli.log; falls back to notification on failure.
    auto_upgrade: bool = Field(default=False)

    # ── Extension Tuning ────────────────────────────────────
    rate_limit_hourly: int = Field(default=30)
    rate_limit_daily: int = Field(default=150)
    staleness_days: int = Field(default=30)
    enrichment_cache_ttl_days: int = Field(default=90)

    # ── Scoring ────────────────────────────────────────────
    scoring: ScoringConfig = ScoringConfig()

    # ── Enrichment (Apify Profile Lookup) ──────────────────
    enrichment: EnrichmentConfig = EnrichmentConfig()

    # ── Field validators ─────────────────────────────────────

    @field_validator('database_url')
    @classmethod
    def _validate_database_url(cls, v: str) -> str:
        if not v.startswith(('postgresql://', 'postgres://')):
            raise ValueError(
                "database_url must start with 'postgresql://' or 'postgres://'.\n\n"
                'Set it in one of:\n'
                '  1. ~/linkedout-data/config/config.yaml  →  database_url: postgresql://...\n'
                '  2. Environment variable                 →  export DATABASE_URL=postgresql://...\n'
                '  3. .env file                            →  DATABASE_URL=postgresql://...',
            )
        return v

    @field_validator('backend_port')
    @classmethod
    def _validate_backend_port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError(f'backend_port must be between 1 and 65535, got {v}')
        return v

    @field_validator('log_level')
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = ('DEBUG', 'INFO', 'WARNING', 'ERROR')
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(
                f"log_level must be one of: {', '.join(allowed)}. Got: '{v}'",
            )
        return upper

    @field_validator('log_format')
    @classmethod
    def _validate_log_format(cls, v: str) -> str:
        allowed = ('human', 'json')
        if v not in allowed:
            raise ValueError(
                f"log_format must be one of: {', '.join(allowed)}. Got: '{v}'",
            )
        return v

    # ── Computed defaults & path expansion ──────────────────

    @model_validator(mode='after')
    def _expand_paths_and_compute(self) -> 'LinkedOutSettings':
        # Warn (don't error) if OpenAI provider is selected but no API key.
        # The key is only needed at embed time, not at startup.
        if self.embedding.provider == 'openai' and self.openai_api_key is None:
            _log = logging.getLogger('linkedout.config')
            _log.warning(
                "OPENAI_API_KEY is not set but embedding provider is 'openai'. "
                'Embedding operations will fail until the key is configured.\n'
                'Set it in ~/linkedout-data/config/secrets.yaml or '
                'export OPENAI_API_KEY=sk-...',
            )

        # Embedding dimension validation: warn on mismatch between provider and dimensions
        _expected_dims = {'openai': 1536, 'local': 768}
        expected = _expected_dims.get(self.embedding.provider)
        if expected and self.embedding.dimensions != expected:
            _log = logging.getLogger('linkedout.config')
            _log.warning(
                "Embedding dimensions (%d) don't match expected dimensions for "
                "provider '%s' (%d). Existing embeddings may be incompatible. "
                "Run `linkedout embed --force` to re-embed.",
                self.embedding.dimensions,
                self.embedding.provider,
                expected,
            )

        # Expand ~ in path fields
        self.data_dir = os.path.expanduser(self.data_dir)

        # Computed: log_dir defaults to data_dir/logs
        if not self.log_dir:
            self.log_dir = f'{self.data_dir}/logs'
        else:
            self.log_dir = os.path.expanduser(self.log_dir)

        # Computed: metrics_dir defaults to data_dir/metrics
        if not self.metrics_dir:
            self.metrics_dir = f'{self.data_dir}/metrics'
        else:
            self.metrics_dir = os.path.expanduser(self.metrics_dir)

        # Computed: backend_url from host+port
        if not self.backend_url:
            self.backend_url = f'http://{self.backend_host}:{self.backend_port}'

        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """Custom source order: env > .env > secrets.yaml > config.yaml > defaults."""
        return (
            env_settings,
            dotenv_settings,
            YamlSecretsSource(settings_cls),
            YamlConfigSource(settings_cls),
            init_settings,
        )

    def ensure_data_dirs(self) -> None:
        """Create the full directory tree under ``data_dir``."""
        for subdir in _DATA_DIR_SUBDIRS:
            Path(self.data_dir, subdir).mkdir(parents=True, exist_ok=True)

    # ── Backward-compat property aliases ────────────────────

    @property
    def BACKEND_BASE_URL(self) -> str:
        """Alias used by existing code (``backend_config.BACKEND_BASE_URL``)."""
        return self.backend_url


# ── Singleton ───────────────────────────────────────────────

_settings_instance: LinkedOutSettings | None = None


def get_config() -> LinkedOutSettings:
    """Return a process-wide ``LinkedOutSettings`` singleton."""
    global _settings_instance
    if _settings_instance is None:
        try:
            _settings_instance = LinkedOutSettings()
        except ValidationError as e:
            print('ERROR: LinkedOut configuration invalid.\n', file=sys.stderr)
            for error in e.errors():
                field = error['loc'][0] if error['loc'] else 'unknown'
                msg = error['msg']
                print(f'  {field}: {msg}\n', file=sys.stderr)
            sys.exit(1)
    return _settings_instance
