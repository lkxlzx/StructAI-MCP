"""Offline tests for profile-based configuration.

Covers the config-file contract: per-product profiles, profile selection
precedence, environment overrides, and the guarantee that a key is never echoed
by the diagnostics surface.  Run with::

    python -m unittest discover -s tests -p 'test_*.py'
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from midas_mcp import config  # noqa: E402

# A synthetic key for the fixtures below: a real MAPI-Key must never live in a
# tracked file, so this module deliberately contains no usable credential.
FAKE_KEY = "TESTKEY0000000000000"  # 22 chars, same shape as a real key

# Every env var load_config consults; cleared per-test so the developer's own
# environment (and the repo's real config.json) cannot influence a result.
_ENV_VARS = (
    "MIDAS_MAPI_KEY", "MIDAS_BASE_URL", "MIDAS_MCP_CONFIG", "MIDAS_MCP_PROFILE",
    "MIDAS_MCP_ALLOW_BULK_DELETE", "MIDAS_MCP_LOG_LEVEL", "MIDAS_MCP_MAX_WORKERS",
    "MIDAS_MCP_TIMEOUT_QUERY", "MIDAS_MCP_TIMEOUT_ASSIGN",
    "MIDAS_MCP_TIMEOUT_ANALYSIS", "MIDAS_MCP_TIMEOUT_TABLE",
)


class ConfigTestCase(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in _ENV_VARS}
        for k in _ENV_VARS:
            os.environ.pop(k, None)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def write_config(self, doc: dict, name: str = "config.json") -> str:
        path = self.tmp / name
        path.write_text(json.dumps(doc), encoding="utf-8")
        return str(path)

    def load(self, doc: dict, *cli: str) -> config.Config:
        return config.load_config(["--config", self.write_config(doc), *cli])


class FlatConfigTests(ConfigTestCase):
    """The pre-profile file shape must keep working."""

    def test_flat_file_supplies_url_and_key(self):
        cfg = self.load({"base_url": "http://host:3030/gen", "mapi_key": "flat-key"})
        self.assertEqual(cfg.base_url, "http://host:3030/gen")
        self.assertEqual(cfg.mapi_key.reveal(), "flat-key")
        self.assertIsNone(cfg.profile)

    def test_trailing_slash_is_stripped(self):
        cfg = self.load({"base_url": "http://host:3030/gen/", "mapi_key": "k"})
        self.assertEqual(cfg.base_url, "http://host:3030/gen")

    def test_flat_file_without_key_is_an_error(self):
        with self.assertRaises(RuntimeError) as ctx:
            self.load({"base_url": "http://host:3030/gen"})
        self.assertIn("No MAPI-Key found", str(ctx.exception))

    def test_flat_file_rejects_profile_argument(self):
        with self.assertRaises(ValueError) as ctx:
            self.load({"mapi_key": "k"}, "--profile", "anything")
        self.assertIn("defines no", str(ctx.exception))

    def test_non_object_json_is_rejected(self):
        path = self.tmp / "config.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        with self.assertRaises(ValueError):
            config.load_config(["--config", str(path)])

    def test_invalid_json_is_rejected(self):
        path = self.tmp / "config.json"
        path.write_text("{ not json", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            config.load_config(["--config", str(path)])
        self.assertIn("not valid JSON", str(ctx.exception))

    def test_missing_explicit_config_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            config.load_config(["--config", str(self.tmp / "nope.json")])
        self.assertIn("not found", str(ctx.exception))


class ProfileTests(ConfigTestCase):
    DOC = {
        "active_profile": "MIDAS GEN NX",
        "profiles": {
            "MIDAS GEN NX": {"base_url": "http://localhost:3030/gen",
                             "mapi_key": "gen-key"},
            "MIDAS CIVIL NX": {"base_url": "http://localhost:3030/civil",
                               "mapi_key": "civil-key"},
        },
    }

    def test_active_profile_is_used_by_default(self):
        cfg = self.load(self.DOC)
        self.assertEqual(cfg.profile, "MIDAS GEN NX")
        self.assertEqual(cfg.base_url, "http://localhost:3030/gen")
        self.assertEqual(cfg.mapi_key.reveal(), "gen-key")

    def test_explicit_profile_selects_the_other_product(self):
        cfg = self.load(self.DOC, "--profile", "MIDAS CIVIL NX")
        self.assertEqual(cfg.profile, "MIDAS CIVIL NX")
        self.assertEqual(cfg.base_url, "http://localhost:3030/civil")
        self.assertEqual(cfg.mapi_key.reveal(), "civil-key")

    def test_profile_match_ignores_case_and_padding(self):
        cfg = self.load(self.DOC, "--profile", "  midas civil nx ")
        self.assertEqual(cfg.profile, "MIDAS CIVIL NX")

    def test_unknown_profile_lists_the_available_ones(self):
        with self.assertRaises(ValueError) as ctx:
            self.load(self.DOC, "--profile", "MIDAS BRIDGE NX")
        message = str(ctx.exception)
        self.assertIn("unknown profile", message)
        self.assertIn("MIDAS GEN NX", message)
        self.assertIn("MIDAS CIVIL NX", message)

    def test_env_var_selects_profile(self):
        os.environ["MIDAS_MCP_PROFILE"] = "MIDAS CIVIL NX"
        self.assertEqual(self.load(self.DOC).profile, "MIDAS CIVIL NX")

    def test_cli_profile_beats_env_var(self):
        os.environ["MIDAS_MCP_PROFILE"] = "MIDAS CIVIL NX"
        cfg = self.load(self.DOC, "--profile", "MIDAS GEN NX")
        self.assertEqual(cfg.profile, "MIDAS GEN NX")

    def test_env_var_beats_active_profile(self):
        os.environ["MIDAS_MCP_PROFILE"] = "MIDAS CIVIL NX"
        cfg = self.load(self.DOC)
        self.assertEqual(cfg.base_url, "http://localhost:3030/civil")

    def test_single_profile_needs_no_active_marker(self):
        doc = {"profiles": {"Only": {"base_url": "http://h/gen", "mapi_key": "k"}}}
        self.assertEqual(self.load(doc).profile, "Only")

    def test_multiple_profiles_without_selection_is_an_error(self):
        doc = {"profiles": {k: dict(v) for k, v in self.DOC["profiles"].items()}}
        with self.assertRaises(ValueError) as ctx:
            self.load(doc)
        self.assertIn("no profile selected", str(ctx.exception))

    def test_profiles_must_be_an_object(self):
        with self.assertRaises(ValueError) as ctx:
            self.load({"profiles": ["a", "b"]})
        self.assertIn("must be a JSON object", str(ctx.exception))

    def test_profile_block_must_be_an_object(self):
        with self.assertRaises(ValueError) as ctx:
            self.load({"profiles": {"Bad": "http://h/gen"}})
        self.assertIn('profile "Bad"', str(ctx.exception))

    def test_profile_key_aliases_are_accepted(self):
        doc = {"profiles": {"P": {"base-url": "http://h/gen", "MAPI_KEY": "alias"}}}
        cfg = self.load(doc)
        self.assertEqual(cfg.base_url, "http://h/gen")
        self.assertEqual(cfg.mapi_key.reveal(), "alias")


class OverrideTests(ConfigTestCase):
    DOC = {
        "active_profile": "GEN",
        "log_level": "warning",
        "max_workers": 8,
        "timeouts": {"query": 30, "assign": 60, "analysis": 1800, "table": 180},
        "profiles": {
            "GEN": {"base_url": "http://localhost:3030/gen", "mapi_key": "gen-key"},
            "CIVIL": {"base_url": "http://localhost:3030/civil", "mapi_key": "civil-key",
                      "log_level": "debug", "max_workers": 3,
                      "timeouts": {"analysis": 600}},
        },
    }

    def test_env_key_wins_over_profile_key(self):
        os.environ["MIDAS_MAPI_KEY"] = "env-key"
        cfg = self.load(self.DOC)
        self.assertEqual(cfg.mapi_key.reveal(), "env-key")
        self.assertEqual(cfg.base_url, "http://localhost:3030/gen")

    def test_env_base_url_wins_over_profile(self):
        os.environ["MIDAS_BASE_URL"] = "http://elsewhere:3030/gen/"
        cfg = self.load(self.DOC)
        self.assertEqual(cfg.base_url, "http://elsewhere:3030/gen")

    def test_profile_scalars_override_top_level(self):
        cfg = self.load(self.DOC, "--profile", "CIVIL")
        self.assertEqual(cfg.log_level, "debug")
        self.assertEqual(cfg.max_workers, 3)

    def test_profile_timeouts_merge_over_top_level(self):
        cfg = self.load(self.DOC, "--profile", "CIVIL")
        self.assertEqual(cfg.timeouts["analysis"], 600)   # profile wins
        self.assertEqual(cfg.timeouts["query"], 30)       # inherited

    def test_env_timeouts_beat_profile(self):
        os.environ["MIDAS_MCP_TIMEOUT_ANALYSIS"] = "77"
        cfg = self.load(self.DOC, "--profile", "CIVIL")
        self.assertEqual(cfg.timeouts["analysis"], 77)

    def test_env_config_path_is_used(self):
        path = self.write_config(self.DOC, "elsewhere.json")
        os.environ["MIDAS_MCP_CONFIG"] = path
        cfg = config.load_config([])
        self.assertEqual(cfg.config_source, "env")
        self.assertEqual(cfg.profile, "GEN")

    def test_env_config_path_pointing_nowhere_is_an_error(self):
        os.environ["MIDAS_MCP_CONFIG"] = str(self.tmp / "ghost.json")
        with self.assertRaises(ValueError) as ctx:
            config.load_config([])
        self.assertIn("missing file", str(ctx.exception))

    def test_discovered_path_is_reported(self):
        path = self.write_config(self.DOC)
        cfg = config.load_config(["--config", path])
        self.assertEqual(cfg.config_source, "cli")
        self.assertEqual(cfg.config_path, Path(path))


class CliSurfaceTests(ConfigTestCase):
    DOC = {"profiles": {"GEN": {"base_url": "http://h/gen", "mapi_key": "gen-key"}}}

    def test_unknown_cli_argument_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self.load(self.DOC, "--base-url", "http://evil")
        self.assertIn("unsupported CLI argument", str(ctx.exception))

    def test_key_cannot_be_passed_on_the_command_line(self):
        with self.assertRaises(ValueError):
            self.load(self.DOC, "--mapi-key", "stolen")

    def test_profile_without_value_is_rejected(self):
        with self.assertRaises(ValueError):
            self.load(self.DOC, "--profile")


class DiagnosticsRedactionTests(ConfigTestCase):
    DOC = {"profiles": {"GEN": {"base_url": "http://h/gen",
                                "mapi_key": FAKE_KEY}}}

    def test_describe_config_does_not_leak_the_key(self):
        cfg = self.load(self.DOC)
        out = config.describe_config(cfg)
        self.assertNotIn(cfg.mapi_key.reveal(), out)
        self.assertNotIn(FAKE_KEY, out)
        self.assertIn("profile      : GEN", out)
        self.assertIn("http://h/gen", out)
        self.assertIn(f"{len(FAKE_KEY)} chars", out)

    def test_list_profiles_never_reports_key_material(self):
        path = self.write_config(self.DOC)
        rows, meta = config.list_profiles(path)
        self.assertEqual(meta["path"], Path(path))
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["has_key"])
        self.assertEqual(rows[0]["base_url"], "http://h/gen")
        self.assertNotIn("mapi_key", json.dumps(rows))
        self.assertNotIn(FAKE_KEY, json.dumps(rows))

    def test_list_profiles_marks_active_profile(self):
        doc = {"active_profile": "B",
               "profiles": {"A": {"mapi_key": "a"}, "B": {"mapi_key": "b"}}}
        rows, _ = config.list_profiles(self.write_config(doc))
        by_name = {r["name"]: r["active"] for r in rows}
        self.assertEqual(by_name, {"A": False, "B": True})

    def test_list_profiles_reports_missing_key(self):
        rows, _ = config.list_profiles(self.write_config({"profiles": {"A": {}}}))
        self.assertFalse(rows[0]["has_key"])

    def test_redact_scrubs_the_configured_key(self):
        cfg = self.load(self.DOC)
        self.assertNotIn(FAKE_KEY, config.redact(f"sent key {FAKE_KEY}", cfg))

    def test_secret_repr_carries_no_payload(self):
        self.assertEqual(repr(config.Secret("hunter2")), "<Secret>")
        self.assertEqual(str(config.Secret("hunter2")), "<Secret>")


class DiscoveryTests(ConfigTestCase):
    def test_default_search_order_puts_cwd_first(self):
        paths = config.default_config_paths()
        self.assertEqual(paths[0], Path.cwd() / "config.json")
        self.assertEqual(paths[-1], config.user_config_dir() / "config.json")

    def test_user_config_dir_honours_appdata(self):
        os.environ["APPDATA"] = str(self.tmp / "Roaming")
        self.assertEqual(config.user_config_dir(), self.tmp / "Roaming" / "midas-mcp")


if __name__ == "__main__":
    unittest.main()
