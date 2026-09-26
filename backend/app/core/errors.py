"""Error code registry — 总纲 §4.4 (all 10 subsections).

This module is the *only* place error codes are defined. V2.1 §4 / §20 and
v1.2 §50 must reference this registry and must not add codes (总纲 §0.3, A-3).

``OK`` is not part of §4.4: it is the success code of the REST envelope defined
in 总纲 §4.3.1 (``"code": "OK"``) and is included here so that a single type
covers both branches of the envelope.
"""

from enum import Enum
from typing import Any

__all__ = [
    "ErrorCode",
    "ERROR_HTTP_STATUS",
    "LEGACY_ERROR_ALIASES",
    "LEGACY_FALLBACK_CODE",
    "normalize_legacy_code",
    "http_status_for",
    "AppError",
]


class ErrorCode(str, Enum):
    """Every error code of 总纲 §4.4, plus the §4.3.1 success code."""

    # --- envelope success code (总纲 §4.3.1, not part of §4.4) --------------
    OK = "OK"

    # --- §4.4.1 认证与授权 -------------------------------------------------
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_INVALID = "AUTH_INVALID"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    CONFIRMATION_INVALID = "CONFIRMATION_INVALID"

    # --- §4.4.2 请求与资源 -------------------------------------------------
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"

    # --- §4.4.3 MCP 层 -----------------------------------------------------
    MCP_SERVER_ERROR = "MCP_SERVER_ERROR"
    MCP_CLIENT_ERROR = "MCP_CLIENT_ERROR"

    # --- §4.4.4 Adapter 与能力 ---------------------------------------------
    ADAPTER_NOT_FOUND = "ADAPTER_NOT_FOUND"
    ADAPTER_UNAVAILABLE = "ADAPTER_UNAVAILABLE"
    CLIENT_NOT_CONNECTED = "CLIENT_NOT_CONNECTED"
    CAPABILITY_NOT_SUPPORTED = "CAPABILITY_NOT_SUPPORTED"
    INTERFACE_NOT_FOUND = "INTERFACE_NOT_FOUND"

    # --- §4.4.5 MIDAS 上游 -------------------------------------------------
    MIDAS_CONNECTION_FAILED = "MIDAS_CONNECTION_FAILED"
    MIDAS_AUTH_FAILED = "MIDAS_AUTH_FAILED"
    MIDAS_API_ERROR = "MIDAS_API_ERROR"
    MIDAS_CALCULATION_ERROR = "MIDAS_CALCULATION_ERROR"

    # --- §4.4.6 任务 -------------------------------------------------------
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    TASK_ALREADY_RUNNING = "TASK_ALREADY_RUNNING"
    TASK_CANCEL_FAILED = "TASK_CANCEL_FAILED"
    TASK_TIMEOUT = "TASK_TIMEOUT"

    # --- §4.4.7 AI 工程助手 ------------------------------------------------
    INTENT_UNRESOLVED = "INTENT_UNRESOLVED"
    PARAMETER_INCOMPLETE = "PARAMETER_INCOMPLETE"
    PARAMETER_INVALID = "PARAMETER_INVALID"
    PLAN_NOT_CONFIRMED = "PLAN_NOT_CONFIRMED"
    PLAN_STEP_FAILED = "PLAN_STEP_FAILED"
    DRAWING_UNSUPPORTED = "DRAWING_UNSUPPORTED"
    RECOGNITION_LOW_CONFIDENCE = "RECOGNITION_LOW_CONFIDENCE"
    CODE_STANDARD_MISSING = "CODE_STANDARD_MISSING"

    # --- §4.4.8 AI 模型 ----------------------------------------------------
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    MODEL_TIMEOUT = "MODEL_TIMEOUT"
    MODEL_API_ERROR = "MODEL_API_ERROR"

    # --- §4.4.9 数据与系统 -------------------------------------------------
    DATABASE_ERROR = "DATABASE_ERROR"
    BACKUP_FAILED = "BACKUP_FAILED"
    RESTORE_FAILED = "RESTORE_FAILED"
    IMPORT_VALIDATION_FAILED = "IMPORT_VALIDATION_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


#: 总纲 §4.4.1 – §4.4.9: HTTP status for every registry entry.
ERROR_HTTP_STATUS: dict[ErrorCode, int] = {
    # §4.4.1
    ErrorCode.AUTH_REQUIRED: 401,
    ErrorCode.AUTH_INVALID: 401,
    ErrorCode.AUTH_EXPIRED: 401,
    ErrorCode.PERMISSION_DENIED: 403,
    ErrorCode.CONFIRMATION_INVALID: 403,
    # §4.4.2
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.RESOURCE_NOT_FOUND: 404,
    ErrorCode.RESOURCE_CONFLICT: 409,
    ErrorCode.RATE_LIMITED: 429,
    # §4.4.3
    ErrorCode.MCP_SERVER_ERROR: 500,
    ErrorCode.MCP_CLIENT_ERROR: 502,
    # §4.4.4
    ErrorCode.ADAPTER_NOT_FOUND: 404,
    ErrorCode.ADAPTER_UNAVAILABLE: 503,
    ErrorCode.CLIENT_NOT_CONNECTED: 409,
    ErrorCode.CAPABILITY_NOT_SUPPORTED: 422,
    ErrorCode.INTERFACE_NOT_FOUND: 404,
    # §4.4.5
    ErrorCode.MIDAS_CONNECTION_FAILED: 502,
    ErrorCode.MIDAS_AUTH_FAILED: 502,
    ErrorCode.MIDAS_API_ERROR: 502,
    ErrorCode.MIDAS_CALCULATION_ERROR: 502,
    # §4.4.6
    ErrorCode.TASK_NOT_FOUND: 404,
    ErrorCode.TASK_ALREADY_RUNNING: 409,
    ErrorCode.TASK_CANCEL_FAILED: 409,
    ErrorCode.TASK_TIMEOUT: 504,
    # §4.4.7
    ErrorCode.INTENT_UNRESOLVED: 422,
    ErrorCode.PARAMETER_INCOMPLETE: 422,
    ErrorCode.PARAMETER_INVALID: 422,
    ErrorCode.PLAN_NOT_CONFIRMED: 409,
    ErrorCode.PLAN_STEP_FAILED: 500,
    ErrorCode.DRAWING_UNSUPPORTED: 422,
    ErrorCode.RECOGNITION_LOW_CONFIDENCE: 422,
    ErrorCode.CODE_STANDARD_MISSING: 422,
    # §4.4.8
    ErrorCode.MODEL_UNAVAILABLE: 503,
    ErrorCode.MODEL_TIMEOUT: 504,
    ErrorCode.MODEL_API_ERROR: 502,
    # §4.4.9
    ErrorCode.DATABASE_ERROR: 500,
    ErrorCode.BACKUP_FAILED: 500,
    ErrorCode.RESTORE_FAILED: 500,
    ErrorCode.IMPORT_VALIDATION_FAILED: 422,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.NOT_IMPLEMENTED: 501,
    # 总纲 §4.3.1 success envelope
    ErrorCode.OK: 200,
}


#: 总纲 §4.4.10 — legacy name -> canonical code(s).
#: ``TIMEOUT`` is deliberately ambiguous in the source document; the caller must
#: pick between ``TASK_TIMEOUT`` and ``MODEL_TIMEOUT`` by context.
LEGACY_ERROR_ALIASES: dict[str, tuple[ErrorCode, ...]] = {
    "AUTH_FAILED": (ErrorCode.AUTH_INVALID,),
    "VALIDATION_FAILED": (ErrorCode.VALIDATION_ERROR,),
    "TIMEOUT": (ErrorCode.TASK_TIMEOUT, ErrorCode.MODEL_TIMEOUT),
    "INVALID_REQUEST": (ErrorCode.VALIDATION_ERROR,),
}

#: 总纲 §4.4.10 last row: anything not listed above normalizes to INTERNAL_ERROR.
LEGACY_FALLBACK_CODE: ErrorCode = ErrorCode.INTERNAL_ERROR


def normalize_legacy_code(code: str, *, timeout_is_model: bool = False) -> ErrorCode:
    """Map a pre-v1.0 error code string onto the §4.4 registry.

    ``AUTH_FAILED`` / ``VALIDATION_FAILED`` / ``INVALID_REQUEST`` map directly.
    ``TIMEOUT`` maps to ``TASK_TIMEOUT`` unless ``timeout_is_model=True``, which
    selects ``MODEL_TIMEOUT``. Unknown names fall back to ``INTERNAL_ERROR``.
    """
    if code in LEGACY_ERROR_ALIASES:
        candidates = LEGACY_ERROR_ALIASES[code]
        if len(candidates) == 1:
            return candidates[0]
        if code == "TIMEOUT":
            return ErrorCode.MODEL_TIMEOUT if timeout_is_model else ErrorCode.TASK_TIMEOUT
        return candidates[0]
    try:
        return ErrorCode(code)
    except ValueError:
        return LEGACY_FALLBACK_CODE


def http_status_for(code: ErrorCode | str) -> int:
    """HTTP status for a registry code; unknown codes are treated as 500."""
    try:
        return ERROR_HTTP_STATUS[ErrorCode(code)]
    except (ValueError, KeyError):
        return 500


class AppError(Exception):
    """Domain error carrying a registry ``code``, a message and optional details.

    Serialization belongs to the REST layer (总纲 §4.3.1 envelope); this class
    only guarantees that ``code`` is always a registry member.
    """

    def __init__(
        self,
        code: ErrorCode | str,
        message: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        resolved = code if isinstance(code, ErrorCode) else normalize_legacy_code(str(code))
        self.code: ErrorCode = resolved
        self.message: str = message or resolved.value
        self.details: dict[str, Any] = dict(details or {})
        super().__init__(self.message)

    @property
    def http_status(self) -> int:
        """HTTP status declared for this code in 总纲 §4.4."""
        return http_status_for(self.code)

    def to_dict(self) -> dict[str, Any]:
        """Return the §4.3.1 failure payload fragment (without envelope fields)."""
        return {
            "success": False,
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"AppError(code={self.code.value!r}, message={self.message!r})"
