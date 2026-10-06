# net — the multiplayer conventions

Read this before any multiplayer task. The strategy is `serversupportsysdesign.md` (4.1
authority, 4.2 where state lives, 4.8 the two modes); the authoring helpers are
`Scripts/uebp/CLAUDE.md`; the harness is the root `CLAUDE.md`'s `--net`. This file is the
rules a graph follows, how to prove one, and what the spike (task M4, 2026-10-06) found
broken. Its code is what the builders share to keep one graph right in both modes
(`__init__.py` maps it): `pause.py`, the session (`session_consts.py`,
`game_instance.py`), where state lives (`state*.py`), who is nearby (`players*.py`) and
whose keys a graph reads (`input_checks.py`).

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
  - **Still player 0:** a kill's credit (`state_graph.first_player_state`, M14).

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
  | the pose (weights, support hand, accuracy, carry, ready pose, steady) | every copy |
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
- **Not done here:** the non-local copies of a character still run from their own
  unreplicated state (walk speed, stance, what is held): M12, M13, M18, M19.

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
- **Kills are credited to player 0's PlayerState** (`state_graph.first_player_state`): no
  blow says yet who struck it. Right in single player; M14's instigator replaces it.
- **The wanderer's number (`NpcId`) is taken on the server only,** so a client's debug
  overlay draws 0 beside each health bar until the health component replicates (M14).
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
- Still to come, and not the pause's: a dead client's restart key reopens the level locally
  (death by mode, the table's third row).

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
  them, do not run on a client. What a client's death does is still the death task's.
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
| health | Health written on the server (100 to 40) stayed 100 on both clients: nothing replicates it. Damage is the weapon writing `Health` directly, not `ApplyDamage` (which does nothing in this game) | measured | M14 |
| firing and ammo | A shot fired on client 1 spent a round there (5 to 4); the server and client 2 still had 5 and saw no shot. The trace and the damage ran on the client alone | measured | M19, M21 |
| the loadout and held items | Every process spawns its own copy of each character's six items (not replicated, each with local authority), so the three worlds start alike and part at the first change | measured | M18 |
| items on the ground | The 24 mushrooms and the test garments are level actors whose classes do not replicate (`BP_Mushroom`, `BP_Hat`: read off the class defaults): each process has its own, and a pick-up on a client removes it nowhere else | measured (the counts, the defaults), read (the pick-up) | M23, M31 |
| day and night | Each process rolls its own start time: in one run it was day on the server and client 2 and night on client 1 | measured | M30 |
| walk speed, sprint, stance | The weapon component wrote `MaxWalkSpeed` every tick in every process from its own unreplicated state. **Since M10 only the local player's copy writes it** (the sprint and the aim are behind the local gate), so the server's copy keeps the speed the character was built with. Sprint, crouch and prone are keys read on the client, so the server will correct a sprinting client | the write measured; the rubber-band read | M12 |
| input | **Fixed (M10): "Input", above.** The weapon component polled keys in its Tick on every copy of every character, the server's included, and on `GetPlayerController(0)`, so a client's press drove every character it could see | read; the fix measured (`probe_net_local_input.py`, headless and `--windowed`) | M10 done |
| stamina, hunger, thirst, temperature | Per-process component and GAS state: no builder replicates a variable or a component yet (`net.replicate` has no caller outside `dev/check_net_authoring.py`) | read | M12, M26 |
| animation of the other player | Only what CharacterMovement replicates reaches a simulated proxy (velocity, falling): stance, aim, the held item's pose and montages do not | read | M13, M21 |
| sounds and effects | Played where the graph that caused them ran, so a shot, a blow or a footstep is heard by its own client only | read | M21 |
| player starts | The level has one PlayerStart: the two spawned 70 cm apart, the engine nudging the second | measured | M16 |
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
- **M14:** "damage ... always carries an instigator" starts from no damage event at all:
  the weapon writes `Health` on the component. The engine's `ApplyDamage` reaches nothing.
- **M16:** "a random player start" needs player starts: the level generator places one.
- **M18:** the starting loadout is spawned by every process today; the server alone must
  spawn it, as replicated actors, or the client's local copies must go.
- **Any probe:** "client 1" is not the server's player 0, and no actor name is shared
  between processes (above).

## Memory (measured, the editor binary; `serversupportsysdesign.md` 5 has the table)

| process | 200 m map | 1 km map |
|---|---|---|
| dedicated server | 1.9 GB | 2.5 GB |
| client, `-nullrhi` | 1.9 GB | 2.2 GB |
| client, `--windowed` | 5.8 GB | not measured |
