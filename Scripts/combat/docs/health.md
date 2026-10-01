# Combat: health, respawn, dying, hit boxes and blood

Part of `Scripts/combat/CLAUDE.md`, which indexes it.

## Health, respawn and the pack's numbering (`health_component.py`, `respawn.py`)

- **Respawns land 75–100 m from the player's current location.**
  - The band point is a *request*, stored in `RespawnPoint`, because the projection node is pure.
  - It is projected onto the navmesh (`RESPAWN_PROJECT_EXTENT`, 30 × 30 × 100 m).
  - Z is then **re-traced onto real collision** (`RESPAWN_TRACE_UP`/`_DOWN`; the trace starts only
    2 m up, to miss canopies) and lifted by the 88 cm capsule half-height, because navmesh Z can be
    86 cm low.
  - It spawns with `AdjustIfPossibleButAlwaysSpawn`.
  - `RESPAWN_ATTEMPTS` (2) bearings are tried, then any navigable point near the player. If that
    fails too, the wanderer is not replaced.
- **World-floor net:** anything below `WORLD_FLOOR_Z` (−1000 cm) gets `Health = 0` and dies the
  ordinary way. The player too: walking off the map kills you. `DespawnOnDeath` gates only the
  `[NPC-FELL]` log line.
- **Numbering:**
  - Each wanderer takes `NpcSpawnCount` from the GameMode into its own `NpcId` and logs
    `[NPC-SPAWN] #n at …`.
  - Set `NpcId` **first**, then write the counter back from `NpcId`. The other order numbers the
    first one 2, because the add is pure.
  - `[NPC-FELL] ERROR #n fell to … — spawned at …` quotes the stored `SpawnedAt`, which is for
    diagnosis only.
  - Both lines are `PrintWarning` (Blueprint has no Error severity) and appear in the log only.
- **Debuff drain** (`debuff_drain.py`) sits between the net and the death check.

## Dying

- **Everything collapses into a ragdoll** (`_author_death_collapse`):
  `DisableMovement` → capsule `NoCollision` → mesh profile `Ragdoll` → `SetAllBodiesSimulatePhysics`.
  - Use `DisableMovement`, not `DisableInput`: the HUD polls restart off the controller.
  - Turn off the capsule, not the mesh, because it is the capsule that blocks and is traced.
  - Set the profile **before** simulating.
  - `SetSimulatePhysics` would simulate only the root body.
- **There is no death animation, and none is possible.** Meshy rigs ship only walk and run, and
  the `MM_Death_*` clips are staggers that end standing.
- **The ragdoll joints are tuned** (`ragdoll.tune_ragdolls()`), for every mesh under
  `/Game/Sourced/Characters`.
  - The importer's `create_physics_asset` gives soft 45° cones centred on the bind pose, so limbs
    fold both ways.
  - `RAGDOLL_JOINTS` gives each role a one-sided flex range. `ragdoll_plan()` builds both frames
    from the reference pose:
    - a ball joint has X along the bone and Y as the flex axis;
    - a hinge has X as the flex axis;
    - an off-centre range turns the parent frame (PA_Mannequin's trick);
    - springs are 500/50 for ball joints and 1000/100 for hinges.
  - Write through `unreal.find_object(pa, "PhysicsConstraintTemplate_N")` →
    `set_editor_property("DefaultInstance", …)`. The property-change notification is required,
    or the edit reverts on save.
  - `ConstraintInstanceBlueprintLibrary` has no frames. `AngularRotationOffset` is ignored by
    physics assets.
- **Corpse loot** is rolled on the counted-kill arm, after the gun drop (`loot/roll.py`, see
  `Scripts/loot/CLAUDE.md`). It lives on the corpse's health component and goes with it.
- **A wanderer's corpse** (`_author_corpse`, on the `DespawnOnDeath` arm):
  `GetController` → `SetLifeSpan(controller, 0.1)` → `Owner.SetLifeSpan(60)`.
  - **`DestroyActor` on a controller is a no-op from Blueprint** (overridden empty in
    `Controller.cpp`). A lifespan calls the real `Destroy()`.
  - Use `GetController`, not the `Controller` member (not BlueprintReadOnly).
  - Use `SetLifeSpan` rather than a `Delay` owned by the actor being destroyed.
  - The corpse state itself is `npc/corpse.py`.
- **The player's death:**
  - collapse → `Delay 2.2` → `GameMode.PlayerDead` → `[PLAYER-DEAD] killed with N` → pause.
  - The delay is also the ragdoll's settle time.
  - The HUD draws YOU DIED, the kill count and `[R] try again`. That unpauses **before**
    `OpenLevel`; a level opened paused stays paused.
  - Restart is polled from `DrawHUD`, which runs while paused.
  - `FullBodySlot` is spliced into `ABP_Unarmed` and asserted, though nothing plays into it yet.
- **The dead do nothing** (`weapon_component/dead.py`): the weapon component's Tick starts at a
  gate on its owner's health component, `Dead OR Health <= 0`, and a dead owner gets none of
  it. Through the 2.2 s collapse the Tick used to poll every key: a dead player fired,
  reloaded, switched, threw and ate.
  - It is one gate at the head, not a term in each action's condition. A new action added to
    the Tick is covered without knowing about it.
  - `Health <= 0` as well as `Dead`, because `Dead` is written by the health component's own
    Tick: on the frame of the killing blow either component may tick first.
  - The dead arm lets go of what the Tick was holding (`Aiming`, `SightAiming`, `Sprinting`,
    `Blocking`), snaps the zoom and the camera home, and shows a body and gun a scope had
    hidden. It snaps because the eases live in the Tick that no longer runs.
  - The verifier's `wg` is the **living** Tick. `fixtures.py` keeps the dead arm apart as
    `wg_dead`, so "written once" checks stay about the living Tick; `verify/dead.py` checks
    the gate and the arm.
  - `OwnerDead` is the gate's answer, for others that act for the player. The HUD's loot
    window reads it (`graphics_menu/loot_tick.py`): a dying player searches nobody.
  - `FireForced` is a probe's stand-in for the fire key's press.
    `probes/probe_dead_no_actions.py` fires with it alive, and cannot dead.
  - A wanderer has the same rule in its steps (`Scripts/npc/CLAUDE.md`, "The corpse state").
- **Combat trace:**
  - Toggle it in the console with `ke * CombatTraceOn` / `CombatTraceOff`, or set
    `COMBAT_TRACE_DEFAULT`.
  - It logs one `[COMBAT-TRACE]` line per landed swing.
  - The flag is on the GameMode. `combat_trace.py` **owns the GameMode's EventGraph** and wipes it
    every build.
  - The level verifier allows only the `[COMBAT-TRACE]` and `[NPC-CORPSE]` PrintStrings.
  - **Known, unfixed:** a wanderer can land one more swing on a player already at 0 HP.

## Hit boxes and hit reactions

- **The capsule decides whether a character was hit; the physics asset decides where.**
  - `_author_hit_zone` retraces the same line with `K2_LineTraceComponent` against the struck
    `Mesh`. This ignores channels, but the mesh needs query collision
    (`install_hit_zones` raises otherwise).
  - Head is ×1.5 and limbs ×0.75 (`COMBAT.head_multiplier`/`limb_multiplier`). A trace through the
    capsule that finds no body counts ×1.
- **Hit tables are derived per character.** `HeadBones`/`LimbBones` on each character's
  HealthComponent template come from `hit_zones(mesh)`:
  - bodies come from the physics asset's **constraints**, because `SkeletalBodySetups` is protected;
  - each is zoned via `BoneIsChildOf` on a transient component.
- **Characters must be shootable.** `make_shootable()` sets the capsule to block Visibility (see
  the root gotcha about `Pawn` ignoring it).
- **Hit reactions** (`hit_reaction.py`, on the death branch's False arm) poll
  `Health < PrevHealth`. The flow:
  - Check the cooldown `hit_react_cooldown_s`.
  - Pick a direction from `LastHitFrom` (a unit vector towards the source; zero counts as Front).
  - Play the montage into `HitSlot`.
  - Set `PrevHealth = Health` on every arm.
- **The clips are Epic's `MM_HitReact_*`, not `MM_Death_*`**, which carry the head up to 2.2 m.
  - The verifier measures every clip, including the retargeted copies: head under 30 cm, chest
    under 60°.
  - Left and right reuse `Front_Hvy_01` and `Front_Lgt_04`, chosen by head motion.
- **Order contract:** `NPC_HIT_REACTION_CLIPS` in `forest_generator/npc_placement.py` is the one
  definition, and the graph bakes its indices (`HIT_DIR_*`). It is all six clips or none; an empty
  array means no flinch.
- **`HitSlot` is its own slot**, created by `_ensure_hit_slot` behind a second `LayeredBoneBlend`,
  because `DefaultSlot` holds the ready pose.
  - All slots share one montage group, so a flinch stops the ready pose.
  - `_author_ready_pose_keepalive` restarts the ready pose when both slots are quiet. It is
    required.
- **Each wanderer variant's clips travel on its AI controller** and are copied at possession,
  because a child BP's inherited component override is unreachable from Python.
- **Debuff drain:** `debuff_drain.py` lowers `PrevHealth` along with `Health`, so starving is not
  read as a hit.

## Blood (`blood.py`)

- **19 lit droplets:** 14 of spray in a 34° cone plus 5 slow ones.
  - `M_Blood` is linear `(0.150, 0.014, 0.012)`, roughness 0.22, not emissive.
- **Flight uses the closed form of `dv/dt = g − k·v`** (k = 3.6/s, g = 980):
  - `A(t) = (1 − e^(−kt))/k` and `B(t) = (t − A)/k`;
  - `local = Velocity·A + Fall·B`;
  - fade `clamp((0.45 − Age)/0.14, 0, 1)`.
- **Launch velocity is baked into each droplet's build-time relative location** (÷100). The layout
  comes from a fixed seed, so the verifier recomputes it.
- **The impact spawns it rotated to the surface normal** (`MakeRotFromX`), scaled by
  `clamp(Damage/24, 0.65, 1.6)`.
- **Not Niagara:** Python can't build or retune an emitter stack in 5.8.
- **Trap:** a Kismet math node's **A** pin won't hold a literal. Keep constants on B, e.g.
  `(e^(−kt) − 1)/−k`.
