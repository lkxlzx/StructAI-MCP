"""Mock adapter package (V2.1 §22) — the offline test double."""

from app.adapters.mock.adapter import DEFAULT_MODEL, DEFAULT_SCHEMAS, MockAdapter, MockResponse

__all__ = ["MockAdapter", "MockResponse", "DEFAULT_MODEL", "DEFAULT_SCHEMAS"]
