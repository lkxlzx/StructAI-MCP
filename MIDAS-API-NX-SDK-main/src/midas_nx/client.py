"""Core HTTP client for the MIDAS NX Open API.

Instance-based (no global mutable class-attribute state), raises exceptions on
error responses instead of exiting the process, and exposes a free-function
``MidasAPI(method, command, body)`` wrapper for parity with the calling
convention already documented in the MIDAS-API manual repo's README and
examples/python/basic_example.py.
"""
from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Any, ClassVar, Mapping, Optional, Tuple, Union

import requests

logger = logging.getLogger("midas_nx")

_HOST = "moa-engineers.midasit.com"

#: What ``requests`` accepts for ``timeout``: one number covering both phases,
#: or a ``(connect, read)`` pair. Aliased so per-request overrides and the
#: client default stay describable by the same name.
Timeout = Union[float, Tuple[float, float]]


class Product(str, Enum):
    GEN = "gen"
    CIVIL = "civil"


def build_base_url(product: "Product | str") -> str:
    """Build the default global Base URL for a product.

    Regional variants (e.g. ``-in``/``-kr``/``-gb``/``-us``/``.cn`` hostnames,
    used by MIDASIT's official SDKs) are not documented in the MIDAS-API
    manual and are intentionally not guessed at here — pass ``base_url``
    explicitly to ``MidasClient`` if you need one. See docs/coverage.json.
    """
    product = Product(product)
    return f"https://{_HOST}:443/{product.value}"


class MidasAPIError(Exception):
    """Base class for all errors raised by this SDK.

    Subclasses may set ``HINT`` to a short, actionable suggestion; it's
    appended to the message automatically so callers see both the server's
    own error text and, where there's a common fix, what to do about it.
    """

    HINT: ClassVar[str] = ""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        method: Optional[str] = None,
        endpoint: Optional[str] = None,
        response_body: Any = None,
    ) -> None:
        if self.HINT:
            # "(Hint: ...)" rather than an em-dash separator: this message
            # is read directly by non-developers, including on a Windows
            # console using a non-Unicode codepage (e.g. cp949) that can't
            # encode an em-dash and would otherwise render it as a
            # "\uXXXX" escape in the middle of the message.
            message = f"{message} (Hint: {self.HINT})"
        super().__init__(message)
        self.status_code = status_code
        self.method = method
        self.endpoint = endpoint
        self.response_body = response_body


class MidasAuthError(MidasAPIError):
    """401 / 403 — invalid or missing MAPI-Key."""

    HINT = (
        "check your MAPI-Key. Get or verify one from the Gen NX / Civil NX "
        "application's Open API / Apps menu > API Key"
    )


class MidasNotFoundError(MidasAPIError):
    """404 — model not connected, or resource/id not found."""

    HINT = (
        "either the product isn't connected (call client.verify_connection() "
        "to check) or the id you asked for doesn't exist in the current model"
    )


class MidasRequestError(MidasAPIError):
    """Other 4xx — malformed request."""


class MidasServerError(MidasAPIError):
    """5xx — server-side failure."""


class MidasConnectionError(MidasAPIError):
    """Network failure / timeout before a response was received."""

    HINT = "check that MIDAS Gen NX / Civil NX is running with Open API connected"


class MidasResultError(MidasAPIError):
    """HTTP 200, but the body carries an ``{"error": {...}}`` object.

    Several endpoints report a refusal this way instead of with an HTTP error
    status — e.g. a story table asked for before ``ope.calculate_story()`` has
    run, or a design check whose preconditions aren't met. Treating the 2xx as
    success hands the caller an error dict that looks like a result, so the
    client raises instead. Pass ``MidasClient(raise_on_result_error=False)`` to
    get the raw body back and inspect it yourself.
    """

    HINT = (
        "the request reached the product but it refused the operation; check the "
        "model state the call needs (analysis run, story calculation, design "
        "parameters) rather than the request shape"
    )


class ProductMismatchError(MidasAPIError):
    """Raised when a resource's PRODUCTS doesn't include the client's product."""


class UnsupportedMethodError(MidasAPIError):
    """Raised when a resource doesn't support the requested HTTP method
    (e.g. calling .create() on a GET/PUT-only endpoint like MATD)."""


class DestructiveOperationError(MidasAPIError):
    """Raised when a call that would destroy model data was made without
    explicitly confirming it (e.g. ``DbResource.delete_all()`` without
    ``confirm=True``).

    Raised **before** anything is sent, so nothing has changed on the server
    when you see this. There is no undo through the API, and the products
    have no confirmation dialog on the API path, so the guard is here rather
    than in the product.
    """

    HINT = (
        "pass confirm=True if you really mean to empty the whole table, or use "
        "delete(ids) to remove specific records"
    )


_STATUS_EXCEPTIONS = {401: MidasAuthError, 403: MidasAuthError, 404: MidasNotFoundError}


def _exception_for_status(status_code: int) -> "type[MidasAPIError]":
    return _STATUS_EXCEPTIONS.get(
        status_code, MidasServerError if status_code >= 500 else MidasRequestError
    )


class MidasClient:
    """A configured connection to one MIDAS NX Open API server.

    Example::

        client = MidasClient(mapi_key="...", product=Product.CIVIL)
        client.request("POST", "/doc/NEW", {"Argument": {}})
    """

    def __init__(
        self,
        mapi_key: Optional[str] = None,
        base_url: Optional[str] = None,
        product: "Product | str" = Product.GEN,
        timeout: Timeout = 30.0,
        strict_product: bool = True,
        session: Optional[requests.Session] = None,
        raise_on_result_error: bool = True,
    ) -> None:
        # Annotated rather than inferred: this ends up in a request header, and
        # an Optional here would silently allow a None-valued "MAPI-Key".
        # The trailing `or ""` is what makes that provable — mypy widens
        # `x or os.getenv(k, "")` back to `str | None`.
        self.mapi_key: str = mapi_key or os.getenv("MIDAS_MAPI_KEY") or ""
        self.product = Product(product)
        self.base_url = (base_url or os.getenv("MIDAS_BASE_URL") or build_base_url(self.product)).rstrip("/")
        self.timeout = timeout
        self.strict_product = strict_product
        self._session = session or requests.Session()
        self.raise_on_result_error = raise_on_result_error

    def check_product(self, resource_products: frozenset, resource_name: str) -> None:
        if self.product.value not in resource_products:
            message = (
                f"{resource_name} supports {sorted(resource_products)}, "
                f"but this client is configured for product='{self.product.value}'"
            )
            if self.strict_product:
                raise ProductMismatchError(message)
            logger.warning(message)

    def request(
        self,
        method: str,
        command: str,
        body: Optional[Mapping[str, Any]] = None,
        *,
        timeout: "Timeout | None" = None,
    ) -> dict:
        """Send one request. ``timeout`` overrides the client default for this
        call only; omitting it keeps the client's own ``timeout``.

        Pass a ``(connect, read)`` tuple to bound the two phases separately —
        useful for calls that are known to hang once the product has accepted
        them (the ``*-ANAL`` design-check family), where you want to give up
        waiting quickly and read the result back with a follow-up GET instead
        of blocking on a response that may never arrive. A timeout is not a
        rollback: the product may well finish the operation after the client
        has stopped waiting.
        """
        return self._send(method, self.base_url + command, body, endpoint=command, timeout=timeout)

    def verify_connection(self, *, timeout: "Timeout | None" = None) -> dict:
        """GET {base url with the /gen or /civil product segment removed}/mapikey/verify.

        Docs: the MIDAS-API manual repo's docs/AUTHENTICATION.md, "연결 전 상태
        확인 — /mapikey/verify" — a health-check endpoint documented in the
        repo's auth guide rather than a per-chapter manual page (so it isn't
        tracked in docs/coverage.json/ROADMAP.md alongside the itemized
        endpoint surface). Distinguishes three cases: HTTP 200 with
        ``"status": "connected"``/``"keyVerified": True`` (healthy — the
        product process is alive and this MAPI-Key is valid for it); HTTP 200
        with ``"status": "disconnected"`` (product not connected — returned
        as-is, not raised, since it's a normal response shape, not an HTTP
        error); and HTTP 404 with a "client does not exist" message (the
        product process died after connecting — surfaced as
        ``MidasNotFoundError`` like any other 404). Useful as a sanity check
        right after constructing a client, or before a batch of calls that
        would otherwise each hit their own timeout if the product has
        silently died.

        ⚠️ **This is not a preflight check, and a "connected" answer does not
        mean the next call will work.** While the product is showing a modal
        dialog — a confirmation prompt, an access-denied error, a crash-
        recovery notice — the relay keeps answering ``/mapikey/verify`` with
        ``"connected"`` while every ``/db/*`` call on that same session times
        out until a human dismisses the dialog. Confirmed live. So treat a
        healthy answer here as "the key is valid and the process was alive a
        moment ago", not as clearance to run a destructive operation. There
        is no API-visible signal for a dialog-blocked session; the only
        reliable check is a cheap real call (e.g. a small ``GET``) and a
        short ``timeout``.
        """
        suffix = f"/{self.product.value}"
        root = self.base_url[: -len(suffix)] if self.base_url.endswith(suffix) else self.base_url
        return self._send(
            "GET", f"{root}/mapikey/verify", None, endpoint="/mapikey/verify", timeout=timeout
        )

    def _send(
        self,
        method: str,
        url: str,
        body: Optional[Mapping[str, Any]],
        *,
        endpoint: str,
        timeout: "Timeout | None" = None,
    ) -> dict:
        headers = {"Content-Type": "application/json", "MAPI-Key": self.mapi_key}

        try:
            response = self._session.request(
                method.upper(),
                url,
                headers=headers,
                json=body,
                timeout=self.timeout if timeout is None else timeout,
            )
        except requests.RequestException as exc:
            raise MidasConnectionError(
                f"{method.upper()} {endpoint} failed: {exc}", method=method, endpoint=endpoint
            ) from exc

        try:
            data: Any = response.json() if response.text else {}
        except ValueError as exc:
            # A proxy, captive portal or SSL-inspection appliance answering
            # instead of the product — the body isn't the documented JSON at
            # all. Keep it inside this SDK's exception hierarchy rather than
            # letting a raw JSONDecodeError escape past `except MidasAPIError`.
            snippet = " ".join(response.text.split())[:200]
            exc_cls = MidasServerError if response.ok else _exception_for_status(response.status_code)
            raise exc_cls(
                f"{method.upper()} {endpoint} -> {response.status_code}: "
                f"response body is not JSON: {snippet!r}",
                status_code=response.status_code,
                method=method,
                endpoint=endpoint,
                response_body=response.text,
            ) from exc

        if response.ok:
            # A 200 does not mean success: several endpoints report a refusal
            # with an {"error": {...}} body under a 2xx status. See
            # MidasResultError and docs/live_verification_notes.md.
            if self.raise_on_result_error and isinstance(data, dict) and data.get("error"):
                error = data["error"]
                detail = error.get("message", error) if isinstance(error, dict) else error
                raise MidasResultError(
                    f"{method.upper()} {endpoint} -> {response.status_code} "
                    f"with an error body: {detail}",
                    status_code=response.status_code,
                    method=method,
                    endpoint=endpoint,
                    response_body=data,
                )
            return data

        exc_cls = _exception_for_status(response.status_code)
        message = response.reason
        if isinstance(data, dict):
            error = data.get("error")
            error_message = error.get("message", error) if isinstance(error, dict) else error
            message = data.get("message") or error_message or message

        raise exc_cls(
            f"{method.upper()} {endpoint} -> {response.status_code}: {message}",
            status_code=response.status_code,
            method=method,
            endpoint=endpoint,
            response_body=data,
        )


_default_client: Optional[MidasClient] = None


def get_default_client() -> MidasClient:
    """Return the process-wide default client, constructing it lazily from
    MIDAS_MAPI_KEY / MIDAS_BASE_URL env vars on first use."""
    global _default_client
    if _default_client is None:
        _default_client = MidasClient()
    return _default_client


def configure(**kwargs: Any) -> MidasClient:
    """Reconfigure the process-wide default client.

    Example::

        configure(mapi_key="...", product=Product.CIVIL)
        MidasAPI("POST", "/doc/NEW", {"Argument": {}})
    """
    global _default_client
    _default_client = MidasClient(**kwargs)
    return _default_client


def MidasAPI(method: str, command: str, body: Optional[dict] = None) -> dict:
    """Free-function convenience wrapper around the default client.

    Matches the calling convention documented in the MIDAS-API manual repo's
    README.md and examples/python/basic_example.py.
    """
    return get_default_client().request(method, command, body)


def post_argument(
    command: str,
    argument,
    client: Optional[MidasClient] = None,
    *,
    timeout: "Timeout | None" = None,
) -> dict:
    """Shared POST-with-``"Argument"``-wrapper helper for the non-ID-keyed
    endpoint families (``/doc/*``, ``/ope/*``, ``/view/*``, and the two plain
    ``/post/*`` endpoints in ``post/design.py``) — as opposed to the ID-keyed
    ``"Assign"`` wrapper used by ``db/base.py``'s ``DbResource``.

    ``timeout`` overrides the client default for this call only. The
    ``*-ANAL`` design-check family has been observed hanging after the
    product accepted the request, so a short timeout plus a follow-up read of
    the matching ``*-TABLE`` is the documented way to drive those."""
    return (client or get_default_client()).request(
        "POST", command, {"Argument": argument}, timeout=timeout
    )


def get_result(
    command: str, client: Optional[MidasClient] = None, *, timeout: "Timeout | None" = None
) -> dict:
    """Shared GET helper (no request body) for the same non-ID-keyed
    endpoint families as :func:`post_argument`."""
    return (client or get_default_client()).request("GET", command, timeout=timeout)
