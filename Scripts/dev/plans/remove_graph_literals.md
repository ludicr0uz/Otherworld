# Task: remove meaningless literals from the Blueprint-authoring Python

You are working in `/Users/alexeysukhov/Documents/Unreal Projects/Otherworld`, an Unreal
Engine 5.8 project on macOS with no C++ module. All gameplay Blueprints are authored node by
node from Python under `Scripts/`. Read the root `CLAUDE.md` first and obey its hard rules.
The ones that matter most here:

- Never edit `.uasset`/`.umap` as text. Everything goes through the `unreal` Python API.
- Run scripts through `python3 Scripts/dev/uepy.py <script>` (warm editor). Never cold-run a
  builder while an editor is open. Use absolute paths when invoking the editor directly.
- Modules stay under ~500 lines, functions under ~150 (graph-authoring functions ~250).
- Run `python3 -m unittest discover -s Scripts/dev/tests` after touching `Scripts/dev`.
- Builders log `[GEN]`, verifiers `[VERIFY]`. `uepy.py --summary` exits non-zero on any
  failed check.

This is a refactor of the authoring code only. **The built Blueprints must come out
structurally identical, except for node positions.** No gameplay change is in scope. Work on a
branch. One commit per phase. If a phase cannot be completed to its acceptance criteria, stop,
leave the tree clean at the last passing commit, and report what blocked you.

## Why

An agent pays tokens for every line it reads. The builders are dominated by text that carries no
meaning: node coordinates, the eight plumbing pin names, and duplicated helper code. Measured
before this task:

| literal kind | count | meaning |
|---|---|---|
| node coordinates inside `_at(...)` | 2,315 | none; nothing reads positions back |
| `x0, y0` parameters threaded through `_author_*` signatures | 212 functions | none |
| plumbing pin names (`execute`, `ReturnValue`, `self`, `A`, `B`, `Condition`, `Object`, `CastFailed`) | ~3,700 of 5,237 `_pin(...)` calls | none |
| specific pin names (`TargetArray`, `TraceStart`, ...) | ~1,500 | real: keep |
| `FN_*` / `NODE_*` path constants | 658 definitions in 68+ files, 3,585 uses | real, but duplicated |
| Blueprint variable names as bare strings | 293 (vs 265 via constants) | real, but spelled in builder, verifier and probe |
| `_set(n, "Pin", "false")` string-typed literals | 699 | real, but untyped |
| copies of the graph helpers (`_node`, `_pin`, `_connect`, `_set`, `_at`) | 3 (`combat/graph.py`, `npc/graph.py`, `build_graphics_menu.py`) plus 21 files defining a local `_out` | none |

Positions are read in exactly three places, all in `Scripts/build_graphics_menu.py`
(`BEL.get_node_pos(begin_play)` / `(tick)` used as layout origins). No verifier reads them.

## Phase 0: the fingerprint tool and one authoring library

### 0a. Fingerprint tool (do this first; it is the safety net for every later phase)

Write `Scripts/dev/graph_fingerprint.py`, run inside the editor via `uepy.py`. It writes one
JSON file per Blueprint to a directory given on the command line (default
`Saved/uepy/fingerprint/<label>/`).

Scope: every `Blueprint` and `WidgetBlueprint` asset under `/Game` **except** `/Game/Fab`,
`/Game/Sourced`, `/Game/FPS_Weapon_Bundle`, `/Game/Characters`, `/Game/LevelPrototyping`,
`/Game/Tmp`, plus the three patched stock assets explicitly: `ABP_Unarmed`,
`BP_ThirdPersonCharacter`, `BP_ThirdPersonGameMode` (find their paths with the asset registry;
do not guess). Use `unreal.AssetRegistryHelpers` to enumerate; do not hard-code the list.

Per Blueprint, record, with **no positions anywhere**:

- member variables: name, pin type category and sub-category object path, and the CDO default
  value as text (use the comparison rules in `combat/graph._same`'s docstring: structs via
  `to_tuple()`, objects by path, `FKey` via `export_text()`, arrays element-wise);
- components (SCS): variable name, class path, parent variable name, sorted;
- for the event graph and every function graph: a sorted list of node records and a sorted
  list of connection records.
  - node record: `class name | node title | sorted input pin names | sorted output pin names |
    sorted (input pin name, literal value) for unconnected input pins`. Normalise literals as
    the project does: a value equal to the pin default may read as `""` or `"0.0"` depending on
    whether the editor is the one that authored it (see `CLAUDE.md` "A literal equal to its
    pin's default isn't saved"), so canonicalise numerics with `float()` and treat `""` as `0`.
  - connection record: `(node record A, pin name A) -> (node record B, pin name B)`. If two
    nodes have identical records, disambiguate by an ordinal assigned in order of the node's
    object name (`get_name()`), which follows creation order.
- Never guess API names across a boot: the first run should `dir()` the graph, node and pin
  libraries you need and print them, then use what exists. `BlueprintEditorLibrary`
  (`BEL`), `BlueprintGraphPinLibrary` (`PIN`), `BlueprintGraphEditor` and
  `SubobjectDataBlueprintFunctionLibrary` are already used by the verifiers in
  `Scripts/combat/verify/common.py` and `Scripts/combat/graph.py`; start there.

Add `Scripts/dev/graph_fingerprint_diff.py` (plain Python, no `unreal`) that compares two
fingerprint directories and prints a readable diff: Blueprints added/removed, then per
Blueprint the node/connection/variable/component records added and removed. Exit code 1 on
any difference.

**Validate the tool before trusting it:**

1. Run the full builder sweep (below), fingerprint to `baseline_a`.
2. Run the full builder sweep again with no code change, fingerprint to `baseline_b`.
3. `graph_fingerprint_diff baseline_a baseline_b` must be empty. If it is not, the tool is
   capturing something non-deterministic (node names, ordering, literal formatting). Fix the
   tool, not the builders, until two consecutive builds fingerprint identically.

Keep `baseline_a` as **the baseline** for every phase below.

The full builder sweep, in this order (dependencies between them matter; `CLAUDE.md`'s table
names them):

```bash
python3 Scripts/dev/uepy.py --summary \
  Scripts/build_weapons_and_combat.py \
  Scripts/build_survival.py \
  Scripts/build_npc_blueprints.py \
  Scripts/build_graphics_menu.py \
  Scripts/build_day_night.py \
  Scripts/build_clothing.py
```

Confirm this order against each entry point's docstring before the first run; if one says it
must run after another, follow the docstring. The full verifier sweep:

```bash
python3 Scripts/dev/uepy.py --summary \
  Scripts/verify_weapons_and_combat.py \
  Scripts/verify_survival.py \
  Scripts/verify_npc_blueprints.py \
  Scripts/verify_graphics_menu.py \
  Scripts/verify_day_night.py \
  Scripts/verify_clothing.py
```

Record the per-verifier pass counts from the summary line. They must not change in any phase.

### 0b. One authoring library

Create package `Scripts/uebp/` with:

- `graph.py`: the helpers currently in `Scripts/combat/graph.py` (`_log`, `_assets`, `_node`,
  `_palette`, `_pin`, `_pin_names`, `_loose_pin`, `_connect`, `_set`, `_literal_matches`,
  `_at`, `_create_blueprint`, `_float_type`, `_declare`, `_must_load`, `_same`,
  `_apply_defaults`, the component helpers, `_rot`, `_key`, `_vec`, `_events`,
  `_post_physics_tick`), moved **verbatim**. Where `npc/graph.py` or
  `build_graphics_menu.py` has a variant with different behaviour (for example
  `npc/graph._try_set`, `_name_literal`, `out`, `_resolve`), keep the variant under its own
  name in `uebp/graph.py` rather than merging semantics. Add `out(node, name="ReturnValue")`
  and `then(node)` here once; delete the 21 local `_out` definitions and import this one.
- `__init__.py` docstring mapping each module in one line, as every package here does.

Then make `combat/graph.py`, `npc/graph.py` and the helper block in `build_graphics_menu.py`
import from `uebp.graph` (thin re-imports are acceptable for this phase only so that the 180
call sites do not change yet; note the project rule "no re-exporting facades" and record in
the report that these shims are temporary and removed in Phase 2).

`_log` prefixes differ per package (`[GUN]`, `[GEN]`, ...). Keep the prefixes: give
`uebp.graph.make_log(prefix)` and have each package's shim bind its own.

Mind the module-purge lines at the top of each entry point (they delete `sys.modules` entries
for their own packages so edits reload in a warm editor). Add `"uebp"` to each purge list.

**Acceptance for Phase 0:** builder sweep runs clean; fingerprint diff against baseline is
empty; verifier counts unchanged; `python3 -m unittest discover -s Scripts/dev/tests` passes;
no module over budget got longer. Commit: `Phase 0: graph fingerprint tool and the uebp
authoring library`.

## Phase 1: delete the coordinates and lay graphs out after the fact

### 1a. Layout pass

Add `uebp/layout.py` with `arrange(ed)`:

- Collect all nodes in the graph.
- Column: longest path from any event node (nodes with no exec input and an exec output,
  plus any node with no inputs connected) following **both** exec links and data links,
  where a data supplier is placed one column left of its consumer. Use a topological order;
  graphs here are acyclic apart from exec loops, so break cycles by ignoring a back edge when
  one is detected and log it once.
- Row: within a column, order by creation (object name), stacking at a fixed pitch.
- Pitch: 400 px per column, 200 px per row, is enough that the node bodies do not overlap at
  default zoom. Positions are `IntPoint`; keep them within ±100,000.
- Call `arrange(ed)` once per graph at the end of each builder's graph authoring, immediately
  before the compile. Find the compile points: `grep -rn "compile_blueprint" Scripts`.
  Where a builder authors several graphs in one Blueprint (event graph plus functions), arrange
  each.
- The existing `_at` becomes a no-op that returns its node, kept only until 1b lands.

Run the sweep with the layout pass added and the old coordinates still present. Fingerprint
diff must be empty (positions are not in the fingerprint; this proves the pass itself changes
nothing structural). Open one Blueprint in the editor by hand is not possible for you; instead
log, per graph, the number of nodes, the number of columns and the maximum row count so the
report can show the layout is sane.

### 1b. Codemod: strip coordinates

Write `Scripts/dev/codemods/strip_coords.py` (plain Python; prefer `ast`/`tokenize` or
`libcst` if available, otherwise careful regex with a dry-run mode that prints each rewrite).
It must:

1. Rewrite `_at(EXPR, X, Y)` to `EXPR` wherever `X` and `Y` are the trailing two arguments,
   however they are spelled (`1040`, `-5200`, `x0 + 240`, `y0 - 300`, `origin.x + 320`,
   `x`, `px`).
2. Rewrite `_palette(ed, NAME, X, Y)` to `_palette(ed, NAME)`; make `_palette`'s `x`, `y`
   parameters optional defaults so untouched callers still work during the migration.
3. In `_G` (`Scripts/combat/weapon_component/common.py`) and any class like it: drop the
   `x, y` parameters from `keep`, `get`, `put`, `call`, `iget`, `iput`, `branch`, and from
   every call site of them.
4. Remove trailing positional parameters named `x`, `y`, `x0`, `y0`, `px`, `py` from the
   signature of every `_author_*`, `_body_trace`, `_note`, `_z`, `_head_worth`, `_prop`,
   `_muzzle_location`, `emit_*`, `author_*` style function **and** the matching trailing
   arguments at every call site. Do this by name resolution, not by position guessing: build
   the list of (module, function, which trailing params to drop) first, print it, then apply.
5. Remove the three `BEL.get_node_pos(...)` origin lookups in `build_graphics_menu.py` and the
   arithmetic that depends on them.
6. Delete `_at` from `uebp/graph.py` once no caller remains.

Run the codemod in dry-run, read the whole rewrite list, then apply. Then:

```bash
grep -rnE "_at\(|[^a-z_](x0|y0|px|py)\b" Scripts --include='*.py' | grep -v __pycache__
```

must return only hits that are genuinely not coordinates (there may be a few: a `px` unit in
the graphics menu strings, for example). List any survivors in the report with the reason each
was kept.

**Acceptance for Phase 1:** builder sweep clean; fingerprint diff against baseline empty;
verifier counts unchanged; dev unit tests pass; `wc -l` on
`Scripts/combat/weapon_component/*.py` and `Scripts/npc/*.py` shows the reduction (report
before and after totals). Commit: `Phase 1: graphs are laid out by uebp.layout; every
coordinate literal is gone`.

## Phase 2: collapse the plumbing pins

Scope for this run is the two mechanical rewrites and the API. Opportunistic migration of
whole fragments onto `_G` is **out of scope** unless Phases 0 and 1 are committed and verified.

1. Move `_G` from `combat/weapon_component/common.py` into `uebp/g.py` (keep `_prop`,
   `_trace_defaults`, `_muzzle_location` where they are: they are combat-specific). Add
   `out`, `then`, `else_`, `exec_in` helpers if not already present after Phase 0.
2. Codemod `Scripts/dev/codemods/plumbing_pins.py`:
   - `_pin(N, "ReturnValue", is_input=False)` -> `out(N)`
   - `_pin(N, "<name>", is_input=False)` -> `out(N, "<name>")`
   - `_connect(E, _pin(N, "execute"))` -> `exec_in(N, E)` where `exec_in` connects and
     returns `N`; or, if simpler and equally clear, leave `_pin(N, "execute")` and only do the
     first two. Decide once, apply uniformly, say which in the report.
   - `BEL.find_then_pin(N)` -> `then(N)`.
   Dry-run, review, apply.
3. Remove the Phase 0 import shims: every module imports what it uses from `uebp.graph`
   directly (`grep -rn "from combat.graph import\|from npc.graph import" Scripts`), and
   `combat/graph.py` / `npc/graph.py` keep only what is specific to that package or are
   deleted. The project rule is explicit imports, no facades.

**Acceptance for Phase 2:** same as Phase 1. Also report the new `_pin(` count and the number
of distinct pin-name strings remaining. Commit: `Phase 2: plumbing pins are helpers; uebp is
imported directly`.

## Phase 3: one node catalog

1. Create `uebp/nodes.py`. Move every `FN_*`, `NODE_*`, `INF` and similar constant from
   `combat/nodes.py`, `npc/nodes.py`, `combat/weapon_component/slot_nodes.py` and the 68
   files that define their own (find them with
   `grep -rlE '^(FN|NODE)_[A-Z_0-9]+ = ' Scripts | grep -v nodes.py`). Where two names hold the
   same path, keep one name and rewrite the other's uses. Where one name holds two different
   paths in two files, rename one of them explicitly and list it in the report.
2. If the merged file exceeds the ~500-line budget, split by engine library
   (`nodes_math.py`, `nodes_actor.py`, `nodes_array.py`, ...) with `nodes/__init__.py`
   listing the modules. No `import *`.
3. Add `Scripts/dev/check_node_catalog.py`, run via `uepy.py`, that resolves every path in the
   catalog by creating the node in a scratch Blueprint (create it under `/Game/Tmp`, delete
   it afterwards) and asserting the node has pins, exactly as `uebp.graph._node` does. Exit
   non-zero on any unresolved path. Run it; it should pass on the merged catalog.

**Acceptance for Phase 3:** sweep clean; fingerprint diff empty; verifier counts unchanged;
catalog check passes. Commit: `Phase 3: one node catalog, checked against the editor`.

## Phase 4: declare each Blueprint's variables once

1. For each Blueprint a builder declares variables on (start with `BP_WeaponComponent`,
   `BP_HealthComponent`, `BP_GraphicsMenuHUD`, the NPC controller), add a `vars.py`-style
   table next to its builder: a frozen dataclass per variable with `name`, `pin_type`
   (a callable or spec that yields the `_float_type()` / basic type / struct / object type),
   and `default`. The builder's declare loop iterates the table. Fragments reference
   `V.Health.name` (or a `Var` object whose `str()` is the name) instead of `"Health"`.
2. Make the verifier fixtures and the probes' `WRITABLE` lists read the same table.
3. Rewrite the 293 bare strings. Use the fingerprint's variable section to confirm no variable
   was added, removed or retyped.

**Acceptance for Phase 4:** as above, plus `grep -rnE 'add_(get|set)_member_variable_node\("'`
returns zero hits in the migrated packages. Commit per Blueprint if large.

## Phase 5: typed `_set`

`_set` accepts Python `bool`, `int`, `float` and formats them (`True` -> `"true"`). Codemod
`_set(N, "P", "true")` -> `_set(N, "P", True)` and `"false"` likewise. Fingerprint diff must be
empty, which proves the formatting round-trips. Commit.

## Reporting

At the end (or at the point you stop), write `Scripts/dev/plans/remove_graph_literals_report.md`
with:

- which phases completed, with commit hashes;
- a table of line counts before and after per package (`Scripts/combat`, `Scripts/npc`,
  `Scripts/graphics_menu`, `Scripts/survival`, `Scripts/world`, `Scripts/clothing`);
- the literal counts table from the top of this file, re-measured;
- verifier pass counts before and after;
- the fingerprint diff result for each phase (expected: empty);
- anything you decided that this document left open, in one line each;
- anything that blocked you, with the exact error text.

Update the root `CLAUDE.md` and the affected package `CLAUDE.md` files to describe the new
authoring API in a few lines (import from `uebp`, no coordinates, `_G` style, the catalog check
command). Keep the additions short: those files are read by every session.

## Do not

- Do not change any gameplay behaviour, tuning value, variable default or pin literal value.
  The fingerprint diff is the arbiter.
- Do not touch anything under `Content/` directly, or any `/Game/Forest/Scanned` asset.
- Do not run while PIE is active; `uepy.py` refuses by default. Leave that refusal in place.
- Do not "fix" a verifier to make it pass. If a verifier fails after a phase, the phase is
  wrong; revert to the last commit and find out why.
- Do not sign in to Fab or acquire assets.
- Do not delete `Saved/uepy/fingerprint/baseline_a` until the report is written.
