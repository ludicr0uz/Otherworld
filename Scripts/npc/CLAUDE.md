# The NPCs (wanderers)

`Scripts/build_npc_blueprints.py` builds `/Game/Forest/NPC` from Python. It is idempotent and
rebuilds the AI graph and the Behavior Trees every run. The code is this package (`__init__.py` is
the map: one module per step fragment — stats, melee, chase, patrol, senses, agro, corpse — plus the
steps, the tree, the step task, the controller and the character).

Graphs are authored with `Scripts/uebp` (root `CLAUDE.md`): no coordinates, node paths from
`uebp.nodes`; `npc/graph.py` keeps only `_log`, `_Graph` and `_mesh_object`.

- Every movement, melee and spawn-band number lives in `forest_generator/npc_placement.py`.
- Every sense and patrol number lives in `forest_generator/npc_agro.py`.
- The step between two swings is `forest_generator/npc_strafe.py`.
- The wendigo's hunt is `forest_generator/npc_stalk.py`.
- What fire does to it is `forest_generator/npc_ward.py`.
- The fire that draws a zombie is `forest_generator/npc_drawn.py`.
- Who is silent on patrol (the wendigo) is `forest_generator/npc_voice.py`.
- None imports `unreal`, so the offline generator checks exactly what gets built.
- What a landed swing can leave on the player (a wendigo's: bleeding, 33%) is
  `survival/on_hit.py`, rolled at the end of `melee.py` by `survival/on_hit_graph.py`. The
  controllers name `GE_Bleeding`, so this build runs after `build_survival.py`
  (`Scripts/survival/CLAUDE.md`; checked by `verify_on_hit.py`, `probes/probe_bleeding.py`).
- **The tunable ones are not pin literals.** Senses, patrol, run speed, melee damage/range/
  interval and health are `Tune*` variables on each controller (`tuned.py`), defaulted to
  `monster_tuning.monster_specs(key)`: `Scripts/npc/monster_tuning.csv` over the files
  above. So are the wendigo's hunt (`TuneStalk*`: charge range, catch-up range, how far the player may run, leg speed,
  the wait behind a tree, the time between turns) and what fire does to it (`TuneWard*`:
  range, cone, ring, prowl speed, the time between turns, the hold, the flight). Every
  controller has those variables, but only a creature with the Stalk or Ward step reads
  them. The rest of `npc_stalk.py` and `npc_ward.py` (the cover search, the trunk width,
  the roar) are still literals, and the numbers quoted in the sections below are the built
  defaults. The M panel's MONSTER SETTINGS tab (`graphics_menu/CLAUDE.md`) writes them live and
  saves the CSV. A new tunable is a `MONSTER_STATS` row, a `stock_specs` entry, and the
  fragment reading it with `tuned()` (`tuned_pin()` in a `_Graph` fragment; a speed share is
  `_author_walk_speed(scale="<column>")`), then the CSV rewritten with the new column
  (`write_table` over `monster_specs`) and both builds. A check or a probe of a tuned number
  reads `_fed(node, pin, column)` or `monster_specs(key)`, never the literal: a saved tuning
  must still pass.

`Scripts/verify_npc_blueprints.py` checks patrol, agro, the trees, the step between swings and
the wendigo's hunt and the fire that holds it off, and the fire that draws a zombie (`verify.py`, `verify_tree.py`, `verify_strafe.py`, `verify_stalk.py`, `verify_stalk_cover.py`, `verify_ward.py`, `verify_ward_roar.py`, `verify_drawn.py`). The level verifier owns the chase and the melee.
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
                                (the wendigo: Approach (selector): Stalk, Chase → Swing → Wait 0.5,
                                 and ahead of it all: Engage (selector): Ward, Attack (sequence):
                                 Approach, Swing → Wait 0.5)
      Notice                    PlayerPresent → Senses (selector): Hurt, Sight, Touch, Sound
      Patrol                    Stroll → Wait 0.5
                                (the zombie: Wander (selector): Drawn, Stroll → Wait 0.5)
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
    sends `RebuildNavigation` and waits. The cause was a `RecastNavMesh` saved into the map
    (`forest_generator/CLAUDE.md`, Navmesh).
  - **Feel check (needs a play session):** the body plays its forward walk while it moves back
    and sideways (the anim Blueprints blend on speed only), so the feet slide a little.
- **The wendigo hunts before it chases** (`stalk.py`, `stalk_cover.py`, numbers in
  `forest_generator/npc_stalk.py`):
  - It is one more step, `BT_Stalk`, ahead of Chase in a selector of the two. Only the
    creatures in `NPC_STALK_ROAR` get the event, its variables and the tree node; a new
    stalker is a row there (its roar clip) and an entry in `mixamo_paths.ROAR_CREATURES`.
  - **It roars again as it charges, with its voice alone.** The one `StalkCharging` write
    (close enough, the player run off, stalled, nowhere to go) plays one of its `Voices`
    and fails the step on that same pass: no clip and no stand, so Chase orders the run
    at once. An enraged one has its own voice (below) and never gets here.
  - **The step succeeds while it hunts and fails for good to charge.** A pass that succeeds
    has given its own move order, so Chase is not reached; once `StalkCharging` is set the
    step fails first thing, every pass, and the chase (and its strafe) is all that runs.
  - **Roar:** the first pass stops it, faces the player, and plays the roar clip into
    `DefaultSlot` (upper body, like the swing) and one of its `Voices`. It stands 2.4 s. The
    clip is the Mixamo Scary pack's zombie scream, retargeted onto the wendigo alone by
    `import_mixamo.py`; without it the roar is sound only.
  - **Legs are run at 169% of its run speed** (`NPC_STALK_RUN_SCALE`: 130%, and 30% on top;
    a tuned 690 cm/s is 1166, faster than the player's sprint of 900), written after the
    order and on every pass of a leg. The Chase step writes the run speed back on its first
    pass, so the charge is at the run.
  - **Past 150 m it does not stalk** (`NPC_STALK_CATCH_UP_CM`): once it has roared, a pass
    that far from the player orders it straight at them (`SimpleMoveToLocation`, their
    spot) at the speed of a leg, zeroes `StalkLegUntil` and succeeds. The first pass inside
    picks a leg. An enraged one never gets there: it charges, at its run.
  - **A player who runs off is charged** (`NPC_STALK_FLED_CM`, `TuneStalkFled`: 30 m). The
    roar stores where the player stands (`StalkOrigin`); once it has roared, a pass that
    finds them further than that from the spot (flat) sets `StalkCharging` and fails, ahead
    of the catch-up and the legs, whatever it was doing. It is measured from the roar's
    spot, not from the wendigo: a player who walks about inside 30 m is still hunted. A
    flight from fire zeroes `StalkRoarUntil`, so the next hunt's roar takes a new spot.
    `probes/probe_wendigo_fled.py` watches it; `probe_wendigo_catch_up.py`, which stands
    the player in a far corner, writes `StalkOrigin` there so it still tests the catch-up.
  - **The way round alternates.** `StalkSide` is a coin at the roar, and `StalkTurnAt` a
    game time thrown with it (the roar's end + 4–9 s). The first leg picked once that time
    is up goes the other way and throws the next (now + 4–9 s). It turns only at a pick,
    never in the middle of a leg or of a wait: a leg and its wait are 3–8 s, so it is one
    to three legs each way.
  - **Shot, it is enraged** (`Enraged` on the controller, never cleared): the step's first
    Branch fails it, so there is no roar, no tree and no arc, only the Chase. What sets it
    is the hurt sense's own flag (`DamagedByPlayer`: a pellet, a blade, a fist), read by
    `senses._author_hurt` right behind that Branch, with one of its voices the once. It is
    a latch of its own, apart from `StalkCharging`, which a flight from fire clears: a
    shot wendigo comes back from a flight charging. **Fire still holds an enraged one
    off** (the Ward step is ahead of the whole attack).
  - **Legs:** each leg sweeps a
    3 m sphere along a line at the player, 35 / 50 / 20° round them from where it stands,
    from 3 m to 18 m closer (half as far and as wide again as the 12 m and 2 m it began
    with). The first tree struck is the candidate; the spot is 170 cm past
    its trunk, seen from the player. It runs there (`SimpleMoveToLocation`), waits 1–2.5 s
    facing the player, and picks the next. No cover on any line: a leg 6 m closer in the
    open.
  - **In the open it never stops.** A leg with no tree at its end is over 7 m short of its
    spot (`NPC_STALK_OPEN_ARRIVE_CM`: more than it runs in the half second between two
    passes), and that same pass picks the next leg, so the new order arrives while it is
    still running. Before, it ran the leg out, stood, and was re-ordered a pass or two later.
  - **A tree is an instanced mesh the sweep struck** (as for the axe), and it stands where
    `GetInstanceTransform(HitItem)` says. Never the impact point: the sphere mostly touches
    crowns, metres from the trunk, and a sweep that starts inside one has no impact point.
  - **Not every tree is cover.** A sapling's stem is a few centimetres across, its twigs
    are seen through, and the island trees lean off their own foot. Two tests:
    - **The trunk is as wide as the wendigo**: 45 cm at chest height
      (`NPC_STALK_TRUNK_MIN_CM`). `NPC_STALK_TRUNK_CM` holds each planted species' width
      there at scale 1, measured with line traces across the trunk in the level, and
      `cover_trees()` turns it into the least scale per mesh. The graph tells the mesh by
      its name (`GetObjectName` of the cell's `StaticMesh`) and reads the scale off the
      instance's transform. The pine sapling (1.2 cm a unit of scale) is never cover; the
      small deciduous tree is from 3.2x; the fir and the island trees nearly always are.
      **A new species needs a row**, or the verifier fails.
    - **A line from the spot to the player strikes that same tree** (the same component
      and `HitItem`). It used to be any tree: trees collide by their own triangles
      (`CTF_UseComplexAsSimple`), leaves included, so a sapling's twigs ten metres further
      on counted as a hiding place.

    And the spot is at least 1 m closer than the wendigo stands, no nearer the player than
    12 m (outside the charge range, or the run there would set the charge off), and on the
    navmesh.
  - **An object pin of `Equal (Object)` takes no asset literal** (`set_pin_value` reads back
    empty), which is why the mesh is compared by name.
  - **The sweep ignores what the pawn stands on** (`GetMovementBaseActor`: the terrain, one
    mesh, which a sphere that wide drags along on any slope) and the pawn: `bIgnoreSelf` in a
    controller graph is the controller.
  - **It never stands.** Within 10 m it charges; so does a leg it is not moving on half a
    second after the order (no path), and a pick with no cover and no navmesh under the open
    spot either. Before that rule, an open spot off the navmesh was re-picked every pass and
    the wendigo stood at 30 m for good. A leg still running after 6 s is re-picked.
  - `verify_stalk.py` checks the graph (`verify_stalk_cover.py` the next tree);
    `probes/probe_wendigo_stalk.py` watches one hunt
    (with whatever turns fall in it); `probes/probe_wendigo_rage.py` makes a turn come due
    and shoots one on its hunt and one on patrol; `probes/probe_wendigo_catch_up.py` stands
    the two in opposite corners of the map, 250 m apart.
    `verify.py` and `verify_strafe.py` count a controller's nodes outside this step
    (`outside_step`), so their counts are the same for every creature.
  - **Maths nodes are wildcards until wired:** wire A, then set B (`stalk_cover._Graph.op`). A
    literal set first is refused.
  - **Feel check (needs a play session):** the roar is upper body only, on standing legs; the
    wait behind a trunk has no crouch or peek; its 4–9 s voice still sounds from behind its
    tree; at 169% the legs outrun the blend space's top (the feet slide) and it outruns a
    sprinting player; whether 45 cm is the right trunk; and
    rage shows only as a voice and the charge (no clip, and no faster than its run).
- **Fire holds the wendigo off** (`ward.py`, numbers in `forest_generator/npc_ward.py`):
  - It is one more step, `BT_Ward`, in a selector with the whole attack (the approach and
    the Swing, now a sequence of their own). Only the creatures in `NPC_WARD_FEARS` get the
    event, its variables and the tree nodes.
  - **The step succeeds while it is held off or running away, and fails otherwise.** A
    success has given its own move order and ends the pass at the Wait, so the Swing is
    never reached: nothing in the melee was touched.
  - **Held off** is all three: the player's `FireWard` is up (a bool on
    `BP_WeaponComponent`, `combat/paths.FIRE_WARD_VAR`), the wendigo is within 7 m, and it
    stands within 90° of where the player's body faces. It then circles them 4 m off, 50°
    further round on every pass, facing them, at 60% of its run.
  - **Past the fire it attacks.** More than 90° round, the step fails and Stalk, Chase and
    Swing run as ever. A player who turns with it holds it off again.
  - **The way round** is `WardSide`, a coin when the hold begins, turned about every
    2–4.5 s (`WardTurnAt`, one throw per turn: half the hunt's 4–9 s, so twice as often,
    and never under 1 s) and when a pass of a hold under way finds it standing still (a
    trunk in its way). 50° a pass is 90° in a second, so a turn does not keep it from
    getting round a player who stands still.
  - **30 s of being held off and it runs:** `WardSince` is when the hold began, and a hold
    broken for under 2 s (`WardLast`) is the same hold, so getting round once does not
    start the count over. It runs straight away from the player for 12 s
    (`WardFleeUntil`), 15 m ahead of itself per order, snapped onto the navmesh; off the
    navmesh (the map's edge) it gets no order and stands. The flight is the step's first
    Branch: it runs whether or not the fire is still up.
  - **Held off, it roars twice** (`ward_roar.py`; the bellow itself, shared with the
    hunt's first pass, is `roar.py`): once 13–17 s into the hold (`WardRoarAt`, one throw
    when the hold begins, 0 once given) and once at the hold's end, before it runs. Each
    time it stands for the roar's 2.4 s, facing the player (`WardRoarUntil`), so the
    flight is the roar and then its 12 s. The first roar is tested behind the held check
    and the stamp of `WardLast`: it is longer than the 2 s grace, and stamped it does not
    break the hold; and a wendigo whose fire goes down mid-roar attacks at once. Standing
    still also turns the way round about, so it comes out of a roar either way.
    Neither time is tuned: with `TuneWardHold` under the first roar's time, only the
    last one is given.
  - **A blow that lands on the player starts the hold over:** the Swing step writes
    `WardSince` back to 0 after the damage (`melee._author_melee`'s `clears`, a blocked
    blow too), so the next held pass begins a new hold: 30 s again, and the first roar
    thrown anew.
  - **A flight starts the hunt over:** `StalkRoarUntil`, `StalkLegUntil` and
    `StalkCharging` go back to zero, so it comes back with a roar and tree to tree. The
    Ward step is authored after the Stalk step for that reason (it writes its variables).
  - **`FireWard` is raised by a burning stick held out** (the use key:
    `combat/weapon_component/torch.py`, which writes it every frame; `Scripts/combat/CLAUDE.md`).
    A probe cannot write it by hand (the next frame overwrites it):
    `probes/probe_wendigo_ward.py` takes the issued stick in hand, sets it `Lit` and
    holds the use key (`SightsForced`).
  - **The player's body faces where the controller looks:** its yaw is written from the
    control rotation every frame, so a probe turns the player with
    `set_control_rotation`. `set_actor_rotation` is undone by the next frame.
  - **`WardSince` is tested against exactly 0** (`Equal (Float)`), not `<= 0`: a probe that
    writes a hold's start back in time gets a negative game time early in a run.
  - **A creature afraid of fire carries the `FearsFire` actor tag**
    (`combat/heat_tuning.FIRE_FEAR_TAG`), written on its variant's CDO by
    `character.build_variant_blueprint` for the keys in `NPC_WARD_FEARS`, and an empty list
    on every other. Combat reads it: a hot blade's blow does double damage to a tagged body
    (`combat/weapon_component/hot_blow.py`). A placed wanderer inherits it from its class.
  - A weapons build from before the flag has no `FireWard`: `ward.wards()` then leaves the
    step out, with a log line, and `verify_ward.py` fails until the weapons are rebuilt.
  - `verify_ward.py` checks the graph and `verify_ward_roar.py` the roars and the blow;
    `verify.py` and `verify_strafe.py` count a controller's nodes outside this step too.
    In the game: `probes/probe_wendigo_ward.py` and `probe_wendigo_ward_roar.py`.
  - **Feel check (needs a play session):** a wendigo that was never aggro before it met
    the fire roars, standing, once it gets round it (its hunt's first pass); it circles in
    its forward run, feet sliding, as the strafe does; 50° a pass at 4 m is quick, so a
    player has to keep turning; the roars at the fire are the hunt's clip, upper body on
    standing legs; and its fear shows only in them and the flight (no clip of its own).
- **A zombie is heard three ways** (`Sound/sound_monsters.py` says which takes; `Sound/CLAUDE.md`):
  its patrol growls on the Pulse's timer, only while it is not `Aggro` (`NPC_QUIET_ON_HUNT`:
  the mirror of the wendigo's Branch below, the timer kept 4 s off while it hunts); one of
  its `AggroVoices` right behind `_author_enter_agro`'s one write of `Aggro` (so once per
  hunt, whichever sense noticed); one of its `AttackVoices` in the Swing step, between
  arming the cooldown and the clip. The wendigo has the same nodes and empty arrays.
  `verify_voice.py` reads the graph; `probes/probe_monster_sounds.py` the live arrays and
  the hushed timer.
  - **Feel check (needs a play session):** whether growl 10 at the roar's reach tells the
    player a zombie has noticed them; the snarl on every swing (one each 1.5 s) is not too
    much; a chasing zombie, silent between swings but for its feet, reads right; the
    monsters' footsteps at volume 1 against the player's 0.3.
- **A wendigo on patrol makes no sound** (`stats.py`, the list in `forest_generator/npc_voice.py`):
  - Every wanderer growls on the Pulse's 4–9 s timer (`NextVoiceTime`). A creature of
    `NPC_QUIET_ON_PATROL` reaches that timer only through a Branch on its own `Aggro`; while
    it is false the pass writes `NextVoiceTime = now + 4` instead, so nothing comes due.
  - That write is also why its first growl of a hunt is 4 s after it notices the player and
    not on the pass that roars. The roar, the rage and the fire's roars play their own voice
    in their own steps, all behind `Aggro`.
  - A sound can't be heard in a headless game: `probe_wendigo_quiet.py` watches the timer
    (never under ~4 s off on patrol; run down and re-armed once it hunts; a zombie's runs
    down on patrol, and `probe_monster_sounds.py` watches it held off once it hunts).
- **A fire draws the zombies** (`drawn.py`, numbers in `forest_generator/npc_drawn.py`):
  - It is one more step, `BT_Drawn`, in a selector with the Stroll and ahead of it. Only the
    creatures in `NPC_DRAWN_BY_FIRE` get the event, its two variables and the tree node.
  - **Drawn is the state between patrol and hunt.** With a campfire burning within 200 m
    (flat; the nearest of several, kept in `DrawnTo`) the step sets `Drawn`, orders the
    zombie to the fire (`SimpleMoveToLocation`) at its patrol walk (`TunePatrolSpeed`, written
    after the order as the Stroll does) and succeeds, so the Stroll is not reached. Within
    3 m of the fire it stops and stands.
  - **The senses still run first:** Notice is ahead of Patrol, so a drawn zombie that sees,
    touches or hears the player goes aggro as ever. A fire lit beside the player brings the
    zombies to the player. `Drawn` is what the last Drawn step found, and an aggro zombie
    never runs it again: read "Drawn and not Aggro".
  - **Let go:** no fire that near (it burnt out: the actor is destroyed) and the step clears
    `Drawn` and fails. The zombie strolls again about where it spawned (`PatrolHome` is not
    moved), so it walks back.
  - **The step looks for the fire, every pass** (`GetAllActorsOfClass(BP_Campfire)`, then
    `FindNearestActor`, pure: read once into `DrawnTo`). The fire does not tell the zombies
    when it is lit: the controllers are separate Blueprints, so it would need a cast per
    creature. So a zombie that comes within 200 m of a fire already burning (a respawn) is
    drawn too. This build runs after `build_survival.py`; without `BP_Campfire`,
    `drawn.draws()` leaves the step out with a log line and `verify_drawn.py` fails.
  - **None of it is tuned:** the range and the stand-off are literals, and the speed is the
    patrol's own share.
  - `verify_drawn.py` checks the graph and the tree; `probes/probe_zombie_drawn.py` lights a
    fire and watches a zombie walk to it. `verify.py` and `verify_strafe.py` count a
    controller's nodes outside this step too.
  - **Feel check (needs a play session):** whether the patrol walk is the right "slowly"
    (a zombie 200 m off takes about 110 s of a fire's 180); the zombies gather 3 m off and
    stand, with no clip of their own; and they walk home once the fire is out.
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
  - It ends with the controller. A killed wanderer's replacement is a new pawn with a new
    controller and Blackboard, and the death menu's restart reopens the level, so neither
    comes back hunting: `probes/probe_respawn_calm.py` holds both. What does bring a fresh
    one straight in is a sense: the respawn band (75–100 m) is inside the all-round reach of
    the rifle (90 m), the shotgun (85) and the sniper (150), so the next shot wakes it.
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
  `PrintWarning`, which also puts it on screen, so it is gated on the GameState's `DebugMode`.
- **Debug mode also draws each live wanderer's sight (aggro) cone** (`sight_cone.py`): from the
  pawn, along its forward vector, `TuneSightRange` long and `TuneSightHalfAngle` either side —
  the sight sense's own inputs, so the MONSTER SETTINGS tab moves the cone and the sense together.
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
