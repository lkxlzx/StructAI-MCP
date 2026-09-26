## Fixed

- **`MidasClient._send()` could raise a bare `AttributeError` instead of a
  `MidasAPIError` subclass.** The non-2xx error path built its message with
  `(data.get("error") or {}).get("message")`, assuming `error` is always a
  dict. A 4xx/5xx response shaped like `{"error": "some string"}` (a non-dict
  `error` value) crashed with `AttributeError: 'str' object has no attribute
  'get'` instead of raising `MidasAuthError`/`MidasRequestError`/
  `MidasServerError` as documented — breaking any `except MidasAPIError:`
  handler and discarding the real status code and response context. The
  2xx-with-error-body branch already guarded against this shape; the non-2xx
  branch now mirrors it. Added a regression test
  (`test_non_dict_error_body_on_4xx_does_not_crash`).

## Docs

- Two stale docstrings corrected, found in the same review pass:
  `db/dynamic_loads.py`'s `TimeHistoryGlobalControlPayload` still said
  "CIVIL NX only" even though the class has correctly had no product
  restriction since the 2026-07-29 live finding that THGC also works on
  Gen NX; `db/design.py`'s `RebarNameDist` still cited `/db/REBW`'s old,
  confirmed-wrong manual field names (`VERTICAL_REBAR`/`HORIZONTAL_REBAR`/
  `BE_HORIZONTAL_REBAR`) instead of the server-confirmed ones
  (`VER_BAR`/`HOR_BAR`/`BE_HOR_BAR`) the code actually uses.

## How this was found

A review pass across all of `src/midas_nx/` (41 modules, ~16,400 lines),
prompted by a week of heavy docs-only changes with no corresponding review
of the SDK itself. Everything else — `db/base.py`'s CRUD pattern, all
model/load/analysis resources, `doc.py`/`ope.py`/`view.py`, `post/*`'s
shape-based table unwrapping, and all three RC/steel/SRC design-code
chapters — came back clean, including the two areas with the highest known
prior defect risk (the `NodalMass` `rmX`/`rmY`/`rmZ` crash workaround and
`/db/REBW`'s field-name correction), both verified still correctly
implemented.
