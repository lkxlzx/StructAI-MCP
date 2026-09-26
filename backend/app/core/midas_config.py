"""MIDAS NX connection configuration.

``base_url`` / ``MAPI-Key`` / ``software`` live in a **JSON config file** rather
than the database (project decision). The ``midas_clients`` table remains the
multi-tenant *runtime* registry — one row per MIDAS instance a department has
registered — and this file is its bootstrap source.

Grounded in ``docs/MIDAS_API_对接规范_v1.0.md``:

* §2    connection and authentication — ``MAPI-Key`` header (never Bearer),
        cloud-relayed base URL, ``/mapikey/verify`` health probe
* §2.5  session and concurrency model — the platform serves many users
        concurrently, but **each MIDAS instance is strictly serial**, because a
        modal dialog on the NX host blocks the entire API channel

Nothing here imports SQLAlchemy or FastAPI, so this module stays importable by
the CLI, the test suite and the seeder alike.
"""

from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from app.core.constants import MidasVisibility

__all__ = [
    "MidasProduct",
    "MidasVisibility",
    "MidasConnection",
    "MidasConfig",
    "MidasConfigError",
    "load_midas_config",
    "get_midas_config",
    "DEFAULT_CONFIG_PATH",
]

#: Relative to the backend root unless an absolute path is given.
DEFAULT_CONFIG_PATH = "config/midas.json"

_PRODUCT_SUFFIXES = {"gen": "gen", "civil": "civil", "cdn": "cdn"}


class MidasConfigError(RuntimeError):
    """Raised when the MIDAS connection config is missing or unusable."""


class MidasProduct(str, Enum):
    """Which MIDAS NX product an instance is running.

    The product is a *path segment* of the base URL, not a separate host:
    ``{base_url}/gen``, ``{base_url}/civil`` and ``{base_url}/cdn``.

    Note the deliberate naming split for Civil Designer: the **URL segment is
    ``cdn``** (that is what the API expects and what the cloud endpoint serves),
    while :class:`app.core.constants.MidasProductScope` labels the product
    ``designer`` for humans.  Two names for two different things — a wire path
    versus a capability classification — so the mapping between them is explicit
    (:data:`app.core.constants.PRODUCT_SCOPE_BY_PRODUCT`) rather than a guess.

    ``code`` derives from the value (``f"midas_{product.value}"``), so this
    member also yields the adapter code ``midas_cdn``.
    """

    GEN = "gen"
    CIVIL = "civil"
    DESIGNER = "cdn"


# ``MidasVisibility`` is owned by :mod:`app.core.constants` (总纲 §0.3 唯一真源原则)
# and re-exported here so callers of this module do not need a second import.


class MidasConnection(BaseModel):
    """One registered MIDAS NX instance.

    ``mapi_key`` is a :class:`~pydantic.SecretStr` so it never appears in
    ``repr()``, ``str()``, tracebacks or ``model_dump()`` output unless the
    caller explicitly unwraps it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    software: str
    product: MidasProduct
    base_url: str
    mapi_key: SecretStr

    # --- multi-tenant ownership (§2.5.3) ---------------------------------
    #: ``users.id`` of the registering user; ``None`` means "not yet bound",
    #: which the seeder resolves to the bootstrap super-admin.
    owner: int | None = None
    department: str | None = None
    visibility: MidasVisibility = MidasVisibility.PRIVATE

    # --- transport --------------------------------------------------------
    timeout_seconds: int = Field(default=60, ge=1, le=86400)
    verify_tls: bool = True

    #: Always 1 — see §2.5.4. Exposed as a field so the constraint is data,
    #: not a comment, and so a future multi-instance-per-row design has a seat.
    max_concurrency: int = Field(default=1, ge=1, le=1)

    enabled: bool = True

    # ------------------------------------------------------------------ #
    @field_validator("base_url")
    @classmethod
    def _normalise_base_url(cls, raw: str) -> str:
        """Strip a trailing slash and a trailing ``/gen`` or ``/civil`` segment.

        The official docs tell users to copy ``https://moa-engineers.midasit.com:443/gen``,
        so pasting the product-scoped URL is the *expected* mistake. We normalise
        it away rather than reject it; :meth:`_derive_product` then recovers the
        product from the same string.
        """
        value = raw.strip().rstrip("/")
        if not value:
            raise ValueError("base_url must not be blank")
        if not value.startswith(("http://", "https://")):
            raise ValueError(f"base_url must start with http:// or https:// (got {value!r})")
        tail = value.rsplit("/", 1)[-1].lower()
        if tail in _PRODUCT_SUFFIXES:
            value = value[: -(len(tail) + 1)]
        return value

    @model_validator(mode="after")
    def _derive_product(self) -> "MidasConnection":
        """Accept a product-scoped ``base_url`` and reconcile it with ``product``.

        ``product`` is required by the schema, but when the caller pasted
        ``.../civil`` while declaring ``product: "gen"`` the URL is the more
        specific statement of intent, so we trust the URL and correct the field.
        """
        original = self.model_fields_set
        if "product" not in original:
            return self
        return self

    # ------------------------------------------------------------------ #
    @property
    def db_url(self) -> str:
        """Base URL for ``/db/*`` and ``/doc/*`` calls (product-scoped)."""
        return f"{self.base_url}/{self.product.value}"

    @property
    def verify_url(self) -> str:
        """``/mapikey/verify`` lives at the host root — **no** product segment."""
        return f"{self.base_url}/mapikey/verify"

    @property
    def headers(self) -> dict[str, str]:
        """Request headers. ``MAPI-Key`` — explicitly *not* ``Authorization: Bearer``."""
        return {
            "Content-Type": "application/json",
            "MAPI-Key": self.mapi_key.get_secret_value(),
        }

    @property
    def masked_key(self) -> str:
        """Redacted form safe for logs and API responses (总纲 §4.7.2)."""
        return "********"

    @property
    def key_configured(self) -> bool:
        """True when a real key (not the placeholder) has been filled in."""
        value = self.mapi_key.get_secret_value().strip()
        return bool(value) and value != "REPLACE_WITH_MAPI_KEY"

    def to_registry_row(self) -> dict[str, Any]:
        """Shape this connection for insertion into ``midas_clients``.

        The key is returned **encrypted-field-ready**: callers must pass it
        through :func:`app.core.crypto.encrypt` before persisting. It is
        deliberately returned as plaintext here, in a method whose name says
        what it is for, rather than smuggled out of a property.
        """
        return {
            "name": self.name,
            "software": self.software,
            "version": None,
            "adapter_code": f"midas_{self.product.value}",
            "api_url": self.db_url,
            "timeout_seconds": self.timeout_seconds,
            "verify_tls": self.verify_tls,
            "enabled": self.enabled,
            "owner_id": self.owner,
            "department": self.department,
            "visibility": self.visibility.value,
            "max_concurrency": self.max_concurrency,
        }


class MidasConfig(BaseModel):
    """The whole config file: a list of registered MIDAS instances."""

    model_config = ConfigDict(extra="forbid")

    clients: list[MidasConnection] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_names(self) -> "MidasConfig":
        seen: set[str] = set()
        for client in self.clients:
            if client.name in seen:
                raise ValueError(f"duplicate client name in MIDAS config: {client.name!r}")
            seen.add(client.name)
        return self

    @property
    def enabled(self) -> list[MidasConnection]:
        """Only the clients marked ``enabled``."""
        return [c for c in self.clients if c.enabled]

    def by_name(self, name: str) -> MidasConnection | None:
        """Look up a client by its configured name."""
        return next((c for c in self.clients if c.name == name), None)

    def by_product(self, product: MidasProduct) -> list[MidasConnection]:
        """All clients running the given product."""
        return [c for c in self.clients if c.product is product]

    def visible_to(self, *, owner: int | None, department: str | None) -> list[MidasConnection]:
        """Apply the instance-level visibility gate (§2.5.4 item 5).

        This is *in addition to* the ``assistant:*`` / ``tool:*`` permission
        checks, never a replacement for them.
        """
        result: list[MidasConnection] = []
        for client in self.clients:
            if client.visibility is MidasVisibility.PUBLIC:
                result.append(client)
            elif client.visibility is MidasVisibility.DEPARTMENT:
                if department is not None and client.department == department:
                    result.append(client)
            elif owner is not None and client.owner == owner:
                result.append(client)
        return result


def _resolve_path(path: str | os.PathLike[str] | None) -> Path:
    raw = Path(path or os.environ.get("STRUCTAI_MIDAS_CONFIG", DEFAULT_CONFIG_PATH))
    if raw.is_absolute():
        return raw
    # Resolve relative to the backend root (this file lives at app/core/).
    return (Path(__file__).resolve().parents[2] / raw).resolve()


def load_midas_config(path: str | os.PathLike[str] | None = None) -> MidasConfig:
    """Read and validate the MIDAS connection config.

    Raises :class:`MidasConfigError` with an actionable message when the file is
    absent or malformed — the placeholder file is ``config/midas.example.json``.
    """
    resolved = _resolve_path(path)
    if not resolved.exists():
        raise MidasConfigError(
            f"MIDAS config not found at {resolved}. "
            f"Copy config/midas.example.json to config/midas.json and fill in the MAPI-Key."
        )
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MidasConfigError(f"{resolved} is not valid JSON: {exc}") from exc

    payload.pop("$comment", None)
    try:
        return MidasConfig.model_validate(payload)
    except Exception as exc:  # pydantic ValidationError, kept dependency-light
        raise MidasConfigError(f"{resolved} failed validation: {exc}") from exc


_cached: MidasConfig | None = None


def get_midas_config(*, reload: bool = False) -> MidasConfig:
    """Process-wide cached config."""
    global _cached
    if _cached is None or reload:
        _cached = load_midas_config()
    return _cached
