# The NPCs (wanderers)

`Scripts/build_npc_blueprints.py` builds `/Game/Forest/NPC` from Python. It is idempotent and
rebuilds the AI graph and the Behavior Trees every run. The code is this package (`__init__.py` is
the map: one module per step fragment — stats, melee, chase, patrol, senses, agro, corpse — plus the
steps, the tree, the step task, the controller and the character).

- Every movement, melee and spawn-band number lives in `forest_generator/npc_placement.py`.
- Every sense and patrol number lives in `forest_generator/npc_agro.py`.
- Neither imports `unreal`, so the offline generator checks exactly what gets built.

`Scripts/verify_npc_blueprints.py` checks patrol, agro and the trees (`verify.py`,
`verify_tree.py`). The level verifier owns the chase and the melee.
`Scripts/probes/probe_npc_behavior_tree.py` proves the trees run in the game.

Respawn, the world-floor net and the `[NPC-SPAWN]`/`[NPC-FELL]` numbering are in
`BP_HealthComponent`. See `Scripts/combat/CLAUDE.md`.

## The brain: a Behavior Tree per controller (`tree.py`, `steps.py`, `step_task.py`)

```
OnPossess → RunBehaviorTree(BT_<controller>)

Wanderer (selector)
  Alive (sequence)
    Pulse            [possessed? no: fail] → [dead? corpse, StopLogic] → stats → patrol setup
    Act (selector)
      Hunt [BB Aggro is set]    Chase (MoveToActor : MoveToLocation) → Swing → Wait 0.5
      Notice                    PlayerPresent → Senses (selector): Hurt, Sight, Touch, Sound
      Patrol                    Stroll → Wait 0.5
  Idle: Wait 0.5
```

- **The tree decides; the controller does the work.** Each step is a custom event on the
  controller, `BT_<Step>`, authored from the same fragments the old Delay loop used. One task
  Blueprint per controller, `BTT_<controller>_Step`, has an instance-editable `Step` name: it
  casts `OwnerController`, calls `BT_<Step>` and finishes with the controller's `StepResult`.
  Each tree node sets `Step` and its node name, which is what the BT editor shows.
  - One task class per controller because the controllers are separate Blueprints (not children
    of one), and Python can't add a Blueprint interface. So one tree per controller too.
  - **Every exit of every step writes `StepResult`** (`verify_tree.py` walks them). A dangling exit
    leaves the last step's result, and the tree takes the wrong branch.
  - **A step runs to its end in one call:** no Delay, no latent node. The task reads
    `StepResult` straight after the call.
- **The senses' priority is the Senses selector's child order.** Adding a sense is a fragment
  in `agro._author_agro_steps`'s table and a `SENSE_STEPS` entry (`paths.py`): the event, the
  task's dispatch, the tree node and the verifier's expected order all follow.
- **Aggro lives on the controller and is mirrored into the Blackboard** (`BB_ForestWanderer`:
  `Aggro`, `AggroReason`) when a sense fires. The Hunt branch's decorator reads the Blackboard.
  A sense that fires makes Notice succeed; the next pass (next frame) takes Hunt.
- **The tree is authored as the runtime tree** (`RootNode`, `Children`), because Python can't
  build the BT editor's graph nodes. An asset with no editor graph gets one built from the
  runtime tree when first opened in the BT editor (`UBehaviorTreeGraph::OnCreated`), so it still
  shows and debugs. **Edits made in the BT editor are overwritten** — and a saved editor graph
  would be written back over the runtime tree, so the builder deletes and recreates each `BT_*`.
- **Build order matters** (`controller.py`): empty the step task and compile the empty controller
  (or the dependent task logs a compile error per stale call), recreate the tree, author the
  steps, compile, build the task (its cast needs the compiled controller), fill the tree.
- **Python traps met here:**
  - A by-reference `Name` pin (the Blackboard's `KeyName`) takes no literal, and
    `EqualEqual_NameName` is a wildcard until wired. Feed both from `MakeLiteralName`
    (`graph._name_literal`).
  - `BlackboardKeyType_Bool`/`_String` aren't exposed as `unreal.*`: `unreal.load_class(None,
    "/Script/AIModule.BlackboardKeyType_Bool")`, then `new_object(kind, bb)`.
  - `set_editor_property` writes `BlueprintReadOnly` properties (only `EditConst` is refused),
    which is what lets Python write `RootNode` and `Children`.
  - `BTTask_Wait.wait_time` is a `ValueOrBBKey_Float`: write its `default_value`.
- **Melee is the Swing step**, right after Chase, not given its own Tick.
- **Every exit of the melee chain reaches the Swing step's `StepResult`,** including both
  cast-failure pins.
- **Melee:**
  - It is a distance check (`NPC_MELEE_RANGE_CM` 200) plus a wall-clock cooldown per controller.
  - It plays `MM_Attack_01` into the upper-body-only `DefaultSlot`.
  - Damage is dealt by writing `Health` on the player's component, because
    `ApplyDamage`/`AnyDamage` would need a graph on the Enhanced Input template character.
  - If `BP_HealthComponent` is missing, the NPC only chases.
  - A landed swing also stamps the player's `LastDamageTime` with the game time, after
    `LastHitFrom`. The HUD's save-and-exit countdown is called off by it.
  - **The player's guard** (`block.py`) sets the per-controller `HitDamage` before the Health
    write: 2.5 and 20 of the player's stamina when the player is `Blocking` and faces the swing
    (within 60°), otherwise 10. See `Scripts/combat/docs/stance.md`, "Blocking".
- **The corpse state** (`corpse.py`):
  - It checks the pawn's `Dead` before anything else, every pass.
  - Then: `Corpse = true`, `StopMovement`, one `[NPC-CORPSE]` line, and `StopLogic`: the tree
    ends. (Called inside a running task, the stop is queued until the task returns.)

## The character (`BP_ForestWanderer`)

- **It mirrors the player's rig setup** (mesh at z −89, yaw 270, a retargeted `ABP_Unarmed`
  per creature).
- **`use_acceleration_for_paths` must be True.** When it is False, `Acceleration` stays zero,
  and `ABP_Unarmed` gates on it: the NPC glides in its idle pose.
- **The variants are `BP_Wanderer_<Creature>`**, children of `BP_ForestWanderer`, listed in
  `npc_placement.NPC_VARIANTS`.
  - A child's inherited-component override is unreachable from Python, so per-variant values
    (health, hit-reaction clips) travel on the controller and are copied at possession.
  - Changing the parent's components leaves the children dirty. Recompile and save them too
    (see `survival/install.py`).

## The pack (`npc_placement.py`)

| dial | value | constraint |
|---|---|---|
| `NPC_COUNT` | 10 | |
| `NPC_RUN_SPEED_CMS` | 600 | the top of the blend space; the player sprints at 900 |
| `NPC_SPAWN_MIN/MAX_DISTANCE_CM` | 7500 / 10000 | clamped to `npc_usable_radius` (80 m on the 200 m map); `spawn_band()` is the only decider, and its check reports the band used |
| `NPC_MIN_SEPARATION_CM` | 600 | |
| `NPC_ACCEPTANCE_RADIUS_CM` | 120 | **must stay below** the melee range, or they park out of reach |
| `NPC_MELEE_DAMAGE` / `_INTERVAL_S` | 10 / 1.5 | balanced for the **pack** (~67 dps if all ten connect) |

## Patrol and agro (`patrol.py`, `senses.py`, `agro.py`)

- **They spawn patrolling.** A patrolling NPC strolls within `patrol_radius_cm` of its spawn point
  (zombie 15 m, wendigo 30 m) at 30% of its own run speed, re-picking a point every
  `patrol_repick_*`.
- **Aggro is a one-way switch:** once `Aggro` is set it is never cleared, and the NPC runs.
- **The senses** (per creature, from `npc_agro.py`):

  | sense | trigger |
  |---|---|
  | hurt | `DamagedByPlayer` |
  | sight | within range and half-angle, **and** `LineOfSightTo` (trunks hide the player) |
  | touch | within `touch_range_cm` |
  | sound | the latest noise's reach × `hearing_scale` |

- **Patrol traps:**
  - **NPCs that stand still while patrolling mean there's no navmesh under them.** Check that
    first, in the world you're playing: `PatrolTarget == PatrolHome` and
    `get_random_reachable_point_in_radius` returning `None`. See `bForceRebuildOnLoad` in
    `forest_generator/CLAUDE.md`. `verify_npc_blueprints.py` passes regardless, because it checks
    only the graph.
  - `GetRandomReachablePointInRadius` is pure. Read only `RandomLocation`, once, into
    `PatrolTarget`.
  - On failure it returns the centre, or the zero vector (the player's spawn). Refuse points
    outside `radius × 1.1 + 2 m`.
  - Stroll with `SimpleMoveToLocation`. The level verifier counts exactly one `MoveToActor` and one
    `MoveToLocation`.
  - Write speeds from the stored `RunSpeed`, never from the live `MaxWalkSpeed`.
- **Noise** is one record on the GameMode (`Noise*`, written by `combat/noise.py`).
  - A new noise overwrites the record only if the old one is older than `noise_hold_s` (0.6 s,
    which must outlast the tree's 0.5 s beat) or the new one is at least as loud.
  - **Gunshots:** the reach is the weapon's `ShotVolume` (`SHOT_VOLUME_CM`: sniper 150 m, rifle
    90, shotgun 85, SMG 50, pistol 35), plus a 1.6× cone within 30° of the shot's line.
  - **Footsteps (player only):** 12 m at a run, 18 m sprinting, 6 m while aiming.
- **Every transition logs `[NPC-AGRO] <sense> -- <actor>`, in debug mode only.** The line is a
  `PrintWarning`, which also puts it on screen, so it is gated on the GameMode's `DebugMode`.

## Following to the edge of the map

- **The navmesh covers the whole terrain.** See `forest_generator/CLAUDE.md`. An uncovered ring
  used to make the pack stall at an invisible line, because a partial-path `MoveToActor`
  "succeeds" at the navmesh edge.
- **The straight-line fallback** handles the last metre or two of steep corner ramp.
  - Twice a second, both ends are projected, using a 200 cm XY by 400 cm Z box. A loose box snaps
    and lies.
  - If either end misses, the same move is re-issued with `bUsePathfinding` off.
  - `bProjectDestinationToNavigation` **must stay false**.

## Probing live NPCs

- **`set_editor_property` refuses Blueprint variables on a live object.** The console's
  `setnopec <object> <prop> <value>` works.
- **Plain `set` on a component class re-runs every owner's construction script.**
- **For class-wide values, write the CDO and reopen the level.** See the root gotchas.
