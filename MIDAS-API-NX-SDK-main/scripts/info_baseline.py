"""Capture ``GET /info{endpoint}`` for every endpoint, and diff it.

``/info`` is the server's own JSON Schema for an endpoint. It is the only
permitted contract source that is the product rather than a document, and
``contracts/README.md`` treats it as such. This script keeps a committed
baseline of what the product declared, so two questions can be answered without
guessing:

  * **Did a product patch change the API surface?** ``--diff`` compares a fresh
    capture against ``schema/info-baseline.json`` and prints every property
    added, removed or retyped. The 2026-09-02 patch was checked this way
    against 26 endpoints and changed none of them; the baseline now covers
    every endpoint that answers, so the next patch gets a real comparison.
  * **Does a contract record what the product declares?** ``--against-contracts``
    is offline and sweeps both directions - properties ``/info`` declares that no
    contract has, and names a contract publishes that ``/info`` declares nowhere.
    The forward pass found MD-34 (`/db/REBR`'s whole item shape), MD-35 (four
    fields on all six `/db/LCOM-*`) and MD-36. The reverse pass is where a wrong
    *name* shows up instead of a missing one, which the forward pass cannot see:
    it found MD-37 (`/db/POGD-M1`'s `UPLIFT` for `UPLIFTING`) and MD-38
    (`/db/STRPSSM`'s `PY` for `Y`). Read the reverse list weakly - the printed
    preamble says why, and `/db/STBK` is the counter-example that sets the bar.

``--capture`` is the only mode that talks to a product, and it issues **GET
only**, so it is safe against an open model - the same guarantee
``scripts/live_readonly_sweep.py`` gives. It records schemas and error strings
and nothing else: a GET response body is the author's model contents and never
belongs in this repository, and ``--capture`` has no code path that would store
one.

``/info`` is served for ``/db/*`` only. Every ``/DESIGN/*`` pair 404s - an API
fact, not a URL bug - and so do the Civil Hyper-S trio ``/db/IEHG-GL-M1``,
``/db/IEHG-PSS-M1`` and ``/db/IEHG-TRUSS-M1``, which is why those three cannot
be contracted at all.

Usage::

    python scripts/info_baseline.py --capture --out fresh.json
    python scripts/info_baseline.py --diff fresh.json
    python scripts/info_baseline.py --against-contracts
"""
from __future__ import annotations

import argparse
import io
import json
import pathlib
import sys
from typing import Any, Iterable, TypedDict

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE = ROOT / "schema" / "info-baseline.json"
CONTRACTS = ROOT / "contracts" / "endpoints"

# These are ceilings, not exact totals.  A count going down means a contract
# learned more of the product schema and is the outcome this check exists to
# encourage.  A new endpoint or a larger per-endpoint count is silent drift.
# Keeping the expectation per endpoint prevents one repaired contract from
# hiding a newly missing property in another.
class _AgainstContractsExpectation(TypedDict):
    contractsComparedAtLeast: int
    unmergedTablesSkippedAtMost: int
    infoOnlyWaiversAtMost: int
    unrecordedInfoPropertiesAtMost: dict[str, int]
    contractOnlyNamesAtMost: dict[str, int]


class _DivergenceExpectation(TypedDict):
    endpointsAnsweringBothAtLeast: int
    divergentSchemasAtMost: int
    absentFieldsAtMost: dict[str, int]


EXPECTED_AGAINST_CONTRACTS: _AgainstContractsExpectation = {
    "contractsComparedAtLeast": 206,
    "unmergedTablesSkippedAtMost": 16,
    "infoOnlyWaiversAtMost": 1,
    "unrecordedInfoPropertiesAtMost": {
        "/db/SECT": 995,
        "/db/MATD": 172,
        "/db/NLLP": 66,
        "/db/TDMT": 60,
        "/db/SWIND": 40,
        "/db/SSEIS": 34,
        # Closing THIS-M1's final unmerged manual table makes the standing
        # comparison visible for the first time. These 20 /info properties
        # have no matching row in the vendored manual; the ceiling records the
        # observed gap without guessing that they are request fields.
        "/db/THIS-M1": 20,
        # /db/THIK is compared once its Stiffened DB table is merged. The manual
        # documents the Value type and one of the four Stiffened sub-types (DB);
        # /info also carries the others' objects (VALUE, WALL, the YZ section).
        # Recorded as the observed gap, not added as fields no table describes.
        "/db/THIK": 13,
        # /db/EPMT is compared once its model tables are merged. /info declares
        # a seventh model object, MICROPL (MU, PARAM_C, PARAM_K), on both
        # products; the section's MODEL_TYPE row names six models and no table
        # describes this one, so it is recorded here rather than transcribed.
        "/db/EPMT": 4,
        # /db/SPLC is compared once its damping and GEN NX-only tables are
        # merged. CQCRATIO and iANGLETYPE (Civil NX) and bAUTO and iAUTOTYPE
        # (Gen NX) are in no table; a GET after a POST without them returns
        # the first three with server-supplied values.
        "/db/SPLC": 4,
        # /db/SPFC is compared once its design-code tables are merged. The
        # section tables ten of its SPEC_CODE values and lists the rest (IBC,
        # UBC, the other Chinese, Taiwanese and "Other Countries" codes) only
        # by name; /info carries their STR/OPT/VAL members and a VA2 object.
        "/db/SPFC": 72,
        # /db/THIS is compared once its mode tables are merged. COMMON.aGILC is in
        # /info on both products and in no table or example of the section.
        "/db/THIS": 1,
        # /db/MVHL is compared once its country tables are merged. The chapter
        # tables five countries' objects and names VEH_BS, VEH_EUROCODE, VEH_RU
        # and VEH_IN without a table; /info carries VEH_BS, VEH_FR and VEH_IN
        # and further VEH_DEFAULT and VEH_EUROCODE members that no row states.
        "/db/MVHL": 71,
        # /db/MVLD is compared once its national DEFAULT tables are merged.
        # AUTO_OPTIMIZE.NUM_LOADED_LANES is in /info on both products and in no
        # row or example of this section; other country sections of the chapter
        # use the name, and it is not borrowed from them.
        "/db/MVLD": 1,
    },
    "contractOnlyNamesAtMost": {
        "/db/POGD-M1": 2,
        "/db/LLANop": 1,
        "/db/SMLC": 1,
        "/db/STBK": 1,
        # OPT_UPDATE_ALL_H: the chapter itself says it is in the section's JSON
        # Schema and in neither its table nor its example. /info does not declare it
        # either. Counted once /db/CSCS stopped being skipped for unmergedTables.
        "/db/CSCS": 1,
        # W_CON: the Wall table documents it and the Wall Request Body sends it;
        # /info declares it on neither product, and Gen NX accepts a wall without
        # it and never returns it even when sent (2026-09-22). Kept as documented.
        "/db/ELEM": 1,
    },
}

# Product-specific field tags are complete today.  Unlike the standing sweep
# above, `untagged` therefore has no tolerated baseline: one such field is one
# false cross-product claim.  Missing contract fields remain a per-endpoint
# ceiling because /db/SPLC's contract leaves out four product-only /info
# properties no manual table describes (CQCRATIO and iANGLETYPE on Civil NX,
# bAUTO and iAUTOTYPE on Gen NX); it was 15 while its GEN NX-only tables
# were still unmerged.
EXPECTED_DIVERGENCE: _DivergenceExpectation = {
    "endpointsAnsweringBothAtLeast": 177,
    "divergentSchemasAtMost": 10,
    "absentFieldsAtMost": {"/db/SPLC": 4},
}


# --- reading a capture ------------------------------------------------------


def _load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _schemas(capture: dict[str, Any]) -> dict[tuple[str, str], dict]:
    """(endpoint, product) -> schema, for every pair that answered."""
    out: dict[tuple[str, str], dict] = {}
    for endpoint, per_product in capture["endpoints"].items():
        for product, payload in per_product.items():
            if isinstance(payload, dict) and payload.get("schema"):
                out[(endpoint, product)] = payload["schema"]
    return out


def _paths(schema: dict, *, with_types: bool = False) -> dict[str, str]:
    """Every property path a schema declares, dotted, array steps elided.

    An array step is elided on purpose: ``ITEMS[].NAME`` and ``ITEMS.NAME``
    describe the same wire name, and the contracts write the second.
    """
    out: dict[str, str] = {}

    def walk(node: Any, prefix: str) -> None:
        if not isinstance(node, dict):
            return
        properties = node.get("properties")
        if isinstance(properties, dict):
            for name, sub in properties.items():
                path = f"{prefix}.{name}" if prefix else name
                out[path] = (sub or {}).get("type", "unstated") if with_types else ""
                walk(sub, path)
        items = node.get("items")
        if isinstance(items, dict):
            walk(items, prefix)

    root = schema.get("Argument") if isinstance(schema.get("Argument"), dict) else schema
    walk(root, "")
    return out


# --- reading the contracts --------------------------------------------------


def _contract_documents() -> dict[str, dict]:
    import yaml  # noqa: PLC0415

    found: dict[str, dict] = {}
    for path in sorted(CONTRACTS.glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(document, dict) and document.get("endpoint"):
            found[document["endpoint"]] = document
    return found


def _contract_leaves(contract: dict) -> set[str]:
    """Every wire name this contract names anywhere, variants included.

    The reverse sweep compares against this rather than against paths. A
    contract and /info disagree about nesting often enough that a path
    mismatch is not evidence of anything; a wire name /info never mentions
    at any depth is. /db/POGD-M1 is the case that made this worth having -
    the contract said `UPLIFT` where the server says `UPLIFTING`, and a
    one-directional sweep reported the second as missing while saying
    nothing at all about the first.
    """
    out: set[str] = set()

    def walk(fields: Iterable[dict] | None) -> None:
        for field in fields or []:
            out.add(field["key"])
            walk(field.get("properties"))

    walk(contract.get("fields"))
    for variant in contract.get("variants") or []:
        walk(variant.get("fields"))
    # The envelope is documentation of the wrapper, not of the record.
    return out - {"Assign", "Argument"}


def _info_only(contract: dict) -> set[str]:
    """Paths this contract says the server declares but no caller should send."""
    return {entry["path"] for entry in contract.get("infoOnly") or []}


def _contract_paths(contract: dict) -> set[str]:
    out: set[str] = set()

    def walk(fields: Iterable[dict] | None, prefix: str) -> None:
        for field in fields or []:
            path = f"{prefix}.{field['key']}" if prefix else field["key"]
            out.add(path)
            walk(field.get("properties"), path)

    fields = contract.get("fields") or []
    walk(fields, "")
    # A variant's fields are siblings of the field it gates on. Without a
    # declared attach point, offer them at the root and under every root field,
    # so a variant member is not reported as missing.
    for variant in contract.get("variants") or []:
        walk(variant.get("fields"), "")
        for field in fields:
            walk(variant.get("fields"), field["key"])

    # The request envelope is documentation of the wrapper, not of the record.
    for path in list(out):
        for envelope in ("Assign.", "Argument."):
            if path.startswith(envelope):
                out.add(path[len(envelope):])
    return out


# --- the three modes --------------------------------------------------------


def diff(fresh_path: pathlib.Path) -> int:
    baseline = _schemas(_load(BASELINE))
    fresh = _schemas(_load(fresh_path))

    gone = sorted(set(baseline) - set(fresh))
    new = sorted(set(fresh) - set(baseline))
    changed: list[tuple[tuple[str, str], list[str]]] = []

    for key in sorted(set(baseline) & set(fresh)):
        before = _paths(baseline[key], with_types=True)
        after = _paths(fresh[key], with_types=True)
        notes = [f"+ {p} ({after[p]})" for p in sorted(set(after) - set(before))]
        notes += [f"- {p} ({before[p]})" for p in sorted(set(before) - set(after))]
        notes += [
            f"~ {p}: {before[p]} -> {after[p]}"
            for p in sorted(set(before) & set(after))
            if before[p] != after[p]
        ]
        if notes:
            changed.append((key, notes))

    print(f"baseline: {BASELINE.name}, captured {_load(BASELINE)['capturedAt']}")
    print(f"fresh:    {fresh_path.name}, captured {_load(fresh_path)['capturedAt']}")
    print(f"pairs compared: {len(set(baseline) & set(fresh))}")
    print()
    if not (gone or new or changed):
        print("No difference. Every endpoint declares exactly the schema it did before.")
        return 0
    for endpoint, product in new:
        print(f"NEW      {endpoint} ({product}) now answers /info")
    for endpoint, product in gone:
        print(f"GONE     {endpoint} ({product}) no longer answers /info")
    for (endpoint, product), notes in changed:
        print(f"CHANGED  {endpoint} ({product})")
        for note in notes:
            print(f"           {note}")
    return 1


def _check_against_contracts(
    *,
    compared: int,
    skipped: int,
    waived: int,
    unrecorded: dict[str, int],
    contract_only: dict[str, int],
) -> int:
    """Fail only when the established sweep gets less complete or drifts up."""
    errors: list[str] = []
    minimum = EXPECTED_AGAINST_CONTRACTS["contractsComparedAtLeast"]
    if compared < minimum:
        errors.append(f"contracts compared fell from {minimum} to {compared}")

    for label, found, ceiling in (
        (
            "unmergedTables skips",
            skipped,
            EXPECTED_AGAINST_CONTRACTS["unmergedTablesSkippedAtMost"],
        ),
        (
            "infoOnly waivers",
            waived,
            EXPECTED_AGAINST_CONTRACTS["infoOnlyWaiversAtMost"],
        ),
    ):
        if found > ceiling:
            errors.append(f"{label} grew from {ceiling} to {found}")

    for label, found, expected in (
        (
            "unrecorded /info properties",
            unrecorded,
            EXPECTED_AGAINST_CONTRACTS["unrecordedInfoPropertiesAtMost"],
        ),
        (
            "contract-only names",
            contract_only,
            EXPECTED_AGAINST_CONTRACTS["contractOnlyNamesAtMost"],
        ),
    ):
        for endpoint in sorted(set(found) | set(expected)):
            actual_count = found.get(endpoint, 0)
            ceiling = expected.get(endpoint, 0)
            if actual_count > ceiling:
                errors.append(
                    f"{label} for {endpoint} grew from {ceiling} to {actual_count}"
                )

    if not errors:
        print("\nOK - /info-to-contract differences did not grow.")
        return 0

    print("\n/info-to-contract standing check failed:", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    print(
        "Counts may shrink without updating the expectation. Growth must be "
        "reviewed and recorded in EXPECTED_AGAINST_CONTRACTS with the change "
        "that explains it.",
        file=sys.stderr,
    )
    return 1


def against_contracts(*, check: bool = False) -> int:
    capture = _load(BASELINE)
    contracts = _contract_documents()

    declared: dict[str, set[str]] = {}
    for (endpoint, _product), schema in _schemas(capture).items():
        declared.setdefault(endpoint, set()).update(_paths(schema))

    rows: list[tuple[int, str, list[str]]] = []
    phantom: list[tuple[str, list[str]]] = []
    skipped: list[str] = []
    waived = 0
    compared = 0
    for endpoint, paths in sorted(declared.items()):
        contract = contracts.get(endpoint)
        if contract is None:
            continue
        if (contract.get("extraction") or {}).get("unmergedTables"):
            skipped.append(endpoint)
            continue
        compared += 1
        known = _contract_paths(contract)
        leaves = {p.rsplit(".", 1)[-1] for p in known}
        declines = _info_only(contract)
        waived += len(declines)
        # Generous on purpose: a property counts as recorded if its full path is
        # known *or* its own name appears anywhere in the contract. /info and
        # the manual disagree about nesting often enough that a path mismatch
        # alone is not evidence of a missing field.
        missing = sorted(
            p for p in paths
            if p not in known and p.rsplit(".", 1)[-1] not in leaves
            and p not in declines
        )
        if missing:
            rows.append((len(missing), endpoint, missing))

        # And the other direction: a wire name the contract publishes that the
        # server declares nowhere. Compared by leaf name, never by path, for
        # the same reason the forward pass is.
        info_leaves = {p.rsplit(".", 1)[-1] for p in paths}
        unknown = sorted(_contract_leaves(contract) - info_leaves)
        if unknown:
            phantom.append((endpoint, unknown))

    rows.sort(key=lambda row: (-row[0], row[1]))
    phantom.sort(key=lambda row: (-len(row[1]), row[0]))
    print(f"contracts compared: {compared}")
    print(f"skipped, field list admittedly incomplete (unmergedTables): {len(skipped)}")
    print(f"properties waived as infoOnly: {waived}")
    print(f"endpoints with an unrecorded /info property: {len(rows)}")
    print(f"unrecorded properties in total: {sum(n for n, _, _ in rows)}")
    print(f"endpoints publishing a name /info never declares: {len(phantom)}")
    print()
    print("A large count is usually not a defect. /info describes the whole")
    print("record including computed read-only members, while a manual section")
    print("often documents only what a request sends - /db/SECT's section-property")
    print("tree is the extreme case. A count of one or two is the interesting")
    print("shape: that is what a missing table row looks like.")
    print()
    for count, endpoint, missing in rows:
        print(f"{count:4}  {endpoint}")
        for index in range(0, len(missing), 6):
            print("        " + ", ".join(missing[index:index + 6]))

    print()
    print("=" * 70)
    print("Names this contract publishes that /info declares nowhere.")
    print()
    print("Read these the other way round from the list above, and read them")
    print("weakly. /info listing a property is not the same as the server")
    print("accepting only those: /db/STBK's LCNAME appears in neither product's")
    print("schema, and scripts/live_crud_check.py runs a confirmed round trip")
    print("that sends it on both. So a name here supports a note, never a")
    print("removal. What it is good for is the case where the manual and the")
    print("server both name a field and name it differently - /db/POGD-M1's")
    print("UPLIFT for UPLIFTING, /db/STRPSSM's PY for Y - because there a")
    print("caller following the manual sends a key the server never mentions")
    print("while the one it does mention goes unsent. Removing a documented")
    print("field takes what settled /db/REBC: a live comparison in which the")
    print("documented shape was refused and the other accepted.")
    print()
    for endpoint, unknown in phantom:
        print(f"{len(unknown):4}  {endpoint}")
        for index in range(0, len(unknown), 6):
            print("        " + ", ".join(unknown[index:index + 6]))
    if not check:
        return 0
    return _check_against_contracts(
        compared=compared,
        skipped=len(skipped),
        waived=waived,
        unrecorded={endpoint: count for count, endpoint, _ in rows},
        contract_only={endpoint: len(names) for endpoint, names in phantom},
    )


def _check_divergence(
    *,
    both: int,
    different: int,
    untagged: dict[str, int],
    absent: dict[str, int],
) -> int:
    """Fail when product divergence becomes less completely accounted for."""
    errors: list[str] = []
    minimum = EXPECTED_DIVERGENCE["endpointsAnsweringBothAtLeast"]
    if both < minimum:
        errors.append(f"endpoints answering on both products fell from {minimum} to {both}")

    ceiling = EXPECTED_DIVERGENCE["divergentSchemasAtMost"]
    if different > ceiling:
        errors.append(f"endpoints declaring different schemas grew from {ceiling} to {different}")

    for endpoint, count in sorted(untagged.items()):
        if count:
            errors.append(
                f"untagged product-specific fields for {endpoint} must be 0, found {count}"
            )

    expected_absent = EXPECTED_DIVERGENCE["absentFieldsAtMost"]
    for endpoint in sorted(set(absent) | set(expected_absent)):
        actual_count = absent.get(endpoint, 0)
        endpoint_ceiling = expected_absent.get(endpoint, 0)
        if actual_count > endpoint_ceiling:
            errors.append(
                f"absent product-specific fields for {endpoint} grew from "
                f"{endpoint_ceiling} to {actual_count}"
            )

    if not errors:
        print("\nOK - product-divergence tagging remains complete.")
        return 0

    print("\n/info product-divergence check failed:", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    print(
        "Absent counts may shrink without updating the expectation. Any "
        "untagged field or growth must be reviewed and recorded with the "
        "change that explains it.",
        file=sys.stderr,
    )
    return 1


def divergence(*, check: bool = False) -> int:
    """Where the two products declare different schemas for one endpoint.

    `products: [civil, gen]` on a contract says the route answers on both. It
    does not say the record is the same, and for ten endpoints it is not. A
    field the contract lists unqualified is a claim about both products, so
    each of these needs a per-field `products` tag or the contract is wrong on
    one product - which is what `docs/live_verification_notes.md` concluded for
    /db/POGD on 2026-09-03, from a sweep of nine endpoints. This is the same
    question asked of all 177 pairs that answer on both.
    """
    capture = _load(BASELINE)
    contracts = _contract_documents()

    def tagged(contract: dict | None) -> dict[str, list[str] | None]:
        out: dict[str, list[str] | None] = {}
        if not contract:
            return out

        def walk(fields: Iterable[dict] | None) -> None:
            for field in fields or []:
                out[field["key"]] = field.get("products")
                walk(field.get("properties"))

        walk(contract.get("fields"))
        for variant in contract.get("variants") or []:
            walk(variant.get("fields"))
        return out

    both = 0
    rows: list[tuple[str, list[str], list[str], list[str]]] = []
    for endpoint, per_product in sorted(capture["endpoints"].items()):
        civil = (per_product.get("civil") or {}).get("schema")
        gen = (per_product.get("gen") or {}).get("schema")
        if not (civil and gen):
            continue
        both += 1
        pc = _paths(civil, with_types=True)
        pg = _paths(gen, with_types=True)
        only_civil = sorted(set(pc) - set(pg))
        only_gen = sorted(set(pg) - set(pc))
        retyped = sorted(p for p in set(pc) & set(pg) if pc[p] != pg[p])
        if only_civil or only_gen or retyped:
            rows.append((endpoint, only_civil, only_gen, retyped))

    print(f"baseline: {BASELINE.name}, captured {capture['capturedAt']}")
    print(f"endpoints answering /info on both products: {both}")
    print(f"of those, declaring different schemas: {len(rows)}")
    print()
    print("A field listed on a contract without a `products` tag is a claim")
    print("about both products. Below, `untagged` counts the ones this contract")
    print("makes that claim for and /info contradicts; `absent` counts the ones")
    print("no contract records at all.")
    print()
    untagged_counts: dict[str, int] = {}
    absent_counts: dict[str, int] = {}
    for endpoint, only_civil, only_gen, retyped in rows:
        contract = contracts.get(endpoint)
        have = tagged(contract)
        # A contract that has declared its own field list incomplete is not
        # making the claim this mode checks for, so `absent` there is a known
        # gap rather than a finding. Say which, instead of counting it twice.
        incomplete = bool((contract or {}).get("extraction", {}).get("unmergedTables"))
        suffix = ("" if contract else "   (no contract)")
        if incomplete:
            suffix = "   (field list declared incomplete: unmergedTables)"
        print(f"{endpoint}{suffix}")
        for label, names in (("civil only", only_civil), ("gen only", only_gen),
                             ("retyped", retyped)):
            if not names:
                continue
            leaves = [n.rsplit(".", 1)[-1] for n in names]
            untagged = [n for n in leaves if n in have and not have[n]]
            absent = [n for n in leaves if n not in have]
            untagged_counts[endpoint] = untagged_counts.get(endpoint, 0) + len(untagged)
            absent_counts[endpoint] = absent_counts.get(endpoint, 0) + len(absent)
            print(f"    {label:10} {len(names):3}"
                  f"   untagged {len(untagged):3}   absent {len(absent):3}")
            for index in range(0, len(names), 5):
                print("        " + ", ".join(names[index:index + 5]))
    if not check:
        return 0
    return _check_divergence(
        both=both,
        different=len(rows),
        untagged=untagged_counts,
        absent=absent_counts,
    )


def capture(out_path: pathlib.Path, products: list[str]) -> int:
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "scripts"))
    from live_readonly_sweep import (  # noqa: PLC0415
        _all_resources,
        _import_all_submodules,
    )

    from midas_nx import MidasClient, Product  # noqa: PLC0415
    from midas_nx.client import MidasAPIError  # noqa: PLC0415

    _import_all_submodules()
    resources = _all_resources()
    endpoints = sorted({resource.ENDPOINT for resource in resources})
    print(f"sweeping /info for {len(endpoints)} endpoints x {len(products)} product(s)")

    results: dict[str, dict[str, Any]] = {}
    for product in products:
        client = MidasClient(product=Product(product))
        for endpoint in endpoints:
            slot = results.setdefault(endpoint, {})
            try:
                response = client.request("GET", f"/info{endpoint}")
            except MidasAPIError as error:
                slot[product] = {"status": None, "error": f"{type(error).__name__}: {error}"}
            else:
                # Only the schema is kept. A GET response body is model data and
                # never enters this file.
                slot[product] = {"status": 200, "schema": response}
        print(f"  {product}: done")

    answered = sum(1 for v in results.values() for p in v.values() if p.get("schema"))
    payload = {
        "$comment": _load(BASELINE)["$comment"] if BASELINE.exists() else "",
        "capturedAt": __import__("datetime").date.today().isoformat(),
        "method": "GET /info{endpoint}",
        "nxVersions": {product: "TODO: record the build you ran against" for product in products},
        "coverage": {
            "endpointsSwept": len(results),
            "pairsWithSchema": answered,
            "pairsAnswering404": sum(
                1 for v in results.values() for p in v.values() if p.get("error")
            ),
        },
        "endpoints": results,
    }
    io.open(out_path, "w", encoding="utf-8", newline="\n").write(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n"
    )
    print(f"wrote {out_path} ({answered} pairs with a schema)")
    print("Fill in nxVersions before committing this as a baseline.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--capture", action="store_true", help="live GET-only sweep")
    mode.add_argument("--diff", metavar="CAPTURE", help="compare a capture against the baseline")
    mode.add_argument(
        "--against-contracts",
        action="store_true",
        help="offline: which declared properties no contract records",
    )
    mode.add_argument(
        "--divergence",
        action="store_true",
        help="offline: where the two products declare different schemas",
    )
    parser.add_argument("--out", default="info-capture.json", help="--capture output path")
    parser.add_argument(
        "--product",
        action="append",
        choices=["civil", "gen"],
        help="repeatable; defaults to both",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="with --against-contracts or --divergence, fail when established differences grow",
    )
    args = parser.parse_args()

    if args.check and not (args.against_contracts or args.divergence):
        parser.error("--check requires --against-contracts or --divergence")

    if args.divergence:
        return divergence(check=args.check)
    if args.against_contracts:
        return against_contracts(check=args.check)
    if args.diff:
        return diff(pathlib.Path(args.diff))
    return capture(pathlib.Path(args.out), args.product or ["civil", "gen"])


if __name__ == "__main__":
    raise SystemExit(main())
