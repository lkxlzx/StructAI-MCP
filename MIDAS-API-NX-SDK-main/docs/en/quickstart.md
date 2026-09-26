# midas-nx Getting Started Guide (no prior programming experience needed)

This guide is for structural engineers who use MIDAS Gen NX/Civil NX daily
but have never written a line of Python before. It walks through everything
from installing Python to running your first script, in order, so you can
follow it start to finish in one sitting.

> `midas-nx` is an employee-led open-source project, built by a MIDAS IT
> employee from hands-on product and API verification work. It is **not an
> officially released or supported MIDAS IT product** — please report problems
> with this SDK or guide on
> [GitHub Issues](https://github.com/Dennis5882/MIDAS-API-NX-SDK/issues) rather
> than to MIDAS IT product support, which does not cover it.

> If you already write code, [README.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/README.md)'s Quick Start is
> faster. This guide is for the step before that — for anyone who isn't
> sure what Python even is yet.

## Before you start

- A Windows PC (this guide is written for Windows)
- MIDAS Gen NX or Civil NX installed, with a valid license
- An internet connection (the SDK talks to MIDAS's cloud relay server)

## Step 1: Install Python

`midas-nx` requires **Python 3.11 or newer** — 3.11, 3.12, 3.13 and 3.14 are
all tested in CI.

1. Go to https://www.python.org/downloads/ and take the button's latest
   release. If you already have 3.11 or newer, you do not need to install
   anything.
2. Run the installer. **Make sure to check the "Add python.exe to PATH"
   checkbox at the bottom of the first screen** before clicking "Install
   Now." Skipping this means your command prompt won't recognize `python`
   later.
3. Once installed, verify it worked. Search for "cmd" in the Start menu to
   open Command Prompt, then type:

   ```
   python --version
   ```

   You should see `Python 3.11.x` or newer. If you already had an older
   Python installed (e.g. `Python 3.10.x`), install a current one as above —
   `pip install` will refuse `midas-nx` on anything below 3.11 in the
   next step. If you get `'python' is not recognized as an internal or
   external command`, you missed the PATH checkbox in step 2 — reinstall
   Python and check it this time.

## Step 2: Install midas-nx

In the same Command Prompt window:

```
python -m pip install midas-nx
```

(`python -m pip` rather than a bare `pip` avoids installing into the wrong
Python if you have more than one version on your machine — worth using
even if you've only ever seen `pip install package` written the other way.)

You'll see `Successfully installed midas-nx-...` when it's done.

## Step 3: Get a MAPI key

The `MAPI-Key` is the authentication key this SDK uses to talk to MIDAS
Gen NX/Civil NX. You don't get it from Python — you get it **from inside
the MIDAS Gen NX (or Civil NX) application itself**.

1. Launch MIDAS Gen NX (or Civil NX).
2. In the top menu, open **Apps** and click **API Settings**.
3. The screen shows a **Base URL** and a **MAPI-Key**. Click the **Copy**
   button next to each to copy it.
4. Click **Connected**. If it succeeds, Status switches to **Connected** —
   that's what confirms Open API is actually active.

> Want a fresh key (e.g. you think one leaked)? Click **Refresh** next to
> it. The old key is invalidated immediately.

> ⚠️ **Treat it like a password while it's live.** The scripts below paste
> the key directly into the code, which is fine for a one-off file on your
> own machine — but don't commit that file to Git, paste it into a public
> chat/issue, or share a screenshot that shows it. If you think a key leaked,
> just click **Refresh** above for a new one; the old one still expires when
> you close the app.

> 🌏 **No need to guess which regional server you're on.** Use the
> **Base URL** shown on that same screen — it's correct for any region,
> including China's separate server. If it differs from the SDK's default
> global relay (`moa-engineers.midasit.com`), add
> `base_url="the copied value"` to the `MidasClient(...)` call below.

## Step 4: Write and run your first script (read-only)

**Risk level: 1 — read-only** (see [Risk levels](../safety.md#risk-levels)).

Open Notepad (or VS Code, or any text editor) and paste the following
exactly as-is. Just replace
`"paste_the_key_you_copied_in_step_3_here"` with your actual key.

```python
from midas_nx import MidasClient, Product
from midas_nx.db.node_element import Node

# Using Civil NX instead? Change this to product=Product.CIVIL.
client = MidasClient(mapi_key="paste_the_key_you_copied_in_step_3_here", product=Product.GEN)

print(client.verify_connection())

nodes = Node.items(client=client)
print(f"Connected. Found {len(nodes)} node(s) in the current model.")
```

Save the file as `first_script.py` (your Desktop or any folder works fine).

In Command Prompt, navigate to the folder where you saved it and run it.
For example, if you saved it to your Desktop:

```
cd Desktop
python first_script.py
```

You should see something like:

```
{'status': 'connected', 'keyVerified': True}
Connected. Found 3 node(s) in the current model.
```

(The exact node count depends on whatever model you currently have open —
`0` is a perfectly normal answer if it's a blank project.)

**This script only reads data.** It cannot create, change, or delete
anything in your model, no matter which project you run it against — safe
to try against real work.

## If something goes wrong

- **`MidasConnectionError`**: check that Gen NX/Civil NX is running and
  Open API is connected. This SDK's error messages end with a
  `(Hint: ...)` telling you what to check.
- **`MidasAuthError`**: make sure you pasted the key from step 3 exactly.
  Keys can change when you restart the app — get a fresh one and paste it
  in again if this happens.
- **Behind a corporate firewall**: see
  ["Connectivity troubleshooting"](../safety.md#connectivity-troubleshooting)
  for the exact port/address info to hand to your IT team.

## Step 5: Add data to a blank model (optional — this changes your model)

**Risk level: 2 — limited addition** (see [Risk levels](../safety.md#risk-levels)).

Before running this, open Gen NX/Civil NX yourself and start a **new, empty
project** through the GUI (File > New Project, or similar) — this script
adds data to whatever project is currently open, it does not create one.
Unlike Step 6 below, it never calls `doc.new_project()`, so there's nothing
for it to discard.

```python
from midas_nx import MidasClient, Product
from midas_nx.db.node_element import Node

# Using Civil NX instead? Change this to product=Product.CIVIL.
client = MidasClient(mapi_key="paste_the_key_you_copied_in_step_3_here", product=Product.GEN)

Node.create({1: {"X": 0, "Y": 0, "Z": 0}, 2: {"X": 0, "Y": 0, "Z": 3.2}}, client=client)

nodes = Node.items(client=client)
print(f"Added 2 nodes. The model now has {len(nodes)} node(s).")
```

Run it the same way as Step 4. You should see `Added 2 nodes. The model now
has 2 node(s).` (more, if the blank project you opened wasn't actually
empty), and switching to Gen NX will show two new points in the model.

## Step 6: Build a whole model (optional — this changes your model)

**Risk level: 4 — high risk** (see [Risk levels](../safety.md#risk-levels)).
`doc.new_project()` discards unsaved work, which is why this step is
optional and separate from Steps 4 and 5.

Step 4 proved your connection works, and Step 5 added data safely to a
model you prepared yourself. If you'd like to see `midas-nx` build an
entire model from scratch — including creating the project itself — here's
the same example the MIDAS-API manual uses. Read the warning first.

> ⚠️ **This script calls `doc.new_project()`, which discards any unsaved
> work in whatever document is currently open in Gen NX/Civil NX** — even
> work unrelated to this script. Only run it against a blank project, or one
> you don't mind losing unsaved changes in. If you have a real model open,
> save it first (or close it and start a new blank project).

```python
from midas_nx import MidasClient, Product, doc
from midas_nx.db.node_element import Element, Node
from midas_nx.db.project import Unit
from midas_nx.db.properties.material import Material
from midas_nx.db.properties.section import Section

# Using Civil NX instead? Change this to product=Product.CIVIL.
client = MidasClient(mapi_key="paste_the_key_you_copied_in_step_3_here", product=Product.GEN)

doc.new_project(client=client)
Unit.update({1: {"DIST": "M", "FORCE": "KN"}}, client=client)

Material.create(
    {1: {"TYPE": "CONC", "NAME": "C24",
         "PARAM": [{"P_TYPE": 1, "STANDARD": "KS01(RC)", "DB": "C24"}]}},
    client=client,
)
Section.create(
    {1: {"SECTTYPE": "DBUSER", "SECT_NAME": "Column",
         "SECT_BEFORE": {"USE_SHEAR_DEFORM": True, "SHAPE": "SB", "DATATYPE": 2,
                          "SECT_I": {"vSIZE": [0.6, 0.6]}}}},
    client=client,
)
Node.create({1: {"X": 0, "Y": 0, "Z": 0}, 2: {"X": 0, "Y": 0, "Z": 3.2}}, client=client)
Element.create({1: {"TYPE": "BEAM", "MATL": 1, "SECT": 1, "NODE": [1, 2]}}, client=client)
doc.save(client=client)

print("Success! Check Gen NX — a column should now be in the model.")
```

Run it the same way as Step 4 (save as a `.py` file, run with `python`).
You should see `Success! Check Gen NX...` printed, and switching to the
Gen NX window will show a new 0.6m x 0.6m concrete column, 3.2m tall.

> The material/section combination above (`C24`/`KS01(RC)`) was
> live-verified against a real Gen NX and Civil NX session on 2026-07-22
> (see [docs/live_verification_notes.md](../live_verification_notes.md)) —
> this script uses confirmed values, not an untested guess, so it's meant to
> just work.

## Next steps

- **Keep going with an AI coding assistant.** Once you know the pattern
  above, you don't need to memorize or hand-write every call yourself.
  Show this script to Claude Code, ChatGPT, GitHub Copilot, or similar, and
  ask in plain language — "make a 20m beam instead of a column," "add a
  load combination" — and it'll turn that into real `midas-nx` code. This
  SDK is built to make that easy (type hints, clear error messages). Before
  you run anything it writes, see
  [Safe start: building with an AI coding assistant](../ai-coding/safe-start.md)
  for a context pack to give it and a checklist to review its code against.
- More realistic examples: the
  [`examples/python/`](https://github.com/Dennis5882/MIDAS-API-NX-SDK/tree/main/examples/python/) folder on GitHub (beam load
  combinations, wind loads, construction stages, ...) — a good thing to
  show your AI assistant as a "build me something like this" reference.
- Full list of what's implemented: [ROADMAP.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/ROADMAP.md)
- More detailed usage and design notes: [README.md](https://github.com/Dennis5882/MIDAS-API-NX-SDK/blob/main/README.md)

If you got stuck anywhere following this guide, please open a GitHub
issue — it helps make the guide better for the next person.
