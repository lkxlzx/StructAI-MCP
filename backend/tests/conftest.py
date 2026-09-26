"""Make ``app.*`` importable no matter where pytest is invoked from, and make
password hashing cheap for the test session.

``backend`` is not a package (no ``__init__.py``) and the tests live one level
below the backend root, so pytest's default ``prepend`` import mode would only
put ``backend/tests`` on ``sys.path``.
"""

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ---------------------------------------------------------------------------
# Password hashing: cheap in tests, correct in production
# ---------------------------------------------------------------------------
# Captured at import time — i.e. before the autouse fixture below lowers it — so
# a test can still assert what production actually ships.
from app.core import crypto as _crypto  # noqa: E402  (needs sys.path set above)

PRODUCTION_PBKDF2_ITERATIONS: int = _crypto._PBKDF2_ITERATIONS

#: The iteration count the test session runs with.  Production keeps
#: ``_PBKDF2_ITERATIONS`` (260 000, ≈200 ms per hash) — that cost is the *point*
#: of a password KDF and must not be weakened for convenience.
#:
#: At 200 ms per call the auth suite spent ~100 s of its 128 s inside PBKDF2,
#: which makes the feedback loop useless.  The KDF's cost is a security
#: parameter, not behaviour under test, so tests run with a trivial count while
#: ``test_production_password_hash_cost_is_not_weakened`` pins the real value.
TEST_PBKDF2_ITERATIONS = 1


@pytest.fixture(autouse=True, scope="session")
def _cheap_password_hashing():
    """Lower PBKDF2's cost for the whole test session (see the note above)."""
    original = _crypto._PBKDF2_ITERATIONS
    _crypto._PBKDF2_ITERATIONS = TEST_PBKDF2_ITERATIONS
    try:
        yield
    finally:
        _crypto._PBKDF2_ITERATIONS = original


@pytest.fixture(scope="session")
def production_pbkdf2_iterations() -> int:
    """The iteration count production ships with, captured before the override."""
    return PRODUCTION_PBKDF2_ITERATIONS


# ---------------------------------------------------------------------------
# Database schema: build it once, copy it per test
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def schema_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the full 49-table schema **once** for the whole session.

    ``Base.metadata.create_all()`` costs roughly two seconds (49 tables plus
    their indexes, foreign keys and CHECK constraints).  Two suites used to pay
    that per test — 62 auth tests spent ~100 s of the run in setup, more than
    everything else combined.  Building the schema once and copying the file per
    test costs about a millisecond and keeps the per-test isolation that made a
    real database file worth having in the first place.
    """
    from sqlalchemy import create_engine

    from app.db.base import Base
    import app.models  # noqa: F401 — populate Base.metadata

    path = tmp_path_factory.mktemp("schema") / "template.db"
    engine = create_engine(f"sqlite:///{path}", future=True)
    try:
        Base.metadata.create_all(bind=engine)
    finally:
        engine.dispose()
    return path
