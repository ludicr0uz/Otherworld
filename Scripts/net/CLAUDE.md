# net — the multiplayer conventions

Read this before any multiplayer task. The strategy is `serversupportsysdesign.md` (4.1
authority, 4.2 where state lives, 4.8 the two modes); the authoring helpers are
`Scripts/uebp/CLAUDE.md`; the harness is the root `CLAUDE.md`'s `--net`. This file is the
rules a graph follows, how to prove one, and what the spike (task M4, 2026-10-06) found
broken. It holds no code yet: M9's shared helpers ("nearest living player") land here.

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
  the GameState, a PlayerState, or a replicated actor or component.
- **Player 0 means nothing on a server.** There, index 0 is whoever joined first (client 2
  in one spike run, client 1 in the next). A component asks its owner, a widget its owning
  player, an NPC chooses among the players.

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
| HUD | `ReceiveDrawHUD` casts the GameMode, which a client does not have: `Accessed None ... AsBP_Third_Person_Game_Mode` on every rendered client (16 lines a client in a 48 s run). The only runtime error of the spike, and invisible with `-nullrhi` | measured (`--windowed`) | M7 |
| GameMode readers | 12 builder modules call `FN_GET_GAME_MODE` and 11 cast to it (combat 4, npc 4, graphics_menu, survival, the menu build); each reads None on a client. Only the HUD's logged, because only it ran | read | M7 |
| player 0 | 26 builder modules call `FN_GET_PLAYER_PAWN` (graphics_menu 15, npc 7, combat 2, survival 1, world 1). On the server that is the first joiner, so every wanderer hunts one player, and the night cold, campfire warmth and ammo pick-up serve only them | read; the join order measured | M8, M9, M27 |
| health | Health written on the server (100 to 40) stayed 100 on both clients: nothing replicates it. Damage is the weapon writing `Health` directly, not `ApplyDamage` (which does nothing in this game) | measured | M14 |
| firing and ammo | A shot fired on client 1 spent a round there (5 to 4); the server and client 2 still had 5 and saw no shot. The trace and the damage ran on the client alone | measured | M19, M21 |
| the loadout and held items | Every process spawns its own copy of each character's six items (not replicated, each with local authority), so the three worlds start alike and part at the first change | measured | M18 |
| items on the ground | The 24 mushrooms and the test garments are level actors whose classes do not replicate (`BP_Mushroom`, `BP_Hat`: read off the class defaults): each process has its own, and a pick-up on a client removes it nowhere else | measured (the counts, the defaults), read (the pick-up) | M23, M31 |
| day and night | Each process rolls its own start time: in one run it was day on the server and client 2 and night on client 1 | measured | M30 |
| walk speed, sprint, stance | The weapon component writes `MaxWalkSpeed` every tick in every process from its own unreplicated state (a client's write of 1200 was 400 again at once, and it moved at 400). Sprint, crouch and prone are keys read on the client, so the server will keep the jog speed and correct the client | the write measured; the rubber-band read | M10, M12 |
| input | The weapon component polls keys in its Tick on every copy of every character, the server's included; nothing asks whether the pawn is locally controlled | read | M10 |
| stamina, hunger, thirst, temperature | Per-process component and GAS state: no builder replicates a variable or a component yet (`net.replicate` has no caller outside `dev/check_net_authoring.py`) | read | M12, M26 |
| animation of the other player | Only what CharacterMovement replicates reaches a simulated proxy (velocity, falling): stance, aim, the held item's pose and montages do not | read | M13, M21 |
| sounds and effects | Played where the graph that caused them ran, so a shot, a blow or a footstep is heard by its own client only | read | M21 |
| player starts | The level has one PlayerStart: the two spawned 70 cm apart, the engine nudging the second | measured | M16 |
| pause and the title menu | The harness starts every process with `-nomenu`; without it a client opens on the title menu, which pauses, and a client cannot pause the server. `FN_SET_PAUSED` is called from the menu build, `menu_main`, `menu_screens` and `death` | read | M5, M6 |
| the profile and the tuning slots | A client loads the local `OtherworldProfile` and the tuning tabs' save slots as in single player (the harness sets the slots aside for a run: `probes/kept_slots.py`) | read | M32, M35 |

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
