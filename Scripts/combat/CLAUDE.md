# Weapons, inventory and combat

`Scripts/build_weapons_and_combat.py` builds `/Game/Weapons` and installs it on the characters.
`Scripts/verify_weapons_and_combat.py` reads the saved assets back. Both are thin entry points:
the code is this package (`__init__.py` is the map) and the verifier's sections are `verify/`.

Graphs are authored with `Scripts/uebp` (root `CLAUDE.md`): no coordinates, `out`/`then`
for pins, node paths from `uebp.nodes`, and a variable by its row (`WV.Held` from
`weapon_component/vars.py`, `HV.Health` from `health_vars.py`, `IV.Loaded` from
`item_vars.py`) or its `*_VAR` constant. `_log` is `combat/log.py`.

## Controls, and where they live

The defaults are all rebindable on the settings screen:

- Left click fires. It **auto-fires while held** on the SMG and the assault rifle, a tap
  **eats or drinks** a held consumable, **wears** a held garment (`weapon_component/wear.py`,
  `Scripts/clothing/CLAUDE.md`), with the **knife** in hand it **slashes**
  (`weapon_component/knife.py`), with the **matches** it **lights a campfire**
  (`weapon_component/light.py`), and with **empty hands it punches**
  (`weapon_component/punch.py`; all in `docs/firing_gate.md`).
- A gun is **carried lowered** (the jog's own arms, the gun in the hand) and comes up into its
  ready pose while an aim key or the guard is held, and for a shot or a reload
  (`weapon_component/carry.py`, `docs/aiming.md`).
- Right click aims **over the shoulder**, middle click aims **down the sights** (both held).
  Only a gun has sights (`HasSights`): with anything else in hand the middle click is the
  **use key** (`weapon_component/use.py`) and does not aim at all
  (`probes/probe_item_no_sights.py`). It lights a stick at a campfire and holds a burning one
  out, and with a hot knife or axe it cauterises a bleed (both below); on a cold blade, the
  matches, wood and food it does nothing yet.
  **1-4** bring the primary, secondary, pistol or melee slot's item to hand (the same key
  again puts it back: empty hands), **5-9** the bag's first five slots, **Q** the next filled
  bag slot, round the bag (not the weapon slots: `NextRequest`, `probes/probe_slots.py`) (all fixed keys, not settings binds: see "The slots" below), **G** drops, **E** interacts (an item in reach is picked up; a campfire heats the knife or axe in hand), **Shift** sprints, **F** blocks (held),
  **C** toggles crouch (in a sprint it slides: G5, "Crouch, slide and traversal from the sample"), **Z** toggles prone, **Left Alt** held down the sights holds the breath (`docs/aiming.md`), **V** held cocks the arm and shows the throw's arc, which ends on the reticle's point, and a click throws (see below).
- **R** reloads, and restarts from the death menu.
- M belongs to the graphics menu; **I** (the inventory: the backpack and the worn
  garments, with drag and drop) and Tab (the loot window) to the HUD.

The keys are CDO defaults on `BP_WeaponComponent`. The HUD pushes them from `BP_Settings`
every frame. Sprint and every other key live on the component, not on the character, because
`BP_ThirdPersonCharacter`'s graph is the Enhanced Input template, which the API cannot
partially rebuild.

**The keys are read only where the owner is locally controlled**
(`weapon_component/local.py`; `Scripts/net/CLAUDE.md`, "Input"). The component ticks on the
server and on other players' clients too; there the Tick skips the view, the keys and the
actions and runs only the pose, the slots and the equip. Every poll's self is `LocalPC`
(`local.local_pc`), never a controller by index, and a new key is polled in a fragment on
the local arm (`tick._author_wc_tick`'s first half or `_author_actions`).

R is shared safely between reload and restart: Tick does not run while paused, and the death
menu polls its own copy from `DrawHUD`, which does.

Death's pause is single player's (`death.py`, authored by `net.pause.author_pause`): a Branch
on IsStandalone stands in front of it, so on a server the world runs on past a dead player
(`verify/health.py`; `probes/probe_death_pause.py` is the standalone arm). What a dead
player gets there instead: their gear onto the body (`weapon_component/shed.py`) and a new
body 10 s later (`player_respawn.py`); `docs/health.md`, "Dying", and
`Scripts/net/CLAUDE.md`, "Death".

## The shape of it

- **Weapons are Actors, not components.** You can't leave a component behind in the world, so:
  - equipping is an attach, and dropping is a detach;
  - `Inventory` is one typed array of `BP_WeaponItem`;
  - firing reads every stat off `Held`, with one cast and no per-weapon branching.
- **A new weapon is a row plus a model and its outline.** Add a row in
  `weapon_specs._weapon_specs()`. Adding the SMG, the rifle and the sniper changed **no** node
  in the fire, reload or gate graphs.
- **The shotgun and the pistol are Quaternius models** (`weapon_models.py`): the Ultimate Gun
  Pack's `SM_Shotgun_3` (a pump gun with a straight wooden stock) and `SM_Pistol_1`, CC0,
  imported by `asset_pipeline/import_quaternius.py` into `/Game/Sourced/Quaternius/Guns`
  (zips in `assets/cache/quaternius/`). The pack is at no one size, so each row's model
  carries its scale to real size (0.18 and 0.11: 104 cm and 20 cm). Static meshes have no
  muzzle socket: the muzzles are the barrels' ends, measured. The shotgun's index can't reach
  its guard from the rifle's ready pose (`docs/aiming.md`). The shotgun is held in a pose of
  its own, `A_AimShotgun` (`shotgun_pose.py`): the rifle's, with the right thumb over the
  stock's wrist and the left along the pump, out of its low sight line, and the left hand
  turned under the pump with its fingers closed on the wood (the rifle pose cups a deep
  handguard: its knuckles stood inside the pump and its fingers out to the right), and
  moved, with the arm, to where its own fingers fit the pump (`pump_seat.py`: the rifle
  pose's wrist is right only by the accident of one body's hands).
- **The SMG, the rifle and the sniper are Fab models** (`weapon_models.py`): the FPS Weapon
  Bundle's SMG11 (`SK_SMG11_X`, a MAC-11 with its wire stock folded), AK 47 (`SK_KA47_X`) and
  AS Val (`SK_KA_Val_X`) with its 25x56 scope, under `/Game/FPS_Weapon_Bundle`.
  - **The SMG is held like the pistol:** its row's `aim` is the pistol's ready pose, so the grip
    is solved against it and it is one-handed (`TwoHanded` follows `aim`:
    `weapon_specs.two_handed_poses()`), guarding with fists.
  - A row with a `model` builds the model instead of its `parts`. Its `parts` are then the
    model's **measured outline**: boxes that are never built, which the grip solve and the sight
    checks read exactly as they read a primitive gun's parts. Re-measure them if the mesh changes.
  - The pack's `_X`/`_Y` are **axis** variants, not textures: `_X` points down +X, which is the
    weapon's frame, so the model sits unrotated at real size. Muzzles are the meshes'
    `b_gun_muzzleflash` sockets.
  - The pack isn't committed. Without it the build stops at `_must_load`.
    `Scripts/asset_pipeline/fab_library.json` is the restore recipe.
  - The pack has no shotgun or pistol (those are Quaternius's, above), and its KA74U was not
    asked for.
- **Equipping is authored once.** BeginPlay, a slot key, drop and pick-up only change an
  item's `Slot` or `Inventory`; the slot sync raises `NeedsRefresh` when the hand slot's item
  is not `Held`. Tick's last block consumes it and runs the single equip sequence (which
  empties `Held` first, so a hand slot with nothing in it is empty hands). Weapons are spawned once at
  BeginPlay and then hidden or shown, never destroyed, so a dropped weapon is the same actor.
- **The slots** (`slot_tuning.py`; `weapon_component/slot_sync.py`, `slot_moves.py`; checks
  `verify/slots.py`; `probes/probe_slots.py`). Everything carried is still in `Inventory`;
  each item says where it is itself, in its `Slot`: 0 the hand, 1-4 the primary,
  secondary, pistol and melee slots, 5-14 the backpack's ten, -1 UNPLACED. So an item that
  leaves `Inventory` (eaten, dropped, thrown, worn) leaves its slot, and nothing else is told.
  - **`WeaponKind` on the item is the weapon slot it belongs in:** the pistol's the pistol
    slot, every other gun's the primary (a long gun fits the secondary too), the knife's
    and the axe's the melee. Everything else is `NOT_A_WEAPON` and fits no weapon slot; the
    hand and the bag take anything (`slot_tuning.fits`, mirrored by `slot_nodes.fits`).
  - **The slot sync is the last fragment before the refresh.** It rebuilds `SlotItems`
    (15 entries, the HUD's view) from the items' Slots (a second claim on a code is
    UNPLACED), puts each UNPLACED item in a free weapon slot it fits (a weapon goes to its
    own slot before the bag), else the first free bag slot, else the empty hand, then writes `EquippedIndex` (the hand's item's index,
    -1 for empty hands) and `HasRoom` (a bag slot or the hand free). **Nothing else writes
    the hand:** the old writes of `EquippedIndex` (drop, throw, eating, wearing, light) are
    overwritten by it the same frame.
  - **A pick-up, a take-off and the loot window go in UNPLACED**, after testing `HasRoom`:
    a weapon into a free weapon slot of its kind, anything else (and a weapon whose slots
    are taken) into the bag, or empty hands with the bag full; with the bag full and
    something in hand nothing is picked up, a weapon with a free slot included (`HasRoom`
    is not per item). The held item stays held
    (`probes/probe_pickup_weapon_slot.py`).
  - **One pick-up goes to the hand: a blade taken back out of what it was thrown into.**
    The strike flags the item `Lodged` as it sets it into a tree or a body
    (`throw_strike.py`); the take (`pickup._author_to_hand`) lowers it and, with empty
    hands (`Held` not valid), writes `Slot = HAND` over the UNPLACED, `HandFrom` the
    item's `WeaponKind`, so 4 puts it away. With something in hand it is placed like
    any weapon. A blade that glanced off and fell is not `Lodged`. After a drop, a throw or eating the
    last one the hands stay empty: nothing comes up unasked.
  - **A screen never writes a request itself:** the HUD calls the component's `Ask…`
    events (`combat/ask_consts.py`, `weapon_component/asks.py`), which raise them. The loot
    take (`loot_take.py`) and save and exit's countdown (`save_exit.py`) are events of the
    component too (`Scripts/net/CLAUDE.md`, "A screen asks").
  - **The slots are the server's** (M18; `Scripts/net/CLAUDE.md`, "The inventory"): the
    keys and the HUD call the Server events `AskSlot`, `AskMove` and `AskNext`, the serve
    below runs with authority only, and the server writes what is carried as a record
    (`record_vars.py`; a C++ struct on its own component, written on a frame that changed
    it) from which a client's item actors are made (`view.py`). Single player is the same
    graphs, with authority.
  - **A graph that changes what is carried is followed by `mark_change_sites`**
    (`combat/dirty.py`) before its compile: it puts `MarkInventoryDirty` behind every
    write of `Inventory` or `Worn` and every Set of an item's `Slot`, `Loaded`,
    `Reserve`, `Lit` or `Hot`. Never call the mark by hand, and never write the record's
    variables from a graph. A check that reads an exec chain's neighbours looks through
    the marks with `verify/common.py`'s `past_marks` / `before_marks`.
  - **A request is `SlotRequest`** (a number key, Q, Enter on a bag slot in the I panel, a
    click on a slot): a filled slot's item comes to hand, the hand's item going home first
    (the first slot from the primary on that it fits and that is free, the asked slot
    counting as free: a gun goes back to its weapon slot, anything else to the bag; no home,
    nothing moves). An empty slot takes the hand's item back if it came from there
    (`HandFrom`): 1 twice puts the gun away. **A drag is `MoveFrom`/`MoveTo`** (the HUD's,
    `graphics_menu/inv_drag.py`): moved if it fits, swapped if the other fits back. A drag
    to or from a worn slot is clothing's: `TakeOffTo` with `TakeOffSlot`, and `WearRequest`
    (`weapon_component/wear.py`, `wear_drag.py`; `Scripts/clothing/CLAUDE.md`). **A drag let go
    outside the inventory is `DropRequest`** (`weapon_component/drop_request.py`): a slot
    code, or `SLOT_COUNT` + a worn slot. The item leaves `Inventory` (or `Worn`) and is set
    down as G sets the held one down (`inventory._author_set_down`, shared by both), its
    Slot UNPLACED; the slot sync and the refresh empty the hand if it was the hand's.
    `probes/probe_inventory_drag.py` runs it.
  - **The number keys are fixed** (`SLOT_KEYS`, variables on the component, as every key):
    not in `BIND_VARS`, so the settings page does not rebind them.
  - **Probes equip by writing `EquippedIndex`**: `probes/context.py` turns that write into
    an `AskSlot` for the item's slot (`Probe.hold`; on a client, a write of `SlotForced`,
    which the Tick asks with), and `boot.py` makes `SlotForced` writable for any probe
    that lists `EquippedIndex`.
- **E is Interact, and picking up is one kind of it** (`weapon_component/interact.py`). The key
  (`KeyInteract`, `INTERACT_KEY`) knows nothing about items. Each kind of thing is a
  `(candidates, act)` pair in `interact.KINDS`: `candidates` walks its things and offers some,
  `act` casts the kept target to its kind and does its thing. Of the candidates offered within
  `INTERACT_RADIUS` of the player, the one nearest `AimPoint`, the point the reticle rests on
  (the aim resolve sets it every frame, armed or not), is kept (`InteractTarget`, an Actor, and
  `InteractGap`). A walk only remembers; the act runs once, after the last walk's `Completed`,
  by the first kind whose cast takes the target. `InteractForced` is the probe's key press
  (`probes/probe_pickup.py`).
  - **To add something to interact with,** write its pair in a module of its own and add it to
    `KINDS`. Don't poll the key anywhere else.
  - **One kind is an item** (`weapon_component/pickup.py`): it offers the `Dropped`
    items and asks the server for the target (`Server_Take`, whose body takes it into the
    bag: M20, below). A take inside the walk is how one press used to empty a pile.
  - **The other is a campfire** (`weapon_component/heat.py`), offered only while the held
    item `Heats`. It has no cast: a kind's `act` may test the target any way it likes (here
    `ClassIsChildOf` against `CampfireClass`) as long as it hands on the exec pin a target
    that is not its own leaves by.
  - `verify/interact.py` counts one reach test, one ranking and one keep **per kind**
    (`len(KINDS)`).
  - Searching a body is Tab, not this key (`Scripts/loot/CLAUDE.md`).
- **An item on the ground glimmers** (`glimmer.py`, numbers in `glimmer_tuning.py`): the
  item highlight. `BP_WeaponItem` carries `Glimmer`, a `MaterialBillboardComponent` on
  `Body`, hidden as built, and its Tick's step is `Glimmer.SetVisibility(Dropped)` (after
  what a client's copy of a replicated item shows at all: `item_world.py`).
  `Dropped` is written in half a dozen places, so none of them is told: the item shows the
  sprite by its own flag. `BP_AmmoPickup` is built with its sprite showing.
  - **A child with a Tick of its own overrides the base's** (the knife and the axe:
    `heat.build_heated_model`; the stick), so each calls `author_glimmer` at the tail of
    its own chain. `verify/glimmer.py` finds a child whose wired Tick lacks the step, and
    `is_glimmer_node` sets the node aside in the heat's and the torch's SetVisibility counts.
  - **`Glimmer` is inherited, so a child's builder cannot drop it:** it is in
    `weapon_items.KEEP`. A builder that clears "every other component" must leave it.
  - **The look is `M_ItemGlimmer`:** unlit, additive, one Custom node drawing a four-rayed
    star that appears and is gone every 3 s (it rests at nothing), each item out of step
    (the phase is its place in the world), only near: whole within 5.5 m of the camera
    and nothing past 8.5 m (about 3 m and 6 m ahead of the character; a material cannot
    know the pawn, and the camera stands 2.6 m behind it), through `EyeAdaptationInverse`, so it reads the same at noon and
    at midnight. World-position offset lifts the sprite 10 cm and pulls it 12 cm towards
    the camera, so the ground, the grass and the item's own model do not swallow it.
    `CameraVectorWS` does not exist in a vertex shader (the material fails to compile and
    the default one is drawn): the offset normalises camera position minus world position.
  - **On or off is `MPC_ItemGlimmer.Highlight`,** which the material multiplies by. Combat
    builds it on; the day/night cycle writes it from the WORLD SETTINGS tab's row
    (`world/item_highlight.py`). It is a sprite, not an overlay material: the overlay slot
    is the hot blade's.
  - `probes/probe_item_glimmer.py` runs it in a game.
- **Ammunition lives on the weapon** (`MagazineSize`/`Loaded`/`Reserve` on `BP_WeaponItem`).
  Drop a half-empty gun and it is still half-empty when picked up. The pistol is the fallback: an
  8-round magazine over an endless reserve (`InfiniteReserve`), so it reloads every 8 shots but
  never runs dry. The reload fills its whole gap and never charges its reserve; shell pickups skip
  it; the HUD shows `5 / ∞`.
- **There is no reloading state.** `NextFireTime` is one world-time deadline. Both the fire
  interval and the reload push it out.
- **The shot and the reload are server requests** (M19; `shot_vars.py`,
  `weapon_component/shot.py`; `Scripts/net/CLAUDE.md`, "The shot and the reload"). The
  trigger's gate and R are still polled where the keys are, but what they do is two reliable
  Server events on the component:
  - **`Server_Fire(AimPoint)`** is the shot: it refuses unless `Held` is valid, the owner
    alive, the item a gun (not `Melee`, `Consumable` or `Lights`), a round in it and its
    cooldown over, then runs `firing._author_fire` (the round, the cooldown, the one draw in
    the cloud, the pellets, the damage) and the shot's noise. The pellets leave **the
    server's own muzzle** (`carry._author_shot_origin`, a second copy of the sub-graph)
    towards the `AimPoint` the client sent, in **the server's own `AimSpread`**.
  - **`Server_Reload`** calls `ReloadNow`, a plain event holding `ammo._author_reload`.
  - **The owning client predicts** (`shot._author_shot_ask`, `_author_reload_ask`, off the
    false arm of a Branch on HasAuthority): the kick, the shot's sound, a round off its
    own copy's `Loaded`, its own `NextFireTime`, and `ReloadNow` on its own copy. It
    traces nothing and draws nothing in the cloud: a hit is the server's word, and
    reaches it as health. There is no muzzle flash in the game to predict.
  - **`AsksSent` / `AsksServed` keep the predicted rounds.** A client counts each ask it
    sends; the server counts each it answers, fired or refused, and that count
    replicates to the owner. While it is behind, a record that arrives is older than the
    client's own shots, so `view.py` leaves the rounds alone and takes them once the two
    agree. A refused shot's round comes back the same way.
  - **In single player nothing is predicted:** the one machine has authority, the events
    are plain calls, and a press is one shot as before. Never write the cost on the local
    arm with authority: it would be spent twice.
  - **The cooldown has `FIRE_GRACE_S` (0.1 s) of grace on the server** and is stamped
    from the later of now and the old deadline (`FMax`): a client fires on its own clock
    and packets do not arrive evenly, so an honest burst would lose rounds without it,
    and with the `FMax` the rate over any stretch is still the gun's own.
  - **The server does not ask about sprint or the guard:** both are the local gate's
    (a sprint's end and the shot behind it travel separately; the server has its own
    `Blocking` since M20, and a swing's event does ask it).
  - **Plain Server events, not GAS abilities.** `GA_ConsumeItem` is triggered by a
    gameplay event whose payload is the item actor, on an ability system that does not
    replicate until M26. A shot does not fit that: the event would be raised on the
    client's own ability system and go nowhere; its payload would be an item actor that
    on a client is a local picture, which the server cannot resolve; the aim point needs
    target data, which a Blueprint ability cannot send without C++; and an automatic gun
    asks eleven times a second from a gate that is already a Tick poll. A Server event
    with a vector is the whole of it. Worth another look once the ability system is the
    server's (M26): the cooldown could then be a GameplayEffect.
  - **A dedicated server poses its bodies** (`server_pose.py`): `BP_HealthComponent`'s
    BeginPlay, behind IsDedicatedServer, sets the owner's mesh to
    `AlwaysTickPoseAndRefreshBones`. Nothing is rendered there, and an unrendered mesh
    keeps its reference pose: the hit bodies and the muzzle would be where no client
    sees them. The same arm calls `ThrottleServerPose` (C++; `pose_tuning.py`): the mesh
    is posed every frame within 30 m of another player, 10 times a second further off,
    twice as a ragdoll or with nobody near, and every other skinned mesh on the body (a
    MetaHuman's) stops ticking there (A4; `Scripts/net/CLAUDE.md`, "What the server
    spends on bodies it never draws").
  - **The anim graph's server branch** (`server_anim.py`, `server_anim_consts.py`,
    `verify/server_anim.py`): one Blend Poses by bool on the anim Blueprint's `ServerPose`
    (IsDedicatedServer, written once), authored last of the anim graph's patches, and
    taken out first (`unpatch_server_anim`) so the other builders meet the chain they
    expect. A server skips the foot IK's Control Rig and FullBodySlot; the aim's and the
    flinch's blends stay on both arms. **Anything new that is for the eye goes on the
    client arm**: the verifier fails a server arm holding a slot, a blend or a node class
    that `SERVER_ARM_CLASSES` and `SERVER_SLOTS` do not list. The NPC build branches each
    wanderer's graph the same way (`build_npc_blueprints.py`).
  - **Probes:** `FireForced` and `ReloadForced` are the keys' stand-ins, read on the
    local arm, so on a client they go through the Server events. A probe that calls
    `Server_Fire` itself does so on the server (or in single player).
    `probes/probe_net_fire.py` is the two-client proof; `verify/shot.py` the wiring.
- **The pellet is judged where the shooter saw the target** (M22; `lag_tuning.py`,
  `uebp/nodes/shot.py`; the C++ is `Source/Otherworld`'s `OtherworldHitHistory` and
  `OtherworldShotLibrary`; `Scripts/net/CLAUDE.md`, "Lag compensation"). firing.py's
  pellet trace is one C++ node, `ShotTrace`: the Visibility trace and, for a struck
  character, its bodies along the same line (`bBodyHit`, `BodyBone`, `BodyPoint`, which
  impact.py's hit zone reads in place of its own `K2_LineTraceComponent`). On a server a
  remote shooter's pellets are traced against where every character stood its round
  trip ago (plus `EXTRA_REWIND_S`, at most `MAX_REWIND_S`); a local shooter's, so single
  player's, against the present, the same two engine traces as before.
  `probes/probe_net_lag_hits.py` is the proof, with and without `--lag 150`.
- **Melee, the guard, the throw and the take are server requests too** (M20;
  `strike_vars.py`; `Scripts/net/CLAUDE.md`, "Melee, the guard, the throw and the take").
  Five reliable Server events on the component, each a plain call in single player:
  - **`Server_Punch` / `Server_Slash`** (`weapon_component/punch.py`,
    `author_strike_event`): a queued swing asks for its strike's event, which refuses
    unless the hand is the strike's (empty, or a `Melee` item), the owner alive and not
    `Blocking` and the cooldown over (`STRIKE_GRACE_S`), then stamps the cooldown and
    the blow's time, raises `Pending` and plays the clip. **The blow stage is in the
    Tick's upkeep** (`_author_punch_blow`, `_author_knife_blow`), on every copy, and
    finds a strike pending only where the event ran: the sweep, `TakeHit`, the chop
    and the hot blade's double are the server's. A client of a server stamps its own
    cooldown and plays the clip and the swing's sound at once (its prediction).
    - **A swing written straight into `KnifeQueued` inside the cooldown is refused**
      (the press gate always waited; the event now does too), and so is a punch with
      something in hand. A probe waits for `NextKnifeTime` and empties the hands with
      a slot ask.
  - **`Server_SetHolds(Guard, Use)`** (`weapon_component/holds.py`): the owning machine
    reports its `Blocking` and `Using` on the frame either changes. The server's copy
    of a client's character writes its own `Blocking` (asked AND the movement's own
    stamina AND not sprinting) and `FireWard` (asked AND `Held.Lit`, behind
    `IsValid(Held)`) in the Tick's remote arm. `Blocking` replicates to everyone but
    the owner. `BlockForced` is the probe's block key.
  - **`Server_Throw(Start, Velocity)`** (`weapon_component/throw.py`): the arc, the
    cocked arm and the wind-up are the owning machine's; on the frame the hand lets go
    it stores the launch, plays the throw's sound and asks. The event is the release
    (`_author_throw_release`), refused unless an item is in a living hand, nothing of
    this player's is in the air and `Start` is within `THROW_START_REACH_CM` of the
    server's copy; the speed is capped at the item's `ThrowSpeed`. The flight is in the
    upkeep, behind HasAuthority.
  - **`Server_Take(Item)`** (`weapon_component/pickup.py`): E's item kind asks (while
    its own copy has room); the event is the take, refused unless the item is still
    `Dropped`, within `TAKE_REACH_CM` of the server's copy of the taker, and a slot is
    free.
  - **An item that leaves a hand for the world replicates** (`item_world.py`): the
    release sets `InWorld` and calls `SetReplicateMovement(true)` and
    `SetReplicates(true)` on the server's actor; `Dropped`, `Lodged` and `InWorld` are
    replicated variables of `BP_WeaponItem`. Replication is never switched off (the
    generic driver would leave each client's copy standing): the take lowers
    `InWorld`, and a client's copy hides itself while it is false. That step is the
    first of `glimmer.author_glimmer`, so every child's Tick has it. A take of an item
    placed in the level destroys the server's actor and spawns a fresh one of its class
    into the bag (`TakeItem`), so a late joiner sees it gone (A2); the same step puts
    the actor to sleep while it lies still or is carried (`NetDormancy`), and the graphs
    that change a lying item's state wake it (`item_world.author_wake`;
    `Scripts/net/CLAUDE.md`, "Relevancy, update rates and dormancy").
  - **Every other item in the world replicates by itself** (M23): the same step, on its
    authority arm, makes an item that lies `Dropped` and is not yet `InWorld` a
    replicated actor, on the server. So an item set down, placed in the level, left by a
    kill or cut from a tree is the server's on every machine, and no graph that makes
    one says so. The drop is the server's too: the drop key and a drag out of the
    inventory call `AskDrop` (a Server event), and `DropRequest` is served behind
    HasAuthority (`weapon_component/drop_request.py`). `verify/world_items.py`;
    `probes/probe_net_take.py` is the two-client proof.
  - `verify/strike.py` and `verify/pickup.py` are the wiring;
    `probes/probe_net_throw.py` and `probe_net_melee.py` the two-client proof.
- **Everyone sees and hears the fight** (M21; `fx_vars.py`, `weapon_component/fx.py`;
  `Scripts/net/CLAUDE.md`, "Everyone sees and hears the fight"). Every cosmetic of a
  player's fight is a **pair of events** on the component: `Fx_<Name>` holds the one copy
  of its nodes (the sound, the clip, the spawn), and `Multicast_<Name>`, an unreliable
  Multicast the server calls where the state changed, asks its gate, counts `FxPlayed` and
  calls `Fx_<Name>`. The owning client predicts the five it can (`Fx_Shot`, `Fx_Reload`,
  `Fx_Punch`, `Fx_Slash`, `Fx_Throw`: called off the authority Branch's false arm, where
  the asks are); the point bursts (`PelletHit`, `PunchHit`, `BladeHit`, `Chop`, `Stab`,
  `Lodge`) nobody predicts, so every screen plays them at the server's word, the striker's
  included (the pellets' not one by one: a shot's impacts are noted as they land and told
  in one `Multicast_ShotHits`, `weapon_component/shot_hits.py`, A4); `ThrowClip` is the wind-up's own on the thrower and told to the others.
  - **Three gates, one per kind:** `UNPREDICTED` (HasAuthority OR NOT `LocalInput`: the
    owner already played it), `OTHERS` (NOT `LocalInput`), `SCREEN` (NOT IsDedicatedServer).
    Single player has authority, so each Multicast is a plain call that plays once.
  - **Where a cosmetic's nodes live:** inside the pair, authored by the module that owns
    the action (`fx.pair(ed, name, params, body, gate)`), **before** the event or the Tick
    fragment that `fx.tell`s or `fx.predict`s it (a call finds only an event that exists:
    `build.py` authors every pair first). A new sound or effect of a shot, a blow or a throw
    goes in a pair; never a `PlaySoundAtLocation` or a spawn at the site that decides it,
    which is the server's and has no speaker.
  - **`HeadshotTime` is a RepNotify to the owner** (`headshot.replicate_headshot`): the
    wound is the server's, and the OnRep's Remote arm rewrites the stamp with this
    machine's clock, which the HUD's X compares against.
  - **A montage just started reads as a quiet slot.** `IsSlotActive` is false until the
    montage has blended in, so the ready pose's keep-alive would replace the throw's clip
    on its first frame on another player's copy (the owner's starts from the ready pose,
    which keeps the slot active). Both the keep-alive and the equip's stop ask
    `IsPlayingSlotAnimation(ThrowAnim)`, which sees the montage instance at once; the
    clip plays on through the hand letting go, in both modes.
  - **Hit reactions, the grunt, the heartbeat and the collapse are not pairs:** they follow
    `Health`'s RepNotify on every copy (M14, "Health and damage"), and footsteps are each
    copy's own footstep component, driven by the replicated movement.
  - `verify/fx.py` is the wiring (and `nodes_of` / `in_fx` / `calls` / `predicts` for the
    sections whose nodes moved into a pair); `probes/probe_net_fx.py` the two-client proof.
- **The knife is a melee item, not a gun** (`knife.py`): a `BP_WeaponItem` child flagged `Melee`,
  drawn by the pack's `SK_M9_Knife_X` (blade up, tipped 30° forward, the pistol's grip), and
  not a row of `_weapon_specs()`, whose every column and check is about a gun. Its slash clip
  `/Game/Weapons/Anims/A_KnifeSlash` is keyed from Python (`knife_anim.py`): the pack has no
  animation and no stock clip is a knife attack.
- **The axe is the other melee item** (`axe.py`): Quaternius's Survival Pack `SM_Axe` (CC0,
  `/Game/Sourced/Quaternius/Survival`) at 0.2, a 65 cm camp axe, head up and tipped 30° forward
  with the bit leading, held in `A_HoldKnife` by the stretch of haft above its knob. It has
  **no strike of its own**: `Melee` sends the fire key to the knife's stage, so it swings
  `A_KnifeSlash` for `COMBAT.knife_damage`. An axe that hits harder needs its
  own `Strike` in `weapon_component/` (`punch.py` has the two stages).
- **The axe cuts wood from a tree** (`weapon_component/chop.py`, numbers in `chop_tuning.py`).
  The knife stage's blow passes what it struck to `_author_chop` off its failed health cast
  (`punch._author_blow`'s `scenery`). With an item flagged `Chops` in hand (only the axe) and a
  tree under the blow, it throws `BP_BulletImpact` chips and counts; every third blow on the
  one tree spawns `BP_Wood` 80 cm from the cut, turned 40-80° to one side of the player, traced
  down onto the ground and laid flat.
  - **A tree is "an `InstancedStaticMeshComponent` the sweep struck".** The trees are untagged
    instances of per-cell HISMs (`forest_import/trees.py`) and nothing else instanced has
    collision. One tree is the component plus the hit's `Item` (`ChopTree`, `ChopItem`); a blow
    on another tree starts the count over. Trees never run out and never fall: an instance
    can't be marked or removed cheaply.
  - **`Chops` is read behind its own `IsValid(Held)` Branch**: the blow lands after the press,
    when the hands may be empty.
  - **Order and purity:** `ChopCount` is stored before `ChopTree`/`ChopItem` (the pure "same
    tree" test reads them), and the landing point goes into `WoodSpot` before the trace reads
    it twice (it is built from random draws).
  - `verify/chop.is_chop_node` sets the stage's nodes aside in the older whole-graph counts.
    `probes/probe_chop_tree.py` stands the player at a trunk and swings.
- **Wood is an item with nothing to fire** (`wood.py`): `BP_Wood`, a `BP_WeaponItem` child,
  Quaternius's `SM_WoodLog` scaled apart (0.08 long, 0.055 across) to a 30 cm split, `Dropped`
  by default like food, so a spawned piece is already a pick-up. It is neither `Melee` nor
  `Consumable`, so the fire key runs the guns' path over no pellets, sound, kick or noise, and
  the carry treats it as a gun (it rides in the lowered hand). It stands on end in its own
  frame, held like a club, because the one fist pose closes on a handle running up through it;
  the chop's spawn tips it flat, but one dropped with G stands on its end.
- **The matches light a campfire** (`matches.py`, `weapon_component/light.py`, numbers in
  `light_tuning.py`). `BP_Matches` is Quaternius's `SM_Matchbox` at 0.08 (a 9 cm box), flagged
  `Lights`, carried in `A_HoldItem`. A tap of the fire key with it in hand takes one `BP_Wood`
  out of `Inventory`, destroys it, and spawns `CampfireClass` 130 cm in front of the player,
  on the ground a trace finds. The matches are never spent; with no wood nothing happens.
  - **The strike is the server's** (`Server_Light`, M25): the key's arm only asks. So are
    lighting the stick (`Server_Kindle`), heating a blade (`Server_Heat`) and cauterising
    (`Server_Cauterize`); `combat/fire_vars.py` has the picture and `Scripts/net/CLAUDE.md`,
    "Fire and heat", the rules (a burning stick or a hot blade reaches a client by the
    record; the burn-out and the cooling run behind `IsServer`).
  - **The campfire is survival's** (`survival/campfire.py`): combat only holds a class
    variable. `build_survival.py` writes `CampfireClass`; the weapons build re-declares it
    and puts the old value back (`build._kept_class`), so a weapons-only rebuild keeps the
    fire. Unset, the strike is refused before any wood is spent.
  - **`EquippedIndex` is found again after the removal** (`Array_Find(Inventory, Held)`):
    wood ahead of the matches in the bag moves them down a slot. (The slot sync writes it
    again at the end of the Tick, from the hand's slot.)
  - **The loop only remembers** (`LightWood`); the take runs once off `Completed`, as the
    pick-up's does.
  - The fire goes where the player faces, whatever is there: facing a trunk at arm's length
    puts it in the tree. `probes/probe_campfire.py` runs the whole chain in a game.
- **Knife, food and the stick have their own hold poses, not the pistol's aim**
  (`hold_pose.py`): `A_HoldKnife` (knife up at the chest, left fist raised as a guard),
  `A_HoldItem` (the item carried at the waist, left arm hanging), `A_HoldTorch` (the stick
  up beside the head) and `A_WardTorch` (it held out at arm's length), keyed off the idle by
  arm directions like the guard's. The right hand keeps the pistol pose's orientation and fingers, so the grip solve
  gives the pistol's answer and every item stays upright in the fist. The slash starts and ends
  in `A_HoldKnife`. `probes/probe_hold_poses.py` measures the hand heights in game.
- **The shotgun, pistol, knife, axe, matches and a stick are issued; the SMG, rifle and sniper are found.**
  The issued items are `inventory.STARTER_CLASS_VARS`: one class variable each on the
  component, spawned at BeginPlay into `slot_tuning.STARTER_SLOTS` (the shotgun in hand, out
  of the primary slot; the pistol and the knife in theirs; the axe, the matches and the
  stick in the bag).
  - The gun drop (`gun_drop.py`) is **two seeded rolls** on two `FRandomStream`s on the
    GameMode: `GunDropRollStream < GUN_DROP_CHANCE` (10%) decides whether anything drops, then
    `RandomIntegerFromStream(GunDropPickStream, Length)` decides which.
  - **The loot table is `GUN_LOOT_TABLE`** (`tuning.py`), as weights: SMG 5, rifle 3, sniper 2.
    `DropClasses` holds one entry per ticket, so the uniform pick is the weighted draw.
  - The pick stream advances only on kills that drop, so re-weighting never moves which kills
    drop.
  - **The streams are seeded on the first counted kill,** behind `GunDropSeeded`. This happens
    in the health component because `combat_trace.py` owns the GameMode's graph.
    `GUN_DROP_SEED = 0` means a fresh seed each session. Any other value replays the same
    sequence every run: it is for probes.
  - A stream draw is pure and advances the stream, so each draw has exactly one reader. The
    verifier asserts it.
  - `verify/drops.simulate_gun_drops()` replays `FRandomStream` bit for bit. With a fixed seed,
    a PIE run dropped exactly the predicted guns.
  - Setting `Dropped = true` on the spawned actor is the entire handover.
  - Keep the `Length(DropClasses) > 0` guard, or an unfilled table indexes into nothing.
- **Anything in hand can be thrown** (`weapon_component/throw.py`). Holding **V** draws the
  arc: `PredictProjectilePath` from a point in front of the chest, at the point the reticle
  rests on (below), as world-space instances on `BP_ThrowArc`'s one ISM
  (spawned on first aim; `throw_arc.py`), with a disc where it lands. A click of the fire key
  over the arc plays the skin's throw clip (`throw_windup.py`: Quaternius UAL2's
  `OverhandThrow`, upper body only) and, where the clip's hand lets go (`THROW_RELEASE_S`,
  0.35 s into it), stores the launch and asks `Server_Throw`, whose body detaches the item and
  takes it out of the inventory as a drop does (M20, above); letting V up instead calls it off.
  - **A throw goes where the reticle is** (`weapon_component/throw_launch.py`, the launch
    as pure pins). Its yaw is the bearing from the launch point to `AimPoint`, and its
    pitch the one whose curve passes through `AimPoint` at the item's `ThrowSpeed`, the
    flatter of the two (`DegAtan2` over a root: the docstring has the formula). So the arc
    lies in the upright plane through the reticle's point, stands under the reticle on
    screen and ends on it. The launch point is 55 cm to one side of the camera's line:
    along the view's own yaw the arc ran beside the reticle and never met it.
    - **Out of reach, or at the sky, it is a lob:** the root's inside goes negative past
      what the speed reaches (about 12 m at the default 1100 cm/s, 33 m for a blade), and
      the pitch is then the view's tipped up by the item's `ThrowArcDegrees`, as every
      throw was before. The two meet with a step at the edge of the reach.
    - **A point under `THROW_AIM_MIN_AHEAD` (100 cm) ahead of the launch point is not
      aimed at** (a wall at the shoulder, a trunk between the camera and the player):
      the throw goes out along the view's yaw, tipped.
    - `AimPoint` is where the reticle rests, which with something in hand is the first
      surface on the line from the shot's origin (`aim.py`), not always the camera's.
    - **A probe that faces a thing has not aimed at it:** the camera's line runs beside
      the player's. `probes/probe_throw_strike._reticle_on` turns the view until the
      reticle is on a target; `probes/probe_throw_reticle.py` checks the arc against
      `AimPoint` near, far and at the sky.
  - **While V is held the arm is cocked** (`weapon_component/throw_ready.py`):
    `A_ThrowReady` (`throw_pose.py`) is the throw clip stopped at `THROW_READY_S` (frame
    7, the hand furthest back), held looping in the upper-body slot for as long as the
    arc is drawn. It is asked for every frame by what the slot is playing
    (`IsPlayingSlotAnimation`), not on the key's edge, so it comes back after a flinch or
    a re-equip, and never starts under a flinch (the ready pose's own rule,
    `ready_pose.py`). The click plays the clip on from that moment
    (`InTimeToStartMontageAt`), so the hand lets go `THROW_WINDUP_S` (0.12 s) after it.
    Letting V up sets `NeedsRefresh`: the equip puts the item's own pose back, or stops
    the slot under a lowered gun. A skin with no throw clip has no ready pose.
    - `verify/throw_aim.is_ready_node` sets its two nodes aside in the older count of
      the slot's plays.
  - **The wind-up is a state, `ThrowWinding`: the item being thrown.** While it is valid no
    arc is drawn and the fire gate is shut. The release runs only if the hand still holds
    that item (a switch or a drop in the wind-up throws nothing), and reads the launch on
    its own frame, so the item goes where the view looks then.
  - **A skin with no clip** (`PlayerSkin.throw` is None: the mannequin) stamps no delay, and
    the item leaves on the frame of the click, from no ready pose.
  - **The release re-equips the hand** (`NeedsRefresh`), and the equip plays the next item's
    ready pose or stops the slot, so the clip's follow-through blends out over the equip's
    blend rather than playing to its end.
  - **With V down the fire gate is shut** (`_author_throw_key`'s NOT), so the click does not
    also fire, eat or slash, and the click that threw sets `TriggerSpent`, so it cannot fire
    the automatic equipped in the thrown item's place.
  - **The click needs last frame's `ThrowAiming`:** the Branch sits before the arc is drawn,
    so a click on the frame V goes down throws nothing.
  - **The lob's arc is per item.** `ThrowArcDegrees` defaults to `THROW_PITCH_UP_DEG` (30) on
    `BP_WeaponItem`, so food and water use it; a gun's is its `throw_arc` cell in
    `gun_tuning.csv`, the GUN SETTINGS tab's last row. It is the tip over the view of a
    throw at nothing in reach. Per item too are the speed (`ThrowSpeed`, 1100
    cm/s) and the tumble (`ThrowSpinDegS`, 540°/s): the launch reads the one off `Held`, the
    flight the other off `Thrown`.
  - **A melee weapon is thrown, not lobbed** (`throw_tuning.MELEE_THROW`, spread into the
    knife's and the axe's defaults; a sword's builder would do the same): 1800 cm/s, so its
    curve to a point 10 m off is nearly flat and it reaches 33 m; 8° up at nothing in
    reach, which rises 30 cm over the hand and carries 15 m, against the lob's 1.5 m over
    13 m; and 1080°/s of spin. Its `ThrowEdgeOn` makes the release square it up
    (`throw_flight._author_square`): `MakeRotFromX(ThrowVelocity)` on the detached item, so
    its X runs along the throw and its Y level across it. Every melee model is built blade
    up, edge towards +X, so the blade's plane is then the plane it flies in and the tumble,
    which turns about the across axis, is a throwing axe's forward spin, edge first. A new
    melee model must be built the same way round, or it spins flat-on.
    - The flag is its own bool, not `Melee`: the verifier counts the Branches that ask
      `Held.Melee` (one: the fire gate's).
    - That SetActorRotation is the only one in the graph, and `verify/weapon_inputs.py`
      requires it to come after a detach: nothing turns a weapon still in the hand.

  The flight (`throw_flight.py`) is **kinematic**, not
  physics (items are NoCollision): start + v t + g t²/2 under `THROW_GRAVITY_Z`, the arc's own
  gravity, traced frame to frame on Visibility; on a hit it backs off the surface, traces down
  to the ground and becomes an ordinary `Dropped` item. In the air it tumbles end over end,
  top first, its own `ThrowSpinDegS` (`THROW_SPIN_DEG_S`, 540°/s, by default) about the level
  axis across the throw, added frame by frame (`_author_spin`); it rests as it came down. One item flies at a time.
  What it strikes is the next point's. `ThrowKeyForced` and `ThrowClickForced` are the probe's stand-ins for
  the key and the click
  (`probes/probe_throw.py`, and `probe_throw_melee.py` for the knife and the axe); the throw
  numbers are in `throw_tuning.py`.
- **A thrown blade wounds a body and stays in it, and lodges in a tree** (`weapon_component/throw_strike.py`,
  called by the flight on the frame its segment trace hits something, before the item is set
  down). The whole stage is behind one Branch, `Thrown.ThrowDamage > 0`: the base item's is 0,
  so a thrown gun, mushroom or canteen does neither. The knife's is 50 and the axe's 75
  (the defaults in `throw_tuning.py`; each is its `throw_damage` cell in `gun_tuning.csv`,
  the GUN SETTINGS tab's last row: see Tuning), against the slash's 35: the throw costs the
  weapon until it is picked up again.
  - **A body** (the struck actor has a `BP_HealthComponent`) loses `ThrowDamage`, with the
    three stamps a pellet leaves (`LastDamageTime`, `DamagedByPlayer`, `LastHitFrom`: so a
    thrown blade counts the kill and enrages a wendigo), and `BloodClass` is spawned at the
    wound. No hot blade's double.
  - **A blade in the head does more** (`_head_worth`): the damage is times the struck
    body's own `HeadMultiplier` (1.75, the pellet's: `hit_zones.py`) where the bone the
    blade went in at is one of its `HeadBones`. Only the head: a limb takes it whole.
    That bone is the one the blade is then left in, so a blade seen in the head was a
    head shot. So where it went in (`_author_skin`, below) is found **before** the wound,
    and two variables on the component carry it across: `ThrowBone` (a Name, None for a
    body the blade could not be set into) and `ThrowSkin` (the point on that bone's body).
    `probes/probe_throw_head.py` throws both blades at a zombie's head and at its middle.
    - A probe that aims at the head must aim at the middle of the head's **body**
      (`_head_middle`): the `Head` bone itself is the base of the skull, and the reticle
      there is on the neck, which the `Spine` body covers.
  - **The blade stays in the body** (`_author_stick`): set on the model as it is into a
    trunk (the same `_author_lodge`, the pose below) and attached to the mesh at the bone
    it struck, KeepWorld, then straight to the landing's `Dropped = true`. So it goes
    where the body goes, alive or a ragdoll, and E takes it back from within
    `INTERACT_RADIUS` of the blade itself. Nothing else knows it is there: it is an
    ordinary pick-up whose actor moves.
    - **Where on the body is a trace of the mesh's physics bodies alone**
      (`K2_LineTraceComponent`, as the pellet's hit zone), since the flight's hit is on
      the capsule, far wider than the model. First **on along the blade's own line**:
      from that hit the way the segment flew and `STICK_LINE_REACH_CM` (120) far (not the
      segment itself, which is a frame long and can end short of the model). What that
      strikes is what the blade struck. A blade can also cross the capsule beside the
      model, having wounded it all the same: then, and only then, a second trace runs
      from the hit towards the bone nearest it (`FindClosestBone_K2`, bodies only) and
      `STICK_TRACE_PAST` (1.5) times as far. The one that strikes writes its `BoneName`
      to `ThrowBone` and its `HitLocation` to `ThrowSkin`, which the set and the attach
      read after the wound.
    - **The take detaches** (`pickup._author_take_item`'s `DetachFromActor`, KeepWorld):
      an item taken into the bag with something else in hand is only hidden, and would
      ride on with the body.
    - **A corpse's lifespan ends with the blade still in it**: the engine detaches
      attached actors as it destroys an actor, so the blade is left where the corpse lay,
      a pick-up still. Nothing here does that.
    - A dead body cannot be struck at all: its capsule is NoCollision and the Ragdoll
      profile ignores Visibility, so a throw passes through a corpse as a pellet does.
  - **`ThrowPast` is what the fall's ground trace ignores** (an Actor array on the
    component): emptied every strike, and given a body the blade could not be set into
    (no Character, or neither body trace found anything: `ThrowBone` is None), which drops it at its foot. The
    trace down then cannot land the item on the body's own arm or knee. A wall, a tree or
    the ground must never go in it: the same trace finds the ground through them.
  - **A tree** (no health, and the struck component is an `InstancedStaticMeshComponent`:
    chop's test) struck within `LODGE_MAX_HEIGHT_CM` (250) of its foot chips
    (`ImpactClass`) and keeps the item: one `SetActorLocationAndRotation`, then straight to
    the landing's `Dropped = true`, skipping the fall. Lodged, it is an ordinary pick-up
    hanging in the tree, and E takes it back. The foot is the tree instance's own origin
    (`GetInstanceTransform`, world space), not a trace, which a branch would stop. Higher
    than the pick-up could reach (`INTERACT_RADIUS` from the player's middle), it falls to
    the foot of the tree like any item.
  - **The pose is the item's own** (`combat/lodge.py`; `knife.knife_lodge`,
    `axe.axe_lodge`): `LodgeTurn`, a pitch that takes what goes into the wood (the knife's
    blade, the axe's bit) onto the item's +X, composed before `MakeRotFromX` of the
    segment it just flew; and `LodgePoint`, the point of its frame set on the hit, a
    `LODGE_*_DEPTH_CM` behind the tip or the bit. Both come out of the model's measured
    constants; a new blade's builder calls `lodge_pose` with its own.
  - `LodgeTurn` is a rotator variable, not a pitch into a Make Rotator: `verify/firing.py`
    counts the Make Rotators in the graph. The move is `SetActorLocationAndRotation`, not
    the release's `SetActorRotation`, which `verify/weapon_inputs.py` allows once.
  - `verify/throw_strike.is_strike_node` sets the stage's nodes aside in the older
    whole-graph counts (blood and impact spawns, `LastHitFrom` writes, the chop's tree
    cast, the pellet's body trace). `probes/probe_throw_strike.py` throws both blades and
    a gun at a trunk, and `probes/probe_throw_stick.py` at a body: alive, killed by the
    throw, and gone. With `--windowed` and `OW_THROW_SHOTS=1` each saves a picture of
    every lodged blade. A body the throw kills drops its gun beside it, and E takes the
    item nearest the reticle: the probe presses past it.
- **The use key is the sights key on an item with no sights** (`weapon_component/use.py`,
  names in `use_tuning.py`). `Using` is the key held (or `SightsForced`, the probes'
  stand-in), not sprinting, with a valid `Held` whose `HasSights` is false; `UsePressed` is
  its first frame. The stage runs before the aim, which reads `Using` so the key does not
  also aim, and hands the aim the one poll of the key.
  - **A use is a fragment in `use.KINDS`,** run every frame after those two are written,
    which asks its own flag of `Held` behind a Branch on `Using` or `UsePressed` (false with
    empty hands, so `Held` is valid there). To add one, write it in a module of its own and
    add it to `KINDS`. Don't poll the key anywhere else.
  - `HasSights` is read on the true arm of an `IsValid(Held)` Branch, never folded into the
    key's condition.
- **The stick burns** (`stick.py`, `weapon_component/torch.py`, numbers in `torch_tuning.py`).
  `BP_Stick` is Quaternius's `SM_WoodenTorch` at 0.18 (48 cm), flagged `Burns`, the sixth
  issued item. A press of the use key within `STICK_LIGHT_RADIUS_CM` (3 m) of a campfire
  (any `CampfireClass` actor) sets it `Lit` until `BurnOutTime`, `STICK_BURN_S` (120 s) on.
  - **It burns on its own Tick,** in the hand, in the bag (hidden) and on the ground, and
    shows `SM_WoodenTorch_Fire` and a point light in place of the bare model while `Lit`.
    Burnt out it is a stick again and can be relit: nothing is spent.
  - **Its graph names its components,** so `build_stick` wipes the graph before it rebuilds
    the model: with last build's nodes still reading the dropped components, the compile
    fails.
  - **The carry does not lower it** (`carry.py`: `Burns` joins `Melee` and `Consumable`):
    it is carried up in `A_HoldTorch`.
- **`FireWard` is fire held out in front of the player** (`paths.FIRE_WARD_VAR`, a bool on
  `BP_WeaponComponent`). `torch.py` writes it on every arm, every frame: true while `Using`
  with a `Lit` item in hand, false otherwise, so the key let go, a sprint, a burn-out, a
  drop, a throw or a switch all lower it with no code of their own; the dead gate lets it
  go too. A wendigo reads it (`Scripts/npc/CLAUDE.md`, "Fire holds the wendigo off").
  **Nothing else may write it** where the keys are: a probe that set it by hand is
  overwritten on the next frame (`probes/probe_wendigo_ward.py` holds out a real stick).
  The server's copy of a client's character writes its own, from the use key the
  client reports and its own stick (`weapon_component/holds.py`).
  - **Held out, the stick's `AimPose` is swapped for its `UsePose`** (`A_WardTorch`) and
    the hand re-equips, so the equip and the keep-alive play it with no branch of their
    own. `WardItem` is the stick that is up and `WardCarryPose` what to put back; the
    lowering is tested before the raising. `probes/probe_lit_stick.py` runs all of it.
- **A blade is heated at a campfire** (`heat.py`, `weapon_component/heat.py`, numbers in
  `heat_tuning.py`). With an item flagged `Heats` in hand (the knife, the axe), E on a
  campfire in reach (`INTERACT_RADIUS`) sets it `Hot` until `CoolTime`, `HEAT_S` (20 s) on;
  a press on a hot one starts the time again. Nothing is spent.
  - **It cools on its own Tick,** in the hand, in the bag and on the ground, as the stick
    burns: `heat.build_heated_model` wipes the item's graph, builds the model and authors
    the Tick, for the stick's reason (its nodes name its components).
  - **The glow is an overlay material, not a second mesh:** `M_HotMetal`, unlit and
    additive, masked along an axis of the model component's own space, so the blade glows
    and the handle does not. Each item has an instance (`MI_HotKnife`, `MI_HotAxe`:
    `Axis`, `Start`, `Fade`, measured off the mesh; a scaled static mesh's are in mesh
    units). `HeatMaterial` on the item is what its Tick puts on `Model` while `Hot`, with a
    dim red point light, `HeatGlow`. The material is flagged `used_with_skeletal_mesh` by
    the builder: the knife is one, and a game cannot set the flag itself.
  - **Emissive above about 1 blooms out to white-yellow.** `HOT_EMISSIVE` is 1.0.
  - **The use key on a hot blade cauterises** (`weapon_component/cauterize.py`, a kind in
    `use.KINDS`): a press calls `RemoveActiveEffectsWithGrantedTags(Debuff.Bleeding)` on
    the player's ability system. The bleed is named by its tag because survival's
    `GE_Bleeding` is built after this graph. The blade stays hot.
  - **A hot blade's blow does double damage to a creature afraid of fire**
    (`weapon_component/hot_blow.py`, the blow's `damage` fragment in `punch._author_blow`).
    The knife stage's blow reads `BlowDamage`, written just before the health is: the
    strike's damage, or `HOT_BLOW_SCALE` (2) times it when `Held` is valid, `Held.Hot`,
    and the body carries the `FearsFire` actor tag (three nested Branches). The tag is the
    creature's (`Scripts/npc/CLAUDE.md`): combat never names a wendigo. A punch has no
    such fragment and takes its literal.
  - `probes/probe_hot_blade.py` runs all of it in a game; with `--windowed` and
    `OW_HOT_SHOTS=1` it saves a picture of each hot blade from in front of the player.
- **Kill rewards happen only on the `DamagedByPlayer` arm.** That covers the kill count, the two
  shells and the gun roll. The world-floor net writes `Health = 0` down the same death path, and
  it must not pay out.
- **`BP_AmmoPickup` is walked into.** It measures its own distance on its own Tick. `Credited`
  stops a player with two shotguns being paid twice. It destroys itself only once something has
  taken it.
- **Balance:** sustained DPS across the five weapons spans 75–171 (asserted). The shotgun does
  8 × 18 = 144, so one connected shot kills a 100 HP wanderer. The weapons differ in how damage
  is delivered, not in how much.

## The motion-matching base (G3, 2026-10-08)

The player's base movement is Epic's Game Animation Sample ("GAS": its motion matching,
not the ability system): the sample's `SandboxCharacter_CMC_ABP` and its
`CHT_PoseSearchDatabases` chooser, on the hidden UEFN mannequin the MetaHuman follows
(`Scripts/asset_pipeline/CLAUDE.md`, "The skeleton bridge"). `gas_locomotion.py` authors
it, `gas_locomotion_consts.py` holds its names, `verify/gas_locomotion.py` checks the
graph and `probes/probe_gas_locomotion.py` what it plays (`probe_net_gas_locomotion.py`:
another player's copy and the server's).

- **One switch: `GAS_LOCOMOTION`** (`gas_locomotion_consts.py`). Off, the player is the
  mannequin on the patched `ABP_Unarmed` again after a weapons build, with nothing else to
  change. A checkout without the sample (or without `build_gas_bridge.py`'s assets) wears
  the mannequin too, and says so.
- **One skin** (`skin.py`): `player_skin()` is `SKIN_GAS`, the UEFN mannequin. Its
  `anim_bp` is the graph the layers, the slots and the pose variables are in
  (`ABP_WeaponLayers`, below); `base_anim_bp` (`worn_anim_bp`) is what the Mesh component
  runs, the sample's. A probe finds the row with `skin_of_mesh`.
- **The anim Blueprint is patched where it lies, not copied.** The sample's choosers take
  an object of `SandboxCharacter_CMC_ABP_C` and of no other class: a duplicate ran, read
  the character correctly and was handed no database (`LogChooser: Error: ... ContextData
  entry 0 expects an object of type SandboxCharacter_CMC_ABP_C`). So it is a row of
  `gas_paths.PATCHED`, `import_gas.py` leaves it alone once it is here, and the weapons
  build patches it every run (each part is taken out or rebuilt first). To get the
  sample's own back, delete the file and run `import_gas.py`.
- **What it reads of the character is re-authored** (`Update_PropertiesFromCharacter`).
  As shipped it asks the pawn for `S_CharacterPropertiesForAnimation` through
  `BPI_SandboxCharacter_Pawn`; patched it fills that struct from the pawn's
  `CharacterMovementComponent`, as the sample's own character did (read off
  `SandboxCharacter_CMC.Get_PropertiesForAnimation` with a cold run of
  `dev/graph_fingerprint.fingerprint` on the sample project). So the character Blueprint
  implements and replicates nothing for it, and it runs on every machine. The speeds,
  the stamina-gated sprint and the aim's walk stay the C++ movement's: the gait is read
  off them (`IsSprinting`; a pace under `WALK_BELOW_CMS` is a walk), never set. The
  player faces the view, so the rotation mode is Strafe. Stance is Crouch while the
  movement crouches (G5, below). `AC_PreCMCTick` and `AC_PostABPTick` did not
  come across: each only broadcasts its own tick, the first for the sample character's
  speed logic (ours is C++) and the second for nothing the graph reads.
  - **The landing is kept on the anim instance** (`OwWasFalling`, `OwFallVelocity`,
    `OwLandVelocity`, `OwLandedAt`): the sample's character kept `JustLanded` from its
    own `OnLanded`.
  - **An enum the graph must choose at run time is a number cast to it**
    (`Utilities|Enum|BytetoEnumE_Gait`, behind `SelectInt` and `Conv_IntToByte`); the
    numbers are read off the compiled class's Python enums at build time.
  - **A `K2Node_PropertyAccess` says nothing to Python** (no path, no `export_text`):
    which fields a graph reads was learned from the sample character's Make node, not
    from the anim Blueprint's readers.
- **The databases' search indices are built as a game starts** when it runs from the
  editor binary (out of the derived-data cache after the first time): until they are
  there the motion matching picks nothing and the body stands in its reference pose,
  with `LogPoseSearch: ... databases AsyncBuildIndex are in still in progress` in the
  log. `probe_gas_locomotion` waits for the first pick. A packaged game has them cooked.
- **The server branch is its own** (`gas_locomotion._author_server_branch`; A4's rule,
  `server_anim_consts.py`): one Blend Poses by bool on `ServerPose`, before the pose
  history. A server skips Foot Placement and Leg IK (the ground traces under the feet,
  as the old graph's Control Rig was); the search, the lean, the aim offset, the root's
  offset and the pose history are on both arms. `verify/server_anim.py` still checks
  `ABP_Unarmed`'s branch (the keyed rig's, and each wanderer's); the worn graph's is
  `verify/gas_locomotion.py`'s. The sample's graph has a blend by bool of its own (the
  aim offset's), so the server's is found by its flag, not by its class.
- **The sample's foley component rides on the player, silent** (`install.install_foley`,
  `GasFoley`). The sample's clips carry foot, jump and land notifies that look for
  `AC_FoleyEvents` on the owner and play the sample's own sound in 2D when there is
  none. The player's has a bank with nothing in it (`DA_SilentFoleyBank`): with no bank
  at all it logs an `Accessed None` at every footfall. The game's footsteps are still
  `BP_FootstepComponent`'s, by ground covered.
- **Memory:** a server or a `-nullrhi` client peaks at 4.2–4.3 GB with the sample's
  databases loaded (1.9 GB before). The chooser brings in the dense, sparse and
  extreme-sparse sets alike; dropping the ones the game never selects is not done.
  At 32 bots the server's world tick was 26.4 ms mean, 111.5 p99 (one client, a 45 s
  window, an editor open: A4's own figure was 25.3 / 87.0 with the editor closed), so
  the search itself did not show in the mean.

## The weapon layers (G4, 2026-10-08)

Everything a weapon, a stance or a hit does to the player's body is a second anim
Blueprint on the sample's skeleton, `ABP_WeaponLayers` (`/Game/Sourced/MetaHuman`), linked
into the motion-matching one by a Linked Anim Graph node after Remap Curves.
`weapon_layers.py` authors its start (an Input Pose, the three slots), `gas_locomotion.py`
the link, `weapon_layers_consts.py` holds the picture and the names,
`verify/weapon_layers.py` and `verify/gas_locomotion.py` check them.

- **Its graph has `ABP_Unarmed`'s shape, with an Input Pose where the state machine was**,
  so `aim_pitch.py`, `body_pose.py`, `support_hand.py`, `stance_clips.py` and
  `server_anim.py` run on it as written, each on `skin.anim_bp`, and so do their
  verifiers. The sample's graph was not patched for them: it has component-space
  conversions, blends and a root of its own that those builders would have taken for
  theirs. The upper body is a layered blend per bone from `spine_01`, as it was: the
  sample's graph has no AnimationLayering slot (its one montage slot is full body, and is
  out of the pose line but while a traversal plays: G5, below).
- **The link is after the root's offset.** The aim's blend is in mesh space, so an aimed
  chest faces where the capsule does; before Offset Root Bone it would face where the
  lagging root does (the sample turns in place). It is before the feet and the pose
  history, and on both arms of the base's server branch: the layers move the hit bodies
  and the muzzle, and the layer graph has A4's branch of its own (a server skips
  FullBodySlot), which is the one `verify/server_anim.py` checks for the player.
- **The pose variables are on the linked instance, not the mesh's own.** A graph gets it
  with `GetLinkedAnimGraphInstanceByTag(LAYERS_TAG)` on the mesh
  (`weapon_component/sight_pitch._anim_instance`: the four writers, `sight_pitch`,
  `pose_weights`, `support_hand`, `look`), a probe with `p.pose_instance(mesh)`. Montages
  and slot questions (`PlaySlotAnimationAsDynamicMontage`, `IsSlotActive`,
  `IsPlayingSlotAnimation`) stay on the mesh's own instance: the layer class has
  `bUseMainInstanceMontageEvaluationData`, so its slots play the main instance's montages.
- **A linked graph's tag is the graph node's `tag`**, not the inner struct's (`Tag` there
  is a deprecated field Python calls protected).
- **A clip belongs to one skeleton**, so the layers' clips are copies on
  `SK_UEFN_Mannequin` (`asset_pipeline/retarget_to_uefn.py`: the two ready poses, the
  punch and the six flinches off the mannequin, the crouch, crawl, kneel and throw off
  Quaternius's own rig; `SKIN_GAS` names them), and the poses the build keys (the hold
  poses, the shotgun's, the throw's, the slash) are keyed on that skeleton from them and
  from the sample's idle.
- **No clip played into a slot may have root motion** (`hold_pose.in_place`,
  `verify/weapon_layers.py`). A montage of a clip with the flag on takes the character's
  movement over. The sample's clips have it on, the hold poses are copies of its idle,
  and a hold pose is a looping montage: with the knife or the axe out the player could
  not walk. The mannequin's punch has it on too (150 cm forward), so until G3 a punch
  carried the player forward; its copy here is in place, flag off.
- **The body is 10 cm shorter than the mannequin** and the ready poses are retargeted
  chain to chain, so the fist of a ready pose is 11-14 cm nearer and 14-19 cm lower in the
  capsule's frame (`carry_tuning.CARRY_GRIP`, re-measured) and the sights' view with it.
  The shotgun's grip thumb is laid for this hand (`shotgun_pose.SHOTGUN_THUMBS`).
- **A body on another skeleton re-creates the hold poses** (`A_HoldItem` and the rest
  are deleted and keyed again: `hold_pose._copy_of`), and every item Blueprint outside
  this package that names one is left holding nothing: run `build_survival.py` and
  `build_clothing.py` after the weapons build (their verifiers say so: "is carried in
  A_HoldItem").
- **Probes that share a game disturb each other** more than they did (the dev-all-guns
  request, `RaiseForced`, a thrown item): `probe_carry`, `probe_knife`, `probe_punch`,
  `probe_net_fire` and `probe_net_melee` pass alone and failed behind another probe.
- **A headless frame is about 10 ms now**, so a probe that writes an eased value every
  frame and reads what the Tick made of it (`probe_scope_hide` did) sees one ease step of
  that size; hold the key's stand-in (`SightsForced`) and wait instead.
- **`probe_sight_align` fails one check of 186** (the rifle, looking up 25°: the shot's
  point 0.37° off the sight line). The view is still and the point is a hit 7.7 m away,
  5 cm off the line: the aim trace grazing a branch from the lower eye point, not the pose.

## Crouch, slide and traversal from the sample (G5, 2026-10-08)

The moves the sample ships beyond the walk and the run, on the keys the game already
had, each behind its own switch in `gas_moves_tuning.py` (`GAS_CROUCH`, `GAS_SLIDE`,
`GAS_TRAVERSAL`; a builder or a verifier asks `gas_moves.crouch_on()` and its two
siblings, which are also off on the mannequin fallback). Change one, then run the
weapons build. `verify/gas_moves.py` checks each switch both ways,
`probes/probe_gas_traversal.py` crouches, slides and mantles a 1 m block, and
`probes/probe_net_slide.py` slides as a lagged client.

- **The crouch is the sample's Stance.** `Update_PropertiesFromCharacter` sets
  `Stance = Crouch` while `GetStance(pawn) == 1` (crouched, not prone: the movement's own
  answer, so every machine's copy), and the sample's chooser picks its crouch databases
  (idles, walks, starts, stops, pivots, the stand-to-crouch transition). The weapon
  layers then author **no** crouch blend (`stance_clips.py`): the two Quaternius crouch
  clips are still built and named by the skin, and come back with the switch off.
  `PoseCrouch` is still eased (nothing reads it on this body). Prone, the kneel and the
  crawl are the layers' as before; the capsule, the speed and the key are unchanged.
- **The slide is ours, posed by the sample's clip.** The sample's CMC character has no
  slide: its slide is the Mover variant's movement mode and the Mover's chooser, neither
  of which came across (the CMC chooser has no slide row). So the movement is a state of
  `UOtherworldCharacterMovement` (`Source/CLAUDE.md`, "Predicted movement"): the crouch
  key pressed in a sprint (`weapon_component/stance.py`: `RequestSlide`, and that one
  frame the stance is the crouch although sprinting) starts it if the sprint is going at
  least `SLIDE_MIN_START_SCALE` of its speed; it coasts along the way it was going for
  `SLIDE_SECONDS` (1 s, about 3.7 m), from its speed down to the crouch's, steering and
  spending nothing, and ends crouched (sprint still held: the sprint's escape stands it
  up, as ever). Standing up, lying down or leaving the ground ends it early.
  - The pose is `M_Neutral_Slide_FootOut_Loop` blended in by `PoseSlide` in the layers'
    graph, over the crouch and under the crawl; the weapon component eases `PoseSlide`
    to `IsSliding(owner)`, which a simulated copy answers from the character's
    replicated `bSliding`. The clip holds its own root (`force_root_lock`).
  - **`CrouchForced` is a probe's press of the crouch key**, ORed with the key and spent
    by the frame that read it, after the slide's Branch (the press is a pure read).
  - **A sprint is a sprint only while it is steered ahead**: a probe that presses the key
    and stops steering on the same frame gets a crouch, not a slide.
- **Traversal is the sample's own component** (`gas_traversal.py`): `AC_TraversalLogic`
  on the player as `GasTraversal`, with a `MotionWarping` component. The jump key's
  `Started` calls `JumpPressed`, a custom event of the character (a probe calls it: an
  injected `IA_Jump` never reaches a headless game): on the ground, not crouched and not
  already in one, it calls `TryTraversalAction` with the sample's own sweep (75 to 350 cm
  ahead by speed) and jumps only when the check or the montage choice failed.
  - **It climbs `LevelBlock_Traversable` and nothing else.** The check casts what the
    sweep hits to that class and reads the ledges off its splines. **The forest has
    none**, so until blocks are placed (or the check is taught the forest's rocks and
    logs) the jump key jumps everywhere, as before. The probe spawns one
    (`OtherworldLoadLibrary.SpawnActorAt`).
  - **The component is patched where it lies** (a row of `gas_paths.PATCHED`): both
    reads of `S_CharacterPropertiesForTraversal` are made from the owner as a Character
    (the sample asked through `BPI_SandboxCharacter_Pawn`), and its Server event asks the
    RPC guard first (by its own name, which has no row: the default rate), then refuses a
    ledge further than `LEDGE_REACH_CM` from the server's copy.
  - **Its montages play in the base's own `Slot(DefaultSlot)`, which is in the pose line
    only while one plays** (`gas_traversal_slot.py`: one Blend Poses by bool on
    `OwTraversing`, the component's `DoingTraversalAction`). The layers' ready and hold
    poses play in a slot of the same name, upper body only, in their own graph: with the
    sample's slot always in the line a raised gun or a knife in hand became the whole
    body's pose and the motion matching under it stopped (the legs stood while the
    capsule ran). `probe_gas_traversal`'s first check guards it.
  - **While one plays the hand's pose is off** (`weapon_component/carry.py`: `Lowered`
    is also `DoingTraversalAction`): the sample's Play Montage stops every montage, and
    the keep-alive, which asks `Lowered`, would otherwise play the hold pose over the
    climb (one montage of a group stops the other). The pose is back when it ends.
  - **Removing an earlier run's nodes walks data pins only** (`_data_feeders`). A walk
    through exec pins reaches the graph's events: it took the component's BeginPlay out
    and unhooked `TryTraversalAction`'s entry, and the jump key then did nothing at all.
    `verify/gas_moves.py` checks both are whole.
  - **As a client of a server it is authored and not proven.** The component replicates
    and the flow is the sample's (the client's check, a Server event, a Multicast, and
    the sample's own client-authoritative position for the montage's length:
    `SetReplicationBehavior`). There is no `--net` probe: a block a probe spawns exists
    on one machine, and the levels have none. Prove it before blocks go into a level
    (`Scripts/net/CLAUDE.md`, "Traversal").
  - A shot fired in a traversal leaves from the carry's lowered point (`Lowered` is
    held), and the fire gate does not ask about it.

## Tuning

`COMBAT`, a frozen `CombatConfig` in `tuning.py`, is the **one** place global combat numbers
live: lethality, sprint and stamina, ADS, mouse sensitivity, recoil and the hit reactions.
Per-weapon numbers live in `_weapon_specs()`.

**The jog, the sprint and the stamina bar's times are `player_tuning.csv`'s** (`player_tuning.py`),
laid over `COMBAT` and tuned in game by the menu's PLAYER SETTINGS tab (`docs/stance.md`).

**Per-gun numbers can be tuned in game** (the M panel's **T** tab, `graphics_menu/tune_*.py`):
- `gun_tuning.csv` (tracked) holds each gun's 21 tunable stats (`gun_tuning.TUNE_STATS`: damage,
  pellets, range, interval, reload, magazine, sights zoom, shot volume, the accuracy columns,
  the sway's rate and the throw's arc).
- **The melee weapons have rows too** (`Knife`, `Axe`, under the guns:
  `gun_tuning.MELEE_WEAPONS`), holding their throw alone: `throw_arc` and `throw_damage`
  (`melee_tuning.py`, which `knife.py` and `axe.py` lay over `MELEE_THROW`; the defaults
  are `throw_tuning`'s). `throw_damage` is the table's 22nd column and no gun's: a gun's
  `ThrowDamage` stays 0, which is what keeps a thrown gun from wounding.
  `gun_tuning.columns_of(weapon)` says which columns are a weapon's own; a cell outside
  them is empty in the CSV, a dash on the tab, and never written onto the weapon. The
  slash's damage is not there: it is `COMBAT.knife_damage`, a literal in the blow's graph.
  `_weapon_specs()` lays it over its literals, so **the CSV wins**; the literals are the
  fallback for a missing cell. Edit the CSV by hand or through the tab, never only the literal.
- The tab writes the carried guns live and Enter saves the CSV; the Blueprints change only when
  `build_weapons_and_combat.py` and then `build_graphics_menu.py` run (the HUD's copy of the
  table is baked too: `tune_checks` fails if it is stale).
- A tuned value can break a design check that pins it (e.g. "the shotgun does 18 per pellet",
  the DPS spread, the recoil 4:1): update the check with the design, or re-tune.

There is no DataAsset on purpose. Every number is a pin literal baked into a compiled graph,
and `Content/` is not committed, so an edit in the editor would be erased by the next build.
The verifier asserts the old loose constants are gone.

## Topic notes: read the one you are changing

The design rules and traps for each area are in `docs/`, one file per area. Read the file
before you change anything it covers. It is not loaded until then, so a session that only
touches the fire graph doesn't pay for the notes on blood.

| file | covers |
|---|---|
| `docs/aiming.md` | the carry (a gun rides lowered until aimed or fired: `weapon_component/carry.py`), shoulder and down-the-sights aim, the accuracy cloud and recoil, the reticle and scope, sight pitch, the player's own head hidden down the sights, the camera's near plane (2 cm, so the pistol's hands are not cut open), the left hand held on the gun there (`weapon_component/ads.py`, `accuracy.py`, `sight_pitch.py`, `sights.py`, `head_hide.py`, `sway.py`, `support_hand.py`), how a weapon sits in the hand (`grip.py`, `verify/grip_fit.py`) |
| `docs/stance.md` | sprint, blocking (the guard's quarter damage and stamina cost), crouch and prone (`weapon_component/stance.py`), the procedural body poses (`body_pose.py`, `weapon_component/pose_weights.py`) |
| `docs/health.md` | health, respawn and the pack's numbering (`health_component.py`, `respawn.py`), dying (the ragdoll collapse), hit boxes and hit reactions (`hit_zones.py`, `hit_bodies.py`, `hit_reaction.py`), blood and bullet impacts on the scenery (`burst.py`, `blood.py`, `bullet_impact.py`) |
| `docs/skin.md` | the player's body: the Meshy mesh and its retarget (`skin.py`) |
| `Scripts/Sound/CLAUDE.md` | every sound: the areas' tables, the bindings, attenuation, volumes, `build_sound.py` (it was `docs/audio.md`) |
| `docs/firing_gate.md` | what may fire and when, eating through the fire button (`weapon_component/consume.py`), debug mode |
| `docs/anim_blueprint.md` | authoring Animation Blueprints from Python: AnimGraphs, pose pins, anim node settings |

## Collision

- **The collision enum is `unreal.CollisionResponseType.ECR_BLOCK`** (`CollisionResponse` is a
  struct). Use `get_/set_collision_response_to_channel`.
- **To test a collision change without playing,** spawn the actor into the editor world and run
  `SystemLibrary.line_trace_single` through it. A/B it by reverting the change.

## Still needs a play session

These are feel checks a headless run can't do:

- the motion matching (`gas_locomotion.py`): it was seen in six 1280x720 pictures from in
  front (`probe_metahuman_look.py`) and measured, never played. Whether the jog at 400 and
  the sprint at 600 cm/s read right on clips shot for the sample's 500 and 700 (it scales
  the play rate); the run strafe, whose hips turn 22–37° toward the way it goes while the
  chest follows up to 46° (the sample's own strafe: is that the strafe wanted, or should
  the aim offset hold the chest squarer); turning in place with the view, idle breaks,
  pivots and stops under real keys; and the first seconds of a game from the editor binary,
  standing in the reference pose while the indices load;

- the sample's crouch, the slide and the mantle (G5, `gas_moves_tuning.py`): measured by
  `probe_gas_traversal.py`, never seen or played. How the sample's crouch reads under a
  raised gun and at the crouch's 180 cm/s; the slide: whether 1 s and about 3.7 m feel
  right, the one loop clip blended in over 0.1 s with no "into" and no "out" (the sample
  has both, for the Mover), a gun in the sliding hand, the camera dropping with the
  capsule in one frame, and that it makes the crouch's noise; the mantle: the arms over
  whatever is in the hand a moment before, the hold pose snapping back as it ends, and
  the 0.25 s back to the motion matching;

- the weapon layers on it (`weapon_layers.py`): seen in pictures (`probe_metahuman_look.py`:
  the axe, the rifle carried and down its sights) and measured, never played. Whether the
  sights' view, about 12 cm lower than on the mannequin, reads right; the MetaHuman's left
  hand down the sights (the hidden mesh's is on the gun, `probe_sight_hands`; the drawn
  one is open beside the receiver in the picture); the sample's own aim offset under a
  lowered gun and with empty hands; a strafe's hips turning 22-37° under an aimed chest;
  Foot Placement under a crouch, a crawl and a kneel; and the punch, which no longer
  carries the player forward;
- sprint held with an aim key until the stamina runs out: no key can be pressed in a headless
  game, so the latch setting (`SprintSpent`, `docs/stance.md`) is checked on the graph only.
  Whether needing to let go of Shift before the next sprint feels right;
- the jog (`player_gait.py`): the jog clip covers about 470 cm/s and plays at rate 1 under a
  400 cm/s jog, so the feet slide a little; a sprint plays the same clip at the same rate
  (there is no sprint clip), so only the ground's speed tells the two apart; and a jog nudged
  on the PLAYER SETTINGS tab drifts off the jog row until the next weapons build;
- the carry (`carry_tuning.py`): how a rifle reads jogging in one hand with the arm's swing
  (there is no two-handed carry clip), whether the gun coming up in 0.25 s behind the first
  shot reads, and whether 1.5 s is the right time to keep it up after the last one;
- the knife: how the keyed slash reads (`knife_anim.SLASH_KEYS`), whether the blow at
  `COMBAT.knife_impact_s` lines up with the cut, how the knife sits in the fist (the pistol
  grip's solve), and how the two hold poses read (`hold_pose.HOLD_*_DIRS`; the wrist keeps the
  pistol pose's angle on a lower forearm);
- the axe: how it reads in the fist and over the shoulder in the knife's stance (the head
  stands 35 cm above the hand, near the face), and swung on the knife's short slash, which
  was keyed for a blade (`probes/probe_axe.py` only proves it is in the hand and lands);
- chopping (`chop_tuning.py`): whether three blows a piece feels right, whether the chips
  read as a cut (there is no chop sound and no mark on the trunk), where the wood lands on a
  slope or among roots, and how the wood looks in the hand: the fist's joints sit up to 1.6 cm
  inside the 6 cm log (it has no handle), and a log dropped with G stands on its end;
- the matches and the campfire: the box in the fist (it is 1.3 cm thick and the one fist
  pose is closed on a pistol's grip, so the fingers stand up to 4 cm off it), a strike with
  no animation, sound or message (above all the silent one with no wood), a fire that
  appears at once 130 cm ahead, on a slope or inside whatever stands there, and how the
  pack's flat-shaded flames and the point light read at night;
- the stick (`stick.py`, `hold_pose.HOLD_TORCH_DIRS`, `WARD_TORCH_DIRS`): how the torch
  reads carried beside the head and held out at arm's length (both keyed, both only looked
  at from behind in one windowed shot), the fist on a 3.8 cm handle, the pack's flat-shaded
  flames and the 7 m point light at night, lighting it with no animation, sound or message
  (and the silent press with no fire in reach), whether 2 minutes of burning and 3 m of
  reach feel right, whether a torch burning down unseen in the bag reads as fair, and the
  middle click no longer aiming a knife or an axe over the shoulder;
- the heated blade (`heat_tuning.py`): heating it with no animation, sound or message
  (and the silent press with a cold fire out of reach, or with the stick in hand), nothing
  on the HUD saying it is hot or how long is left, whether 20 s is long enough to reach a
  wendigo, the flat red of the axe's whole head by day (the overlay adds one colour, and
  the top of the haft inside the head glows with it), the glow and its light at night,
  and cauterising with no animation, sound or cost;
- the punch's feel: whether the blow at `COMBAT.punch_impact_s` lines up with the fist in
  `MM_Attack_01`, and whether a flinch cutting the swing short (same montage group) reads;
- a real trigger pull through the hit zones (a pistol head shot should take a wanderer from 100
  to 61);
- the fitted hit bodies (`hit_bodies.py`): whether a shot that looks on the zombie ever misses
  (the bodies are capsules down each bone's own vertices, cut where a limb tapers: `capsule_fit.py`; `FIT_ROUNDNESS` and `FIT_END_OVERLAP` trade overhang
  for gaps), and whether a near miss vanishing at the capsule, with no chips behind, shows;
- the pistol emptying after 8 shots, clicking, and R refilling it to 8 (no key can be injected
  into a headless game, so only the verifier covers this);
- the rifle-arm pose on flinching creatures;
- whether a sustained SMG burst reads as a burst;
- bringing the sights up (`weapon_component/seat.py`): from the key the camera travels in
  one motion from the boom onto the sights, zooming as it goes, while the view stays on the
  target and the gun rises into it, about 0.3 s in all from a lowered gun. Whether that
  reads as one move; whether the camera reaching the eye point just before the gun is level
  (0.9 of the way when the gun is 10° off, `SIGHT_SEAT_DEG`) shows the gun still coming up
  from below, and whether its path bowing about 30 cm toward the rising gun is seen; the
  crosshair going out at 0.9 of the way with no fade (`RETICLE_HIDE_SEAT`), now before the
  sights have settled on the middle; the scope's glass closing while the rifle is still
  rising; sprinting out of the sights still lowers the gun under a camera on its way home;
- every gun down its sights, now that the eye is ON the sight line and the view runs down it
  (`docs/aiming.md`): the SMG11's is a 3 mm peep in a plate 15 cm from the eye, so the plate
  hides much of the view below and beside the target; the shotgun's support-hand fingers
  stand just right of the bead (its thumb no longer stands left of it); the adventurer's
  hair shows at the top of the AK's view;
- the hands down the pistol's sights, now that the eye is 25 cm behind the grip
  (`PISTOL_SIGHT`) and both hands stand partly in the view: whether they take too much or
  too little of it; the left hand, whose fingers are seen spread below the grip rather than
  wrapped over the right hand's (the support hand's pose, hidden at 14 cm); and anything
  the 2 cm near plane (`NEAR_CLIP_CM`) shows that 10 cm hid (the player's own body with
  the boom pulled in against a wall);
- the shotgun's thumbs (`shotgun_pose.SHOTGUN_THUMBS`): how the right thumb reads over the
  stock's wrist from behind and at the hip (its base joint is inside the wood, as the rifle
  pose's was), whether the left one closes on the pump or hovers (its base is 5 cm off the
  wood), and both on the mannequin fallback, where only the directions were carried over;
- the shotgun's left hand (`shotgun_pose.SUPPORT_PALM`, `SUPPORT_FINGERS`): how the wrist
  reads now the hand is turned 16° down under the pump on the rifle pose's forearm, the
  fingertips leaning forward up the pump's right side, and the right hand, left as the rifle
  pose has it (a pistol grip's fist on a straight stock: its fingers run into the receiver's
  belly and the guard);
- the head leaving the view on the way onto the sights (`HEAD_HIDE_SEAT` 0.8): whether it is
  seen to go, from behind, in the last of the camera's travel, and whether the headless
  shadow is noticed with the sun behind the player;
- the sight sway (`sway_tuning.py`): whether 0.3° reads as a held breath or as drunk,
  above all through the 4x scope, and whether crouch and prone steady it enough; whether
  the halved rate (0.5) is slow enough to time a shot, and holding the breath
  (`breath_tuning.py`): Left Alt with a real keyboard (on a Mac it is Option), whether 5 s
  held and 5 s winded feel right, and that nothing on the HUD shows the breath left;
- the left hand held on the gun down the sights (`support_hand.py`): whether the hand
  now reads as one with the gun while swaying and walking, on the AK above all; whether
  the hand is seen to shift (0.7 cm) as the hold eases in with the sights; a throw wound
  up down the sights keeps the left hand on the gun until the sights come off;
- a reload with the sights up: the view follows the gun, so it is thrown about with the
  arms. A hit no longer does (`weapon_component/steady.py`: no flinch down the sights);
  whether taking hits with no reaction at all reads, and the hit-then-sights blend;
- the `GUN_ACCURACY` numbers: how wide each cloud feels at the hip, and whether the reticle's
  gap (and its 240 px cap) reads well on a real window;
- how the death camera looks under the terrain;
- how the sights' pitch looks at steep angles (the eye swings on an arc round the spine);
- the throw: whether V and its arc read well (dot size and spacing, the landing disc on
  slopes), whether 11 m/s at 30° up feels right, holding V and clicking with a real
  keyboard and mouse (the probe forces both); the throw's clip: whether the release
  0.12 s after the click feels right, the follow-through cut short by the re-equip, how
  it reads with a two-handed gun in the fist, crouched and prone;
- the throw at the reticle (`weapon_component/throw_launch.py`): whether the arc reads
  as under the reticle (it starts 55 cm to one side and closes on the point); the arc
  jumping as the reticle crosses the edge of a near thing onto far ground, or leaves
  the item's reach (12 m for a lobbed item: just inside it the throw goes up at about
  45°, just outside it is the tipped lob); a gun thrown straight at a point 3 m off at
  11 m/s, which is fast for a lob;
- the ready pose (`throw_pose.py`): how the cocked arm reads from behind with a long gun
  in the fist (seen once, in one windowed shot: the shotgun stands up beside the head),
  the 0.15 s it takes going up and coming down, holding it while walking, crouched and
  prone, and with the left hand of a two-handed gun left where the pose puts it; and whether 540°/s of tumble suits
  every item; a melee weapon's throw: whether 18 m/s at 8° up reads as thrown hard rather
  than shot, whether three turns a second reads as a spin or a blur, and the snap as the
  knife or the axe squares up to the throw on leaving the hand;
- a thrown blade's strike (`throw_tuning.py`): whether 50 and 75 HP are worth giving the
  weapon up for, and 75 and 112 in the head (a thrown axe in the head kills a full-health
  wanderer); how often a throw at a moving wanderer's head is in the head, the blade
  leaving the hand to the left of and below the camera; a hit with no sound, on a body or in the wood; the blade always going in
  point or bit first whatever its spin was at the moment it struck, and only into a tree
  (off a rock or the ground it still falls flat); how the lodged knife and axe read
  from the front and from the far side of a thin trunk (7 cm and 5 cm are in the wood);
  one that struck above 2.5 m dropping to the foot of the tree; and a blade thrown into a
  wendigo's capsule beside its body still wounding it (the flight has no hit zones);
- a blade left in a body (`weapon_component/throw_strike.py`): where it sits on a walking,
  swinging wanderer, since it goes in at the body part nearest where it met the capsule
  (thrown at a zombie's side it is in the arm) and not always where it was aimed; whether
  it clips through the limb as the bone turns; taking it back off a wendigo that is
  attacking (E within 2.5 m of the blade, nearest the reticle); a blade in a corpse lying
  under the gun the corpse dropped, where E takes whichever is nearer the reticle; and
  the blade left hanging a little off the ground when the corpse under it goes after 60 s;
- the stance clips in motion (`stance_clips.py`): the crouched walk covers about 55 cm/s and
  plays at 2x, so at the crouch's 270 cm/s the feet slide; the crawl is the UAL's face-down
  swim (no crawl clip exists in the packs), a two-armed pull and a frog kick, which may read
  as swimming on dry ground; with a gun in hand, only its legs show under the aim (prone keeps the gun up). A prone body is longer
  than its capsule, so it can clip into slopes and walls. On the mannequin fallback the
  procedural poses still apply, with the walk cycle on top of them;
- the bullet impact on the scenery (`bullet_impact.py`): whether 1-3 cm lit chips and dust
  read at all at range and at night (they are not emissive, as blood is not), and whether
  0.6 s is long enough to see where a round landed. It leaves no mark behind;
- the shotgun's index finger along the receiver, 4 cm above the guard (`docs/aiming.md`);
- the glimmer (`glimmer_tuning.py`): it was seen only in 1280x720 pictures (four across a
  flash at noon and at midnight, `OW_GLIMMER_SHOTS=1` on the probe, windowed). The 28 cm
  star at 8 emissive that rested at 0.3 was too bright; whether the 18 cm one at 3 that
  rests at nothing is now too faint by day over pale sunlit ground, where light added to
  near-white shows least; whether 5.5-8.5 m from the camera is the right "near"; how it sits over a long gun (it stands at
  the item's origin, not its middle), over a blade lodged in a trunk or a body, and in tall
  grass.
