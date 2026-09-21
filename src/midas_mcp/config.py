"""Configuration for the MIDAS MCP connector.

Credentials live in a JSON config file, grouped into *profiles* so every MIDAS
product keeps its own endpoint + key::

    {
      "active_profile": "MIDAS GEN NX",
      "profiles": {
        "MIDAS GEN NX":   {"base_url": "http://localhost:3030/gen",   "mapi_key": "..."},
        "MIDAS CIVIL NX": {"base_url": "http://localhost:3030/civil", "mapi_key": "..."}
      }
    }

Select a product with ``--profile`` (or ``MIDAS_MCP_PROFILE``); leave it out and
``active_profile`` is used.  Environment variables still win over the file, so a
one-off run or CI job can override without editing anything.  The key is never
accepted on the command line and never echoed once loaded.
"""
from __future__ import annotations

import dataclasses
import json
import os
import stat
from pathlib import Path

DEFAULT_BASE_URL = "http://localhost:3030/gen"
DEFAULT_TIMEOUTS = {"query": 30, "assign": 60, "analysis": 1800, "table": 180}

CONFIG_ENV = "MIDAS_MCP_CONFIG"
PROFILE_ENV = "MIDAS_MCP_PROFILE"
CONFIG_FILENAME = "config.json"

# Accepted spellings inside a profile block, so hand-written files are forgiving.
_BASE_URL_KEYS = ("base_url", "base-url", "baseUrl", "url", "endpoint")
_MAPI_KEY_KEYS = ("mapi_key", "mapi-key", "MAPI_KEY", "mapiKey", "key")


class Secret:
    """A value that is safe to log: its repr carries no payload."""

    __slots__ = ("_value",)

    def __init__(self, value: str):
        self._value = value

    def reveal(self) -> str:
        return self._value

    # repr and str both redact; never log ._value directly.
    def __repr__(self) -> str:
        return "<Secret>"

    __str__ = __repr__


@dataclasses.dataclass(frozen=True)
class Config:
    base_url: str
    mapi_key: Secret
    registry_dir: Path
    allow_bulk_delete: bool = False
    timeouts: dict = dataclasses.field(default_factory=lambda: dict(DEFAULT_TIMEOUTS))
    log_level: str = "warning"
    max_workers: int = 8
    # Diagnostics only -- never carry the key in these.
    profile: str | None = None
    config_path: Path | None = None
    config_source: str = "defaults"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _pick(mapping: dict, keys) -> object | None:
    """First present, non-empty value among ``keys`` (alias-tolerant lookup)."""
    if not isinstance(mapping, dict):
        return None
    for k in keys:
        if k in mapping:
            value = mapping[k]
            if value is not None and str(value).strip() != "":
                return value
    return None


def user_config_dir() -> Path:
    """Per-user config location (``%APPDATA%`` on Windows, XDG elsewhere)."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "midas-mcp"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "midas-mcp"


def default_config_paths() -> list[Path]:
    """Search order used when ``--config`` is not given (first hit wins)."""
    project_root = Path(__file__).resolve().parent.parent.parent
    return [
        Path.cwd() / CONFIG_FILENAME,
        project_root / CONFIG_FILENAME,
        user_config_dir() / CONFIG_FILENAME,
    ]


def discover_config_path(explicit: str | Path | None = None) -> tuple[Path | None, str]:
    """Return ``(path, source)`` for the config file that should be used."""
    if explicit:
        path = Path(explicit).expanduser()
        if not path.exists():
            raise ValueError(f"config file not found: {path}")
        return path, "cli"
    env_path = os.environ.get(CONFIG_ENV)
    if env_path:
        path = Path(env_path).expanduser()
        if not path.exists():
            raise ValueError(f"{CONFIG_ENV} points at a missing file: {path}")
        return path, "env"
    for path in default_config_paths():
        if path.exists():
            return path, "discovered"
    return None, "none"


def _load_document(path: Path | None) -> dict:
    if path is None:
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"config file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError(f"config file must contain a JSON object: {path}")
    return doc


def profiles_of(doc: dict) -> dict:
    """Normalised ``{name: profile_dict}``; empty when the file is flat."""
    raw = doc.get("profiles")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError('"profiles" must be a JSON object of name -> settings')
    out = {}
    for name, block in raw.items():
        if not isinstance(block, dict):
            raise ValueError(f'profile "{name}" must be a JSON object')
        out[str(name)] = block
    return out


def _normalise(name: str) -> str:
    return " ".join(str(name).split()).casefold()


def resolve_profile(doc: dict, requested: str | None) -> tuple[str | None, dict]:
    """Pick the profile block to use.

    Order: explicit ``requested`` -> ``MIDAS_MCP_PROFILE`` -> ``active_profile``
    -> the only profile when exactly one is defined -> flat top level.
    """
    profiles = profiles_of(doc)
    if not profiles:
        if requested:
            raise ValueError(
                f'profile "{requested}" requested but the config file defines no '
                '"profiles" block')
        return None, {}

    wanted = requested or os.environ.get(PROFILE_ENV) or doc.get("active_profile")
    if not wanted:
        if len(profiles) == 1:
            return next(iter(profiles.items()))
        raise ValueError(
            "no profile selected; set \"active_profile\" in the config file, pass "
            "--profile, or set " + PROFILE_ENV + ". Available: "
            + ", ".join(sorted(profiles)))

    lookup = {_normalise(k): k for k in profiles}
    hit = lookup.get(_normalise(str(wanted)))
    if hit is None:
        raise ValueError(
            f'unknown profile "{wanted}". Available: '
            + ", ".join(sorted(profiles)))
    return hit, profiles[hit]


def list_profiles(path: str | Path | None = None) -> list[dict]:
    """Safe profile inventory for ``--list-profiles`` -- never includes keys."""
    resolved, source = discover_config_path(path)
    doc = _load_document(resolved)
    active = doc.get("active_profile")
    rows = []
    for name, block in profiles_of(doc).items():
        rows.append({
            "name": name,
            "base_url": _pick(block, _BASE_URL_KEYS) or doc.get("base_url"),
            "has_key": bool(_pick(block, _MAPI_KEY_KEYS)),
            "active": _normalise(name) == _normalise(str(active)) if active else False,
        })
    if not rows:
        rows.append({
            "name": None,
            "base_url": doc.get("base_url"),
            "has_key": bool(_pick(doc, _MAPI_KEY_KEYS)),
            "active": True,
        })
    return rows, {"path": resolved, "source": source}


def _warn_if_world_readable(path: Path) -> str | None:
    """A config file holds a credential; flag loose permissions on POSIX."""
    if os.name == "nt":
        return None
    try:
        mode = path.stat().st_mode
    except OSError:
        return None
    if mode & (stat.S_IRGRP | stat.S_IROTH):
        return (f"{path} is group/world readable but stores a MAPI-Key; "
                f"run: chmod 600 {path}")
    return None


def load_config(argv: list[str] | None = None) -> Config:
    """Build Config from CLI + config file + environment.

    ``--config <path>`` and ``--profile <name>`` may appear in ``argv``; every
    other CLI value is rejected so the connector cannot be pointed at a wrong
    URL or key by accident.
    """
    config_path: Path | None = None
    profile_arg: str | None = None
    if argv:
        rest = list(argv)
        while rest:
            tok = rest.pop(0)
            if tok == "--config" and rest:
                config_path = Path(rest.pop(0))
            elif tok == "--profile" and rest:
                profile_arg = rest.pop(0)
            else:
                raise ValueError(f"unsupported CLI argument: {tok}")

    resolved, source = discover_config_path(config_path)
    doc = _load_document(resolved)
    profile_name, profile = resolve_profile(doc, profile_arg)

    # Profile values win over the file's top level; environment wins over both.
    def merged_scalar(key: str, default=None):
        if key in profile:
            return profile[key]
        return doc.get(key, default)

    key = os.environ.get("MIDAS_MAPI_KEY") or _pick(profile, _MAPI_KEY_KEYS) \
        or _pick(doc, _MAPI_KEY_KEYS)
    if not key:
        where = f"{resolved} (profile: {profile_name})" if resolved else "no config file"
        raise RuntimeError(
            "No MAPI-Key found. Add one to the config file "
            f"({where}) as \"mapi_key\" inside the product profile, or set the "
            "MIDAS_MAPI_KEY environment variable. It is never accepted on the "
            "command line.")

    base_url = os.environ.get("MIDAS_BASE_URL") or _pick(profile, _BASE_URL_KEYS) \
        or _pick(doc, _BASE_URL_KEYS) or DEFAULT_BASE_URL
    base_url = str(base_url).rstrip("/")

    timeouts = dict(DEFAULT_TIMEOUTS)
    file_timeouts = doc.get("timeouts")
    if isinstance(file_timeouts, dict):
        timeouts.update({k: int(v) for k, v in file_timeouts.items()})
    profile_timeouts = profile.get("timeouts")
    if isinstance(profile_timeouts, dict):
        timeouts.update({k: int(v) for k, v in profile_timeouts.items()})
    env_timeouts = {k.replace("MIDAS_MCP_TIMEOUT_", "").lower(): int(os.environ[k])
                    for k in os.environ if k.startswith("MIDAS_MCP_TIMEOUT_")}
    timeouts.update(env_timeouts)

    registry_dir = Path(merged_scalar(
        "registry_dir",
        Path(__file__).resolve().parent.parent.parent / "registry"))

    warning = _warn_if_world_readable(resolved) if resolved else None
    if warning:
        import sys
        print(f"midas-mcp: warning: {warning}", file=sys.stderr)

    return Config(
        base_url=base_url,
        mapi_key=Secret(str(key)),
        registry_dir=registry_dir,
        allow_bulk_delete=_env_bool("MIDAS_MCP_ALLOW_BULK_DELETE")
        or bool(merged_scalar("allow_bulk_delete", False)),
        timeouts=timeouts,
        log_level=os.environ.get("MIDAS_MCP_LOG_LEVEL")
        or str(merged_scalar("log_level", "warning")),
        max_workers=int(os.environ.get("MIDAS_MCP_MAX_WORKERS",
                                       merged_scalar("max_workers", 8))),
        profile=profile_name,
        config_path=resolved,
        config_source=source,
    )


def describe_config(cfg: Config) -> str:
    """Human-readable, key-free summary of the resolved configuration."""
    key = cfg.mapi_key.reveal()
    # Only the tail is shown: enough to tell two keys apart, not enough to use one.
    fingerprint = f"...{key[-4:]} ({len(key)} chars)" if len(key) >= 8 else "(short)"
    lines = [
        f"profile      : {cfg.profile or '(flat config / env only)'}",
        f"base_url     : {cfg.base_url}",
        f"mapi_key     : {fingerprint}",
        f"config file  : {cfg.config_path or '(none)'} [{cfg.config_source}]",
        f"registry_dir : {cfg.registry_dir}",
        f"timeouts     : {cfg.timeouts}",
        f"log_level    : {cfg.log_level}",
        f"max_workers  : {cfg.max_workers}",
        f"bulk delete  : {cfg.allow_bulk_delete}",
    ]
    return "\n".join(lines)


def redact(text: str, cfg: Config | None = None) -> str:
    """Remove any MAPI-Key that leaked into a string before it is logged/sent."""
    if cfg is None:
        return text  # without a config there is nothing trusted to scrub against
    secret = cfg.mapi_key.reveal()
    if secret and secret in text:
        return text.replace(secret, "***")
    return text
