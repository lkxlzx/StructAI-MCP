"""Runtime settings.

``STRUCTAI_MASTER_KEY`` is read straight from the environment (总纲 §4.7.1) and
is deliberately *not* given a default. The timezone default is
``Asia/Shanghai`` because 总纲 §4.5.1 stores UTC and converts to the configured
zone on output.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "get_settings"]


class Settings(BaseSettings):
    """Environment-driven configuration for the StructAI backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- security (总纲 §4.7.1) -------------------------------------------
    #: AES-256-GCM master key. Must be set before any encrypted column is used.
    structai_master_key: str | None = None

    # --- persistence -------------------------------------------------------
    #: SQLAlchemy URL. SQLite is the default deployment (V2.1 §1.3 rule 8);
    #: PostgreSQL must remain a drop-in replacement.
    database_url: str = "sqlite:///./data/structai.db"
    sql_echo: bool = False

    # --- runtime (总纲 §4.5.1) --------------------------------------------
    #: IANA zone used when serializing timestamps for API output.
    timezone: str = "Asia/Shanghai"

    # --- HTTP service ------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8765
    log_level: str = "INFO"

    # --- MIDAS connection config ------------------------------------------
    #: JSON file holding ``base_url`` / ``MAPI-Key`` / ``software`` per MIDAS
    #: instance (project decision: these live in a config file, not the DB).
    #: The ``midas_clients`` table remains the multi-tenant runtime registry and
    #: this file is its bootstrap source. Relative paths resolve against the
    #: backend root. See ``app/core/midas_config.py`` and
    #: ``docs/MIDAS_API_对接规范_v1.0.md`` §2.
    midas_config_path: str = "config/midas.json"

    # --- rate limiting (总纲 裁决 B-7, mirrored into security_configs) -----
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 120
    rate_limit_burst: int = 30
    #: Honour ``X-Forwarded-For`` / ``X-Real-IP`` when choosing a rate-limit
    #: bucket.  **Default off, deliberately.**  Both headers are client-supplied
    #: text: with the flag on, any client that sends a different value per request
    #: gets a different bucket per request and the limit stops existing.  Turn it
    #: on only when a reverse proxy you control overwrites/append to the header
    #: and nothing can reach the app directly — see
    #: :func:`app.core.rate_limit.client_key` for which hop is then used.
    trust_proxy_headers: bool = False

    # --- convenience -------------------------------------------------------
    @property
    def is_sqlite(self) -> bool:
        """True when the configured database is SQLite."""
        return self.database_url.startswith("sqlite")

    @property
    def sqlite_file_path(self) -> str | None:
        """Filesystem path of the SQLite database, or ``None`` for memory/PG."""
        if not self.is_sqlite:
            return None
        _, _, raw = self.database_url.partition(":///")
        if not raw or raw == ":memory:" or raw.startswith("file:"):
            return None
        return raw

    @property
    def master_key_configured(self) -> bool:
        """True when a non-blank master key is configured."""
        return bool(self.structai_master_key and self.structai_master_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide :class:`Settings` singleton."""
    return Settings()
