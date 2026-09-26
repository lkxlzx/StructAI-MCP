# Client and exceptions

The connection, the free-function wrapper, and the exception hierarchy.

## MidasClient

::: midas_nx.client.MidasClient

## Product

::: midas_nx.client.Product

## Module-level helpers

::: midas_nx.client.configure

::: midas_nx.client.get_default_client

::: midas_nx.client.MidasAPI

::: midas_nx.client.build_base_url

## Exceptions

All of these descend from `MidasAPIError`, so a single `except MidasAPIError`
catches everything this SDK raises — including the client-side guards, which
raise before any request is sent.

::: midas_nx.client.MidasAPIError

::: midas_nx.client.MidasAuthError

::: midas_nx.client.MidasNotFoundError

::: midas_nx.client.MidasRequestError

::: midas_nx.client.MidasServerError

::: midas_nx.client.MidasConnectionError

::: midas_nx.client.MidasResultError

::: midas_nx.client.ProductMismatchError

::: midas_nx.client.UnsupportedMethodError

::: midas_nx.client.DestructiveOperationError
