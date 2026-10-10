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

Each task's narrative (what was built, why, what was measured, its proof) is in
`docs/history/multiplayer.md`, moved there word for word; the last line under a heading
here names its part.

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


- M8, M9, M10, M14 player 0, task by task: docs/history/multiplayer.md#player-0


## A screen asks, the character acts (M11, done)

A server has no HUD, so nothing a player does may live in a widget graph. Each thing done
through a screen is **one custom event on `BP_WeaponComponent`**, which the HUD calls with
what was picked (`graphics_menu/ask.py`, `ask(ed, wc, ASK_MOVE, execs, made, From=…, To=…)`)
and which decides whether it happens. The names are `combat/ask_consts.py`.

- **A new action through a screen gets an event the same way.** Refuse in the event, not
  in the widget: what the widget greys out is display, and a client's widget is not trusted.
- M11 a screen asks: docs/history/multiplayer.md#m11

## Input (M10, done)

A component ticks on every machine that has its character: the player's own, the server
and every other client. Only the first has that player's keys.

- **A component polls `LocalPC`, behind the local gate**
  (`combat/weapon_component/local.py`). At the head of the Tick, after the dead gate:
  the owner is a Pawn, its controller is a PlayerController and `IsLocalController`.
  True writes `LocalPC` (that controller) and `LocalInput`; anything else clears both.
  `local_pc(ed)` is the pin every poll's self is; `_author_local_only` asks
  `LocalInput` again further down a chain.
- **Never ask for a controller or a camera by index.** `GetPlayerController(0)` is the
  local player on a client whichever character the graph is on (one press of fire used to
  fire every character that client could see), and the first joiner on a server.
  `FN_GET_PC` and `FN_GET_CAM` are gone from the node catalog; the camera is `LocalPC`'s
  `PlayerCameraManager` (`combat/weapon_component/aim.py`).
- M10 input: docs/history/multiplayer.md#m10

## Movement states are predicted (M12, done)

- **Sprint, prone and the aim-walk are the movement component's**, a C++ subclass
  (`Source/CLAUDE.md`, "Predicted movement"; `combat/player_move.py` reparents the
  player onto it). Each is a flag on every move the owning client sends, and both
  machines work the speed, the capsule and the stamina out of the flags in the same
  step, so the client moves at once and the server agrees.
- M12 predicted movement states: docs/history/multiplayer.md#m12

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

- M13 other players' characters: docs/history/multiplayer.md#m13

## Health and damage (M14, done)

Health is the value a cheater most wants, so only the server changes it, and every blow
says who struck it. `combat/damage.py` is the whole of it.

- **A blow calls the target's `TakeHit(Amount, From, InstigatedBy, Cause)`,** a custom
  event on `BP_HealthComponent`, with `damage.hit(ed, as_health, amount, came_from,
  instigator, cause, execs)`. No graph writes another body's `Health`, `LastDamageTime`,
  `LastHitFrom` or `DamagedByPlayer` (`combat/verify/damage.py` fails on one in the weapon
  component, `npc/verify.py` in a wanderer's controller).
- **Players hurt players (M15, done), and nothing was added to make them.** A pellet, a
  swing and a thrown blade take health off whatever carries a `BP_HealthComponent`, through
  `TakeHit`, with the target's own hit-box tables; a player's character carries one as a
  wanderer's does. Never give a blow a "is this a wanderer" test: friendly fire is on until
  teams exist (M33), and the team check will go in `TakeHit`, the one place every blow
  passes.
- M14 health and damage, M15 players hurt players: docs/history/multiplayer.md#m14

## The inventory (M18, done)

What a player carries is the server's. The server keeps the item actors every graph already
works on (`Inventory`, each item's `Slot`, `Loaded`, `Reserve`); what travels is a **record**
of them, plain data, one C++ struct on its own component (`combat/record_vars.py`,
`Source/Otherworld/Public/OtherworldInventoryRecord.h`):

| on `UOtherworldInventoryRecordComponent` | holds | replicates to |
|---|---|---|
| `Record` (`FOtherworldInventoryRecord`): `Items[i]` (class, slot code, loaded, reserve, lit, hot), `Worn[slot]` (class or none) | a row per carried item, in `Inventory`'s order, and a class per worn slot | the owning client (`COND_OwnerOnly`), whole, with one RepNotify |
| `HandClass`, `HandLit`, `HandHot` | the class in hand, or none; whether it burns or glows | everyone else (`COND_SkipOwner`), each a RepNotify |

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
- M18 the inventory, A3 the record: docs/history/multiplayer.md#m18

## The shot and the reload (M19, done)

Shooting has to feel immediate to the shooter while the server stays the judge of ammo,
timing and hits. `combat/shot_vars.py` has the picture; the graphs are
`combat/weapon_component/shot.py`.

- **`Server_Fire` is a C++ RPC since W1** (`UOtherworldWeaponComponentBase`, the weapon
  component's native parent; `Source/CLAUDE.md`). Reliable, with a `_Validate` that
  closes the connection only for an `AimPoint` that is not a number. Its
  implementation asks the guard, counts the ask served, refuses quietly (no gun, a dead
  owner, no round, the cooldown), spends the round, stamps the deadline, marks the
  record, and raises `ShotFired` for the graph; the pellets' traces and `TakeHit` are its
  `FirePellets`.
- **`Server_Reload` is a C++ RPC since W2**, reliable, on the same base: the guard, the
  count, then `ReloadNow`, a plain function the owning client also calls as its
  prediction. It works out how many rounds move once and writes the magazine, the
  reserve and the deadline; a reload that moved rounds raises `Reloaded` for the graph's
  clack. Everything else is still a Blueprint Server event.

- **The client sends one thing: where its reticle rests.** The server traces from its own
  copy's muzzle (`carry._author_shot_origin`) and draws the shot inside its own copy's
  `AimSpread`, so a client cannot shoot from where it is not, nor choose its place in
  the cloud. The hold-breath sway and the sights need nothing of their own: both move
  the client's view, and the view is what `AimPoint` is taken from; down the sights the
  server's cloud is closed because its copy mirrors the aim mode. The aim mode is still
  the client's word ("Other players' characters", above).
- M19 the shot and the reload: docs/history/multiplayer.md#m19

## Lag compensation (M22, done)

A shot asked of the server arrives a round trip after the shooter saw the target, and
the shooter saw the target where the server's last update put it. Traced against the
present, a round aimed at a strafing character's chest passed behind it: with 150 ms
of lag the old graph landed 0 pistol rounds in 8. The server now judges the shot
against where the target stood when the shooter fired. It is C++, the `Otherworld`
module (`serversupportsysdesign.md` 4.3: not practical in Blueprint); the numbers are
`combat/lag_tuning.py`; the one node is `uebp/nodes/shot.py`.

- M22 lag compensation: docs/history/multiplayer.md#m22

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

- M20 melee, the guard, the throw and the take: docs/history/multiplayer.md#m20

## Picking up, dropping and looting (M23, done)

Two players reaching for one item is settled by the server, and nothing is duplicated:
every item in the world is one actor, the server's, and every way of taking one or
setting one down is a reliable Server event on the weapon component.

- **An item lying in the world replicates by itself** (`combat/item_world.py`,
  `_author_enter_world`): in the item's own Tick, on its authority arm and only where
  `IsServer`, an item that is `Dropped` and not yet `InWorld` is made `InWorld` and a
  replicated actor. That covers the drop, an item placed in the level, a gun left by a
  kill, wood cut from a tree and whatever spawns one later: **a graph that makes an
  item lie in the world says nothing about replication.** Only the throw's release
  still calls `author_into_world` itself (it is in the air, not `Dropped`).
- M23 picking up, dropping and looting: docs/history/multiplayer.md#m23

## Clothing (M24, done)

Wearing and taking off are the server's, on the inventory's pattern: the server keeps the
item actors (`Worn[slot]`, the very garment that was picked up), a record of them travels,
and the owning client's `Worn` is a picture of the record.

- M24 clothing: docs/history/multiplayer.md#m24

## Fire and heat: the tree, the campfire, the stick, the blade (M25, done)

What changes the world happens once, on the server, and everyone sees it.
`combat/fire_vars.py` has the picture; each event is its owner's module.

| the client asks | the server checks, on its own copy | then |
|---|---|---|
| `Server_Light()` (the fire key tapped, the matches in hand) | alive, its item in hand `Lights`, a `CampfireClass` to spawn, a piece of wood in its bag | the wood is spent, a campfire is spawned 130 cm in front of its copy, `Multicast_Match` |
| `Server_Kindle()` (the use key pressed, a stick that `Burns` in hand) | alive, its item `Burns` and is not `Lit`, a campfire within 3 m of its copy | `Lit` until `BurnOutTime` |
| `Server_Heat(Fire)` (E on a campfire) | `Fire` is there and a `CampfireClass`, within `HEAT_REACH_CM` of its copy, alive, its item `Heats` | `Hot` until `CoolTime` |
| `Server_Cauterize()` (the use key pressed, a `Hot` blade in hand) | alive, its item `Hot`, its ability system | every effect granting the bleeding tag comes off |

- M25 fire and heat: docs/history/multiplayer.md#m25

## Survival: hunger, thirst, temperature, the debuffs, eating (M26, done)

The server owns every survival value; `Scripts/survival/CLAUDE.md`, "On a server", has
the table and the reasons the ability system lives on the character.

- M26 survival: docs/history/multiplayer.md#m26

## Everyone sees and hears the fight (M21, done)

A fight must look and sound the same to everyone near it, and losing a sound must never
change the outcome, so cosmetics travel apart from state: the server changes the state
in its event, then tells everyone, unreliably. `combat/fx_vars.py` has the picture; the
machinery is `combat/weapon_component/fx.py`, and each cosmetic's nodes stay with the
module that owns the action.

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
- M21 everyone sees and hears the fight: docs/history/multiplayer.md#m21

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
- **Never roll a state value on a client "to predict it".** Two draws do not agree. The
  owning client may predict a cosmetic (recoil's drift); the server's answer is the state.
- M17 random rolls: docs/history/multiplayer.md#m17

## Who is nearby (M9, done)

A world actor, a wanderer's controller or any graph that is not a player's own asks
`BPL_Players`, a Blueprint function library (`/Game/Weapons`, built by `players.py` in
the weapons build), through `players.py`'s fragments. Never author a `GetPlayerPawn`.

| the question | the fragment | what it is |
|---|---|---|
| every living player | `living_players(ed, in_execs)` | an exec call: the array is made once. `each_living_player` wraps it in a ForEach |
| the living player nearest a point | `nearest_living_player(ed, point)`, read with `player_pin(node)` | a pure node: asked again at every read, as `GetPlayerPawn` was |

- **Nearest is None while no one lives.** Put the read behind a Branch of its own
  (`combat/ammo_pickup.py`, `combat/replacement.py`). The wanderers' steps sit behind the
  tree's player-present step (`npc/agro.py`), which asks whether `LivingPlayers` is empty.
- M9 who is nearby: docs/history/multiplayer.md#m9

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
- M7 where state lives: docs/history/multiplayer.md#m7

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
- M5 pause: docs/history/multiplayer.md#m5

**Death** (M16, done). One death path, forked where the table says: the health component's
(`combat/death.py`) runs on every machine as before, and standalone's ends where it always
did (the pause, the death menu's restart, the profile deleted). Outside standalone:

- M16 death: docs/history/multiplayer.md#m16

**The title and the session** (M6, done). The modes are the title's first two rows, each a
page (`graphics_menu/mode_*.py`, its `CLAUDE.md` "The two modes"):

- **Traps:**
  - **IsStandalone is already false while a join is pending**, on the title's own world
    (the engine derives the net mode from the pending game). Nothing on the title may ask
    it to mean "I am on a server"; the title's graph asks `GameStarted`.
  - **A dead address fails after 20 s** (the engine's connection timeout) as
    `ConnectionTimeout`, not `PendingConnectionFailure`.
  - **A failure reloads `GameDefaultMap`**, the 1 km level, whatever level the process was
    on. `uepy.py` names the run's level as the default map on every `--game` and `--net`
    command line, so a probe returns to the level it knows.
- M6 the title and the session: docs/history/multiplayer.md#m6

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

- M4 what the spike found: docs/history/multiplayer.md#m4

## Relevancy, update rates and dormancy; the late joiner (A2, done)


- A2 relevancy, update rates, dormancy, the late joiner: docs/history/multiplayer.md#a2

## Memory (measured, the editor binary; `serversupportsysdesign.md` 5 has the table)


- Memory, as measured: docs/history/multiplayer.md#memory

## Measured at scale (A1, 2026-10-07)

**Where the server's tick goes (W0, 2026-10-09).** One run of `uepy.py --net --clients 2
--bots 32 --trace --probe Scripts/probes/probe_net_load.py` (world tick 29.3 ms mean, 26.9 Hz,
64 characters). The game thread over 80 s of its window, 2 160 frames: 13.7 s the tick-rate
sleep, **66.3 s worked (30.7 ms a frame)**, which the shares below are of. Inclusive time;
a row marked ⊂ lies inside the row it names.

| # | cost | s | share | ms a frame | what it is |
|---|---|---|---|---|---|
| 1 | the mannequin's mesh, `CharacterMesh0` | 38.90 | 58.7% | 18.0 | the pose of every living body: `USkinnedMeshComponent_TickComponent` 35.3 s (13.6 s its own), 69 ticks a frame. 2.6 s of the row is the mesh moved by rows 5 and 9 |
| 2 | ⊂ 1: the motion-matching anim Blueprint, `SandboxCharacter_CMC_ABP_C` | 17.98 | 27.1% | 8.3 | 9.3 s its own (the graph's update and evaluation), 4.7 s its Blueprint functions (below), the chooser and the trajectory under them |
| 3 | the tick dispatch's own time, `ProcessUntilTasksComplete` | 4.17 | 6.3% | 1.9 | exclusive: 859 tick functions a frame handed out and waited on |
| 4 | the weapon component's Tick | 4.21 | 6.3% | 1.95 | all of it the Blueprint VM, 51 ticks a frame at 38 µs: 1.6 s bytecode, the rest the natives it calls, most of them the body-parts loops' (`weapon_component/body_parts.py` under `head_hide.py` and `sights.py`: `GetChildrenComponents` 17 times a tick, 0.47 s; `UnHideBoneByName` 0.56 s; 4.0 M `Array_Get`) |
| 5 | the character movement | 2.70 | 4.1% | 1.25 | 1.3 s of it moving the mesh and the MetaHuman's parts under it |
| 6 | the wanderers' behaviour trees | 2.44 | 3.7% | 1.13 | the zombie's step 1.81 s (918 calls, 2.0 ms each), the wendigo's 0.59 s (705) |
| 7 | `Tick_Core` (timers, RPCs) | 2.33 | 3.5% | 1.08 | `SpawnAIFromClass` 1.12 s (21 wanderers, 53 ms each); `Server_Fire` 0.09 s for 861 shots |
| 8 | the health component | 2.14 | 3.2% | 0.99 | 1.54 s is `RestartPlayerAtPlayerStart` (25 respawns, 62 ms each: a new body); its Tick 0.57 s |
| 9 | the AI controllers' tick | 1.58 | 2.4% | 0.73 | native: 1.42 s turning the capsule with the mesh and the MetaHuman's parts under it |
| 10 | the net driver | 1.24 | 1.9% | 0.57 | the replication graph 1.01 s |

Below them: the world's post-actor-tick delegates 1.10 s (the hit history among them, not
split), the six item Blueprints' Ticks 0.92 s together (33 ticks a frame each), the survival
component 0.42 s, the footsteps 0.29 s, `ShotTrace` 0.04 s for 6 880 pellets.

**The Blueprint VM is 15.8 s, 24% of the worked time** (each script scope counted once, at
its outermost; natives it calls included):

| class | s | share | of it |
|---|---|---|---|
| `SandboxCharacter_CMC_ABP` (the anim Blueprint) | 4.73 | 7.1% | `BlueprintThreadSafeUpdateAnimation` 2.40, `BlueprintUpdateAnimation` 1.06, post-evaluate 0.52, exposed inputs 0.75; `ABP_WeaponLayers` 0.21 more |
| `BP_WeaponComponent` | 4.29 | 6.5% | Tick 4.20, `Server_Fire` 0.09 |
| the NPC controllers (`BP_ForestWandererAI_Zombie`, `_Wendigo`, entered from their BT step tasks) | 2.40 | 3.6% | zombie 1.81, wendigo 0.59; not split further (natives called that deep carry no scope) |
| `BP_HealthComponent` | 2.11 | 3.2% | 1.54 the respawn's native call, Tick 0.57 |
| the item Blueprints (`BP_Knife`, `_Stick`, `_Axe`, `_Pistol`, `_Matches`, `_Shotgun`) | 0.92 | 1.4% | their Ticks |
| `BP_SurvivalComponent`, `BP_FootstepComponent` | 0.58 | 0.9% | their Ticks |
| the record component (`InventoryRecord`, C++) | 0.03 | 0.0% | no script: 73 400 ticks |

- **The guess was wrong in rank.** `serversupportsysdesign.md` 4 expected the weapon
  component's Tick to sink the server; it is 6.3%. The pose is 58.7% against A4's 24%:
  A4's trace had `ABP_Unarmed_C` under the mesh (0.73 s of 20 s), this one the
  motion-matching graph (18.0 s of 80 s), whose chooser and trajectory a server runs for
  every body.
- **No port reaches the 25 ms line alone.** Every component, item and controller graph
  run for nothing would give back 9.3 s, 4.3 ms of the 30.7 ms frame.
- **The first port is the weapon component's Tick** (the largest script cost off the anim
  graph), and in it first the body-parts loops, which a server runs each frame for a head
  only the owner's camera sees. `Server_Fire` alone is 0.1%.
- **The trace costs something itself:** `-trace=cpu` names every scope, 82.6 M on the game
  thread in the 80 s, heaviest where a graph calls many natives, so the weapon component's
  row is its ceiling. The numbers are one run's.
- **How:** `UnrealInsights -OpenTraceFile=<trace> -NoUI -AutoQuit
  -ExecOnAnalysisCompleteCmd="TimingInsights.ExportTimingEvents events.csv -threads=GameThread
  -startTime=80 -endTime=160 -columns=ThreadId,TimerId,StartTime,EndTime,Depth"` (2 min, a
  2.6 GB csv), `TimingInsights.ExportTimers timers.csv` for the names in a second invocation,
  then summed per timer down the depth column (a timer already on the stack not counted
  again). The trace: `Saved/traces/net_load_32bots_w0_2026-10-09.utrace`.


**The shot's server half in C++ (W1, 2026-10-09): before and after.** The same run
(`--bots 32 --trace`), and one export for both traces: `TimingInsights.ExportTimerStatistics
stats.csv -threads=GameThread` in place of W0's events export (one row a timer, a 1 MB
csv, a minute), over the whole trace, so W0's own trace reads 0.127 s for 1 205 shots
where its 80 s window read 0.09 s for 861.

| | before (W0's trace) | after |
|---|---|---|
| `Server_Fire`, inclusive | 0.127 s, 1 205 calls, **105 µs** each | 0.135 s, 1 178 calls, **114 µs** each |
| of it | all Blueprint VM; `ShotTrace` 0.059 s (9 624 pellets, 6 µs) | its own C++ 10 µs; the graph under `ShotFired` 25 µs (the sound told, the muzzle, the draw, the batch, the noise); `FirePellets` 79 µs (the traces about 49, eight `PelletFlew` events 16) |
| the weapon component's Tick, a call | 37 µs (`ExecuteUbergraph_BP_WeaponComponent`) | 38 µs |
| the mesh's tick, a call | 176 µs | 188 µs |
| world tick, mean | 29.3 ms, 26.9 Hz, 64 characters | 38.2 ms, 24.3 Hz, 76 characters (two more runs: 36.4 ms at 75, 35.6 ms at 67) |

- **The port does not move the tick, as W0 said it would not.** A shot costs what it
  did: the validation and the spend went from the VM to 10 µs of C++, and the pellets'
  loop from the VM to a call, but each pellet comes back to the graph as an event for
  its tracer and its blood or chips, which costs what the loop's own nodes did.
- **The world tick is not comparable between the two days.** What nobody touched costs
  the same a call (the rows above), and the later runs carry more bodies a frame (99
  mesh ticks against 89; 59 weapon component ticks against 49): more wanderers and bots
  alive, and the pose is 59% of the frame. The three processes peaked at 15.3-15.6 GB
  of this machine's 16.
- **Marking the record by the item cost 55 µs a shot** (`MarkCarriedItemDirty` searches
  every carrier's inventory: 154 µs a shot in the run before it was changed). C++ that
  knows its carrier marks by the carrier (`MarkInventoryDirty`).
- The trace: `Saved/traces/net_load_32bots_w1_after_2026-10-09.utrace`.


- A1 measured at scale: docs/history/multiplayer.md#a1

## Every Server event asks the guard first (A5, done)

A C++ RPC has the engine's `_Validate` hook; a Blueprint one has nothing, so a Server
event runs whatever arrives, as often as it arrives, unless its graph asks. Every Server
event on the weapon component (21: the shot and the reload, the swings, the holds, the
throw, the take, the look, the fire and heat four, the wear, the eating and the seven
asks) asks first, one way:

- **The fragment is `net/guard.py`:** `allowed, refused = author_guard(g, NAME,
  [then(event)])` is the first thing after `net.server_event(...)`, and the event's body
  hangs off `allowed`. (`author_allow` gives the answer and the exec apart, for an
  event that must do something between the ask and its Branch.)
- **`Server_Fire` asks in C++** (W1): `Allow` by its own name (the base's
  `FireEventName`, the row's key), the count, then `AimAllowed`. **`Server_Reload` asks
  in C++ too** (W2, `ReloadEventName`): `AsksServed` is counted between the ask and the
  answer, so a refused reload is answered like any other the server did not do. Each is a
  row of `RATES` like the rest, and `verify/guard.py` counts them among the component's
  Server events.
- **A new Server event** gets a row in `RATES` and the fragment; `combat/verify/guard.py`
  fails on an event with no row, a row with no event, a builder that makes a Server
  event and does not name the fragment, and an event whose first node is not its own
  `Allow` and Branch. A Server event on another Blueprint fails there too: the guard is
  the player's, so its component would have to be reached first.
- A5 the RPC guard: docs/history/multiplayer.md#a5

## The slide, and traversal (G5, 2026-10-08)


- G5 the slide, and traversal: docs/history/multiplayer.md#g5

## What the server spends on bodies it never draws (A4, 2026-10-08)

- **The anim graphs have one IsDedicatedServer branch** (`combat/server_anim.py`,
  `server_anim_consts.py`; `combat/verify/server_anim.py`, which the NPC verifier runs
  for the wanderers too): a Blend Poses by bool on `ServerPose`, which the anim
  Blueprint's own BlueprintInitializeAnimation writes once. A server skips the player's
  foot IK (the Control Rig, which traces the ground under both feet) and FullBodySlot,
  and never gives the support hand's IK a weight (`weapon_component/support_hand.py`).
  It keeps the aim's blend (DefaultSlot: the arms' hit bodies and the muzzle) and the
  flinch's (HitSlot), on the player and on the wanderers: each moves a hit box a shooter
  is aiming at. (A blend's base and its slot take one pose: a cached pose, updated once
  a frame on either arm, `uebp/pose_share.py`. Linked plainly it was updated once per
  link, and played everything under it that many times too fast.) **A new node for the eye goes on the client arm**; the verifier
  fails a server arm that holds a slot, a blend or a node class the table does not list.
- A4 what the server spends on bodies it never draws: docs/history/multiplayer.md#a4
