# midas-nx 2.8.4

A shared PyPI/npm version release. **Three members of one npm type become
optional, and that is the only change in either package.**

| surface | what actually changed |
| --- | --- |
| Python | nothing that runs — one comment in `src/midas_nx/db/base.py` points at git history instead of a file removed from `docs/`. The wheel behaves exactly as 2.8.3 |
| npm | `TendonPropertyPayload`'s `FT`, `FPK` and `TDMFNAME` change from required to optional, each carrying the condition that makes it required |

## Changed on npm — `TendonPropertyPayload` relaxes three members

This is the opposite direction from 2.8.3, which narrowed a type. **Nothing
that typechecked against 2.8.3 stops typechecking here**: code that always set
these three still compiles, and the request an SDK sends is unchanged.

```diff
 export interface TendonPropertyPayload {
-  /** Relaxation Factor ξ (TB05/TB10092/Q-CR/AS/JTJ/JTG 코드) */
-  FT: number;
+  /** Relaxation Factor ξ ... Required when RM is 2 or 3 or 10 or 11 or 12 or 13. */
+  FT?: number;
-  /** Characteristic Strength fpk (TB05/TB10092/Q-CR/JTJ/JTG 코드) */
-  FPK: number;
+  /** Characteristic Strength fpk ... Required when RM is 2 or 3 or 10 or 12 or 13. */
+  FPK?: number;
-  /** Relaxation Function Name (User Defined) */
-  TDMFNAME: string;
+  /** Relaxation Function Name (User Defined) Required when RM = 100. */
+  TDMFNAME?: string;
 }
```

`/db/TDNT`'s three members are required *per relaxation model*, not always.
`RM` picks the model, and the manual's own field table states the dependency in
prose the generator could not act on: `FT` applies to six of the `RM` values,
`FPK` to five, and `TDMFNAME` only to the user-defined model `RM = 100`. The
type said all three were always required, so the one payload the SDK itself
sends live — the manual's KSCE LSD15 example, which sets none of them — did not
satisfy its own published type.

The contract now records each dependency as an `appliesWhen` condition, which
is what moves the member to optional and puts the condition in the JSDoc. A
caller reading the type sees when the field is needed rather than being told to
always send it.

No exported name was added, removed or renamed: npm exports the same 765 type
names as 2.8.3, across the same 305 resources.

## Python

`src/midas_nx/` has no behavioural change. The only edit is a comment in
`db/base.py` whose reference to a `docs/` report no longer resolved after that
report was removed; it now cites the commit instead. PyPI republishes
equivalent code under the aligned number, as the lockstep rule requires.

## Not in either package

Most of the work since 2.8.3 does not ship, and is listed here only so the
release is not mistaken for the sum of it:

- **Live write coverage moved 201 → 207**, with reads at 193. `/db/TDNT`,
  `/db/POGD` (Civil), `/db/POGD-M1`, `/db/MVLDch`, `/db/MVLDid` and `/db/PTNS`
  earned write evidence through both SDKs on Build 09/15/2026.
- **The live fixture is at 220 cases over 196 endpoints, 183 confirmed**, and
  npm has replayed every one of those 183 on each product it declares.
- Every confirmed case was re-verified on Build 09/15/2026, and the remaining
  40 `/db` endpoints below write level each have a recorded reason in
  `docs/live_verification_playbook.md`.
- Contracts record what `/db/MATD` and `/db/SPLC` actually do live, without
  changing what they assert.
