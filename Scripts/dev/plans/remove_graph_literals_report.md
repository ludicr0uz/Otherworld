# Report: remove meaningless literals from the Blueprint-authoring Python

Plan: `remove_graph_literals.md`. Branch `remove-graph-literals`, off `night-mode` at
`df8de0b`. All six phases completed; every phase ended on a clean builder sweep, an
empty fingerprint diff against `baseline_a`, and unchanged verifier counts.

## Phases

| phase | commit | what |
|---|---|---|
| 0 | `51ca497` | `graph_fingerprint.py` + `graph_fingerprint_diff.py`; `Scripts/uebp/graph.py`; the three helper copies and the 21 `_out` gone |
| 1 | `8756db5` | `uebp/layout.py` `arrange(ed)` before each compile; `strip_coords.py`; `_at` deleted |
| 2 | `56ebf78` | `out` / `then` / `else_`; `_G` in `uebp/g.py`; shims removed, `uebp` imported directly |
| 3 | `d8ddb19` | `uebp/nodes/` (8 modules, 351 paths); `check_node_catalog.py` |
| 4 | `4272f54` | `uebp/vars.py`, 11 variable tables, `uebp/props.py` |
| 5 | `b3514cc` | `_set` formats a bool; 118 `"true"`/`"false"` literals typed |

## Line and character counts (git, `df8de0b` -> `b3514cc`)

| package | lines before | after | chars before | after |
|---|---|---|---|---|
| `Scripts/combat` (verify included) | 34,520 | 33,467 | 1,741,816 | 1,633,583 |
| `Scripts/combat/weapon_component` | 10,056 | 9,669 after Phase 1 | | |
| `Scripts/npc` | 7,993 | 7,543 | 400,090 | 363,501 |
| `Scripts/graphics_menu` | 12,917 | 12,320 | 641,938 | 587,075 |
| `Scripts/survival` | 2,293 | 2,290 | 106,149 | 103,231 |
| `Scripts/world` | 1,780 | 1,764 | 83,249 | 81,429 |
| `Scripts/clothing` | 412 | 414 | 19,073 | 19,148 |
| `Scripts/uebp` (new) | 0 | 1,304 | 0 | 59,382 |
| `build_graphics_menu.py` | 1,264 | 1,028 | 64,556 | 50,291 |
| all authoring code | 65,870 | 64,824 | 3,281,252 | 3,121,944 |

The saving is mostly inside lines, not in their number: 159 k characters (4.9%) net of
the 59 k the new library adds. No module over budget got longer;
`build_graphics_menu.py` is still over (1,028).

## The literal counts, re-measured

One AST script run on both revisions (so the two columns compare; the plan's own
numbers came from greps and differ a little).

| literal kind | plan said | before | after |
|---|---|---|---|
| `_at(...)` calls (a coordinate pair each) | 2,315 | 2,248 | 0 |
| functions taking coordinate parameters | 212 | 366 | 0 in Blueprint authoring (7 left: real geometry, a material graph, `_vec`'s x/y/z) |
| `_pin(...)` calls | 5,237 | 4,811 | 3,520 |
| ...with a plumbing name | ~3,700 | 3,476 | 2,620 (inputs: `execute`, `A`, `B`, `Condition`, `self`, `Object`) |
| ...with a specific name | ~1,500 | 1,013 | 678 |
| distinct pin-name strings in `_pin` | | 238 | 156 |
| `out` / `then` / `else_` helper calls | | 845 | 3,171 |
| `BEL.find_then_pin` / `find_else_pin` | | 1,186 | 128 (verifiers, probes, and scopes with a local `out`/`then`) |
| `FN_*`/`NODE_*` definitions | 658 in 68+ files | 658 in 71 | 349 in 8 (`uebp/nodes/`), 351 paths with `MACRO_*` |
| variable nodes named by a bare string | 293 | 304 | 0 (and 0 of the 156 through wrappers) |
| `_set(n, pin, "<string>")` | 699 | 155, 118 of them bools | 37 (enums and names; no bools) |
| copies of `_node`/`_pin`/`_connect`/`_set` | 3 | 3 | 1 |
| local `_out` definitions | 21 | 21 | 0 |

The plan's acceptance grep for Phase 1 (`_at\(|[^a-z_](x0|y0|px|py)\b`) still returns
2,284 lines, none a coordinate: 2,146 are `.py` in a path or docstring, 69 are names
ending in `_at(` (`slot_at`, `sway_at`, `row_at`, `get_child_at`, ...), 52 are real
geometry (terrain, placement, audio curves, images, `forest_import/wind.py`'s material
graph), 13 are `px` the unit, 3 are the codemods' own docs, 1 is `x0.9` in a comment.

## Verifier pass counts

| verifier | before | after every phase |
|---|---|---|
| `verify_weapons_and_combat.py` | 1768/1768 | 1768/1768 |
| `verify_survival.py` | 129/129 | 129/129 |
| `verify_npc_blueprints.py` | 417/417 | 417/417 |
| `verify_graphics_menu.py` | 405/405 | 405/405 |
| `verify_day_night.py` | 70/70 | 70/70 |
| `verify_clothing.py` | 100/100 | 100/100 |
| `check_node_catalog.py` (new) | | 351/351 |

Dev unit tests: 213 before, 225 now, all passing.

## Fingerprint diff against `baseline_a` (63 Blueprints, 8,829 nodes)

| | result |
|---|---|
| `baseline_b` (second unchanged build) | identical |
| Phase 0 | identical |
| Phase 1a (layout added, coordinates still there) | identical |
| Phase 1 | identical |
| Phase 2 | identical |
| Phase 3 | identical |
| Phase 4 | identical |
| Phase 5 | identical |

The tool needed three fixes before two unchanged builds matched, all in the tool: a
text literal's key is a fresh GUID per build (stripped); a delegate default reads back
as one of two wrapper types from run to run (now `<opaque>`); the same, nested in a
struct. `baseline_a` was re-taken after the first fix and its opaque values rewritten
in place for the other two. The fingerprint also records each pin's type next to its
name, which the plan did not ask for.

Layout, as logged per graph (nodes, columns, most rows in a column):
`BP_GraphicsMenuHUD` 3057 / 358 / 22, `BP_WeaponComponent` 1940 / 365 / 19,
`BP_ForestWandererAI_Wendigo` 1073 / 71 / 71, `BP_GraphicsTuner` 393 / 55 / 16,
`BP_HealthComponent` 263 / 52 / 9. 36 graphs in all.

## Decided here

- **Sweeps ran in a private headless editor** (`UEPY_SERVE=Saved/uepy/claude`), after
  the first sweep crashed the open editor. `Scripts/dev/plans/sweep.sh <label>` is the
  whole loop: build, fingerprint, verify.
- **`graph_fingerprint.py` takes its directory on the host command line** and hands
  itself to the editor through `uepy.py` (which passes no arguments to a script).
- **Layout:** an exec node goes one column right of the furthest node feeding it, a
  pure node one column left of its nearest consumer; a graph wider than 100,000 units
  is centred on the origin.
- **Comment boxes are not re-fitted.** `add_comment_to_nodes` runs while its nodes
  still sit on the origin, so each box is drawn there.
- **`strip_coords.py` decides by use, not by name:** a parameter, local or loop
  variable is a coordinate when it was read at git `HEAD` and nothing reads it once
  `_at`/`_palette` are stripped. It dropped only `x`, `y`, `x0`, `y0`, `px`, `py`,
  `x1`/`y1`, `wx`/`wy`, `dy`.
- **`join_lines.py`** rejoins statements a codemod left wrapped for no reason, but
  only ones changed since `HEAD`.
- **`_connect(E, _pin(N, "execute"))` is left as it is.** The helper the plan names,
  `exec_in`, is what 110 fragments call their own exec parameter. `else_(n)` was
  applied alongside `then(n)`.
- **`_log` lives in `combat/log.py`** (`[GUN]`), which survival, world, clothing and
  loot use too; `combat/graph.py` is deleted. `npc/graph.py` keeps `_log`, `_Graph`
  and `_mesh_object`. `_asset_sub` became `_assets`.
- **`_G(ed, ITEM_CLASS_PATH)`:** `uebp` cannot import `combat`, so the class `iget`/
  `iput` default to is given at construction.
- **One name per path:** of several names the most used wins. 33 paths had several
  (`FN_AND_B` -> `FN_AND`, `FN_MUL` -> `FN_MUL_FF`, `FN_GREATER`/`FN_GT_FF` ->
  `FN_GREATER_FF`, `NODE_EVENT_TICK` -> `NODE_TICK`, ...); the codemod prints the list.
- **One name held two paths, twice:** `FN_SET_VISIBILITY` keeps
  `SceneComponent.SetVisibility` and the UMG one is `FN_SET_WIDGET_VISIBILITY`;
  `FN_FORWARD` keeps `KismetMathLibrary.GetForwardVector` and npc's
  (`Actor.GetActorForwardVector`) is `FN_ACTOR_FORWARD`.
- **`combat/nodes.py` remains**, holding the four engine class paths that are not
  node paths. `npc/nodes.py` is deleted.
- **`check_node_catalog.py` tries each path in seven scratch graphs** (actor, HUD, AI
  controller, widget, BT task, ability, a copy of `ABP_Unarmed`'s AnimGraph) and
  passes one that resolves in any.
- **A `Var` is a `str` subclass, not a frozen dataclass:** it is its name, so
  `HV.Health` goes straight into the engine API, a dict key or an f-string. It is
  frozen (`__setattr__` raises).
- **Types in the tables came from the fingerprint.** A row is typed, and the
  builder's `_declare` removed, only where the codemod found that `_declare`; a
  default moved only when it is static.
- **A name that already had a `*_VAR` constant in a data module keeps it** rather
  than gaining a row (`BASE_SPEED_VAR`, `GAME_STARTED_VAR`, `LAST_DAMAGE_VAR`,
  `ASC_COMPONENT`). Constants in fragment modules now point at the row
  (`MELEE_VAR = IV.Melee`, `AIM_POINT_VAR`, `RETICLE_SPREAD_VAR`,
  `STARTER_CLASS_VARS`).
- **Phase 5 rewrites only direct `_set` calls.** `_G.put`, `_Graph.put` and others
  tell a literal from a pin by `isinstance(value, str)` and still take `"true"`.
- **Three new dev tests:** the fingerprint diff, `layout.columns`, and
  `test_project_imports.py` (every `from <project module> import name` and
  `alias.name` exists).

## Not done, or left over

- **Phase 4 covers the variables that were bare strings, not every variable.** The
  ones with a `*_VAR` constant (265 uses in the plan's count) are still declared by
  their builders' own `_declare` calls and defaults dicts. Typed rows: weapon
  component 29 of 35, health 8 of 8, weapon item 21 of 36, HUD 8 of 8, NPC
  controller 1 of 1, settings 4, burst 5, footsteps 5, ammo pickup 2, survival 3 of
  9, day/night 0 of 10 (names only).
  Since V1 the weapon component (186 rows) and the weapon item (73) are typed in
  full, and their builders declare nothing themselves.
- **Bare variable names remain outside the builders:** `get_editor_property("...")`
  in the verifiers, `p.get`/`p.set` in the probes, the per-item default dicts' keys
  that the codemod did not reach, and `(GAME_MODE_BP_PATH, "PlayerDead")` in two
  probes' WRITABLE lists (the game mode has no table).
- **Verifier fixtures needed no change:** `combat/verify/fixtures.py` names pins, not
  variables.
- **`forest_import/wind.py` still passes coordinates** to a material graph. It is not
  Blueprint authoring and was left alone.
- **Stale comment boxes pile up.** A rebuild's `remove_nodes(list_all_nodes())` does
  not remove comment nodes: `BP_HealthComponent` held 2,738 of them before this work
  started. Not touched.

## Blocked

Nothing blocked a phase. Two things went wrong on the way:

- **The first builder sweep crashed the open editor** (pid 9365), inside
  `build_weapons_and_combat.py`, before any authoring code had changed:

  ```
  SIGSEGV: invalid attempt to access memory at address 0x9d484d655fd9f2da
  libUnrealEditor-BlueprintEditorLibrary.dylib!UBlueprintGraphEditor::AddCallFunctionNode(FString const&)
  ```

  Anything unsaved in that editor was lost.
- **The headless editor died mid-sweep four more times** (three in
  `build_graphics_menu.py`, one in the fingerprint). `uepy.py` restarted it and re-ran
  the script each time, and the run passed.

## Uncommitted work that was already in the tree

`Scripts/clothing/placement.py`, `survival/forage_level.py`, `world/level_placement.py`
(the `save_level` change), `forest_generator/CLAUDE.md`, `npc/CLAUDE.md` and the
untracked `world/level_save.py` were modified before this started and are still
uncommitted. Phase 2 changed one import line in each of the three `.py` files; only
that line is committed.
