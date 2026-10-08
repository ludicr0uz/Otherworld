# net — the multiplayer conventions

Read this before any multiplayer task. The strategy is `serversupportsysdesign.md` (4.1
authority, 4.2 where state lives, 4.8 the two modes); the authoring helpers are
`Scripts/uebp/CLAUDE.md`; the harness is the root `CLAUDE.md`'s `--net`. This file is the
rules a graph follows, how to prove one, and what the spike (task M4, 2026-10-06) found
broken. Its code is what the builders share to keep one graph right in both modes
(`__init__.py` maps it): `pause.py`, the session (`session_consts.py`,
`game_instance.py`), where state lives (`state*.py`), who is nearby (`players*.py`) and
whose keys a graph reads (`input_checks.py`) and the audit of every random draw
(`random_consts.py`, `random_checks.py`), and what a Server event checks before it runs
(`guard_consts.py`, `guard.py`).

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
| `AskDrop(From)` | a drag out of the inventory, the drop key (no screen) | raises `DropRequest` | **done, M23** |
| `AskTakeOff(Slot, To)` | Enter or a click on a worn slot, a drag off one | raises `TakeOffTo`, `TakeOffSlot` | **done, M24** |
| `AskWear(From)` | a drag onto the worn grid | raises `WearRequest` | **done, M24** |
| `AskLootTake(Body, Index, Want)` | the loot window's Enter or click | the take itself, with its refusals (`weapon_component/loot_take.py`) | **done, M23** |
| `AskSaveExit()` | the menu's save-and-exit row | starts the countdown the component runs (`weapon_component/save_exit.py`) | M35 |

The trigger and R are keys, not a screen's asks, and have Server events of their own:
`Server_Fire` and `Server_Reload` ("The shot and the reload", below).

- **All but save and exit are reliable Server events** (`ask_consts.SERVER_ASKS`; "The
  inventory", "Picking up, dropping and looting" and "Clothing", below).
  `combat/verify/asks.py` asserts which is which on the compiled class; the task that
  makes one a Server event adds it to `SERVER_ASKS`.
- **The int asks only raise the request** the component's Tick already serves, so the
  serve is still where a move is validated, and every serve is in the upkeep's
  authority arm (`tick.py`, `_author_upkeep`): the server's alone.
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
  remote copy's hand is the server's since M18 (the record component's `HandClass`, "The inventory", below).
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
  consume ability, which runs on the server only: "Survival", below), a wanderer's maximum at possession (`npc/stats.py`), a loaded
  profile (standalone). A Blueprint `Set` of a RepNotify calls `OnRep_Health` on that
  machine too, where its Remote arm does nothing.
- **A wanderer's death by a drain is nobody's kill yet:** bleeding out after a player's
  blow is not credited (the drain names no one).
- **Players hurt players (M15, done), and nothing was added to make them.** A pellet, a
  swing and a thrown blade take health off whatever carries a `BP_HealthComponent`, through
  `TakeHit`, with the target's own hit-box tables; a player's character carries one as a
  wanderer's does. Never give a blow a "is this a wanderer" test: friendly fire is on until
  teams exist (M33), and the team check will go in `TakeHit`, the one place every blow
  passes.
  - **The kill's credit is the one PvP thing** (`combat/player_kill.py`): on the player's
    arm of the death path, on the server, `LastInstigator` where it is a PlayerController
    and not the body's own has `PlayerKillCount` raised on its PlayerState: a row of
    `PLAYER_TABLE` apart from the wanderers' `NpcKillCount`, replicated to everyone. The
    death menu shows both (`Monster Kills`, `Player Kills`), in both modes; in single
    player the second stays 0.
  - `LastInstigator` is the last blow's, however long ago: a player who starves or bleeds
    out after another player's blow is that player's kill, until a wanderer's blow names
    someone else.
  - **The check:** `uepy.py --net --clients 2 --probe-timeout 240 --probe
    Scripts/probes/probe_net_pvp.py` (also with `--lag 120`): client 1's slash (35), thrown
    knife (50) and pistol rounds (the body's zone, then the head's 1.75) come off client 2,
    the server and both clients agreeing on the health after each; the last round kills,
    and all three read one player kill for client 1, none for client 2 and no monster
    kill. The corrections it counts on client 2 are the server holding it in place.
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
of them, plain data, one C++ struct on its own component (`combat/record_vars.py`,
`Source/Otherworld/Public/OtherworldInventoryRecord.h`):

| on `UOtherworldInventoryRecordComponent` | holds | replicates to |
|---|---|---|
| `Record` (`FOtherworldInventoryRecord`): `Items[i]` (class, slot code, loaded, reserve, lit, hot), `Worn[slot]` (class or none) | a row per carried item, in `Inventory`'s order, and a class per worn slot | the owning client (`COND_OwnerOnly`), whole, with one RepNotify |
| `HandClass`, `HandLit`, `HandHot` | the class in hand, or none; whether it burns or glows | everyone else (`COND_SkipOwner`), each a RepNotify |

- **One atomic, versioned, serialisable record, sent only when it changes** (A3a, A3b).
  It travels whole (its own `NetSerialize`), so no client ever holds half an inventory;
  it is written on a frame that changed it, never every Tick; and no Blueprint variable
  holds a copy: the six `Inv*` arrays, `WornClass` and the weapon component's own
  `HandClass`, `HandLit` and `HandHot` that mirrored it went with A3b (the weapon build
  takes them, and their OnRep graphs, off a component built before:
  `weapon_component/record.py` `retire_mirror`). `combat/verify/record.py` fails on a
  weapon component that has one again, and on any `.py` under `Scripts/` that names one
  of the six arrays.
- **It is what a save writes** (A3b): `FOtherworldInventoryRecord::ToBytes` and
  `FromBytes`, into a `USaveGame`'s byte array. The layout
  (`Source/Otherworld/Private/OtherworldInventoryBytes.cpp`): a `uint32` version first
  (`SaveVersion`, 1), a `uint16` count of rows, each a class path, three `int32` (slot,
  loaded, reserve) and a flags byte (1 lit, 2 hot), a `uint16` count of worn slots, each
  a class path (empty: nothing worn); little-endian, a path as its UTF-8 length
  (`uint16`) and bytes. Classes go by path, since a save outlives the session that knew
  them by net id. `FromBytes` refuses another version, bytes cut short and bytes with
  more after them, and leaves the record as it was; a row whose class no longer exists
  is dropped and a worn slot of one is empty (a save outlives an item). A changed layout
  is a new `SaveVersion` and a reader of the old one. A load is one `SpawnActor` per
  row. **M35 saves it as it stands**: `InventoryRecordOf(character)`,
  `InventoryRecordToBytes`, `InventoryRecordFromBytes` (`uebp/nodes/inventory.py`), and
  `UOtherworldRecordSave` is a `USaveGame` with the one byte array. Until then the
  single-player profile is `BP_Profile`, unchanged. A body's loot should hold rows of it
  too, not a second form (a body still holds classes: a looted gun is a fresh one).
  Proof: `uepy.py --game --probe Scripts/probes/probe_record_bytes.py` (a pistol with
  five rounds, a burning stick and a worn hat: the version in the first four bytes, the
  same bytes back out of a save slot, the same record out of them, the six refusals, and
  bytes written by hand in the layout above).
- **The server writes it on a frame that changed it** (A3a): the component sits on the
  character beside the weapon component (`combat/install.py`).
  - **A change site marks, and no graph does it by hand.** A node that writes
    `Inventory` or `Worn`, or Sets an item's `Slot`, `Loaded`, `Reserve`, `Lit` or
    `Hot`, is a change site. `combat/dirty.py`'s `mark_change_sites(ed, own)` finds them
    by what they are and splices `MarkInventoryDirty` (`uebp/nodes/inventory.py`) in
    behind each, once a graph is whole: the weapon component's 60, the stick's and the
    blades' own clocks, the ammo pick-up, the HUD's single-player writes. A new graph
    that changes what is carried needs only that call before its compile;
    `verify/record.py` fails on a site with no mark.
  - **The write is after the actors ticked** (`UOtherworldInventoryRecords`, a world
    subsystem on `OnWorldPostActorTick`), so after the slot sync, once, however many
    marks the frame made; with authority only, so in single player too, where nothing
    travels. The shed empties `Inventory` and `Worn`, which marks: the record is written
    empty that frame whatever the dead gate stops.
  - **The audit finds what the pass cannot see** (a write from Python or C++, a carried
    item destroyed in place): with `Otherworld.InventoryRecord.Audit 1`, which
    `probes/boot.py` sets for every probe run, each unmarked record is compared with the
    item actors every frame, and a difference is an `INVENTORY-RECORD-STALE` log line
    naming both. `uepy.py --game` and `--net` count them (the "stale records" column)
    and fail the run. A probe's own `p.set` of an item's state marks for itself; a
    probe that writes `Inventory` or `Worn` itself does not (`probe_net_death.py` writes
    `Worn` on the frame it kills, and the shed marks).
  - **Push Model is on for the record alone** (`Config/DefaultEngine.ini`):
    `net.IsPushModelEnabled=1` and `Net.MakeBpPropertiesPushModel=0`. With the second
    left at the engine's default every Blueprint variable becomes push-based, marked by
    Blueprint Set nodes only, and one written any other way (by reflection; a probe,
    from Python) is silently never sent.
- **A client reads it through the library, a row at a time** (A3b,
  `uebp/nodes/inventory.py`): `InventoryRowCount(carrier)`, `InventoryRow(carrier,
  index, Kind)` (class, slot, loaded, reserve, lit, hot), `WornRowCount`, `WornRow` and
  `HandRow(carrier, Kind)` (class, lit, hot), pure nodes over the record as that machine
  holds it. `Kind` is a class pin whose literal types the `Class` output
  (`DeterminesOutputType`): the record is of `AActor` classes, a C++ module knowing no
  Blueprint, and `ViewRow`'s `Class` is `BP_WeaponItem`'s.
  - **The component's RepNotifies raise `ViewDirty`** on the weapon component, by name
    (`ViewDirtyVar`, written by `combat/install.py`): `OnRep_Record` for the owner,
    `OnRep_Hand` for each of the hand's three on everyone else's machine.
  - **What a change costs the wire** (`uepy.py --net --clients 1 --probe
    Scripts/probes/probe_net_record_cost.py`: the server moves client 1's axe between
    two bag slots 80 times in 20 s, the smallest change there is, against an idle 20 s
    before it; 2026-10-08, the same machine, the A3a build and assets put back for the
    first row):

    | | bytes out in the 80 changes' 20 s | in the idle 20 s | bytes a change |
    |---|---|---|---|
    | before (A3a: the struct and its mirror, six arrays' deltas) | 93 992 | 79 559 | 180 |
    | after (A3b: the struct alone), two runs | 90 850, 90 899 | 79 451, 82 270 | 143, 108 |

    The moving window is steady run to run and 3.1 KB lighter, about 39 bytes a change;
    the idle window wanders by 3 KB, which is the spread in the last column.
  - **The load test does not see it.** A1's harness at N = 32, 2 clients, 90 s, the
    same day: 6.5 and 6.6 KB/s out per client over 89 actor channels before, 6.9 and
    7.0 KB/s over 92 after; world tick 26.6 against 25.2 ms. Not fewer: its clients
    stand still, so what they carry changes only when they die, and three more bodies
    in view outweigh every record sent. The record's own cost is the table above.
- **A client holds no inventory of its own.** BeginPlay issues the loadout with authority
  only. A client's item actors are a **picture** of the record, local and unreplicated
  (`weapon_component/view.py`): the record component's RepNotify raises
  `ViewDirty`, and the next Tick's upkeep, without authority, calls `ViewRow` per row
  (the actor at that index kept if it is of the row's class, else destroyed and one
  spawned; then its slot and rounds) and `ViewTrim`. Its own player's from the rows;
  another player's character from `HandRow` alone, one actor, in the hand. The slot
  sync and the equip run after it on every copy, so nothing below knows whether its
  actors are the server's or a picture.
- **The picture is remade only when a record arrives.** What a client changes itself
  stays until the server next says otherwise, and it is
  why an action that is not the server's would still show on its
  own client, and be undone by the next record. Make the
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
  one is routed by the VM, when a graph calls it). A probe that has to send one as no
  graph would (a wrong argument, two hundred in a second) uses
  `unreal.OtherworldNetLibrary.send_server_event(wc, name, [each argument as text])`
  (A5, `probe_net_guard.py`); an honest ask still goes through its door, below. So a probe asks with `p.ask_slot(wc,
  slot)`, `p.ask_move(wc, src, dst)` or `p.hold(wc, index)` (`probes/context.py`): the
  call itself with authority, and on a client a write of `SlotForced` or
  `MoveForcedFrom`/`MoveForcedTo`, which the component's Tick turns into the ask where
  the keys are read. The shot's and the reload's doors are `FireForced` and
  `ReloadForced` (M19); a swing's `KnifeQueued` and `PunchQueued`, the guard's
  `BlockForced`, the use key's `SightsForced`, the throw's `ThrowKeyForced` and
  `ThrowClickForced` and the take's `InteractForced` (M20); the next Server event
  needs one of the same kind.
- **A burning stick and a hot blade are in it** (M25, "Fire and heat", below): a
  row's `bLit` and `bHot`, and `HandLit` and `HandHot` beside `HandClass`.
  The dev-all-guns cheat still spawns on the machine it is pressed on.
- `combat/verify/record.py` checks the wiring. Proof (clean with `--lag 120`, as
  `probe_net_fire.py`, `probe_net_clothing.py` and `probe_net_death.py` are, each run by
  itself: the death and inventory probes start from a fresh loadout): `uepy.py --net
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
  Blood, chips and the shot's sound reach everyone through the cosmetic pairs, and the
  headshot's X through `HeadshotTime`'s RepNotify ("Everyone sees and hears the fight",
  below); the tracer is debug mode's, drawn where the shot ran.
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
  Always is not every frame (A4, "What the server spends on bodies it never draws"
  below): the same arm hands the body to `ThrottleServerPose`.
- **Where the target was** is the next section (M22): the server judges a remote
  shooter's pellets against where every character stood when the shooter fired.
- **Not here:** the server takes the shot whether or not it has the player sprinting or
  guarding. Melee, the throw and the guard are the section after; what everyone sees and
  hears the one after that.
- `combat/verify/shot.py` checks the flags and the wiring. Proof: `uepy.py --net
  --clients 2 --probe-timeout 240 --probe Scripts/probes/probe_net_fire.py` (client 1
  kills a wanderer down the sights and reloads; the server's rounds are client 1's, its
  count of asks client 1's, the kill client 1's, and three `Server_Fire` in one frame
  spend one round); also with `--lag 120`; `--game` runs its single-player arm.

## Lag compensation (M22, done)

A shot asked of the server arrives a round trip after the shooter saw the target, and
the shooter saw the target where the server's last update put it. Traced against the
present, a round aimed at a strafing character's chest passed behind it: with 150 ms
of lag the old graph landed 0 pistol rounds in 8. The server now judges the shot
against where the target stood when the shooter fired. It is C++, the `Otherworld`
module (`serversupportsysdesign.md` 4.3: not practical in Blueprint); the numbers are
`combat/lag_tuning.py`; the one node is `uebp/nodes/shot.py`.

- **The history** (`UOtherworldHitHistory`, a world subsystem): after every actor has
  ticked (`FWorldDelegates::OnWorldPostActorTick`, so the kinematic bodies follow the
  frame's pose) it records every `ACharacter`, a second back, in two rings of fixed
  capacity per character (A4: a frame allocates nothing; a `TMap` finds a character's):
  the *frames* (the capsule's transform, whether it blocked Visibility, the mesh's own
  frame; at most 30 a second, the rate a shot is judged at) and the *poses* (each physics
  body in the mesh's frame, written only on a frame that posed the mesh anew, and only
  for a body a pellet can stop on: a corpse has none). A body the server poses at 10 Hz
  has ten poses a second and a rewound trace blends the two either side of its time.
  Only on a server with clients (`NM_DedicatedServer`, `NM_ListenServer`): single player
  records nothing.
- **The rewind** is the shooter's connection's round trip (`UNetConnection::AvgLag`, the
  PlayerState's ping failing that) plus `EXTRA_REWIND_S`, at most `MAX_REWIND_S` (0.4 s:
  a player on a worse line is at the disadvantage, not the one they shoot). A local
  shooter (single player, a listen host's own player, an AI) gets none.
- **The trace** (`UOtherworldShotLibrary::ShotTrace`) is the pellet's one node, in
  place of `LineTraceSingle` and the `K2_LineTraceComponent` that followed it. With no
  rewind it runs those two engine traces as they were. With one, it traces the world
  with every recorded character ignored, then each character where it stood at the
  rewound time, and the nearest wins; the struck character's bodies are tried along the
  same line for the bone (`bBodyHit`, `BodyBone`, `BodyPoint`, which impact.py's hit
  zone reads). Every capsule is tried first, from the frames alone (a character whose
  capsule's sphere the line does not come near is not traced at all); a body's transform
  is blended only for the one character struck.
- **Nothing is moved.** The engine traces a body where it is now
  (`FBodyInstance::LineTrace`), so the line is carried from where the body was to where
  it is and the hit carried back: rigid transforms both ways, so the distance, the
  bone and the shape are the engine's own, and a shot cannot disturb a ragdoll or
  another shot in the same frame.
- **What it does not do:** the first second after a join is rewound by the join's
  inflated round trip (the engine averages the ping over a second); melee, the throw
  and the aim trace are not rewound (a sweep reaches a metre; the throw flies for
  real); the server's record of the shooter's own muzzle is not rewound either, since
  the shooter is not moving relative to itself.
- **Proof:** `uepy.py --net --clients 2 --probe-timeout 240 --probe
  Scripts/probes/probe_net_lag_hits.py`, and the same with `--lag 150`. Client 2 runs
  across client 1's line of fire; client 1 fires eight pistol rounds down the sights
  at the chest of its own copy of client 2; the server counts the rounds that hurt
  and prints, per shot, the rewind it used against the one that would have put the
  round exactly where client 1 saw the chest (how far back along the server's own
  track of it that point lies). Measured: 6/8 without lag (rewound 43 ms: the
  loopback's frames), 7/8 with 150 ms (rewound 178 ms, wanted 150-220). Single player:
  `probe_headshot`, `probe_ads_hit`, `probe_net_fire --game`; `verify/hit_bodies.py`
  and `verify/player_body.py` check the node and what reads it.
- **The history against the bone it records** (A4): the same probe asks, every frame of
  the strafe, where the history put the chest's box 100 ms before
  (`UOtherworldShotLibrary::HitBoxThen`) and compares it with the server's own track of
  the bone: 0.00 cm apart over 240-260 frames a run. That check is exact; the hit count
  is not. **The count's spread, measured 2026-10-08** (the MetaHuman-rigged player, this
  Mac, the editor open): on the build before A4 it landed 7, 8, 5, 5, 6, 8 of 8 without
  lag and 7 with 150 ms; on A4's, 6, 4, 5 and 4, 7, 5, and 4 to 8 across forty more runs
  of its variants (the anim graph's server arm on and off, the foot IK and the flinch on
  it and off it, the pose throttle off, A4's C++ under the old assets: none moved the
  mean: about 5.6 of 8 over those runs against 6.6 over the seven before A4). Not shown
  equal, and nothing found that makes it
  different: the pellet's line passes 8-24 cm from the chest bone on every build
  (`LastShotLine`), which is the edge of the torso, because the probe fires as soon as
  the reticle is within 12 cm of a chest moving at 4 m/s. A run that lands 4 fails the
  probe's 60% line. Treat one run of it as one sample.

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
  nothing. (The server's item is heated by `Server_Heat`: "Fire and heat", below.)
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
  is seen as `LookPose`). The server's stick is lit by `Server_Kindle` ("Fire and
  heat", below).
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
  - **Every other way into the world is the item's own Tick** (M23, "Picking up,
    dropping and looting", below): the release is the one place that says so itself.
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
- **Not here:** lag compensation of a sweep or a throw. Lighting the stick and heating the blade are "Fire and heat", below. The swing, the throw and
  the hit as other players see and hear them are the next section.
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

## Picking up, dropping and looting (M23, done)

Two players reaching for one item is settled by the server, and nothing is duplicated:
every item in the world is one actor, the server's, and every way of taking one or
setting one down is a reliable Server event on the weapon component.

| the client asks | the server checks, on its own copy | then |
|---|---|---|
| `Server_Take(Item)` (E: of the items in reach, the one nearest the reticle, within `INTERACT_HEIGHT` up or down: chosen on the client, `interact.py`) | M20's: the item exists and is `Dropped`, the taker alive and within reach, a slot free | into the taker's inventory, out of the world |
| `AskDrop(From)` (the drop key: the hand's slot; a drag out of the inventory: the slot dragged) | the slot holds an item | `DropRequest`, served with authority: the server's actor is set down ahead of its copy of the player, `Dropped` |
| `AskLootTake(Body, Index, Want)` (the loot window's Enter or click) | the taker alive, the body within `LOOT_TAKE_REACH_CM`, a slot free, the row there and still holding the class `Want` | the item is spawned into the taker's inventory and the row leaves the body's arrays |

- **An item lying in the world replicates by itself** (`combat/item_world.py`,
  `_author_enter_world`): in the item's own Tick, on its authority arm and only where
  `IsServer`, an item that is `Dropped` and not yet `InWorld` is made `InWorld` and a
  replicated actor. That covers the drop, an item placed in the level, a gun left by a
  kill, wood cut from a tree and whatever spawns one later: **a graph that makes an
  item lie in the world says nothing about replication.** Only the throw's release
  still calls `author_into_world` itself (it is in the air, not `Dropped`).
- **A placed item is loaded by every machine, and is still one actor.** A level actor has
  the same name on the server and a client, so when the server's starts replicating the
  engine joins the client's own copy to it instead of spawning a second: measured, the
  client's hat has no authority a moment after the join and follows the server's
  `Dropped` and `InWorld`. `IsServer`, not HasAuthority alone, gates the step, because
  until then a client has authority over its own copy.
- **Whoever asks first gets it.** A second `Server_Take` finds the item no longer
  `Dropped`. A second `AskLootTake` finds the row gone, or the next row moved up into
  it, which is why the ask carries what the window showed (`Want`): the server takes
  that item or nothing.
- **The loser's UI corrects itself because it predicted nothing.** A client's bag is a
  picture of the server's record, its copy of the item hides when `InWorld` falls, and
  the loot window draws the body's replicated arrays: nothing was shown as taken before
  the server said so.
- **The drop key is an ask now** (`weapon_component/drop_request.py`,
  `_author_drop_keys`): G with something in hand calls `AskDrop(HAND)`, and the one
  serve sets down the hand's item as it does a dragged one. A client sets nothing down
  itself. A probe's door is `DropForced` (`p.ask_drop(wc, slot)`).
- **In single player** each is a plain call, served the same frame, and
  `SetReplicates(true)` sends the item to no one.
- **A late joiner** sees no placed item that was taken: the take destroys a level actor
  and puts a fresh one of its class in the bag ("Relevancy, update rates and dormancy",
  below, A2). A body's loot is still classes, so a looted gun is a fresh one. Eating a mushroom is "Survival"; the campfire and the wood's chop are "Fire and heat",
  below.
- `combat/verify/world_items.py`, `verify/asks.py` and `graphics_menu/loot_checks.py`
  are the wiring. Proof: `uepy.py --net --clients 2 --probe-timeout 300 --probe
  Scripts/probes/probe_net_take.py` (both clients take one row of a body at once and one
  gets it; a take from 80 m off and a take of an item the row does not hold are refused;
  both press E on the level's hat at once and one gets it; the winner drops it and both
  see the server's actor; and the server runs both players' `Server_Take`, and both
  `AskLootTake`, in one frame: the first has it, the second nothing); clean with
  `--lag 120`. Single player's are `probe_pickup`, `probe_pickup_weapon_slot`,
  `probe_pickup_height`, `probe_asks`, `probe_inventory_drag` and `probe_corpse_loot`.

## Clothing (M24, done)

Wearing and taking off are the server's, on the inventory's pattern: the server keeps the
item actors (`Worn[slot]`, the very garment that was picked up), a record of them travels,
and the owning client's `Worn` is a picture of the record.

| the client asks | the server checks, on its own copy | then |
|---|---|---|
| `Server_Wear()` (the fire key with a garment in hand: `weapon_component/wear.py`) | its own `Held` is there and is a garment | out of `Inventory`, into `Worn[its ClothingSlot]`; one worn there goes back into the bag |
| `AskWear(From)` (a drag onto the worn grid) | the slot holds an item, and it is a garment | the same, from wherever it is carried; one worn there takes the slot it left |
| `AskTakeOff(Slot, To)` (Enter or a click on a worn slot, a drag off one) | a garment is worn there, and there is room | into `Inventory`, on `To` if that is the hand or a bag slot, else the bag's first free one |
| `AskDrop(SLOT_COUNT + slot)` (a worn garment dragged out of the inventory: M23's ask) | a garment is worn there | set down on the ground, `Dropped`: a replicated actor from its next Tick |

- **What is worn is the record's `Worn`** (`combat/record_vars.py`): a row per slot
  of the server's `Worn`, the garment's class or none, written by the record component
  with the inventory's rows on a frame that changed either ("The inventory", above) and
  emptied with them at the shed. Plain data, as the rows are: the character's
  save writes it as it stands.
- **It replicates to the owning client alone** (`COND_OWNER_ONLY`), as the task asked:
  nothing is drawn worn yet, so nobody else has anything to draw. **The task that draws
  a garment on the body gives everyone what is worn** (as `HandClass` is given: a
  `COND_SkipOwner` property of the record component beside it, the record itself
  staying the owner's) and draws from it in its RepNotify; nothing else has to change.
- **A client's `Worn` is a picture of it** (`weapon_component/view_worn.py`, `ViewWorn`):
  in the view's dirty arm, a local actor per worn slot, hidden and not `Dropped`, so the
  I panel, which reads `Worn`'s actors, draws a client's worn slots as it draws single
  player's. A client wears and takes off nothing itself and predicts nothing: a refused
  ask changes nothing it showed.
- **The three serves moved** from the Tick's local half to the upkeep's authority arm,
  ahead of the drop's and the slots' (the order they always ran in). In single player
  `Server_Wear` is a plain call run where the wear's graph used to be, so nothing there
  changed; the press is spent (`TriggerSpent`) where the key is read.
- **A client's picture of a carried garment is not a pick-up:** `ViewRow` clears
  `Dropped` on the actor it spawns, as the server's take does on its own. A garment's
  class, like food's, is `Dropped` by default, which is what the pick-up scan and the
  glimmer read.
- **A probe's doors** are `FireForced` (the key), `WearForced` and
  `TakeOffForced`/`TakeOffForcedTo` (`p.ask_wear(wc, slot)`, `p.ask_take_off(wc, slot,
  to)`: `probes/context.py`), and `DropForced` for the drop.
- `combat/verify/wear.py` (`check_server_wears`) and `verify/record.py` are the wiring.
  Proof: `uepy.py --net --clients 2 --probe Scripts/probes/probe_net_clothing.py`
  (client 1 wears the hat by the key and the jacket by a drag, is refused an axe and an
  empty slot, takes the jacket off and drags the hat out onto the ground; after each the
  server's `Worn`, its record's `Worn` and client 1's own `Worn` agree, and client 2 is told
  none of it); clean with `--lag 120`; `--game` runs its standalone arm. Single player's
  are `probe_clothing` (with `probe_clothing_drag`), `probe_inventory_drag` and
  `probe_asks`.
- **Not here:** a garment worn on a server shows on nobody's body (nothing is drawn
  worn), and the single-player profile still saves the bag and not `Worn`
  (`Scripts/clothing/CLAUDE.md`).

## Fire and heat: the tree, the campfire, the stick, the blade (M25, done)

What changes the world happens once, on the server, and everyone sees it.
`combat/fire_vars.py` has the picture; each event is its owner's module.

| the client asks | the server checks, on its own copy | then |
|---|---|---|
| `Server_Light()` (the fire key tapped, the matches in hand) | alive, its item in hand `Lights`, a `CampfireClass` to spawn, a piece of wood in its bag | the wood is spent, a campfire is spawned 130 cm in front of its copy, `Multicast_Match` |
| `Server_Kindle()` (the use key pressed, a stick that `Burns` in hand) | alive, its item `Burns` and is not `Lit`, a campfire within 3 m of its copy | `Lit` until `BurnOutTime` |
| `Server_Heat(Fire)` (E on a campfire) | `Fire` is there and a `CampfireClass`, within `HEAT_REACH_CM` of its copy, alive, its item `Heats` | `Hot` until `CoolTime` |
| `Server_Cauterize()` (the use key pressed, a `Hot` blade in hand) | alive, its item `Hot`, its ability system | every effect granting the bleeding tag comes off |

- **The campfire is a replicated actor** (`survival/campfire.py`: `net.replicate_actor`,
  after the compile). Only the server spawns one, so every client is sent it; its model,
  glow and crackle are components and need nothing more. Its life span and its warmth
  are behind HasAuthority: `Temperature` is the server's (replicated to its owner: "Survival", below), and the server's destroy
  takes every copy.
- **`Lit` and `Hot` are the item's own, and so are their clocks.** The burn-out and
  the cooling (`combat/stick.py`, `combat/heat.py`) run behind `IsServer`, not
  HasAuthority: a client's picture of a carried item is a local actor it has
  authority over, and would otherwise put itself out by its own clock (its
  `BurnOutTime` is 0). A client is told, three ways:
  - an item in the world: `Lit` and `Hot` replicate on the actor (`item_world.REPLICATED`);
  - an item its owner carries: its row of the record (`bLit`, `bHot`), which `ViewRow` writes
    onto the picture;
  - the item in another player's hand: `HandLit` and `HandHot` (`COND_SKIP_OWNER`),
    written when either changes.
  How long is left does not travel: it is the server's clock, and no client draws it.
  A save that wants it writes the server's item's `BurnOutTime` less the time.
- **The chop needed nothing new.** It hangs off the server's blow (M20), its count
  (`ChopCount`, per chopper, on the server's component) is the tree's whole state (a tree
  never runs out), its chips are `Multicast_Chop` and the wood it leaves lies `Dropped`,
  which replicates by itself (`item_world.py`).
- **The match is a cosmetic pair** (`Fx_Match`/`Multicast_Match`, gate `screen`): it was
  a sound played where the strike was decided, which on a dedicated server nobody hears.
- **A client decides none of it.** Its key's arm only asks: the wood, the bag, the place,
  the reach and the item's flags are read off the server's copy. `Server_Cauterize`
  called with a cold blade in the server's hand seals nothing.
- **The probes' doors** are the keys' stand-ins that already existed: `FireForced` (the
  strike), `SightsForced` (the use key: kindle, cauterise) and `InteractForced` (heat).
- **In single player** each is a plain call, and `IsServer` is true: nothing changed.
- **A late joiner** is sent the fire like any replicated actor, dormant since its spawn
  ("Relevancy, update rates and dormancy", below, A2).
- `combat/verify/fire.py` checks the events and how `Lit` and `Hot` travel;
  `verify/light.py`, `torch.py` and `heat.py` what each event asks first;
  `survival/verify/campfire.py` the fire. Proof: `uepy.py --net --clients 2
  --probe-timeout 300 --probe Scripts/probes/probe_net_campfire.py` (client 1 cuts wood,
  takes it, lights a campfire, lights its stick at it, heats its knife and cauterises a
  bleed the server gave it, then sets the burning stick down; client 2 sees the wood,
  the fire, the burning stick and the hot knife in client 1's hand and the stick on the
  ground, and the server's `Temperature` of client 2 rises beside the fire); clean with
  `--lag 120`. Single player's are `probe_campfire`, `probe_chop_tree`,
  `probe_lit_stick` and `probe_hot_blade`.

## Survival: hunger, thirst, temperature, the debuffs, eating (M26, done)

The server owns every survival value; `Scripts/survival/CLAUDE.md`, "On a server", has
the table and the reasons the ability system lives on the character.

- **The stats** (`Hunger`, `Thirst`, `Temperature` on `BP_SurvivalComponent`) are written
  only behind an authority switch (the decay, `world/night_cold.py`, the campfire) and
  replicate `COND_OWNER_ONLY`. A HUD reads its own pawn's component, as before.
- **The debuffs and the bleed** are effects on the character's ability system, applied
  and removed with authority; the component replicates them and the tags on their specs,
  so `GetGameplayTagCount` answers on the owner's machine.
- **Eating** is `Server_Consume()` on the weapon component (`weapon_component/consume.py`):
  the key's arm plays the sound, asks and spends the press; the server, refused unless
  its own `Held` is a Consumable and not a garment, sends `GA_ConsumeItem` its event
  (ServerOnly) and spends the item. Nothing is predicted.
- **On the character, not the PlayerState:** a respawn's new character is fresh by
  construction, the body keeps its state for the drain beside it, and a wanderer has no
  PlayerState.
- Proof: `uepy.py --net --clients 2 --probe Scripts/probes/probe_net_survival.py`, clean
  with `--lag 120`; `survival/verify/server.py`, `combat/verify/consume.py`.

## Everyone sees and hears the fight (M21, done)

A fight must look and sound the same to everyone near it, and losing a sound must never
change the outcome, so cosmetics travel apart from state: the server changes the state
in its event, then tells everyone, unreliably. `combat/fx_vars.py` has the picture; the
machinery is `combat/weapon_component/fx.py`, and each cosmetic's nodes stay with the
module that owns the action.

```
owning client                      server                        every machine
the ask, predicting ---------->    Server_Fire / _Punch /        Multicast_<Name>(params)
  Fx_Shot, Fx_Reload, Fx_Punch,      _Slash / _Throw, ReloadNow    gate? -> FxPlayed + 1
  Fx_Slash, Fx_Throw (off the        state, then fx.tell(...)      -> Fx_<Name>(params):
  authority Branch's false arm)      Multicast_<Name>                 the sound, the clip,
                                   the sweep's blow, a pellet,       the spawn, once
                                   the flight's strike: tell too
```

- **Every cosmetic is a pair of events on `BP_WeaponComponent`:** `Fx_<Name>` holds the
  one copy of its nodes; `Multicast_<Name>` (unreliable) is the server's word of it,
  whose gate asks whether this copy owes it, counts it in `FxPlayed` and calls
  `Fx_<Name>`. The pairs: `Shot`, `Reload`, `Punch`, `Slash`, `Throw(Start, Sharp)`,
  `ThrowClip`, `PunchHit(Location)`, `BladeHit(Location)`, `Chop(Location, Normal)`,
  `Stab(Location, Normal, HeadKill)`, `Lodge(Location, Normal)`, `Match(Location)`.
- **A shot's impacts are told once** (A4; `weapon_component/shot_hits.py`,
  `verify/shot_hits.py`): `Fx_PelletHit(Location, Normal, Scale, Blood)` has no Multicast
  of its own. The fire graph notes each pellet's impact onto three arrays as it lands
  (where it told `Multicast_PelletHit`), and `FlushShotHits`, called off the pellet loop's
  Completed, tells them in one `Multicast_ShotHits(Locations, Normals, Bloods, Scale)`
  (unreliable, gate *screen*), which counts each entry in `FxPlayed` and calls
  `Fx_PelletHit` per entry. One packet's worth of header a shot instead of eight, and
  they all arrive: `probe_net_fx.py`'s client 2 counted 2 impact actors of a shotgun's 8
  before (the other six never arrived; why was not traced: the likely cause is the
  engine's cap on unreliable Multicasts an actor may send in a frame) and counts 8 now.
- **Three gates** (`fx_vars.UNPREDICTED`, `OTHERS`, `SCREEN`):
  - *unpredicted*, `HasAuthority OR NOT LocalInput`: the owning client already played it
    as its prediction (`fx.predict`, off the authority Branch's false arm, where the ask
    is), everyone else owes it. The shot's and the reload's sound, the two swings' clip
    and sound, the throw's sound.
  - *others*, `NOT LocalInput`: the owner played it in both modes before the server knew
    (the throw's clip is the wind-up's, at the click). `ThrowClip`.
  - *screen*, `NOT IsDedicatedServer`: nobody predicted it (a blow lands by the server's
    sweep, a pellet by its trace), so every machine with a screen plays it, the striker's
    included, and the server never. The six point bursts.
  - `LocalInput` is the local gate's answer, written on every copy each Tick ("Input"):
    true on the owning client and in single player, false on the server and on another
    player's copy.
- **Single player plays each once:** the one machine has authority, every Multicast is a
  plain call, *unpredicted* passes (authority), *screen* passes, *others* does not (the
  wind-up played the clip). Nothing is predicted and nothing plays twice.
- **The owner's copy counts none of what it predicted:** `FxPlayed` is each copy's own
  count of cosmetics played at the server's word, a probe's readout and nothing else
  (`probe_net_fx.py`: client 1 counts only its pellets' chips).
- **What is not a pair:** hit reactions, the grunt, the heartbeat and the collapse follow
  `Health`'s RepNotify on every copy ("Health and damage"); footsteps are each copy's own
  footstep component, driven by the replicated movement (the probe watches its copy
  stride); the headshot's X is `HeadshotTime`, a RepNotify to the owner whose OnRep
  rewrites it with this machine's clock (`headshot.replicate_headshot`); the dying is M16's.
  There is no muzzle flash in the game, and the tracer is debug mode's, drawn where the
  shot ran (the server's).
- **The noise the wanderers hear is the server's own event's** (`shot_noise.py`, inside
  `Server_Fire`), never a Multicast's: a lost cosmetic loses nothing a wanderer heard.
- **A new sound or effect of a shot, a blow or a throw goes in a pair,** authored by the
  owning module with `fx.pair(ed, name, params, body, gate)` before the event or the Tick
  fragment that tells it (`build.py` authors every pair first: a call finds only an event
  that exists), and never at the site that decides it, which runs on the server and has
  no speaker. The point bursts' transform is `fx.point_transform` (the event's Location,
  +X on its Normal, a Scale on every axis).
- **A montage just started reads as a quiet slot:** `IsSlotActive` is false until it has
  blended in, so the ready pose's keep-alive would replace the throw's clip on its first
  frame on another player's copy (whose slot holds the hold pose, not the ready pose). The
  keep-alive and the equip's stop ask `IsPlayingSlotAnimation(ThrowAnim)` instead, so the
  clip plays on through the hand letting go, on every copy (`inventory.py`,
  `ready_pose.py`).
- **Not here:** the cocked arm while the throw key is held, and the wind-up before the
  release, are the thrower's alone (the others see the clip from the release on); the
  wanderers' own sounds (their growls, roars and blows run on the server: M27); a
  rendered check that the sounds are heard (the probe counts what each copy played).
- `combat/verify/fx.py` checks the pairs, the gates, the predictions and the RepNotify.
  Proof: `uepy.py --net --clients 2 --probe-timeout 240 --probe
  Scripts/probes/probe_net_fx.py` (client 1 walks, fires at the ground, reloads, slashes
  and throws the knife; the server and client 2 count each at the server's word, client 2
  sees the chips as actors and the knife's and the throw's clips playing on its copy of
  the character, and client 1 counts only its chips), also with `--lag 120`;
  `OW_FX_SHOTS=1 ... --windowed` saves client 2's view of each step to
  `Saved/Screenshots/MacEditor`; `--game` runs its single-player arm.

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
| `combat/gun_drop.py` | state | whether a kill leaves a gun, and which: two streams on the GameMode | the same arm, and the streams are the GameMode's, which a client does not have; the gun is an actor the server spawns, and it replicates as any item lying in the world does (M23) |
| `combat/replacement.py` | state | where a killed wanderer's replacement appears (bearing, distance, the navmesh's point) | the same arm; the wanderer is spawned by the server and replicates |
| `combat/player_respawn.py` | state | which PlayerStart a respawn is given | behind death's IsStandalone Branch and the authority switch; the new pawn replicates |
| `survival/on_hit_graph.py` | state | whether a blow leaves its on-hit effect (a wendigo's: bleeding, 33%) | behind HasAuthority of the target, in the fragment itself; the effect is the target's ability system's, which replicates ("Survival") |
| `npc/patrol.py` | state | a patrol's next point and how long the wanderer waits there | the wanderer's AIController, which exists on the server alone; its movement replicates |
| `npc/stalk.py` | state | the wendigo's hunt: which way round, when it turns, the wait behind a tree | the AIController, as the patrol |
| `npc/strafe.py` | state | between two swings: the sidestep's angle, side and distance | the AIController, as the patrol |
| `npc/ward.py` | state | held off by fire: which way it circles and when it turns | the AIController, as the patrol |
| `npc/ward_roar.py` | state | held off by fire: when the first roar comes (it stands for it) | the AIController, as the patrol |
| `combat/weapon_component/firing.py` | state | where in the gun's cloud a round or a pellet goes | inside `Server_Fire`, which only the server runs (single player: a plain call); the owning client draws nothing, and what the pellets did replicates as health |
| `combat/weapon_component/chop.py` | state | where the wood lands beside the trunk, and how it lies | the weapon component of whoever chops, on the server alone: the chop hangs off the server's blow, and the wood it leaves replicates |
| `world/day_night_graph.py` | state | the time of day a level starts at | every machine's own BP_DayNightCycle at BeginPlay; one clock, the server's, replicated (**M30**) |
| `Sound/play.py` | cosmetic | which take of a sound plays (every sound with more than one) | wherever the sound plays |
| `combat/hit_reaction.py` | cosmetic | which of the three front flinches a blow from the front plays | every machine's copy of the health component, off its own Tick |
| `combat/weapon_component/recoil.py` | cosmetic | the kick's sideways drift, on the view of the player who fired | the owning client: it turns its own controller, as the mouse does |
| `npc/stats.py` | cosmetic | the gap before a wanderer's next growl | the AIController (the server's); every client hears the growl once sounds are multicast (**M21**) |

- **Still drawn by the machine that acts,** until its action is the server's: the hour
  a level starts at (M30: every machine's sky is its own today).
- **A dropped gun is rolled by the server and spawned there;** it reaches a client as
  every item lying in the world does (M23: its own Tick replicates it). A landed bleed is the target's ability
  system's on the server, which replicates its effects: the owner's HUD reads the tag ("Survival").
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
- **The take is the server's** (`AskLootTake` is a Server event: M23, "Picking up,
  dropping and looting"): the row leaves the server's body, so every client's window
  loses it, and the item reaches the taker's bag by the record.
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
| items on the ground | **Fixed (M23)** for players who are there: an item lying `Dropped` replicates from its own Tick on the server, a client's copy of a placed one becomes the server's, and the take and the drop are the server's (measured: `probe_net_take.py`). A client that joins after a placed one was taken sees none: the take destroys the level actor (A2, `probe_net_late_join.py`). Before: the 24 mushrooms and the test garments are level actors whose classes do not replicate (`BP_Mushroom`, `BP_Hat`: read off the class defaults): each process has its own, and a pick-up on a client removes it nowhere else | measured (the counts, the defaults), read (the pick-up) | M23, M31 |
| day and night | Each process rolls its own start time: in one run it was day on the server and client 2 and night on client 1 | measured | M30 |
| walk speed, sprint, stance | The weapon component wrote `MaxWalkSpeed` every tick in every process from its own unreplicated state. **Since M10 only the local player's copy writes it** (the sprint and the aim are behind the local gate), so the server's copy keeps the speed the character was built with. Sprint, crouch and prone are keys read on the client, so the server would correct a sprinting client. **Fixed (M12): "Movement states are predicted", above** | the write measured; the fix measured (`probe_net_move_states.py`, 137 ms) | M12 done |
| input | **Fixed (M10): "Input", above.** The weapon component polled keys in its Tick on every copy of every character, the server's included, and on `GetPlayerController(0)`, so a client's press drove every character it could see | read; the fix measured (`probe_net_local_input.py`, headless and `--windowed`) | M10 done |
| stamina, hunger, thirst, temperature | Per-process component and GAS state: no builder replicates a variable or a component yet (`net.replicate` has no caller outside `dev/check_net_authoring.py`). **Stamina is the server's since M12** (the movement component; the owning client predicts it and is corrected to it). **Hunger, thirst, temperature and the debuffs are the server's since M26: "Survival", above** (measured: `probe_net_survival.py`) | read; stamina and the bars measured | M12, M26 done |
| animation of the other player | Only what CharacterMovement replicates reached a simulated proxy (velocity, falling). **Fixed (M13): "Other players' characters", above**: stance, aim pitch, aim mode, the gun raised or lowered and the hand's pose. **The swing's and the throw's clips: fixed (M21), "Everyone sees and hears the fight"** | read; M21's measured (`probe_net_fx.py`) | M13, M21 done |
| sounds and effects | Played where the graph that caused them ran, so a shot, a blow or a footstep is heard by its own client only. **Fixed (M21):** each cosmetic is an `Fx_`/`Multicast_` pair told by the server, the owner predicting its own; footsteps were already each copy's own component | read; the fix measured (`probe_net_fx.py`) | M21 done |
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

## Relevancy, update rates and dormancy; the late joiner (A2, done)

Before this nothing was configured: every replicated actor was considered for every
connection every frame at the engine's defaults (a 150 m cull distance that the generic
driver applies, 100 Hz), and a placed item that was taken was hidden, so a client joining
later still had its own copy lying there. Now the server sends each client what it can see
or owns, at the rate each thing needs, and a late joiner's world is the server's.

- **One table:** `net/relevancy_consts.py` (`Relevancy(cull_m, update_hz, min_hz)`:
  characters 150 m at 30/5 Hz, items and campfires 60 m at 10/1 Hz). `net/relevancy.py`
  writes a row onto a class's defaults (`NetCullDistanceSquared`, `NetUpdateFrequency`,
  `MinNetUpdateFrequency`) and reads it back; the builders call it after a compile:
  `combat/install.py` (the player's character, and the wanderer's body again),
  `npc/character.py` (the body and each creature's child), `combat/item_world.py`
  `relevance_item` (`BP_WeaponItem`, which every item inherits), `survival/campfire.py`.
  The GameState and the PlayerStates keep the engine's defaults. A component has no row of
  its own: it travels with its actor.
- **The replication graph** (`Source/Otherworld/Public/OtherworldReplicationGraph.h`, the
  `ReplicationGraph` plugin, named for the `IpNetDriver` in `Config/DefaultEngine.ini`):
  a grid-spatialisation node (100 m cells) for everything with a place in the world
  (characters, items, campfires), an always-relevant list for `bAlwaysRelevant` actors (the
  GameState, the PlayerStates), and a node per connection for its own controller, pawn and
  PlayerState. Controllers are routed nowhere (each is its connection's own). Every class's
  cull distance and period come from its CDO, so the graph holds no game logic. Standalone
  has no net driver: single player is untouched.
- **Dormancy:** an item's own Tick, on the server, sets `NetDormancy` `DORM_DormantAll`
  while the item lies still or is carried (`Dropped`, or not `InWorld`) and `DORM_Awake` in
  flight, on the change alone (`Dormant` remembers; `item_world._author_rest`). A dormant
  actor is sent to a connection once and its channel closed; the graph keeps it in its cell
  as a still one. The graphs that change a lying item's replicated state wake it with
  `FlushNetDormancy` (`item_world.author_wake`): entering the world (set down again after a
  carry: it is where it lies now), the take (`InWorld` lowered, or no client would hide its
  copy), a lying stick burning out (`combat/stick.py`), a lying blade cooling
  (`combat/heat.py`). A campfire is `DormantAll` from its class default: lit once, it changes
  nothing after, and its destroy reaches a dormant copy as the engine's destruction info.
- **The take of a level actor:** `Server_Take` asks `IsLevelActor` (C++,
  `UOtherworldNetLibrary`, `uebp/nodes/level.py`: `AActor::IsNetStartupActor`, which
  Blueprint cannot ask) and, for one, spawns a fresh item of its class where it lay,
  destroys the level's, and puts the fresh one in the bag (`TakeItem`, `pickup.py`
  `_author_fresh_item`). The engine tells every client of a destroyed startup actor, the
  ones that join later too (`DestroyedStartupOrDormantActors`, sent as a late joiner comes
  within the graph's destruction-info distance, 150 m). A dropped or thrown item stays one
  actor, as before. In single player the same happens to one machine.
- **The harness:** with `--title` the server's probe now starts with the first player
  (`probes/boot.py`), since each client joins when its probe says.
- **Proof:** `uepy.py --net --title --clients 2 --probe-timeout 420 --probe
  Scripts/probes/probe_net_late_join.py` (client 1 joins; the server has its character
  take the level's hat, cut wood at a trunk with three `Server_Slash`, and light a campfire;
  client 2 joins 20 s later and is stood by the fire: no hat in its world, one fire where the
  server put it, client 1's character). `probe_net_see_each_other.py`,
  `probe_net_take.py`, `probe_net_campfire.py`, `probe_net_clothing.py` and the other M20–M25
  probes still pass. `combat/verify/relevancy.py`, `verify/pickup.py`,
  `survival/verify/campfire.py` and `npc/verify.py` `check_relevancy` are the wiring. A
  probe that held the level actor across a take (`probe_net_take.py`, `probe_pickup.py`,
  `probe_pickup_height.py`, `probe_clothing.py`) now follows the fresh one: the level's is
  invalid after the take, and the bag's new item is its class.
- **Measured (A1's harness, N = 32 bots, 2 `-nullrhi` clients, 90 s, `Lvl_Forest_200m`):**

  | | server world tick ms mean / p99 | server Hz | bytes out per client | actor channels per client |
  |---|---|---|---|---|
  | before (2026-10-07, the generic driver) | 26.4 / 67.2 | 27.8 | 14.1 KB/s | 119 |
  | after (2026-10-07, the graph, the rows, dormancy) | 26.9 / 55.6 | 28.2 | 7.1 KB/s | 90 |

  The server sends each client half the bytes it did (14.1 → 7.1 KB/s) over a quarter fewer
  channels (119 → 90: the items lying still and carried are dormant, and the far bodies are
  culled on the 200 m map), and the same game thread: the world tick is the bodies' and the
  wanderers' (A1's three largest costs), not replication's, so the frame does not move.
  The gain in bytes grows with the players a server has, since each is sent only its
  neighbourhood; the cost that remains is what A3 onwards measures against.
- **Left for M31:** corpses, chopped trees and a cleanup rule (a lifetime, a cap) for what
  lies in a long-running world.

## Memory (measured, the editor binary; `serversupportsysdesign.md` 5 has the table)

| process | 200 m map | 1 km map |
|---|---|---|
| dedicated server | 1.9 GB | 2.5 GB |
| client, `-nullrhi` | 1.9 GB | 2.2 GB |
| client, `--windowed` | 5.8 GB | not measured |

Since G3 (2026-10-08) every process loads the Game Animation Sample's databases with the
player's motion matching: a server or a `-nullrhi` client peaks at 4.2–4.3 GB on the 200 m
map, and a server with two `-nullrhi` clients at 12.9 GB (`Scripts/combat/CLAUDE.md`, "The
motion-matching base").

## Measured at scale (A1, 2026-10-07)

The load harness is `uepy.py --net --bots N`: the dedicated server (the editor binary with
`-server`) spawns N more `BP_ThirdPersonCharacter` bodies as soon as its level is up, each
possessed by the engine's plain AIController and driven by `Scripts/probes/bots.py` from the
engine's ticker: on a timer of 1.5–3 s each walks to a random reachable point within 15 m,
crouches or stands (30%), and fires at the nearest other living body within 60 m through the
same `Server_Fire(AimPoint)` and `Server_Reload` a client asks with, so the weapon component's
Tick, the record, the hit history and the health path run for it as for a player. The aim is a
point within 1.5 m of the target, so most shots miss, as a player's do; a dry gun's reserve is
refilled; a dead bot gets a new body 10 s later and the old one lies 60 s, as a player's does
(`combat/player_respawn.py`). `--bots 0` is the plain `--net`. `--trace` adds
`-trace=net,cpu` to the server, writing `server.utrace` into the run's folder.
`Scripts/probes/probe_net_load.py` is the measurement: once every bot has been spawned and
every client joined, 5 s of play, then a 90 s window (`UEPY_LOAD_SECONDS` changes it) read
through `UOtherworldLoadLibrary` (`Source/Otherworld/Public/OtherworldLoadLibrary.h`:
UNetConnection's counters are not properties, so Python cannot read them without it). Every
figure is a check's detail, and each process writes `load-<process>.json` beside its log.

**The runs:** `Lvl_Forest_200m`, 2 real `-nullrhi` clients, 90 s window each, this Mac
(M-series, 10 cores, 16 GB), the editor closed first. The server's tick rate is the engine's
default `NetServerMaxTickRate` of 30 Hz, so a frame is 33 ms unless the world tick overruns it;
the world tick (UWorld::Tick, which holds the net driver's dispatch and replication) is the work.

| N bots | server frame ms mean / p99 / max (Hz) | server world tick ms mean / p99 | bytes out per client (packets/s) | bytes in per client | actor channels per client | lag ms (server / client) | characters, hit history samples | bot deaths / shots in 90 s | client frame ms mean / p99 (Hz) | memory: server, each client (footprint) |
|---|---|---|---|---|---|---|---|---|---|---|
| 4 (the shakedown: 1 client, a 20 s window) | 39.7 / 248.7 / 384 (25.2) | 11.6 / 221.0 | 5.9 KB/s (25) | 4.1 KB/s (70) | 61 | 29 / 24 | 18, 558 (31 each) | – | 1.5 / 2.1 (656) | 2.0, 2.0 GB |
| 8 | 36.0 / 55.6 / 403 (27.8) | 11.4 / 46.7 | 7.5 KB/s (27.8) | 5.3 KB/s (73) | 77 | 22 / 32 | 33, 990 (30 each) | 2 / 243 | 3.8 / 6.2 (265) | 2.0, 2.0 GB |
| 16 | 36.4 / 78.8 / 403 (27.5) | 18.1 / 64.1 | 9.7 KB/s (27.5) | 4.7 KB/s (67) | 104 | 36 / 47 | 60, 1800 (30 each) | 15 / 473 | 5.8 / 10.4 (174) | 2.0, 2.0 GB |
| 32 (traced) | 36.0 / 62.1 / 368 (27.8) | 27.0 / 53.5 | 13.8 KB/s (27.8) | 2.5 KB/s (44) | 119 | 42 / 58 | 75, 2250 (30 each) | 34 / 933 | 9.7 / 15.0 (103) | 2.0, 2.0 GB |
| 62 | 45.8 / 110.4 / 374 (21.8) | 42.8 / 104.5 | 22.6 KB/s (29.9) | 1.5 KB/s (30) | 180 | 61 / 92 | 136, 2549 (19 each) | 79 / 1766 | 16.5 / 25.2 (60.5) | 2.1, 2.1 GB |

- **N = 62 fits:** the three processes peak at 6.2 GB together (the server grows 0.1 GB for 62
  bodies), so memory is not the limit on this Mac; the server's game thread is. At 62 the
  world tick is 43 ms mean and the server runs at 22 Hz, below its 30 Hz; at 32 it is 27 ms,
  80% of the 33 ms budget. The frame's max of 350–400 ms in every run is a hitch the trace
  names: one call of the wendigo's stalk step (`BTT_ForestWandererAI_Wendigo_Step` →
  `BT_Stalk`, `npc/stalk.py`, `stalk_cover.py`) took 250 ms, and another 72 ms, inside the
  longest frame; five frames of 350 ms or more fell in the traced 20 s. The wendigo's hunt is
  the one thing on the server that stalls a frame.
- **"characters" counts bodies:** bots, players, the 10 wanderers and every corpse lying its
  60 s, each with a mesh that ticks and a row in the hit history. At 62 bots the history holds
  19 samples per character instead of 30 because the server makes 22 frames a second, not 30.
- **The client's bytes in fall as N rises** (5.3 → 1.5 KB/s): the clients' players are shot
  dead within a minute and a dead client sends only its acks until it respawns. The server's
  bytes out per client (7.5 → 22.6 KB/s, 180 actor channels at 62) are the replication cost
  the next tasks measure against. In bytes per second per client at 62: 22.6 KB/s × 64 clients
  would be 1.4 MB/s out of a 64-player server, before any relevancy or dormancy.
- **The bot driver's own cost** is on the server's frame: 0.12 ms a frame at 8 bots, 0.48 at
  32, 1.30 at 62 (mean; p99 5.6 ms at 62), Python in the core ticker. Read it off the world
  tick when a change is judged.
- **The clients spin:** a `-nullrhi` client runs unthrottled (656 Hz alone, 60 Hz at 62 bots),
  so two of them hold two of the ten cores while the server is measured. Unchanged here: the
  existing `--net` probes wait in game time, which a fixed step per frame ties to the frame rate.

**The three largest costs** (Unreal Insights, `-trace=net,cpu`, the N = 32 server, 20 s of its
window: 478 frames, 20.0 s of game thread of which 5.0 s (25%) is the tick-rate sleep in
`UpdateTimeAndHandleMaxTickRate`; exported with `UnrealInsights -OpenTraceFile=... -ExecOnAnalysisCompleteCmd="TimingInsights.ExportTimingEvents events.csv -threads=GameThread -startTime=60 -endTime=80 -columns=ThreadId,TimerId,StartTime,EndTime,Depth" -AutoQuit`, one command per invocation, and summed per timer, inclusive and exclusive; the trace is kept at `Saved/traces/net_load_32bots_2026-10-07.utrace`):

1. **Every character's skeletal mesh and animation Blueprint tick on the dedicated server:
   30% of the game thread** (`USkinnedMeshComponent_TickComponent` 5.96 s inclusive, 3.44 s
   exclusive, 47 080 ticks; `SKM_Adventurer03` 5.78 s; `ABP_Unarmed_C` 2.20 s inclusive, 1.90 s
   exclusive, 52 744 ticks). The server poses 75 bodies a frame, corpses included, with nothing
   to draw; the hit history needs the bones of the living, not of the dead, and not every frame.
2. **The wanderers' behaviour trees: 18%** (`BehaviorTreeComponent` 3.60 s; the zombie's
   `BTT_ForestWandererAI_Zombie_Step` 2.87 s, 14.3% exclusive, 0.65 ms a call;
   `BT_Chase` 1.89 s, `BT_Swing` 1.08 s; the wendigo's step 0.72 s, of which single calls of
   `BT_Stalk` take 70–250 ms: the hitches above). Ten wanderers, a cost that does not grow
   with N and is a seventh of the budget before a player joins.
3. **The weapon component's Tick on every body: 4.5%** (`WeaponComponent` 0.90 s, 66 037
   ticks, 138 a frame; `ExecuteUbergraph_BP_WeaponComponent` 0.89 s), with the character
   movement at 2.6% (`UCharacterMovementComponent_TickComponent` 0.52 s), the net driver's
   replication to two clients at 2.5% (`NetBroadcastTickTime` 0.49 s, 1.0 ms a frame) and
   the hit history's recording at 1.0% (`OnWorldPostActorTick` 0.20 s, 0.4 ms a frame for
   75 characters) behind it. The health component is 1.4%, the ability systems 0.5%.

**What the load found broken, fixed in no task yet:** on the server every `Accessed None`
(142–235 a run) is a wanderer's `NearestLivingPlayer` read with no living player, the ten or so
seconds both real players lie dead at once (`BP_ForestWandererAI_Zombie` 110–187,
`BP_ForestWandererAI_Wendigo` 32–48 a run); on a client, 16 `GetOwningPawn` reads by
`BP_GraphicsMenuHUD` at each death, the frames between the pawn's death and the respawn. Neither
happens with one living player, which is why no earlier probe met them.

## Every Server event asks the guard first (A5, done)

A C++ RPC has the engine's `_Validate` hook; a Blueprint one has nothing, so a Server
event runs whatever arrives, as often as it arrives, unless its graph asks. Every Server
event on the weapon component (21: the shot and the reload, the swings, the holds, the
throw, the take, the look, the fire and heat four, the wear, the eating and the seven
asks) asks first, one way:

- **The guard is a component on the player**, `RpcGuard` (C++ `UOtherworldRpcGuard`,
  `Source/Otherworld/Public/OtherworldRpcGuard.h`; added and given its numbers by
  `combat/install.py`). Its table is `net/guard_consts.py`.
- **The fragment is `net/guard.py`:** `allowed, refused = author_guard(g, NAME,
  [then(event)])` is the first thing after `net.server_event(...)`, and the event's body
  hangs off `allowed`. `Server_Fire` and `Server_Reload` use `author_allow` (the answer
  and the exec apart) so that `AsksServed` is counted between the ask and its Branch: a
  refused shot hands its round back like any other the server did not fire.
- **`Allow(Name)` is a token bucket per event name per connection:** `RATES[Name]` a
  second, `BURST_S` seconds of it held (what a hitch bunches up passes; a flood does
  not). `Server_Fire` is the fastest gun's rate plus 20 % (13.3/s), the asks 10/s, the
  look report 30/s, the rest 5/s. A refusal logs `RPC-REFUSED <name>`; more than
  `KICK_REFUSALS` (100) in `KICK_S` (10 s) closes the connection
  (`RPC-KICKED ClosedByRpcGuard` in the server's log; the close reason is
  `ENetCloseResult::Extended` with that context). The state is the connection's, not the
  character's: a respawn does not empty it.
- **`AimAllowed(AimPoint)`** is `Server_Fire`'s second question: the point must lie in a
  cone along the server's copy's view (`GetBaseAimRotation`), `AIM_CONE_DEG` (20°) wide,
  opening from a disc 1.5 m across that stands 3 m behind its eyes (the camera's boom and
  shoulder offset: a near point is off the eyes' own line), and within the reticle
  trace's reach. **Not the gun's range:** an honest reticle rests on whatever the camera
  sees, a kilometre out for the sky, and the pellets stop at the gun's range whatever the
  point; a limit at the gun's range refused every shot at the sky.
- **Only a remote connection is counted.** In single player, for a listen server's own
  player and for a character the server drives (a load test's bot) both pass and count
  nothing.
- **A new Server event** gets a row in `RATES` and the fragment; `combat/verify/guard.py`
  fails on an event with no row, a row with no event, a builder that makes a Server
  event and does not name the fragment, and an event whose first node is not its own
  `Allow` and Branch. A Server event on another Blueprint fails there too: the guard is
  the player's, so its component would have to be reached first.
- **What already checked itself still does:** `Server_Throw`'s start and speed,
  `Server_Take`'s and `AskLootTake`'s reach, the cooldowns. The bucket is in front of
  them, not in their place.
- **The kicked client** is told only that its connection was lost (it returns to the
  title with that). `uepy.py --net` forgives one client's lost connection for each
  `RPC-KICKED` the server logged, and marks its row.
- **Proof:** `probe_net_guard.py` (`--clients 2`): a `Server_Fire` at a point behind
  client 1 spends nothing; the trigger held asks at the gun's rate with none refused;
  50 `Server_Fire` in a frame get a burst through (14) and the rest refused; 200
  `AskSlot` in a second get client 1 kicked, and client 2 plays on. In `--game` a shot
  behind the player fires and 200 asks count nowhere. `probe_net_fire`, `probe_net_melee`
  and `probe_net_take` are clean with `--lag 120`, with no `RPC-REFUSED` in any server
  log.
- **Not done here:** a gun made faster than the fastest built one on a running server's
  GUN SETTINGS page is refused its extra rounds (the table is written at build time).
  The guard does not rate-limit what the engine sends itself (movement).

## What the server spends on bodies it never draws (A4, 2026-10-08)

A dedicated server draws nothing and judges every shot against the bones, so it must pose
every body; it need not pose one as a screen would. Four changes, each measured with A1's
harness (`uepy.py --net --clients 2 --bots N --probe Scripts/probes/probe_net_load.py`,
`Lvl_Forest_200m`, a 90 s window, this Mac with the editor open):

- **Only the mesh the game runs on ticks** (`ThrottleServerPose`, C++,
  `Source/Otherworld/Public/OtherworldServerPose.h`, called by `combat/server_pose.py`
  behind its IsDedicatedServer Branch): every other skinned mesh on a body stops ticking
  on a dedicated server. With the MetaHuman rig (`asset_pipeline/player_body.py`) that is
  the MetaHuman's body, face and clothes, hung under the mannequin to be drawn: on the
  server they were retargeting the body and solving the face's rig for nobody, 73% of
  the game thread at 32 players.
- **The mesh is posed by how near a player is** (the engine's Update Rate Optimization,
  whose not-rendered rate the C++ rewrites per body four times a second;
  `combat/pose_tuning.py`): within 30 m of another player's body every frame, further
  off 10 times a second, with nobody within the characters' relevancy distance (150 m)
  or as a ragdoll twice. A load test's bot counts as a player. The hit history keeps a
  pose per posed frame and blends between them ("Lag compensation" above).
- **The anim graphs have one IsDedicatedServer branch** (`combat/server_anim.py`,
  `server_anim_consts.py`; `combat/verify/server_anim.py`, which the NPC verifier runs
  for the wanderers too): a Blend Poses by bool on `ServerPose`, which the anim
  Blueprint's own BlueprintInitializeAnimation writes once. A server skips the player's
  foot IK (the Control Rig, which traces the ground under both feet) and FullBodySlot,
  and never gives the support hand's IK a weight (`weapon_component/support_hand.py`).
  It keeps the aim's blend (DefaultSlot: the arms' hit bodies and the muzzle) and the
  flinch's (HitSlot), on the player and on the wanderers: each moves a hit box a shooter
  is aiming at, and these graphs fan a pose out to a blend's base and its slot, so an
  arm that left a blend out would update the locomotion under it fewer times a frame
  than a client's does. **A new node for the eye goes on the client arm**; the verifier
  fails a server arm that holds a slot, a blend or a node class the table does not list.
  - **The player's worn graph is the motion matching's since G3**, and has the same one
    branch, authored by `combat/gas_locomotion.py` and checked by
    `combat/verify/gas_locomotion.py`: a server takes the pose from before Foot Placement
    and Leg IK (the sample's ground traces under the feet) and keeps the search, the
    lean, the aim offset, the root's offset and the pose history. The graph above
    (`ABP_Unarmed` with the player's layers) is still built and checked, and is what G4
    brings over. The motion matching reads the CharacterMovementComponent on each
    machine, so a simulated copy and the server's are animated with nothing replicated
    for it (`probes/probe_net_gas_locomotion.py`).
- **A shot's impacts are one Multicast** ("Everyone sees and hears the fight" above),
  and the hit history is two rings per character with the capsule tried before any body
  is blended ("Lag compensation").

| N bots | | server frame ms mean / p99 (Hz) | server world tick ms mean / p99 | characters, history frames each |
|---|---|---|---|---|
| 32 | before A4 (2026-10-08: the MetaHuman rig, landed after A1 and A2 measured) | 199.2 / 457.2 (5.0) | 194.1 / 442.1 | 77, 4 |
| 32 | A1 and A2's own figure (2026-10-07, the adventurer's body, no MetaHuman) | 36.0 / 62.1 (27.8) | 26.9 / 55.6 | 75, 30 |
| 32 | after, the foot IK still on the server arm | 37.9 / 145.0 (26.3) | 31.5 / 96.0 | 81, 30 |
| 32 | **after A4** (traced) | 37.2 / 143.9 (26.8) | **25.3 / 87.0** | 77, 31 |
| 62 | A1's figure (2026-10-07, no MetaHuman) | 45.8 / 110.4 (21.8) | 42.8 / 104.5 | 136, 19 |
| 62 | **after A4**, 2 clients (13.2 GB of this Mac's 16: it swapped, client 2 never got its pawn) | 50.0 / 181.3 (20.0) | **44.5 / 144.1** | 128, 20 |
| 62 | **after A4**, 1 client (8.4 GB) | 47.6 / 159.7 (21.0) | **42.4 / 112.6** | 150, 15 |

- **What moved:** the MetaHuman's meshes, 14.9 s of a traced 20.4 s before, are 0.8 s of
  20.1 s after (what is left of them is below); the foot IK was 5.5-6 ms of the 32-player
  world tick. Before A4 the server made 5 frames a second at 32 players and was not
  measured at 62.
- **What did not:** against A1's own figures the frame is where it was (25.3 against
  26.9 ms at 32, 42.4-44.5 against 42.8 at 62). The throttle has little to bite on in
  this test: 62 bots on a 200 m map stand within 30 m of one another, so every living
  body is posed every frame (65 of 150 bodies at the window's end; the other 85 were
  corpses, lying their 60 s at 2 Hz, which before A4 were posed every frame too). The
  mannequin the MetaHuman rig runs on costs more a pose than the adventurer A1 measured.
  On `Lvl_Forest_1000m` the same players stand twenty-five times thinner; not measured
  (the three processes do not fit this Mac there).
- **The N = 62 world tick decides `serversupportsysdesign.md` 8's Tier 2 question:
  42-44 ms mean, above the 25 ms line, so the Tier 2 server skeleton is the next task.**
- **The three largest costs after** (the N = 32 server, 20.1 s of its window, 491 frames,
  5.9 s (29%) of it the tick-rate sleep; `Saved/traces/net_load_32bots_a4_after_2026-10-08.utrace`):
  1. **the mannequin's mesh, 24% of the game thread** (`CharacterMesh0` 4.84 s inclusive;
     `USkinnedMeshComponent_TickComponent` 4.03 s, 2.97 s of it its own, over 48 281
     ticks, 98 a frame; `ABP_Unarmed_C` 0.73 s). The pose itself, of every living body.
  2. **the wanderers' behaviour trees, 11%** (2.20 s; the zombie's step 2.02 s).
  3. **the weapon component's Tick, 6.4%** (1.29 s), then the health component 0.84 s,
     the character movement 0.66 s, the net driver 0.28 s and the hit history's recording
     0.18 s (0.37 ms a frame for 77 characters, as before: its cost is the walk over the
     characters, not the allocation the rings removed). `ShotTrace` is 0.01 s for 1 664
     pellets.
- **Left:** something of the MetaHuman still runs each frame on a server though its
  primary ticks are off (`Body` 0.52 s inclusive with `Legs` 0.28 s and `Torso` 0.20 s
  under it, `Face` 0.28 s: 4% together; not a primary tick, not found which). A Tier 2
  body would have none of them.
- **Proof:** `uepy.py --net --clients 2 --probe-timeout 240 --probe
  Scripts/probes/probe_net_server_pose.py` (on the server: one skinned mesh of a body's 6
  ticks; every anim instance has `ServerPose`; two players 5 m apart are posed every
  frame with a pose for each of the history's 31 frames; a wanderer 85 m off every 3
  frames, 11 poses in 31 frames; a player moved 60 m off drops to that rate too. On a
  client: `ServerPose` false, all 6 meshes tick, nothing throttled). `probe_net_fire.py`
  (the server's gun is where the client's is), `probe_net_fx.py`, `probe_net_lag_hits.py`
  with and without `--lag 150` ("Lag compensation" has its numbers and their spread),
  and in single player `probe_ads_hit`, `probe_headshot`, `probe_net_fx --game`. Run the
  `--game` probes one to a launch: `probe_headshot` and `probe_ads_hit` in one launch
  fail each other, and the checks that put a hip round into a wanderer come and go from run
  to run (`probe_headshot`'s chest, which its rounds also missed on the build before A4,
  and `probe_bullet_impact`'s blood, which failed one run of two here).
