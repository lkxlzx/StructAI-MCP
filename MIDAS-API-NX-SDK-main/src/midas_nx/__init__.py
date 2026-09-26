"""midas_nx — unified Python SDK for the MIDAS NX Open API.

Covers both MIDAS Civil NX and MIDAS Gen NX (a "product" parameter selects
which), typed against the schema documented at
https://github.com/Dennis5882/MIDAS-API/tree/main/docs/manual

See ROADMAP.md for endpoint coverage.
"""
from .client import (
    DestructiveOperationError,
    MidasAPI,
    MidasAPIError,
    MidasAuthError,
    MidasClient,
    MidasConnectionError,
    MidasNotFoundError,
    MidasRequestError,
    MidasResultError,
    MidasServerError,
    Product,
    ProductMismatchError,
    UnsupportedMethodError,
    configure,
    get_default_client,
)

#: Single source of truth for the package version — pyproject.toml declares
#: ``dynamic = ["version"]`` and hatchling reads this line, so bumping it here
#: bumps the distribution too. Don't add a second copy anywhere.
__version__ = "2.9.3"

__all__ = [
    "MidasAPI",
    "MidasClient",
    "Product",
    "configure",
    "get_default_client",
    "MidasAPIError",
    "MidasAuthError",
    "MidasNotFoundError",
    "MidasRequestError",
    "MidasResultError",
    "MidasServerError",
    "MidasConnectionError",
    "ProductMismatchError",
    "UnsupportedMethodError",
    "DestructiveOperationError",
    "__version__",
]
