"""Resolve live MIDAS credentials for scripts, tests and probes.

The connector reads credentials through :mod:`midas_mcp.config`.  Standalone
live scripts need the same values *before* they spawn a server subprocess, so
this module wraps that lookup and exports the result into ``os.environ`` for
children to inherit.

Nothing is hardcoded here.  A missing credential raises
:class:`MissingCredentials` with an actionable message instead of silently
falling back to a checked-in key.
"""
from __future__ import annotations

import os
from pathlib import Path

from .config import CONFIG_ENV, PROFILE_ENV, load_config

KEY_ENV = "MIDAS_MAPI_KEY"
URL_ENV = "MIDAS_BASE_URL"
# Opt-in switch that lets live *unittest* modules run without an exported key.
LIVE_ENV = "MIDAS_MCP_LIVE"

_TRUTHY = ("1", "true", "yes", "on")


class MissingCredentials(RuntimeError):
    """Neither the config file nor the environment supplied a MAPI-Key."""


def resolve(profile: str | None = None,
            config: str | Path | None = None) -> tuple[str, str]:
    """Return ``(base_url, mapi_key)``, or raise :class:`MissingCredentials`."""
    argv: list[str] = []
    if config is not None:
        argv += ["--config", str(config)]
    if profile:
        argv += ["--profile", str(profile)]
    try:
        cfg = load_config(argv or None)
    except (RuntimeError, ValueError) as exc:
        raise MissingCredentials(
            f"{exc}\n"
            "Live scripts take credentials from config.json (see "
            "config.example.json) or from the MIDAS_MAPI_KEY environment "
            "variable. No key is hardcoded anywhere."
        ) from exc
    return cfg.base_url, cfg.mapi_key.reveal()


def ensure_credentials(profile: str | None = None,
                       config: str | Path | None = None) -> tuple[str, str]:
    """Resolve credentials and export them for this process and its children.

    Sets ``MIDAS_MAPI_KEY`` and ``MIDAS_BASE_URL`` (plus the profile/config
    selectors when given) so a spawned MCP server subprocess targets exactly the
    profile this script chose.
    """
    base_url, key = resolve(profile, config)
    os.environ[KEY_ENV] = key
    os.environ[URL_ENV] = base_url
    if profile:
        os.environ[PROFILE_ENV] = str(profile)
    if config is not None:
        os.environ[CONFIG_ENV] = str(config)
    return base_url, key


def live_enabled() -> bool:
    """True when the caller explicitly opted into live tests."""
    return os.environ.get(LIVE_ENV, "").strip().lower() in _TRUTHY


def unittest_key() -> str | None:
    """MAPI-Key for live *unittest* modules, or ``None`` to skip them.

    An exported ``MIDAS_MAPI_KEY`` always wins, so ``unittest discover`` keeps
    skipping live tests unless the operator opts in with ``MIDAS_MCP_LIVE=1``
    (which then pulls the key from the config file).

    Raises :class:`MissingCredentials` when ``MIDAS_MCP_LIVE`` is set but no
    credential can be resolved: an explicit opt-in must not degrade into a
    silent skip that hides a misconfigured ``MIDAS_MCP_CONFIG`` path.
    """
    exported = os.environ.get(KEY_ENV)
    if exported:
        return exported
    if live_enabled():
        return resolve()[1]
    return None
