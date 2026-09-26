## Changed

- Bumped three dependency floors: `requests>=2.28` → `>=2.34.2`,
  `mypy>=1.11` → `>=2.3.0`, `pytest>=7.0` → `>=9.1.1`.
- These are the same three Dependabot PRs closed in v2.1.0's release cycle for
  failing the Python 3.9 CI job — each new floor version had itself already
  dropped 3.9 support. v2.1.0 dropped this package's own 3.9 support for the
  same underlying reason (3.9 reached its own EOL on 2025-10-31), which
  removed the only thing blocking these.
- No public API changed.
