# The NPCs (wanderers)

`Scripts/build_npc_blueprints.py` builds `/Game/Forest/NPC` from Python. It is idempotent and
rebuilds the AI graph and the Behavior Trees every run. The code is this package (`__init__.py` is
the map: one module per step fragment — stats, melee, chase, patrol, senses, agro, corpse — plus the
steps, the tree, the step task, the controller and the character).

- Every movement, melee and spawn-band number lives in `forest_generator/npc_placement.py`.
- Every sense and patrol number lives in `forest_generator/npc_agro.py`.
- The step between two swings is `forest_generator/npc_strafe.py`.
- None imports `unreal`, so the offline generator checks exactly what gets built.
- **The tunable ones are not pin literals.** Senses, patrol, run speed, melee damage/range/
  interval and health are `Tune*` variables on each controller (`tuned.py`), defaulted to
  `monster_tuning.monster_specs(key)`: `Scripts/npc/monster_tuning.csv` over the two files
  above. The M panel's MONSTER TUNING tab (`graphics_menu/CLAUDE.md`) writes them live and
  saves the CSV. A new tunable is a `MONSTER_STATS` row, a `stock_specs` entry, and the
  fragment reading it with `tuned()`.

`Scripts/verify_npc_blueprints.py` checks patrol, agro, the trees and the step between swings
(`verify.py`, `verify_tree.py`, `verify_strafe.py`). The level verifier owns the chase and the melee.
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
      Hunt [BB Aggro is set]    Chase (between swings: step off and round : MoveToActor : MoveToLocation) → Swing → Wait 0.5
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
  - It is a distance check (`TuneMeleeRange`, 200) plus a wall-clock cooldown per controller
    (`TuneMeleeInterval`).
  - It plays the creature's `NpcVariant.melee` into the upper-body-only `DefaultSlot`:
    the retargeted `MM_Attack_01`, except the zombie's, which is the Mixamo
    `A_Zombie01_Mx_Scary_ZombieAttack` (`asset_pipeline/import_mixamo.py`). Its own
    `MM_Attack_01` is the fallback when that clip is missing, and the never-spawned parent
    controller always holds it. `probes/probe_zombie_mixamo.py` proves the swing plays it.
  - Damage is dealt by writing `Health` on the player's component, because
    `ApplyDamage`/`AnyDamage` would need a graph on the Enhanced Input template character.
  - If `BP_HealthComponent` is missing, the NPC only chases.
  - A landed swing also stamps the player's `LastDamageTime` with the game time, after
    `LastHitFrom`. The HUD's save-and-exit countdown is called off by it.
  - **The player's guard** (`block.py`) sets the per-controller `HitDamage` before the Health
    write: a quarter of `TuneMeleeDamage` and 20 of the player's stamina when the player is
    `Blocking` and faces the swing (within 60°), otherwise `TuneMeleeDamage` (10). See `Scripts/combat/docs/stance.md`, "Blocking".
- **Between two swings it moves** (`strafe.py`, numbers in `forest_generator/npc_strafe.py`):
  - It is the head of the Chase step, not a step of its own. With the player within 4.5 m and
    the cooldown in its first 60%, the step sends the wanderer 210–280 cm from the player and
    25–60° round from where it stands, left or right, at 45% of its run speed. The rest of the
    cooldown is the ordinary chase, which brings it back into reach for the next swing, so the
    swing rate is unchanged. Every creature does it.
  - **One pick per swing, stored** (`StrafeYaw`, `StrafeDist`), because the random nodes are
    pure. `StrafeFor` holds the `NextAttackTime` the pick was made for; the swing itself has no
    new wire. The point is taken from where the two stand on each pass, so a long cooldown
    carries it on round the player.
  - **It faces the player while it steps:** `SetFocus(player)` (Gameplay priority, which beats
    the Move focus path following sets), with `bOrientRotationToMovement` off and
    `bUseControllerDesiredRotation` on. The chase arm writes both back and clears the focus.
    They are written on the pawn at run time, so the character Blueprint is untouched.
  - The order is `SimpleMoveToLocation`, like the stroll (the level verifier counts the chase's
    two orders). **It needs a navmesh:** without one the wanderer stands where it swung.
  - `verify_strafe.py` checks the graph; `probes/probe_npc_strafe.py` watches a zombie do it.
    A headless `-game` run was found with **no navmesh tiles and none being built**; the probe
    sends `RebuildNavigation` and waits. Not looked into further.
  - **Feel check (needs a play session):** the body plays its forward walk while it moves back
    and sideways (the anim Blueprints blend on speed only), so the feet slide a little.
- **The corpse state** (`corpse.py`):
  - It checks the pawn's `Dead` before anything else, every pass.
  - Then: `Corpse = true`, `StopMovement`, one `[NPC-CORPSE]` line, and `StopLogic`: the tree
    ends. (Called inside a running task, the stop is queued until the task returns.)
  - **Every other step starts at the alive gate** (`_author_alive_gate`, which `_Steps.event`
    puts at the head of each step event): no pawn, or a dead one, and the step fails without
    acting. The tree runs one step a frame, so a wanderer killed after its Pulse still had
    that pass's Chase and Swing to come, and a body on the ground could land one more blow.
    The failed pass falls through to Idle, and the next Pulse ends the tree.
  - Dead is `Dead OR Health <= 0` in both gates (`_dead_pin`): `Dead` is written by the health
    component's Tick, which on the frame of the killing blow may not have run yet.
  - The gate's living arms meet in a `StepResult = false` write, so a step still hangs off
    one exec pin. It is only the default: every exit of the step writes its own.
  - `probes/probe_dead_no_actions.py` calls the Swing step directly: alive it hits the
    player, marked Dead or at 0 HP it does not.

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
| `NPC_RESPAWN_DELAY_S` | 10 | how long a kill leaves the pack one short; must stay under the corpse's 60 s (`combat/docs/health.md`) |
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
  - Write speeds from the stored `RunSpeed`, never from the live `MaxWalkSpeed`:
    `RunSpeed × TuneRunSpeed / stock [× TunePatrolSpeed]`, where stock is the creature's built
    run speed, so the level's per-instance gait survives the tuning. The Chase and Stroll steps
    write it every pass (after their move order); aggro and the setup no longer do.
- **Noise** is one record on the GameMode (`Noise*`, written by `combat/noise.py`).
  - A new noise overwrites the record only if the old one is older than `noise_hold_s` (0.6 s,
    which must outlast the tree's 0.5 s beat) or the new one is at least as loud.
  - **Gunshots:** the reach is the weapon's `ShotVolume` (`SHOT_VOLUME_CM`: sniper 150 m, rifle
    90, shotgun 85, SMG 50, pistol 35), plus a 1.6× cone within 30° of the shot's line.
  - **Footsteps (player only):** 12 m at a run, 18 m sprinting, 6 m while aiming.
- **Every transition logs `[NPC-AGRO] <sense> -- <actor>`, in debug mode only.** The line is a
  `PrintWarning`, which also puts it on screen, so it is gated on the GameMode's `DebugMode`.
- **Debug mode also draws each live wanderer's sight (aggro) cone** (`sight_cone.py`): from the
  pawn, along its forward vector, `TuneSightRange` long and `TuneSightHalfAngle` either side —
  the sight sense's own inputs, so the MONSTER TUNING tab moves the cone and the sense together.
  Yellow on patrol, red once aggro.
  - It is the controller's own **Tick**, not a tree step: the steps run on the tree's 0.5 s
    beat. One frame per draw (`Duration` 0). Gates are nested Branches: `DebugMode`, a pawn,
    not `Corpse`.
  - It is a full cone because the test is a 3D dot product. It doesn't show line of sight
    (a trunk still hides the player), touch or hearing.
  - Each draw stamps `SightConeDrawnAt` with the game time, which is how
    `probes/probe_sight_cone.py` sees the draw in a headless game. `verify_sight_cone.py`
    checks the graph.
  - To look at a debug draw, run a `--game --windowed` probe that sends the console command
    `Shot showui` (lands in `Saved/Screenshots/MacEditor`). `HighResShot` leaves debug lines
    and the HUD out, and `AutomationLibrary.take_high_res_screenshot` writes nothing there.

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
