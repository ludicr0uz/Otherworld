# net — the multiplayer conventions

Read this before any multiplayer task. The strategy is `serversupportsysdesign.md` (4.1
authority, 4.2 where state lives, 4.8 the two modes); the authoring helpers are
`Scripts/uebp/CLAUDE.md`; the harness is the root `CLAUDE.md`'s `--net`. This file is the
rules a graph follows, how to prove one, and what the spike (task M4, 2026-10-06) found
broken. Its code is what the builders share to keep one graph right in both modes
(`__init__.py` maps it): `pause.py`, the session (`session_consts.py`,
`game_instance.py`), where state lives (`state*.py`), who is nearby (`players*.py`) and
whose keys a graph reads (`input_checks.py`) and the audit of every random draw
(`random_consts.py`, `random_checks.py`).

## The authority pattern

The server owns every piece of game state. A client asks, and draws what it is told; nothing
a client reports is trusted (the game is PvP).

```
owning client: read input  --Server RPC-->  server: validate, change state
                                               |-- state replicates to the clients
                                               '-- Multicast: sounds, blood, impacts, montages
```

- **State changes behind the authority switch** (`MACRO_SWITCH_AUTHORITY`, or
  `MACRO_SWITCH_AUTHORITY_COMP` in a component). A variable a client must see is replicated
  (`net.replicate`), and what it should do about a change goes in the RepNotify.
- **Input is read only where the pawn is locally controlled,** and turned into a Server
  event (`net.server_event`) on something that client owns: its pawn, a component of it, its
  controller or its PlayerState.
- **Cosmetics** (a sound, an effect, a montage) are a Multicast called by the server, or a
  RepNotify. Unreliable unless losing it matters.
- **A client has no GameMode.** `GetGameMode` is None there. What a client reads lives on
  the GameState, a PlayerState, or a replicated actor or component ("Where state lives",
  below).
- **Player 0 means nothing on a server.** There, index 0 is whoever joined first (client 2
  in one spike run, client 1 in the next). A component asks its owner, a widget its owning
  player, an NPC chooses among the players.
  - **Done for what a player owns (M8).** Every HUD fragment reads `FN_GET_OWNING_PAWN`
    (the HUD's own pawn); the components already asked `GetOwner`, and no animation graph
    or widget read a pawn by index. `owner_checks.check_no_player_zero_pawn` (the menu
    verifier) fails on a `GetPlayerPawn` in any Blueprint of the game. A widget that
    needs its pawn uses `FN_GET_OWNING_PLAYER_PAWN`. `probe_net_hud_own_pawn.py` is the
    two-client check.
  - **Done for everything else (M9): "Who is nearby", below.** `GetPlayerPawn` is gone
    from the node catalog, and the same check fails on any builder that names it.
  - **Done for the controller and the camera (M10): "Input", below.**
  - **Done for a kill's credit (M14):** it is the blow's instigator's ("Health and
    damage", below). `state_graph.first_player_state` and `FN_GET_PLAYER_STATE` are gone.

## A screen asks, the character acts (M11, done)

A server has no HUD, so nothing a player does may live in a widget graph. Each thing done
through a screen is **one custom event on `BP_WeaponComponent`**, which the HUD calls with
what was picked (`graphics_menu/ask.py`, `ask(ed, wc, ASK_MOVE, execs, made, From=…, To=…)`)
and which decides whether it happens. The names are `combat/ask_consts.py`.

| event | asked by | what it does | becomes a Server event in |
|---|---|---|---|
| `AskSlot(Slot)` | a click on a slot, Enter on a bag slot, the 1-9 keys | raises `SlotRequest` | **done, M18** |
| `AskMove(From, To)` | a drag from slot to slot | raises `MoveTo`, `MoveFrom` | **done, M18** |
| `AskNext()` | the Q key (no screen) | raises `NextRequest` | **done, M18** |
| `AskDrop(From)` | a drag out of the inventory | raises `DropRequest` | M23 |
| `AskTakeOff(Slot, To)` | Enter or a click on a worn slot, a drag off one | raises `TakeOffTo`, `TakeOffSlot` | M24 |
| `AskWear(From)` | a drag onto the worn grid | raises `WearRequest` | M24 |
| `AskLootTake(Body, Index)` | the loot window's Enter or click | the take itself, with its refusals (`weapon_component/loot_take.py`) | M23 |
| `AskSaveExit()` | the menu's save-and-exit row | starts the countdown the component runs (`weapon_component/save_exit.py`) | M35 |

The trigger and R are keys, not a screen's asks, and have Server events of their own:
`Server_Fire` and `Server_Reload` ("The shot and the reload", below).

- **The slots' three are reliable Server events** (`ask_consts.SERVER_ASKS`; "The
  inventory", below); the rest are plain calls yet. `combat/verify/asks.py` asserts which
  is which on the compiled class; the task that makes one a Server event adds it to
  `SERVER_ASKS`.
- **The int asks only raise the request** the component's Tick already serves, so the
  serve is still where a move is validated (the slots': on the server alone). Three of the serves (take-off, wear, drop) sit
  in the Tick's local-only half (`tick.py`, `_author_actions`): M24 and M23 move them to
  where the server runs them.
- **The HUD writes none of those variables** and takes nothing out of a body:
  `graphics_menu/ask_checks.py` fails on a `Set` of any of them in the HUD's graph, and on
  a movement call there.
- **A new action through a screen gets an event the same way.** Refuse in the event, not
  in the widget: what the widget greys out is display, and a client's widget is not trusted.
- **Still in the HUD:** the saved profile's write, read and delete and the level reopened
  after it (the single-player save is the client's own file: 4.8; M35 gives the server
  its own), the dev-all-guns cheat (4.7), and the tuning tabs' writes onto live objects
  (dev tools, 4.7). `Searching` (the kneel) is still written by the loot window.
- **Probe:** `probe_asks.py` calls each event in a game and takes the save-and-exit row.

## Input (M10, done)

A component ticks on every machine that has its character: the player's own, the server
and every other client. Only the first has that player's keys.

- **A HUD polls its owning controller** (`FN_GET_OWNING_PC`). The engine makes a HUD only
  for a local player and none on a dedicated server, so a HUD's polls and its widgets need
  no gate.
- **A component polls `LocalPC`, behind the local gate**
  (`combat/weapon_component/local.py`). At the head of the Tick, after the dead gate:
  the owner is a Pawn, its controller is a PlayerController and `IsLocalController`.
  True writes `LocalPC` (that controller) and `LocalInput`; anything else clears both.
  `local_pc(ed)` is the pin every poll's self is; `_author_local_only` asks
  `LocalInput` again further down a chain.
- **What runs where in the weapon component's Tick** (`tick.py`):

  | part | runs on |
  |---|---|
  | the dead gate | every copy |
  | the view, the aim trace, sprint, block, stance, use, the sights, sway | the local player's |
  | the mirror: the pose's state off what was replicated (`look.py`) | every copy but the local player's |
  | the pose (weights, support hand, accuracy, ready pose, steady) | every copy |
  | the carry (`Lowered`), and the look reported to the server | the local player's |
  | the trigger and the action keys (`_author_actions`: fire, reload, slots' keys, drop, interact, throw, the HUD's requests) | the local player's |
  | the slots served and placed, the equip (`_author_upkeep`) | every copy |

  A later task that moves an action to the server splits it there: the poll stays on
  the local arm and calls a Server event; what the event does goes with the parts that
  run on every copy, behind the authority switch.
- **Never ask for a controller or a camera by index.** `GetPlayerController(0)` is the
  local player on a client whichever character the graph is on (one press of fire used to
  fire every character that client could see), and the first joiner on a server.
  `FN_GET_PC` and `FN_GET_CAM` are gone from the node catalog; the camera is `LocalPC`'s
  `PlayerCameraManager` (`combat/weapon_component/aim.py`).
- **A controller is not there at BeginPlay** unless the pawn was possessed before the
  world began: a client's arrives by replication, a respawned pawn's after the spawn. What
  needs one (the look scales' cache, the audio listener) runs once on the first local
  frame (`local._author_local_once`, `LocalReady`).
- **A controller that is not a PlayerController is not local input.** The engine calls an
  AI controller "local" on the server.
- **A probe's forced key** (`FireForced` and the rest) is read on the local arm, so it
  presses nothing on another player's character: write it on the acting client's own.
- `input_checks.check_local_input` (the menu verifier) fails on a by-index node in any
  Blueprint, on a key poll that is not a HUD's on its owning controller or the weapon
  component's on `LocalPC`, and on a weapon component with no `IsLocalController`.
  `probe_net_local_input.py` is the proof: client 1 forces fire on both characters, its
  own spends a round and the other's does not, on either client or the server, which has
  no HUD and no widgets; `--game` runs its standalone arm.
- **The non-local copies of a character** pose from the mirror ("Other players'
  characters", below) and hold the item the server says is in hand ("The inventory",
  below); nothing is fired there but by the server, when the owner asks ("The shot and
  the reload", below).
  The walk speed, the sprint and the stance of the character itself are M12's, below.

## Movement states are predicted (M12, done)

- **Sprint, prone and the aim-walk are the movement component's**, a C++ subclass
  (`Source/CLAUDE.md`, "Predicted movement"; `combat/player_move.py` reparents the
  player onto it). Each is a flag on every move the owning client sends, and both
  machines work the speed, the capsule and the stamina out of the flags in the same
  step, so the client moves at once and the server agrees.
- **A graph hands it wants and reads its state** (`uebp.nodes.move`), behind the local
  gate: `SetSprintHeld`, `SetStance`, `SetAimWalk`. It never writes `MaxWalkSpeed`, a
  crouched height or the stamina (`combat/verify/aiming.py`, `stance.py`,
  `weapon_inputs.py` fail on one).
- **Stamina is the server's.** It drains and refills with the moves, so the client
  predicts it; a change the server alone makes (`SpendStamina`: a blocked blow;
  `SetStamina`: a loaded profile) reaches the client as a correction, because each move
  reports the client's stamina and the server corrects one more than 2 points off.
  The weapon component's `Stamina`, `Sprinting`, `SprintSpent` and `SprintAhead` are
  copies, written on the owning machine only: on the server ask the movement component.
- **The speed numbers are the character asset's**, the same on every machine. The
  PLAYER SETTINGS tab's (`SetPace`) are taken only with authority: single player, and
  the 4.8 table's "dev settings tabs" row for a client.
- **The check:** `uepy.py --net --clients 1 --lag 120 --probe
  Scripts/probes/probe_net_move_states.py`. At a 137 ms ping the client reached each
  state's speed within 0.1-0.25 s and took no correction through the jog, a sprint
  started and stopped, prone, standing, the aim and its release, while the server held
  the same character at 600, 80 and 200 cm/s. Its control: told to sprint at 900 on its
  own word, the client took 20 corrections in 1.5 s. Each correction is a
  `MOVE-CORRECTION` line in the client's log, counted in the run's report.
- **A probe drives it with** `SprintForced`, `AimForced` and `Stance` on the acting
  client's own weapon component, and `add_movement_input` each frame.
- **How another player's character looks in a state** is the next section.

## Other players' characters (M13, done)

A player reads other players by their animation. The pose part of the weapon component's
Tick runs on every copy from the component's own state; on a copy that is not its player's
own (the server's of a client's character, every other client's) that state is written
first by **the mirror** (`combat/weapon_component/look.py`), from the few facts that travel:

| fact | travels as | the copy writes |
|---|---|---|
| stance | the movement's own flags: the engine's replicated crouch and `AOtherworldCharacter::bProne` (C++, to simulated copies only), read with `GetStance(owner)` | `Stance`; the capsule is sized in C++ (`Source/CLAUDE.md`) |
| aim pitch | the engine's `Pawn.RemoteViewPitch`, read with `GetBaseAimRotation` | the anim BP's `AimPitch`, times `SightBlend` as locally |
| aim mode | `LookAim`: 0 hip, 1 shoulder, 2 sights | `Aiming`, `SightAiming`, and `SightBlend` eased to it |
| raised to fire, or not | `LookLowered` | `Lowered` (the carry runs only where the keys are) |
| the hand's pose class | `LookPose`: the ready pose itself, the held item's `AimPose`, none with empty hands | `HandPose`, which the equip and the keep-alive play |

- **Three replicated variables and nothing more,** `COND_SKIP_OWNER`, on a component that
  now replicates (`net.replicate_component`, in the build and on the character). The owning
  machine reports them with `Server_SetLook`, reliable, only on the frame one changes:
  the aim keys are that machine's (the hand is the server's since M18, but when it is
  raised is the aim's). **One rule now reads them:** the server draws a shot inside its
  own copy's `AimSpread`, which follows the mirrored aim mode and stance ("The shot and
  the reload", below), so a client that reports the sights it is not using gets their
  cloud. What the sights cost, the slower walk, is the movement component's
  (`SetAimWalk`); tying the cloud to that is still to do.
- **`HandPose` is what the equip plays,** not `Held.AimPose`: where the keys are the equip
  takes it off `Held`; on a remote copy `Held` is not read for the pose. The item in a
  remote copy's hand is the server's since M18 (`HandClass`, "The inventory", below).
- **The guard is mirrored since M20** (`Blocking`, replicated to everyone but the owner:
  "Melee, the guard, the throw and the take", below).
- **Not mirrored** (not asked for, and each is a later task's): the kneel, the support
  hand's point (the copy's own `Held`'s), montages (M21).
- **`verify/fixtures.py` keeps the mirror's nodes out of `wg`** (`wg_mirror`), as it does the
  dead arm's: the older "written once" counts are about the machine with the keys.
  `verify/look.py` reads the mirror.
- **The check:** `uepy.py --net --clients 2 --probe-timeout 240 --probe
  Scripts/probes/probe_net_look.py`: client 1 crouches, lies down, aims at the shoulder and
  down the sights with the view up and down, and holds a pistol, a knife, the matches, the
  stick and the rifle's ready pose; client 2 and the server compare their copy of that
  character with what client 1 posted, step by step (the stance and capsule, the mode,
  lowered, the pose and that it plays, the body's pitch, the feet on the ground). With
  `--windowed` and `OW_LOOK_SHOTS=1` client 2 saves a picture of each step. `--game` runs
  its single-player arm.
- **Two players start exactly two capsule radii apart** (the engine nudges the second off
  the one PlayerStart until they just touch). There the server will not let a crouched
  character stand, or go from crouch to prone: its stand-up test counts the touching
  capsule as in the way, while the owning client, whose copy of the other is a hair
  smaller (a proxy's capsule is), stands. They disagree until one walks off. A probe that
  changes stance walks clear first; the fix is player starts (M16).

## Health and damage (M14, done)

Health is the value a cheater most wants, so only the server changes it, and every blow
says who struck it. `combat/damage.py` is the whole of it.

- **A blow calls the target's `TakeHit(Amount, From, InstigatedBy, Cause)`,** a custom
  event on `BP_HealthComponent`, with `damage.hit(ed, as_health, amount, came_from,
  instigator, cause, execs)`. No graph writes another body's `Health`, `LastDamageTime`,
  `LastHitFrom` or `DamagedByPlayer` (`combat/verify/damage.py` fails on one in the weapon
  component, `npc/verify.py` in a wanderer's controller).
  - **The instigator is a controller:** `damage.owner_instigator(ed)` from a component's
    graph (its owner's `GetInstigatorController`; a pawn is its own instigator), the
    wanderer's own from its swing. **The cause is an actor:** the gun, the item in hand
    (none for a fist), the thrown blade, the wanderer.
  - **`TakeHit` is not an RPC.** It runs behind Switch Has Authority: called on a client's
    copy it does nothing, and no client can send it. A client's blow reaches the server
    when its action does (the shot: M19, `Server_Fire`; a swing and a throw: M20,
    `Server_Punch`, `Server_Slash`, `Server_Throw`), and the server's copy of that
    action calls `TakeHit`.
  - It floors `Health` at 0, stamps `LastDamageTime`, keeps `LastHitFrom`,
    `LastInstigator` and `LastCause`, and sets `DamagedByPlayer` where the instigator is a
    PlayerController (so a wanderer's blow blames no player, as before).
- **What travels,** to everyone: `Health` (RepNotify), `MaxHealth`, `Dead`, `HitCount`,
  `LastHitFrom`, `NpcId`, and what the body carries (`Loot` and its names, icons and
  tints: M16, "Death" below). The component replicates (its own default, and on the character
  and the wanderer). `LastInstigator` and `LastCause` stay on the server.
- **A client's copy ticks as the server's does** and reads what arrived: the HUD's bar and
  the heartbeat off `Health`, the flinch off its drop, the collapse off `Health` at 0.
  `OnRep_Health` (a client only: its Remote arm) makes that right:
  - `HitCount` moved with it: a blow. `LastDamageTime` is stamped with **this machine's
    clock** (it is never replicated: each machine's game time is its own), which the bar
    over a wanderer and the grunt read; `PrevHealth` is left behind, so the Tick flinches.
  - It did not: a drain, a heal, a wanderer's maximum. `PrevHealth` follows `Health`, as
    the drain keeps it on the server, and nothing flinches.
- **The server's alone, in the Tick:** the world-floor net and the debuff drain (behind
  one switch at its head), `Dead`, the kill and its drops, the replacement.
- **`Dead` is the server's word; `DeathPlayed` is each machine's latch** for "this copy has
  run the death path" (the cry, the collapse). They are two variables because `Dead` can
  arrive before a client's Tick has seen `Health` at 0, and the path would then never run.
- **The heartbeat is the local player's** (`IsLocallyControlled`): another player's
  character has a health component on this machine too.
- **Still written directly, each on the server:** a heal (`survival/easy_heal.py`: the
  consume ability, M26), a wanderer's maximum at possession (`npc/stats.py`), a loaded
  profile (standalone). A Blueprint `Set` of a RepNotify calls `OnRep_Health` on that
  machine too, where its Remote arm does nothing.
- **A drain's death is nobody's kill yet:** bleeding out after a player's blow is not
  credited (the drain names no one). PvP credit is M15's.
- **A probe** takes health with `health.call_method("TakeHit", (amount, vector, controller,
  actor))` on the server (or in single player); a probe's own write of `Health` on a
  client is that client's copy alone, until the server next sends one.
- **The check:** `uepy.py --net --clients 2 --probe-timeout 240 --probe
  Scripts/probes/probe_net_health.py`: a zombie stood beside client 1 hits them, and the
  server, client 1 (its bar) and client 2 (its copy; its own bar unmoved) agree; a kill
  naming client 2's controller is client 2's; client 2's own `TakeHit` calls change
  nothing; at 20 HP the heart is heard on client 1 alone; at 0 `Dead` reaches both.
  `--game` runs its single-player arm.

## The inventory (M18, done)

What a player carries is the server's. The server keeps the item actors every graph already
works on (`Inventory`, each item's `Slot`, `Loaded`, `Reserve`); what travels is a **record**
of them, plain data (`combat/record_vars.py`):

| variable | holds | replicates to |
|---|---|---|
| `InvClass[i]`, `InvSlot[i]`, `InvLoaded[i]`, `InvReserve[i]` | a row per carried item, in `Inventory`'s order: its class, its slot code, its rounds | the owning client (`COND_OWNER_ONLY`) |
| `HandClass` | the class in hand, or none | everyone else (`COND_SKIP_OWNER`) |

- **It can be saved as it stands:** classes and ints, nothing that points into a running
  world. A load is one `SpawnActor` per row. The character's save and a body's loot
  (M23) should hold rows of it, not a second form.
- **The server writes it every Tick,** after the slot sync, behind HasAuthority
  (`weapon_component/record.py`): no graph that changes what is carried has to remember
  to. Replication compares before it sends, so an unchanged record costs no traffic. The
  dead gate stops that Tick, so the shed empties the record itself.
- **A client holds no inventory of its own.** BeginPlay issues the loadout with authority
  only. A client's item actors are a **picture** of the record, local and unreplicated
  (`weapon_component/view.py`): each replicated variable is a RepNotify that raises
  `ViewDirty`, and the next Tick's upkeep, without authority, calls `ViewRow` per row
  (the actor at that index kept if it is of the row's class, else destroyed and one
  spawned; then its slot and rounds) and `ViewTrim`. Its own player's from the rows;
  another player's character from `HandClass` alone, one actor, in the hand. The slot
  sync and the equip run after it on every copy, so nothing below knows whether its
  actors are the server's or a picture.
- **The picture is remade only when a record arrives.** What a client changes itself
  stays until the server next says otherwise, and it is
  why an action that is not yet the server's (a drop, a meal, a garment: M23, M24,
  M26) still shows on its own client, and is undone by the next record. Make the
  action a server request; do not write the record from a client. (The throw and
  the take of an item are: M20, below.)
- **The slots' asks are Server events** (`AskSlot`, `AskMove`, `AskNext`, reliable): the
  HUD's clicks and drags, and the 1-9 and Q keys, which call them from the Tick's local
  arm (`slot_moves.py`). The request is raised on the server's copy and served there
  (the serve is behind HasAuthority), where a slot out of range, an empty one or an
  item that does not fit is refused. Bringing an item to hand and putting it away are
  both `AskSlot`. In single player they are plain calls: nothing changed.
- **Python cannot send a Blueprint Server event.** `call_method` on a client runs the
  event there (the engine routes only native functions from `ProcessEvent`; a Blueprint
  one is routed by the VM, when a graph calls it). So a probe asks with `p.ask_slot(wc,
  slot)`, `p.ask_move(wc, src, dst)` or `p.hold(wc, index)` (`probes/context.py`): the
  call itself with authority, and on a client a write of `SlotForced` or
  `MoveForcedFrom`/`MoveForcedTo`, which the component's Tick turns into the ask where
  the keys are read. The shot's and the reload's doors are `FireForced` and
  `ReloadForced` (M19); a swing's `KnifeQueued` and `PunchQueued`, the guard's
  `BlockForced`, the use key's `SightsForced`, the throw's `ThrowKeyForced` and
  `ThrowClickForced` and the take's `InteractForced` (M20); the next Server event
  needs one of the same kind.
- **Not yet in the record:** worn garments (M24), a heated blade and a burning stick
  (the item's own state, M25), an item lying in the world (M23). The dev-all-guns cheat
  still spawns on the machine it is pressed on.
- `combat/verify/record.py` checks the flags and the wiring. Proof: `uepy.py --net
  --clients 2 --probe Scripts/probes/probe_net_inventory.py` (client 1 moves the axe to
  another bag slot, brings the pistol to hand and asks for a move no rule allows; the
  server's copy and its record agree after each, the refused one moved nothing, and
  client 2 sees the pistol in client 1's hand); `--game` runs its standalone arm.

## The shot and the reload (M19, done)

Shooting has to feel immediate to the shooter while the server stays the judge of ammo,
timing and hits. `combat/shot_vars.py` has the picture; the graphs are
`combat/weapon_component/shot.py`.

```
owning client                             server
the trigger's gate passes  ------------>  Server_Fire(AimPoint), reliable
  the kick, the shot's sound                AsksServed + 1
  a round off its own Loaded,               a valid Held, a living owner, a gun,
  its own NextFireTime, AsksSent + 1        a round, the cooldown?  no: nothing
                                            a round, NextFireTime, the draw in ITS
                                            cloud, the pellets from ITS muzzle to
                                            AimPoint, TakeHit, the noise
R  ------------------------------------>  Server_Reload: AsksServed + 1, ReloadNow
  ReloadNow on its own copy, AsksSent + 1
```

- **The client sends one thing: where its reticle rests.** The server traces from its own
  copy's muzzle (`carry._author_shot_origin`) and draws the shot inside its own copy's
  `AimSpread`, so a client cannot shoot from where it is not, nor choose its place in
  the cloud. The hold-breath sway and the sights need nothing of their own: both move
  the client's view, and the view is what `AimPoint` is taken from; down the sights the
  server's cloud is closed because its copy mirrors the aim mode. The aim mode is still
  the client's word ("Other players' characters", above).
- **What the owning client predicts** is what it can know: the kick (it turns its own
  controller), the shot's sound, the round and the cooldown on its own copy, the reload
  on its own copy. Not the hit: it traces nothing and rolls nothing ("Random rolls").
  Blood, chips, the tracer and the headshot's X are drawn by the machine that ran the
  shot, so a client of a server sees none of them yet (M21).
- **`AsksSent` and `AsksServed` reconcile the rounds.** The client counts the asks it
  sends; the server counts the asks it answers, fired or refused, replicated to the
  owner as a RepNotify that raises `ViewDirty`. While the server's count is behind, the
  record in hand is older than the client's own shots: the view places items but leaves
  their rounds alone (`view.py`), and takes them on the frame the counts agree. Without
  this a burst's counter climbs back a round every time a record lands. A refused
  shot's round is handed back by the same rule.
- **Both events are reliable:** a lost ask would leave the two counts apart for good.
  An automatic gun sends one every `FireInterval`: eleven a second from the SMG.
- **The server's cooldown has grace** (`FIRE_GRACE_S`, 0.1 s; stamped from the later of
  now and the old deadline): two honest shots can arrive closer together than they were
  fired.
- **A request can arrive after the blow that killed its sender,** so the events ask the
  health themselves; the Tick's dead gate only stops keys.
- **In single player** the local arm has authority: nothing is predicted, the counts
  read 0 sent and one served per ask, and a Server event is a plain call. One shot, as
  before.
- **A dedicated server poses the bodies it judges** (`combat/server_pose.py`): an
  unrendered skeletal mesh ticks its animation but never refreshes its bones, so on a
  server every hit body and every muzzle stood in the reference pose. Every body with a
  health component is set to `AlwaysTickPoseAndRefreshBones` there, at BeginPlay,
  behind IsDedicatedServer. M22's history of hit boxes reads the same bones.
- **Not here:** lag compensation (M22: the server traces against where the target is
  now, so at 120 ms a strafing target is missed where the shooter saw a hit); the fight
  as others see it (M21). The server takes the shot whether or not it has the player
  sprinting or guarding. Melee, the throw and the guard are the next section.
- `combat/verify/shot.py` checks the flags and the wiring. Proof: `uepy.py --net
  --clients 2 --probe-timeout 240 --probe Scripts/probes/probe_net_fire.py` (client 1
  kills a wanderer down the sights and reloads; the server's rounds are client 1's, its
  count of asks client 1's, the kill client 1's, and three `Server_Fire` in one frame
  spend one round); also with `--lag 120`; `--game` runs its single-player arm.

## Melee, the guard, the throw and the take (M20, done)

Every other way of hurting something follows the shot: the keys are read where they
are, a reliable Server event on the weapon component is the action, and the server
judges it from its own copy. `combat/strike_vars.py` has the picture.

| the client asks | the server checks, on its own copy | then |
|---|---|---|
| `Server_Punch`, `Server_Slash` (a swing was queued) | empty hands / a `Melee` item in hand, alive, not `Blocking`, the cooldown (0.1 s of grace) | stamps the cooldown and when the blow lands, plays the clip; its Tick sweeps and calls `TakeHit` |
| `Server_SetHolds(Guard, Use)` (either key changed) | nothing: it keeps `AskGuard`, `AskUse` | each Tick: `Blocking` = asked AND its own stamina AND not sprinting; `FireWard` = asked AND its own item in hand is `Lit` |
| `Server_Throw(Start, Velocity)` (the hand lets go) | an item in a living hand, nothing of this player's in the air, `Start` within 3 m of its copy, the speed capped at the item's `ThrowSpeed` | the item leaves the inventory, becomes a replicated actor and flies; the strike is judged once |
| `Server_Take(Item)` (E on an item) | the item exists and is `Dropped`, the taker alive and within reach of it, a slot free | into the taker's inventory; the record tells the client |

- **A blow is pending only where its Server event ran** (`weapon_component/punch.py`): the
  swing's two stages are now the event (the stamps, `Pending`, the clip) and the blow,
  which moved to the Tick's upkeep and runs on every copy. Only the server's ever finds
  a strike pending, so only it sweeps. The chop (the blow on a tree) and the hot
  blade's double hang off that same blow, so they are the server's too: **the double
  is read off the server's item**, and a client that only says its blade is hot gets
  nothing. (Heating one on a server is M25: until then the server's item is cold.)
- **The owning client predicts the swing it can see:** its own cooldown, the clip and
  the swing's sound, off the false arm of a Branch on HasAuthority. Not the blow.
- **The guard and the use key are reported, not trusted** (`weapon_component/holds.py`):
  the owning machine still writes its own `Blocking` and `FireWard` off its keys, for
  its own pose and fire gate, and tells the server on the frame either key changes.
  The server's copy writes both itself (`_author_holds_mirror`, in the Tick's remote
  arm, behind HasAuthority) from what it was told and from **its own** stamina and
  **its own** stick, and those are what a wanderer's swing (`npc/block.py`) and a
  wendigo (`npc/ward.py`) read. `Blocking` replicates to everyone but the owner, so
  another player's copy poses the guard; `FireWard` goes nowhere (the stick held out
  is seen as `LookPose`). The server's stick is lit by M25; until then a client's
  ward holds no wendigo off.
- **A thrown item is a replicated actor** (`combat/item_world.py`). What is carried is
  the server's unreplicated item actors and each client's picture of the record
  (above); the release (`Server_Throw`) sets `InWorld` on the server's actor and calls
  `SetReplicateMovement(true)` and `SetReplicates(true)`, and from then on every
  client is sent it: where it is each frame of the flight, the bone it is attached
  to in a body, and its `Dropped`, `Lodged` and `InWorld`. The flight
  (`throw_flight.py`) runs in the upkeep behind HasAuthority; `Thrown` replicates to
  the owner alone, whose arc waits on it.
  - **Replication is never switched off again.** The project replicates through the
    engine's generic driver (the log's `replication model Generic`, not Iris), where
    `SetReplicates(false)` only stops the updates: each client's copy would stand
    where it last was for good. So the take lowers `InWorld` instead, and a client's
    copy of an item hides itself while that is false (the item's own Tick, off the
    false arm of HasAuthority, first in `glimmer.author_glimmer` so every child's
    Tick has it). The engine closes the channel of a hidden actor with no collision
    by itself, so the copy of an item in a bag is gone a few seconds on.
  - **Thrown items only.** An item dropped with G, placed in the level or left by a
    kill is still each machine's own (M23): what its drop must do is call
    `item_world.author_into_world`, and the take already serves it.
- **The take is a Server event with an actor in it** (`weapon_component/pickup.py`), so
  it works for an item the server can be told of: a replicated one. An item that is
  only the client's own arrives as None and is refused. Two players reaching for one
  item: the first ask finds it `Dropped`, the second does not.
- **In single player** every one of these is a plain call on the one machine: nothing
  is predicted, the mirror never runs, and `SetReplicates(true)` on an item sends it
  to no one.
- **A probe that queues a swing must wait out the cooldown first** (the press gate
  did; the Server event now refuses one inside it), and must empty the hands the way
  a player does (a slot ask) before a punch: `Held` written to None is put back by
  the next equip, and the server refuses a punch with a gun in hand.
- **A probe's `set_editor_property` on a live actor re-runs its construction script**
  unless it is `p.set` (no edit notification): written with the default on a
  wanderer, the server's body got fresh components and each client's copy of it lost
  its health component.
- **Not here:** the swing, the throw and the hit as other players see and hear them
  (M21); lag compensation of a sweep or a throw; the pick-up of an item that is not
  replicated, the drop, and two clients on one item on one frame as a probe (M23);
  lighting the stick and heating the blade on the server (M25).
- `combat/verify/strike.py` and `verify/pickup.py` check the flags and the wiring.
  Proof: `uepy.py --net --clients 2 --probe-timeout 240 --probe
  Scripts/probes/probe_net_throw.py` (client 1 throws its axe into a trunk, all three
  machines have it lodged in the same place, client 2 takes it out with E and client 1
  sees it gone; a throw from 10 m off, a take of an item in another player's bag and
  a throw at ten times the speed are refused or capped) and `probe_net_melee.py`
  (client 1's slash and punch land by the server's sweep, the hot blade's double
  follows the server's knife, three `Server_Slash` in a frame land one blow, the
  guard reaches the server and client 2, and `FireWard` rises only with the server's
  stick burning); both clean with `--lag 120`. Single player's are the existing
  `--game` probes (`probe_knife`, `probe_punch`, `probe_hot_blade`, `probe_throw*`,
  `probe_pickup`, `probe_wendigo_ward`).

## Random rolls (M17, done)

Chance that changes the game is rolled once, by the machine that owns the state, and the
result replicates; rolled on each machine, two players would see two worlds. A roll that
only varies how something looks or sounds is each machine's own.

- **Every draw a graph makes is audited** in `net/random_consts.py` (`AUDIT`): one row per
  builder that names a `Random*` node, **state** or **cosmetic**, what is drawn, which
  machine draws it. The menu verifier fails on a builder that draws and has no row, on a
  row whose builder no longer draws, and on a Random node in a Blueprint the audited
  builders do not author (`net/random_checks.py`). **A new draw gets its row in the same
  commit.**
- **A state roll runs behind authority,** by one of three means: on an arm already behind
  the switch (the kill's, in `BP_HealthComponent`'s Tick), in a graph only the server has
  (a wanderer's AIController; the GameMode's streams), or behind its own question (the
  on-hit fragment asks `HasAuthority` of its target, so it is right in whatever graph
  lands a hit). Then store the draw (a pure node draws again at every read) and let the
  stored result travel: a replicated variable, or an actor the server spawns.
- **Never roll a state value on a client "to predict it".** Two draws do not agree. The
  owning client may predict a cosmetic (recoil's drift); the server's answer is the state.
- **A table a roll reads is the server's copy's.** `LootChances`, the on-hit bonus and the
  gun-drop table are not replicated and need not be: no client reads them.

| builder | kind | what is drawn | where, and how the others learn it (a **task**: still per machine until then) |
|---|---|---|---|
| `loot/roll.py` | state | what a killed wanderer carries: each loot-table entry against its chance | the kill's arm of BP_HealthComponent, behind the Tick's authority switch; the body's Loot arrays replicate |
| `combat/gun_drop.py` | state | whether a kill leaves a gun, and which: two streams on the GameMode | the same arm, and the streams are the GameMode's, which a client does not have; the gun is an actor the server spawns (**M23**) |
| `combat/replacement.py` | state | where a killed wanderer's replacement appears (bearing, distance, the navmesh's point) | the same arm; the wanderer is spawned by the server and replicates |
| `combat/player_respawn.py` | state | which PlayerStart a respawn is given | behind death's IsStandalone Branch and the authority switch; the new pawn replicates |
| `survival/on_hit_graph.py` | state | whether a blow leaves its on-hit effect (a wendigo's: bleeding, 33%) | behind HasAuthority of the target, in the fragment itself; the effect is the target's ability system's (**M26**) |
| `npc/patrol.py` | state | a patrol's next point and how long the wanderer waits there | the wanderer's AIController, which exists on the server alone; its movement replicates |
| `npc/stalk.py` | state | the wendigo's hunt: which way round, when it turns, the wait behind a tree | the AIController, as the patrol |
| `npc/strafe.py` | state | between two swings: the sidestep's angle, side and distance | the AIController, as the patrol |
| `npc/ward.py` | state | held off by fire: which way it circles and when it turns | the AIController, as the patrol |
| `npc/ward_roar.py` | state | held off by fire: when the first roar comes (it stands for it) | the AIController, as the patrol |
| `combat/weapon_component/firing.py` | state | where in the gun's cloud a round or a pellet goes | inside `Server_Fire`, which only the server runs (single player: a plain call); the owning client draws nothing, and what the pellets did replicates as health |
| `combat/weapon_component/chop.py` | state | where the wood lands beside the trunk, and how it lies | the weapon component of whoever chops; the server's once the chop is a server action (**M25**) |
| `world/day_night_graph.py` | state | the time of day a level starts at | every machine's own BP_DayNightCycle at BeginPlay; one clock, the server's, replicated (**M30**) |
| `Sound/play.py` | cosmetic | which take of a sound plays (every sound with more than one) | wherever the sound plays |
| `combat/hit_reaction.py` | cosmetic | which of the three front flinches a blow from the front plays | every machine's copy of the health component, off its own Tick |
| `combat/weapon_component/recoil.py` | cosmetic | the kick's sideways drift, on the view of the player who fired | the owning client: it turns its own controller, as the mouse does |
| `npc/stats.py` | cosmetic | the gap before a wanderer's next growl | the AIController (the server's); every client hears the growl once sounds are multicast (**M21**) |

- **Still drawn by the machine that acts,** each until its action is the server's: where
  chopped wood lands (M25), the hour a level starts at (M30: every machine's sky is its
  own today). A client of a server changes nothing with the first yet (its wood is its
  own copy's).
- **A dropped gun is rolled by the server and spawned there;** it reaches a client when
  items lying in the world replicate (M23). A landed bleed is the target's ability
  system's on the server; the owner's HUD reads it when the attributes replicate (M26).
- **Not runtime rolls:** the level generator's `random` (seeded, at build time: every
  machine loads the same level) and the materials' wind (a function of world position
  and time).
- **The check:** `uepy.py --net --clients 2 --probe-timeout 240 --probe
  Scripts/probes/probe_net_loot_roll.py`: the server kills all ten wanderers in a
  player's name; one body is loaded to carry a canteen on the server and never on either
  client's copy, one the other way round, the rest roll the table's 50%. Both clients
  read on every body exactly what the server rolled (matched by `NpcId`), one canteen at
  most. `--game` runs its single-player arm; `probe_bleeding.py` is the on-hit roll's.

## Who is nearby (M9, done)

A world actor, a wanderer's controller or any graph that is not a player's own asks
`BPL_Players`, a Blueprint function library (`/Game/Weapons`, built by `players.py` in
the weapons build), through `players.py`'s fragments. Never author a `GetPlayerPawn`.

| the question | the fragment | what it is |
|---|---|---|
| every living player | `living_players(ed, in_execs)` | an exec call: the array is made once. `each_living_player` wraps it in a ForEach |
| the living player nearest a point | `nearest_living_player(ed, point)`, read with `player_pin(node)` | a pure node: asked again at every read, as `GetPlayerPawn` was |

- **Living** is: the PlayerState is in the GameState's `PlayerArray`, its pawn exists, and
  it does not say `PlayerDead`. All three replicate, so a client's answer is the server's
  for the pawns it has.
- **Nearest is None while no one lives.** Put the read behind a Branch of its own
  (`combat/ammo_pickup.py`, `combat/replacement.py`). The wanderers' steps sit behind the
  tree's player-present step (`npc/agro.py`), which asks whether `LivingPlayers` is empty.
- **Who uses which:** what happens to everyone is the loop (the night's cold, a
  campfire's warmth); what one player gets or one wanderer does is the nearest (the
  ammunition box, a dead wanderer's replacement, every wanderer step).
- **The wanderers' choice is the nearest, re-asked at every read.** It can change between
  two reads of one step if two players are the same distance away, and a wanderer keeps
  no target. Choosing one and keeping them, and the cost of the pure node per read once
  there are 32 players (each read walks the PlayerArray), are M27's.
- **Rebuilding a function library:** keep the function graph and wipe its nodes
  (`players._function`). Removing the graph and adding it again names the new one
  `<name>_0`, because the compiled class still holds the old function.
- **Python can call it:** `unreal.get_default_object(cls).call_method("NearestLivingPlayer",
  (point, world))`: the hidden world context is the last argument.
  `probe_net_living_players.py` is the check, in single player and with two clients.

## Where state lives (M7, done)

`serversupportsysdesign.md` 4.2 is the table; `state_consts.py` the two Blueprints, both built
by the weapons build and named on the GameMode (`state.py`):

| home | holds | who writes | who reads |
|---|---|---|---|
| `BP_OtherworldPlayerState` (one per player, replicated to all) | `NpcKillCount`, `PlayerDead` | the server: the death graph (`combat/death.py`) | that player's HUD, through its owning controller |
| `BP_OtherworldGameState` (one, replicated) | `DebugMode`, `Difficulty` | the machine that owns it: the HUD's writes are behind `HasAuthority` of the GameState | every machine: the HUD, the weapon component, the consume ability, the wanderers' AI |
| the GameMode (the server alone) | the spawn counter, the noise record, the gun-drop streams, the combat trace's switch | the server | the server |

- **Reach them with `state_graph.py`,** never a hand-made cast: `game_state`,
  `owned_game_state` (for a write), `player_state_of` (a controller's or a pawn's),
  `owner_player_state` (a component's), and `server_game_mode`, which is Switch Has Authority
  and then the cast. Each returns the pin, the exec for "it is there" and the execs for "it is
  not": read the object only down the first. A client has neither state for its first frames.
- **No graph a client can run reads the GameMode.** `state_checks.check_no_client_game_mode`
  (in the menu verifier) scans every Blueprint: a `GetGameMode` is allowed in a class only the
  server has (the GameMode, an AI controller, a behaviour tree's node) or directly off the
  Authority arm of the switch, which is what `server_game_mode` authors.
- **A new per-player fact** is a row of `PLAYER_TABLE`, a shared one of `GAME_TABLE`; both
  are declared and replicated from the table. The team id (4.2) goes on the PlayerState.
- **A client's write to either does nothing useful** (its copy is the server's to change).
  A client that must change state asks with a Server event on something it owns. The debug
  row and the difficulty therefore do nothing as a client of a server: the dev settings' row
  of the mode table, until a later task lets the server allow them.
- **A kill is credited to the PlayerState of the controller that struck the last blow**
  (the health component's `LastInstigator`, M14: "Health and damage", below). A death
  nobody struck (the world-floor net) is nobody's.
- **The wanderer's number (`NpcId`) is taken on the server only** and replicates with the
  health component (M14), so a client's debug overlay draws the server's number.
- **A probe** reads them with `p.game_state()` and `p.player_state()`; on a server, each of
  `p.players()` has its `.player_state`, and `player_id` is the one name a server and a
  client share for a player (`probe_net_player_state.py`).
- Proof: `probe_net_player_state.py` (each client's HUD shows its own count, the shared
  debug flag, and the death menu on the one dead client; clean with `--windowed`) and, for
  single player, `probe_kill_credit.py`.

## Three questions, never "is this multiplayer"

| question | asks | node (`uebp.nodes`) |
|---|---|---|
| am I the authority? | may I change state | `FN_HAS_AUTHORITY`, `MACRO_SWITCH_AUTHORITY[_COMP]` |
| am I locally controlled? | do I read input, draw the HUD, play first-person cosmetics | `FN_IS_LOCALLY_CONTROLLED`, `FN_IS_LOCAL_CONTROLLER` |
| is this standalone? | the mode table below, and nothing else | `FN_IS_STANDALONE` |

Single player is the engine's standalone net mode: the one process has authority, is
locally controlled, runs a Server event as a plain call and a Multicast once. A graph
written to the pattern above therefore runs unchanged with no server. Write each system
once; never author an offline copy.

## What differs by mode

This table is the whole list (`serversupportsysdesign.md` 4.8, which owns it: a new
difference is added there, with its reason, in the same commit, and copied here).

| | standalone (single player) | client of a server |
|---|---|---|
| pause (title menu, M, loot window) | pauses the world, as today | never pauses; the menu is an overlay |
| the character save | the local `OtherworldProfile` slot, written by the client | a file on the server keyed to the player; the client writes none |
| death | as today: the profile is deleted, back to the title | gear onto a corpse, respawn |
| dev settings tabs and cheats | available | read-only unless the server allows them |
| wanderer population | the level's fixed count | a budget that follows the players |
| the title menu | the game opens on it, paused: Single Player and Multiplayer are chosen there | none: a connected client is in its game, however it joined (the title or an address on the command line). Leaving, a failed join or a dropped connection returns the process to standalone, and so to the title |

**Pause** (M5, done). Every `SetGamePaused` in the game is authored by `net/pause.py`, and
no builder names `FN_SET_PAUSED` itself:

- `author_pause` (the title's at BeginPlay, death's) is `SetGamePaused(true)` off the true
  arm of a Branch on IsStandalone; elsewhere the flow goes on unpaused.
  `net/pause_checks.check_standalone_pause` is the verifiers' check of it.
- `author_unpause` (the menu's first row, the death menu's restart) has no Branch: where
  nothing paused it does nothing, and in standalone nothing may stand between it and its row.
- A menu never relied on the pause to hold the character: `graphics_menu/menu_still.py`
  takes the walk on Tick and `cursor.author_hold_fire` the fire press on DrawHUD, in either
  mode. The M menu, the I panel and the loot window never paused, so they needed nothing.
- Proof: `probe_net_menu_overlay.py` (client 1 opens M and then the title; the server's
  clock runs on and its copy of the character stands still), and for single player
  `probe_death_pause.py` and `probe_main_menu.py`.

**Death** (M16, done). One death path, forked where the table says: the health component's
(`combat/death.py`) runs on every machine as before, and standalone's ends where it always
did (the pause, the death menu's restart, the profile deleted). Outside standalone:

- **Dying is the same collapse on every copy** (the ragdoll, off `Health` at 0: M14), and
  the weapon component's dead gate stops every action on every copy, the dying player's
  own first.
- **The gear goes onto the body** (`combat/weapon_component/shed.py`), the dead gate's first
  act, once: behind a Branch on IsStandalone, the server appends each item of `Inventory`
  and `Worn` (its class, `DisplayName`, `Icon`, `SlotColor`) to the body's `Loot` arrays,
  and every copy destroys its own item actors and empties its slots. A body holds
  classes, as a wanderer's does, so a looted gun is a fresh one (its rounds are M18's,
  when the inventory is plain data).
- **The body's `Loot` arrays replicate** (`BODY_ARRAYS`, on `BP_HealthComponent`), so any
  client's loot window shows a player's body, or a wanderer's, as the server has it. The
  window is the wanderers', unchanged: a dead Character that is not the HUD's own pawn.
- **The take is still the taker's own copy's** (`AskLootTake` is not an RPC until M23): a
  client that takes a row gets the item in its own bag and removes the row from its own
  copy of the body, and the server's body keeps it.
- **The respawn** (`combat/player_respawn.py`) hangs off the false arm of death's pause
  Branch, on the server: `PLAYER_RESPAWN_SECONDS` (10) after the death the controller
  lets go of the body (`UnPossess`) and the GameMode gives it a new pawn
  (`RestartPlayerAtPlayerStart`) at a random one of the level's PlayerStarts. The new
  pawn's BeginPlay issues the starting inventory on every machine, `PlayerDead` is
  lowered, and the body lies `CORPSE_SECONDS` more. The character survives; nothing is
  saved or deleted.
  - **Keep the controller in a variable** (`RespawnFor`): `GetController` is pure and
    answers None once the controller has let go, and `RestartPlayerAtPlayerStart(None)`
    does nothing, silently.
  - **Not `RestartPlayer`:** `AGameModeBase` sends a controller back to its `StartSpot`.
  - **The levels have one PlayerStart today,** so "random" picks it; more starts are the
    level generator's to place.
- **The death menu** (`graphics_menu/menu_screens.py`) is up on the dead client from
  `PlayerDead` until the respawn lowers it: behind IsStandalone the restart key is not
  polled, the hint reads `DEATH_HINT_SERVER`, and a click on it is lowered unserved.
- **The HUD follows the pawn:** every fragment asks `GetOwningPawn` each frame, so the
  respawned player's HUD is the new character's with nothing re-bound.
- Proof: `uepy.py --net --clients 2 --probe-timeout 240 --probe
  Scripts/probes/probe_net_death.py` (the server kills client 1 with a garment worn: the
  ragdoll and the empty slots on all three machines, the loot on the server and on client
  2, client 2's loot window on the body and a take, client 1's death screen, and 10 s
  later the new character, its inventory and its HUD; clean with `--lag 120`); `--game`
  runs its standalone arm (nothing shed, no loot, the pause, the restart hint, no new
  body). `combat/verify/player_death.py` and `graphics_menu/death_checks.py` are the graphs.

**The title and the session** (M6, done). The modes are the title's first two rows, each a
page (`graphics_menu/mode_*.py`, its `CLAUDE.md` "The two modes"):

- **The session lives on the GameInstance** (`BP_OtherworldGameInstance`,
  `net/game_instance.py`, named in `DefaultEngine.ini`): `JoinAddress`, `Connecting`,
  `NetReason`. It is the one object that outlives a travel; later tasks' per-process session
  state (the player's identity, M32) goes there too.
- **Join** is `OpenLevel(address)`. The title stands, paused, until the server's level
  replaces it. **Leave** is the engine's `disconnect`. Either way, and when a join fails or
  the server drops the client, the engine loads `GameDefaultMap` again, standalone: a new
  HUD, whose BeginPlay opens the title on the Multiplayer page if the session ended
  without the player leaving it.
- **A client has no title** (the table's last row): BeginPlay's Branch on IsStandalone sets
  `GameStarted` on its false arm. `uepy.py --net` gives no client `-nomenu`, so every net
  run proves it (`probe_net_join.py` checks it).
- **The character's save is behind IsStandalone in play** (`mode_tick.author_mode_in_play`):
  the profile's load, save and wipe on death, and the dev-all-guns cheat chained after
  them, do not run on a client. What a client's death does is "Death", above.
- **Traps:**
  - **IsStandalone is already false while a join is pending**, on the title's own world
    (the engine derives the net mode from the pending game). Nothing on the title may ask
    it to mean "I am on a server"; the title's graph asks `GameStarted`.
  - **A dead address fails after 20 s** (the engine's connection timeout) as
    `ConnectionTimeout`, not `PendingConnectionFailure`.
  - **A failure reloads `GameDefaultMap`**, the 1 km level, whatever level the process was
    on. `uepy.py` names the run's level as the default map on every `--game` and `--net`
    command line, so a probe returns to the level it knows.
- **Proof:** `probe_net_title.py` (`--net --title --windowed --clients 1`: join through the
  page, Leave Server, then a single-player game, one process), `probe_join_dead_address.py`
  and `probe_title_single.py` (`--game --title`).

Every task is tested in both modes: the verifier sweep and the `--game` probes are the
single-player check and stay green; a `--net` probe is the multiplayer one.

## Writing a `--net` probe

```bash
python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_see_each_other.py
```

One file runs in the server and in every client (`Scripts/probes/net.py` has the API).
`probe_net_join.py` is the smallest; `probe_net_see_each_other.py` is the model for a probe
in which one process acts and the others watch.

- **Say where it runs:** `RUNS_ON = ("server", "client")`, and define `probe_server(p)` and
  `probe_client(p)`. Branch on `p.client` (1..N) for "client 1 acts, client 2 watches".
- **The processes share only the board.** The actor posts what it did, with the numbers the
  others need (`p.post("walked", [x, y, z])`); a watcher waits for it
  (`yield lambda: p.posted("client 1", "walked")`) and compares with its own world.
- **Sequence both ways.** A watcher that must be looking before the act posts that it is
  ready, and the actor waits for that post: otherwise the act can be over before the watcher
  has its pawn.
- **Check all three views** when state is involved: the acting client, another client, and
  the server (the only one whose answer is the truth).
- **Bound every wait by the wall clock** and then `p.check` what the wait was for
  (`_await` in the model). A bare `yield lambda:` that never comes true times out the whole
  probe with no check to read.
- **Never match actors by name across processes.** Each client calls its own character
  `BP_ThirdPersonCharacter_C_0` and the other's `_C_1`; the server numbers them in join
  order. Find the other player's character as "of my pawn's class and not my pawn", and tell
  two apart by a posted position.
- **Nor does `p.players()[0]` on the server mean client 1.** Join order varies from run to
  run.
- **`-nullrhi` clients draw no HUD,** so a HUD or widget error does not appear in the default
  run: the spike's only runtime error shows with `--windowed` alone. A task that touches the
  HUD proves itself with `--windowed`, where "zero errors" means something.
- **Game time keeps pace with the wall clock in a net run** (2.0 game seconds took 2.0 wall
  seconds on a `-nullrhi` client), unlike a lone `-nullrhi -game`.
- **To move a character,** call `add_movement_input` every frame from the waited condition,
  and `jump()`: both go through CharacterMovement as a key would. To drive a Blueprint
  input, write the probe's forced variable with `WRITABLE`, as single-player probes do; it
  is written in that one process only.
- **A probe that works the title** runs with `--title`: no `-nomenu`, and a net run's
  clients start alone on the level (the probe joins through the menu). `probes/title.py`
  has the steps. The world and the HUD are new after every travel: ask `p` again, never
  keep one. A join to a dead address logs `Network Failure`, which fails a `--net` run's
  report: that probe is a `--game --title` one.
- **Memory:** the report prints each process's. Two `-nullrhi` clients and a server are
  5.7 GB; with `--windowed` 13.5 GB, which swaps here. Close the editor, run one at a time.

## What the spike found (M4, 2026-10-06)

`Lvl_Forest_200m`, a dedicated server and two clients, the game exactly as built for single
player. **No change was needed for two players to see each other:** `ACharacter` replicates
itself and its movement by default, and `probe_net_see_each_other.py` passes 20/20 (walk
337 cm, jump 128 cm; both clients and the server agree on the place within a centimetre).
Every process's log was free of Blueprint errors with `-nullrhi` clients.

**What already works** (do not rebuild it):

- Each client possesses its own character (autonomous proxy) and sees the other's (simulated
  proxy); walking and the stock jump replicate, the server's copy agreeing.
- The ten wanderers replicate too: the server runs their AI controllers (clients have none)
  and both clients see each one where the server has it, moving.
- A dedicated server makes no HUD and no widgets (`get_hud()` is None there).

**What broke**, one line per system. *Measured* means a probe read it in the spike;
*read* means it follows from the builders and was not exercised.

| system | what happens on a server with two clients | how known | task |
|---|---|---|---|
| HUD | **Fixed (M7).** `ReceiveDrawHUD` cast the GameMode, which a client does not have: `Accessed None ... AsBP_Third_Person_Game_Mode` on every rendered client (16 lines a client in a 48 s run). The only runtime error of the spike, and invisible with `-nullrhi` | measured (`--windowed`); the fix measured (`probe_net_player_state.py --windowed`: 0) | M7 done |
| GameMode readers | **Fixed (M7): "Where state lives", above.** 12 builder modules called `FN_GET_GAME_MODE` and 11 cast to it (combat 4, npc 4, graphics_menu, survival, the menu build); each reads None on a client. Only the HUD's logged, because only it ran | read | M7 done |
| player 0 | **Fixed (M8, M9).** The HUD reads its owning pawn (measured: `probe_net_hud_own_pawn.py`, headless and `--windowed`); the world actors and the wanderers ask the living players ("Who is nearby"; measured: `probe_net_living_players.py`, the cold falls on both players and the nearest to the second player is the second). Before: 26 builder modules call `FN_GET_PLAYER_PAWN` (graphics_menu 15, npc 7, combat 2, survival 1, world 1). On the server that is the first joiner, so every wanderer hunts one player, and the night cold, campfire warmth and ammo pick-up serve only them | read; the join order measured | M8, M9, M27 |
| health | **Fixed (M14): "Health and damage", above.** Health written on the server (100 to 40) stayed 100 on both clients: nothing replicates it. Damage is the weapon writing `Health` directly, not `ApplyDamage` (which does nothing in this game) | measured; the fix measured (`probe_net_health.py`) | M14 done |
| firing and ammo | A shot fired on client 1 spent a round there (5 to 4); the server and client 2 still had 5 and saw no shot. The trace and the damage ran on the client alone | measured | done for the shot, its round and its damage (M19: the server's); what others see and hear of it is M21 |
| the loadout and held items | **Fixed (M18): "The inventory", above.** Every process spawned its own copy of each character's six items (not replicated, each with local authority), so the three worlds started alike and parted at the first change | measured; the fix measured (`probe_net_inventory.py`) | M18 done |
| items on the ground | The 24 mushrooms and the test garments are level actors whose classes do not replicate (`BP_Mushroom`, `BP_Hat`: read off the class defaults): each process has its own, and a pick-up on a client removes it nowhere else | measured (the counts, the defaults), read (the pick-up) | M23, M31 |
| day and night | Each process rolls its own start time: in one run it was day on the server and client 2 and night on client 1 | measured | M30 |
| walk speed, sprint, stance | The weapon component wrote `MaxWalkSpeed` every tick in every process from its own unreplicated state. **Since M10 only the local player's copy writes it** (the sprint and the aim are behind the local gate), so the server's copy keeps the speed the character was built with. Sprint, crouch and prone are keys read on the client, so the server would correct a sprinting client. **Fixed (M12): "Movement states are predicted", above** | the write measured; the fix measured (`probe_net_move_states.py`, 137 ms) | M12 done |
| input | **Fixed (M10): "Input", above.** The weapon component polled keys in its Tick on every copy of every character, the server's included, and on `GetPlayerController(0)`, so a client's press drove every character it could see | read; the fix measured (`probe_net_local_input.py`, headless and `--windowed`) | M10 done |
| stamina, hunger, thirst, temperature | Per-process component and GAS state: no builder replicates a variable or a component yet (`net.replicate` has no caller outside `dev/check_net_authoring.py`). **Stamina is the server's since M12** (the movement component; the owning client predicts it and is corrected to it) | read; stamina measured | M12 done, M26 |
| animation of the other player | Only what CharacterMovement replicates reached a simulated proxy (velocity, falling). **Fixed (M13): "Other players' characters", above**: stance, aim pitch, aim mode, the gun raised or lowered and the hand's pose. Montages do not yet | read | M21 |
| sounds and effects | Played where the graph that caused them ran, so a shot, a blow or a footstep is heard by its own client only | read | M21 |
| player starts | The level has one PlayerStart: the two spawned 70 cm apart, the engine nudging the second. At that spacing the server refuses a crouched character's stand-up ("Other players' characters") | measured | M16 |
| pause and the title menu | Without `-nomenu` a client opened on the title menu. **The pause is fixed (M5):** it is standalone's alone (`net/pause.py`, above), and a client's menu is an overlay. **The title is fixed (M6):** a connected client has none, and the harness no longer gives a client `-nomenu` | read; the fixes measured (`probe_net_menu_overlay.py`, `probe_net_join.py`, `probe_net_title.py`) | M5, M6 done |
| the profile and the tuning slots | A client loaded the local `OtherworldProfile` as in single player: **fixed (M6)**, the profile's fragment runs in standalone only. It still loads the tuning tabs' save slots (the harness sets them aside for a run: `probes/kept_slots.py`) | read; the profile measured (`probe_net_title.py`) | M32, M35 |

**Corrections to the later tasks' wording** (the task queue is the source; where the spike
contradicts it, this is what holds):

- **M7, M8, M10 (the HUD tasks):** their `--net` probes need `--windowed`. A `-nullrhi`
  client never runs `DrawHUD`, so it cannot show the fault or its fix.
- **M10:** "a dedicated-server log has no widget creation" is already true (no HUD is made
  there). The work is the key polling in component Ticks on the server and on other
  players' characters.
- **M13, M27:** wanderers already replicate their movement to clients with the AI on the
  server only. What is missing for them is what the animation graph and the sounds read,
  and the choice of target.
- **M14 (done):** "damage ... always carries an instigator" started from no damage event at
  all: the weapon wrote `Health` on the component. The event is the component's own
  `TakeHit` ("Health and damage"); the engine's `ApplyDamage` still reaches nothing.
- **M16:** "a random player start" needs player starts: the level generator places one.
- **M18 (done):** the starting loadout was spawned by every process; the server alone
  issues it now, and a client's item actors are local pictures of the server's record,
  not replicated actors ("The inventory").
- **Any probe:** "client 1" is not the server's player 0, and no actor name is shared
  between processes (above).

## Memory (measured, the editor binary; `serversupportsysdesign.md` 5 has the table)

| process | 200 m map | 1 km map |
|---|---|---|
| dedicated server | 1.9 GB | 2.5 GB |
| client, `-nullrhi` | 1.9 GB | 2.2 GB |
| client, `--windowed` | 5.8 GB | not measured |
