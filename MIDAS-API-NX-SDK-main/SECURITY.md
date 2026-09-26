# Security Policy

## Scope

This policy covers the `midas-nx` packages on PyPI and npm, and this repository
only.

`midas-nx` is an employee-led open-source project. It is **not an officially
released or supported MIDAS IT product**, and this policy does not speak for
MIDAS IT.

**Vulnerabilities in MIDAS Gen NX, MIDAS Civil NX, the MIDAS Open API service,
or MIDAS IT's licensing infrastructure are out of scope here.** Report those
through MIDAS IT's official support channels — not through this repository,
whose issue tracker is public and therefore an unsafe place to disclose a
product vulnerability.

## Supported versions

| Version | Supported |
| --- | --- |
| Latest release on PyPI and npm (they share one version number) | ✅ |
| Anything older | ❌ — upgrade first, then report if it still reproduces |

Only the latest release is patched. This is a single-maintainer project; there
are no backport branches.

## Reporting

Use GitHub's **[private vulnerability
reporting](https://github.com/Dennis5882/MIDAS-API-NX-SDK/security/advisories/new)**
(Security → Report a vulnerability). It is private to the maintainer and
doesn't require a shared email address.

> **TODO (maintainer):** private vulnerability reporting must be enabled in
> Settings → Code security for that link to work, and no alternative private
> contact is published for this project yet. Enable it, or add a contact
> address here and delete this note.

Please include: what you can do with it, how to reproduce it, affected version,
and whether it's already public.

Please do **not** open a public issue for something exploitable, and please
don't include a real MAPI-Key, model file, or account identifier in a report —
a redacted reproduction is enough.

## What to expect

Best-effort, from one maintainer, with no SLA. You will get an
acknowledgement, an assessment of whether it's actually in scope for this
package, and a fixed release if it is. Credit in the release notes if you want
it.

## Note on what this package handles

`midas-nx` sends a MAPI-Key in a request header to a MIDAS IT endpoint. It
does not store, log, or transmit that key anywhere else. Two things that are
**your** responsibility rather than this package's:

- Keep the key out of source control. Read it from the environment
  (`MIDAS_MAPI_KEY`) or a gitignored `.env`; never commit it.
- Uncaught exception text can include the endpoint and response body. Don't
  paste raw tracebacks into public issues without checking them first.
