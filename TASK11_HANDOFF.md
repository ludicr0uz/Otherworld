# Task 11 handoff — hit impact animation for player and NPCs

Resume brief for a **fresh agent**. The previous agent's context grew to ~350k
tokens and was re-reading it on every call; everything worth keeping from it is
below. Read this file, then `CLAUDE.md`, then only the specific functions named
here — **do not re-read the big builders end to end.**

Project: `/Users/alexeysukhov/Documents/Unreal Projects/Otherworld`
UE 5.8, Blueprint-only, macOS, all asset work through Unreal Python.
**The Bash cwd resets between calls — absolute paths or `cd` every time.**

---

## Status: implementation is DONE and on disk. Verification is NOT.

`git status` (baseline commit `d0c5cb8 AI progress`):

```
 M Scripts/asset_pipeline/build_retarget.py    +88
 M Scripts/build_npc_blueprints.py             +82
 M Scripts/build_weapons_and_combat.py        +949
 M Scripts/forest_generator/npc_placement.py   +29
 M Scripts/verify_weapons_and_combat.py       +388
 M PROGRESS.md            (orchestrator's file — do not touch)
```

Nothing is committed. Do not commit; the orchestrator does that.

### What is left to do

1. **Rebuild and run the verifiers.** Build order is load-bearing:
   `build_retarget.py` WIPES and rebuilds `Anims/<Creature>/`, so
   `build_npc_blueprints.py` must run AFTER it.
2. All of these must pass in full: `verify_weapons_and_combat.py` (was 636/636
   before this task, plus ~40 new checks), `verify_graphics_menu.py` (118/118),
   `Scripts/generated_levels/Lvl_Forest_200m/verify_Lvl_Forest_200m.py` (172/172).
   **Leave `verify_shotgun_and_health.py` alone** — known pre-existing failure
   on a retired `BP_ShotgunComponent`.
3. `Scripts/uepy.py --game --seconds 35` → 0 blueprint runtime errors,
   0 "Accessed None", 0 script warnings, 10 NPC spawns.
4. **`CLAUDE.md` has NOT been updated** — `git diff CLAUDE.md` is empty. Add a
   short section on the hit reactions. This is outstanding work.
5. Report: design choice, final verifier numbers, runtime evidence, anything to
   eyeball in-game.

### Already done, do not redo

- The runtime probes fired and were **removed**. `HIT_REACT_PROBE = False` and
  the verifier permanently asserts both the switch is off and that neither
  probe prefix survives in the source (`verify_weapons_and_combat.py:1601-1608`).
- The verifier's hit-reaction section is written, as is the reworked AnimGraph
  section.

---

## The design, in short

**Epic's `MM_Death_*` set is not deaths.** Measured off the source assets: all
six are ~1 s, end with the pelvis at 83–88 cm and both feet on the floor, having
staggered 1.5–2 m backwards. They are flinches authored to blend into a ragdoll.
That is why this project's death is a physics ragdoll and nothing plays these at
0 HP — and it is exactly what a survivor being shot needs. Hence this task uses
them.

**Direction is load-bearing.** The six sort into a fixed order and the health
component picks by which side the round came from:

```
NPC_HIT_REACTION_CLIPS = (Front_01, Front_02, Front_03, Back_01, Left_01, Right_01)
HIT_DIR_FRONT = (0, 3)   HIT_DIR_BACK = (3, 1)
HIT_DIR_LEFT  = (4, 1)   HIT_DIR_RIGHT = (5, 1)   # (start index, count)
```

Three Fronts is what Epic shipped, and it is why the common case — shot from in
front — does not read as a loop. **The order is a contract:** it is defined once
in `Scripts/forest_generator/npc_placement.py` as `NPC_HIT_REACTION_CLIPS`,
imported by `build_weapons_and_combat.HIT_REACTION_CLIPS`, and positions in it
are baked into pin literals. Reordering silently plays a Left clip for a hit in
the back. All six or none — the pick indexes a six-entry array, so five of six
is a wrong clip rather than a missing one.

**Playback** is a dedicated `HitSlot` montage slot (`HIT_SLOT = "HitSlot"`),
distinct from the existing full-body slot, added by `_ensure_hit_slot(ed, aim_blend)`.

**Per-creature clips travel on the AI controller.** An AnimSequence belongs to
one skeleton and the three creatures are three skeletons; a child Blueprint's
override of an inherited component's defaults lives in an
`InheritableComponentHandler` the Python API cannot reach. So each variant's six
clips ride on its controller and are copied onto the pawn's health component at
possession — the same route the per-variant health already takes. Without this
every wanderer would flinch with `BP_ForestWanderer`'s mesh's clips, i.e. the
wendigos would not flinch at all.

**Hit direction** is a unit vector from victim toward source, stored in
`LastHitFrom` on `BP_HealthComponent`, written by whoever dealt the damage:
`_author_impact` derives it from the bullet's impact normal; the wanderers'
punch states it explicitly from the two actor locations already on the graph for
its range check. Whichever of the ten wanderers lands the blow writes its own
bearing, so being surrounded reads as hits from all sides, not one repeated stagger.

**Tunables** went into the `COMBAT` dataclass in `build_weapons_and_combat.py`
(the single home for combat tuning):

```
hit_react_cooldown_s: float = 0.45
hit_react_rate:       float = 1.4
hit_react_blend_s:    float = 0.08
```

### Key new symbols

- `build_retarget.py`: `hit_paths(name)`, `HIT_DIR`, `HIT_SOURCES`,
  `RETARGET_SOURCES` (now includes them). Module body is `__main__`-guarded so a
  verifier can import its tables without retargeting three creatures as a side
  effect.
- `build_weapons_and_combat.py`: `HIT_SLOT`, `HIT_REACTION_CLIPS`, `HIT_DIR_*`,
  `HIT_REACTIONS_VAR`, `LAST_HIT_FROM_VAR`, `PREV_HEALTH_VAR`, `NEXT_REACT_VAR`,
  `REACT_INDEX_VAR`, `_slot_name`, `_name_slot`, `_anim_nodes`, `_slot_node`,
  `_ensure_hit_slot`, `_author_hit_reaction`, `_author_ready_pose_keepalive`,
  `hit_reactions(mesh_asset)`, `install_hit_reactions(bp, health_handle)`.
- `npc_placement.py`: `NPC_HIT_REACTION_CLIPS`, `NpcVariant.reactions`.

### Findings recorded in the pose verifier

`_check_pose` gained exemptions for reaction clips, because the existing checks
encode what *grounded locomotion* looks like:
- A reaction is a **stagger** — the creature is knocked off its feet' rhythm and
  shoved 1.5–2 m back, so "feet alternate" and "pelvis stays put" would both
  assert it is *not* a reaction.
- A reaction may put the **head under the hips**. Measured on the wendigo, whose
  bind pose already pitches the neck 59° forward: head 73–105 against hips
  108–124 for about half a second. The zombie and the adventurer stay upright.
  That is a monster doubling over when shot.
- What must still hold: upright, the pelvis band, and head-above-feet. A
  reaction that folds a creature onto the floor would be a death, and this
  project's death is a ragdoll.

---

## Project rules that bind you

- Never open or edit `.uasset`/`.umap` as text.
- Builders under `Scripts/` are the source of truth; **nothing under `Content/`
  is committed**, so anything to persist must be authored by a builder.
- Every builder has a matching `verify_*.py`; new work needs real checks.
- **"A gate that never opens looks identical to one that works."** Any path the
  headless run does not execute must be proven with a temporary probe, which is
  then removed and its absence asserted by the verifier. (Already satisfied here.)
- Save edits to disk incrementally, not batched at the end.
- Do not commit or run state-changing git commands.

## API facts — do not rediscover

- UFunction object paths use a **colon**: `unreal.load_object(None,
  "/Script/Engine.PlayerController:SetDeprecatedInputYawScale")`. The dot form
  returns None. Cheap read-only way to probe whether an API exists.
- `_float_type()` must be `BEL.get_basic_type_by_name("real")` — `"float"` and
  `"double"` silently fall back to **int**.
- A Set node's data pass-through output pin is `Output_Get`.
- `GetComponentByClass` reshapes its return pin to the chosen class — no cast.
- Event Tick does not run while paused; `ReceiveDrawHUD` does.
- ForEach: `ed.add_macro_node("/Engine/EditorBlueprintResources/StandardMacros.StandardMacros:ForEachLoop")`.
- **The `A` pin of Kismet math nodes will not hold a literal** — `set_pin_value`
  reports success, the pin reads back empty, compiles as zero. Constants go on `B`.
- Impure nodes left off the exec chain are pruned; their output reads as the
  type default.
- `SetAllBodiesSimulatePhysics`, never `SetSimulatePhysics`, on a skeletal mesh.
- `GetController`, not the `Controller` member (not BlueprintReadOnly).
- `EditorLevelLibrary.get_game_world()` SIGSEGVs in a `-game` process — use
  `unreal.find_object(None, "<map>.<map>")`.
- Do not pass `-forcelogflush` to `-game`; it dilates the world clock.
- Niagara cannot be authored from Python in UE 5.8, and Cascade is gone.
- The creature rigs are Meshy 24-bone Mixamo-named (no fingers, no twist bones).

## Efficiency guidance for the resumed agent

The previous agent burned ~58M billed input tokens largely by holding the whole
of `build_weapons_and_combat.py` in context across 272 calls. Prefer
`sed -n 'START,ENDp'` and `grep -n` over whole-file reads, work from the
symbol list above, and let the verifier tell you what is wrong rather than
re-reading the file to check.
