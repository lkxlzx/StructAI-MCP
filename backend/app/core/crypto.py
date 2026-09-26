"""Encryption and secret hashing — 总纲 §4.7.

Encrypted column list (closed set, 总纲 §4.7.1)::

    models.api_key_encrypted
    midas_clients.api_key_encrypted
    midas_clients.access_token_encrypted
    mcp_client_credentials.secret_hash        (one-way hash)
    system_configs.config_value               (when is_secret = 1)
    assistant_plans.confirmation_token_hash   (one-way hash)

Algorithm: AES-256-GCM. Master key: environment variable ``STRUCTAI_MASTER_KEY``.

``cryptography`` is imported lazily inside the functions so the rest of the
package (models, constants, Alembic env) imports without the dependency
installed; a missing package raises an actionable ``ImportError``.

Key derivation: the 32-byte AES key is ``SHA-256("structai-master-key-v1" ||
STRUCTAI_MASTER_KEY)``, so operators may supply any passphrase length while the
cipher always receives a full 256-bit key.
"""

import base64
import hashlib
import hmac
import os
import secrets
from typing import Any

__all__ = [
    "MASTER_KEY_ENV",
    "MASKED_VALUE",
    "encrypt",
    "decrypt",
    "hash_secret",
    "verify_secret",
    "mask_secret",
    "is_encryption_configured",
]

#: Environment variable holding the AES-256-GCM master key (总纲 §4.7.1).
MASTER_KEY_ENV = "STRUCTAI_MASTER_KEY"

#: Value returned by :func:`mask_secret` for a configured secret (总纲 §4.7.2).
MASKED_VALUE = "********"

_NONCE_BYTES = 12  # AES-GCM standard nonce length
_TAG_BYTES = 16  # AES-GCM authentication tag length
_KEY_DERIVATION_LABEL = b"structai-master-key-v1"

_PBKDF2_ALGORITHM = "pbkdf2_sha256"
_PBKDF2_ITERATIONS = 260_000
_PBKDF2_SALT_BYTES = 16


# ---------------------------------------------------------------------------
# lazy dependency loading
# ---------------------------------------------------------------------------
def _aesgcm_class() -> Any:
    """Return ``cryptography``'s AESGCM class, or raise a helpful ImportError."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise ImportError(
            "StructAI field encryption requires the 'cryptography' package "
            "(总纲 §4.7.1 mandates AES-256-GCM). Install it with:\n"
            "    pip install 'cryptography>=42'"
        ) from exc
    return AESGCM


# ---------------------------------------------------------------------------
# master key
# ---------------------------------------------------------------------------
def _master_key() -> bytes:
    """Derive the 32-byte AES key from ``STRUCTAI_MASTER_KEY``.

    :raises RuntimeError: the variable is unset or blank.
    """
    raw = os.environ.get(MASTER_KEY_ENV, "")
    if not raw or not raw.strip():
        raise RuntimeError(
            f"{MASTER_KEY_ENV} is not set. 总纲 §4.7.1 requires a master key before "
            "any encrypted column can be read or written. Export it first, e.g.\n"
            f'    set {MASTER_KEY_ENV}=<a long random passphrase>   (Windows)\n'
            f"    export {MASTER_KEY_ENV}=<a long random passphrase>  (POSIX)"
        )
    return hashlib.sha256(_KEY_DERIVATION_LABEL + raw.encode("utf-8")).digest()


def is_encryption_configured() -> bool:
    """True when ``STRUCTAI_MASTER_KEY`` is present (does not touch the DB)."""
    return bool(os.environ.get(MASTER_KEY_ENV, "").strip())


# ---------------------------------------------------------------------------
# AES-256-GCM
# ---------------------------------------------------------------------------
def encrypt(plaintext: str) -> str:
    """Encrypt ``plaintext`` and return ``base64(nonce || ciphertext || tag)``.

    A fresh 96-bit nonce is drawn per call, so encrypting the same value twice
    yields different tokens (no deterministic ciphertext leakage).
    """
    if not isinstance(plaintext, str):
        raise TypeError("plaintext must be str")
    aesgcm = _aesgcm_class()(_master_key())
    nonce = os.urandom(_NONCE_BYTES)
    sealed = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + sealed).decode("ascii")


def decrypt(token: str) -> str:
    """Reverse :func:`encrypt`.

    :raises ValueError: malformed token, wrong master key, or failed authentication.
    """
    if not isinstance(token, str):
        raise TypeError("token must be str")
    try:
        blob = base64.b64decode(token, validate=True)
    except Exception as exc:
        raise ValueError("ciphertext is not valid base64") from exc
    if len(blob) < _NONCE_BYTES + _TAG_BYTES:
        raise ValueError("ciphertext is too short to contain nonce + tag")
    aesgcm = _aesgcm_class()(_master_key())
    nonce, sealed = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
    try:
        return aesgcm.decrypt(nonce, sealed, None).decode("utf-8")
    except Exception as exc:
        raise ValueError(
            "decryption failed: wrong STRUCTAI_MASTER_KEY or tampered ciphertext"
        ) from exc


# ---------------------------------------------------------------------------
# one-way secret hashing (mcp_client_credentials.secret_hash,
# assistant_plans.confirmation_token_hash)
# ---------------------------------------------------------------------------
def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def hash_secret(secret: str) -> str:
    """Hash a secret with PBKDF2-HMAC-SHA256.

    Format: ``pbkdf2_sha256$<iterations>$<salt_b64>$<digest_b64>``.
    PBKDF2 is used as the primary scheme because it needs only the standard
    library; :func:`verify_secret` additionally accepts ``$2b$`` bcrypt hashes
    produced by ``passlib[bcrypt]`` so either scheme may be adopted later.
    """
    if not isinstance(secret, str):
        raise TypeError("secret must be str")
    salt = secrets.token_bytes(_PBKDF2_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", secret.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return f"{_PBKDF2_ALGORITHM}${_PBKDF2_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def verify_secret(secret: str, hashed: str | None) -> bool:
    """Constant-time verification of ``secret`` against ``hashed``.

    Supports the PBKDF2 format written by :func:`hash_secret` and, when
    ``passlib``/``bcrypt`` is installed, ``$2a$`` / ``$2b$`` / ``$2y$`` hashes.
    """
    if not secret or not hashed or not isinstance(hashed, str):
        return False

    if hashed.startswith(_PBKDF2_ALGORITHM + "$"):
        parts = hashed.split("$")
        if len(parts) != 4:
            return False
        try:
            iterations = int(parts[1])
            salt = _b64decode(parts[2])
            expected = _b64decode(parts[3])
        except Exception:
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", secret.encode("utf-8"), salt, iterations
        )
        return hmac.compare_digest(candidate, expected)

    if hashed.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            from passlib.hash import bcrypt as _bcrypt
        except ImportError:  # pragma: no cover - optional dependency
            return False
        try:
            return bool(_bcrypt.verify(secret, hashed))
        except Exception:
            return False

    return False


# ---------------------------------------------------------------------------
# 总纲 §4.7.2 echo shape
# ---------------------------------------------------------------------------
def mask_secret(value: str | None) -> dict[str, Any]:
    """Build the 总纲 §4.7.2 echo fragment for a sensitive column.

    Returns the **bare suffix form** — ``{"configured": bool, "masked": "********"}``.
    The caller prefixes the keys with the field name, e.g.::

        {"api_key_" + k: v for k, v in mask_secret(row.api_key_encrypted).items()}
        # -> {"api_key_configured": True, "api_key_masked": "********"}

    Prefixes in use (总纲 §4.7.2): ``api_key_`` / ``access_token_`` / ``secret_``.
    Plaintext is never returned.
    """
    return {"configured": bool(value), "masked": MASKED_VALUE}
