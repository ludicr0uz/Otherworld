# Otherworld — Server Support System Design

How Otherworld goes from a single-player game to a hosted PvP server that players join.
Written 2026-10-03 from a read of the project's docs, config and builder packages. Nothing
described here is built yet. `systemDesign.md` describes the game as it is today.

**How to read the claims in this file:**

- *Verified* means checked against this repository or the UE 5.8 install on 2026-10-03.
- *Estimate* means a figure from general knowledge of the engine or of GCP pricing, not
  measured here. Replace each estimate with a measurement when the task that produces one is
  done (the spike in Phase 0 gives the memory figures, the load test in Phase 9 the server's).

---

## 1. The target

| decision | choice |
|---|---|
| mode | PvP |
| topology | dedicated server, hosted; players join it |
| players per server | 32–64 |
| teams | players create teams or play solo |
| character | persists between sessions |
| identity | Epic or Steam accounts |
| hosting | GCP, once the game is ready; development on a local server first |

**Defaults assumed where no decision has been made** (each changes only the phase named):

| question | assumed | phase |
|---|---|---|
| what death costs | the character survives; its gear drops on a lootable corpse | 4 |
| where a character lives | one server, one save file per account | 8 |
| where a character logs back in | where it logged out | 8 |
| map size | the 1 km map until the game works, then larger | 9 |
| does a team survive a logout | not decided | 7 |

---

## 2. Where the game stands

The game has no networking at all: no replicated variable, no RPC, no authority check
(*verified*: a grep of the builder packages finds none). It is 449 builder modules, about
67k lines, that author Blueprints from Python. The assumptions below are counted over those
builders, verifiers excluded (*verified*).

| single-player assumption | uses | where | what it becomes |
|---|---|---|---|
| raw key polling on Tick drives gameplay | 50 in 20 files | `combat/weapon_component`, `graphics_menu` | polled only on the locally controlled pawn; each action is a request to the server |
| world state on the GameMode, which exists only on the server | 46 in 13 files | kill count, `PlayerDead`, `DebugMode`, the noise record, the gun-drop streams | GameState (shared) and PlayerState (per player) |
| `GetPlayerPawn(0)` is "the player" | 53 in 27 files | 7 NPC modules, 15 HUD modules, the ammo pickup, night cold | AI picks among all players; the HUD uses its owning pawn; world actors use overlaps |
| the game pauses | 7 | title menu, death, save and exit | removed: a shared world can't pause |
| random rolls run wherever the graph runs | 110 in 36 files | loot, gun drops, spread, patrol, the day's start hour | rolled on the server only |
| the profile is a local save file | `graphics_menu/profile_*.py`, `save_exit.py` | written by the HUD on the player's machine | written by the server, keyed to an account |
| gameplay logic lives in the HUD | loot take, inventory drags, save and exit, the cheat | `graphics_menu` | moved out: a dedicated server has no HUD |

**Designs that break at 32–64 players:**

- **The noise record is one record.** One noise per 0.6 s for the whole world: with dozens
  of players firing, the wanderers hear only the loudest shot on the server.
- **Ten wanderers, respawned 75–100 m from the player start** (`NPC_COUNT = 10`,
  `forest_generator/npc_placement.py`). Both numbers are built round one player.
- **Each wanderer checks one player per heartbeat.** Checking 64 needs a distance pre-filter.
- **Per-actor distance ticks.** `BP_AmmoPickup` measures its distance to the player every
  frame; with many players and items that becomes overlap events.
- **The 1 km map.** 64 players is one per 125 m square, inside the sniper's 200 m reach and
  its shot's 150 m noise. Nobody would be out of a fight.
- **The level generator at a larger size.** The 1 km map has 1.03 million grass clumps and
  1,700 trees (*verified*, its verification report). A 4 km map is 16 times that and needs
  World Partition streaming. The navmesh bounds are capped at exactly 1 km
  (`NAV_MAX_HALF_XY_CM = 50000`) and the mesh is built at boot, about 2 minutes at 1 km.
- **World changes that never go away.** Chopped wood, lodged blades, campfires and dropped
  gear pile up on a long-running server.

---

## 3. What UE 5.8 already provides

The engine supplies the networking plumbing. It cannot supply the conversion of this game's
own rules to server authority, which is most of the work. Plugin presence is *verified*
against the install at `/Users/Shared/Epic Games/UE_5.8`; what each does is from knowledge of
the engine, not tested here.

**Configure, don't build:**

| need | what the engine gives |
|---|---|
| transport, connections, the dedicated server | built in |
| replicated variables, RPCs, ownership, relevancy | built in |
| framework classes | GameMode, GameState, PlayerState, PlayerController already have the right roles |
| basic movement prediction | CharacterMovement predicts and corrects walk, jump and crouch |
| scaling to 64 | Replication Graph (`Plugins/Runtime`), Iris (`Plugins/Experimental`), cull distance, dormancy |
| login, server browser, voice | `OnlineSubsystemEOS`, `OnlineSubsystemSteam`, `SteamSockets`, `EOSVoiceChat` |
| predicted abilities, replicated effects and montages | Gameplay Ability System, already enabled in this project |
| large-world streaming | World Partition |
| AI on the server | behavior trees, navmesh and AI controllers already run server-only |
| lag simulation, profiling | network emulation settings, Network Insights |
| packet encryption | the DTLS and AES-GCM handler plugins |
| save serialisation | `USaveGame` to bytes; `SQLiteCore` for a local database |

**The engine gives a hook, the logic is ours:**

- **Sprint and prone:** CharacterMovement's extension point for predicted states, in C++.
  Mover is installed but experimental; use the stock component with a small subclass.
- **GAS for combat:** fire, reload, melee, throw and consume as abilities get prediction,
  replicated montages and cosmetic cues without hand-written RPCs. Only consume is an
  ability today (`GA_ConsumeItem`). This is the biggest lever the project already has.
- **Teams:** the engine's team interface covers AI attitudes only.
- **Persistence:** serialisation exists; when to save, where, keyed to what, and migrations
  are ours.
- **Load-test bots:** Gauntlet (installed, experimental) orchestrates a server and many
  clients; what the bots do is ours.
- **Anti-cheat:** Easy Anti-Cheat comes through the EOS SDK and needs integration.

**Not in the engine:**

- lag compensation (rewinding hit bodies to what the shooter saw): no plugin in the install;
- this game's rules on the server: inventory, slots, pickups, loot, clothing, campfires,
  chopping, heat, bleeding;
- the wanderers for many players: target choice, population budget, the noise list;
- death, respawn, looting a player's corpse, the combat-log rule;
- admin commands and server config in place of the tuning tabs;
- the build pipeline, deployment, restarts and backups.

**Reference:** Lyra, Epic's sample game, is the reference for this stack (dedicated server,
GAS shooting, teams, EOS login through its CommonUser plugin, Replication Graph). It is not
installed and comes from Fab, so the user acquires it (CLAUDE.md, "Fab assets"). Read it and
borrow its team and login code; don't build on it, since Python-authored Blueprints don't
fit its structure.

---

## 4. Strategy

### 4.1 Authority

The server owns every piece of game state. A client sends requests and draws what it is
told. Because the game is PvP, nothing a client reports is trusted: the server traces the
shots, validates throws and melee, and owns inventory and ammunition.

Every gameplay graph takes this shape:

```
owning client: read input  --Server RPC-->  server: validate, change state
                                               |-- state replicates to the clients
                                               '-- Multicast: sounds, blood, impacts, montages
```

### 4.2 Where state lives

| state | today | becomes |
|---|---|---|
| kill count, per player | GameMode | PlayerState (done, M7: `BP_OtherworldPlayerState`) |
| `PlayerDead` | GameMode | PlayerState (done, M7) |
| team | none | PlayerState (team id), GameState (roster) |
| debug flags, the difficulty, the day's clock | GameMode, `BP_DayNightCycle` | GameState / a replicated actor (debug mode and the difficulty done, M7: `BP_OtherworldGameState`; the clock is M30) |
| the noise record | GameMode | stays on the server (only AI reads it), as a list |
| gun-drop random streams, spawn counter | GameMode | stay on the GameMode: server only is right |
| health, inventory, slots, ammo, worn garments | components, unreplicated | the same components, server-owned and replicated |
| the character's save | a local `BP_Profile` | a server-side file per account |

### 4.3 What needs C++

The project has one C++ module, `Source/Otherworld`, empty so far (task M1; `Source/CLAUDE.md`
has the compile command). A dedicated server target requires a real `Source/` folder; it was
made from the packaging step's generated files in `Intermediate/Source`
(`Otherworld.Build.cs`, the four `.Target.cs`).

| piece | why C++ |
|---|---|
| the RPC flag helper (editor only) | `K2Node_Event::FunctionFlags` is a bare `UPROPERTY()`, so Python cannot mark a custom event Server, Client, Multicast or Reliable (*verified*, `K2Node_Event.h:69`). Replicated variables are fine: `set_blueprint_variable_replication` exists |
| predicted movement | sprint, prone and the aim-walk written from Blueprint rubber-band under lag and invite speed cheats |
| lag compensation | not practical in Blueprint |
| whatever the load test finds too slow | 64 copies of the weapon component's Tick graph on the Blueprint VM is the likeliest thing to sink the server's tick rate |

Everything else stays in the Python-builder workflow, once the RPC helper is exposed in
`uebp`.

### 4.4 Engine builds

- **The installed engine runs a dedicated server from the editor binary**
  (`UnrealEditor-Cmd <uproject> <map> -server`). All porting and local testing uses it.
- **A packaged dedicated server needs UE 5.8 built from source.** The install is the
  launcher's (*verified*: `Engine/Build/InstalledBuild.txt` exists), and an installed build
  cannot compile a server target. The source build lives on the GCP build machine, not on
  the development Mac (section 6).
- **The hosted server is Linux.** The install has no Linux platform support (*verified*),
  and a Mac is not a supported host for cross-compiling one, so the Linux server is built on
  a Linux machine.
- **Windows clients** need a Windows build machine. The owner can join from the Mac; other
  players on Windows wait for Phase 10.

### 4.5 Content on the build machine

The repository is code only: `Content/` (2.0 GB, *verified*) exists only on the development
Mac, is written by the builders, and its Fab assets need the user's Epic sign-in. The build
machine therefore gets a copy of `Content/` (a storage bucket or rsync), scripted, and never
regenerates it.

### 4.6 Identity and persistence

- **Epic Online Services as the service layer, with Steam as a login method.** One stable
  player id either way, a server browser through its sessions, and Easy Anti-Cheat. Confirm
  the current terms and platform coverage before committing.
- **The server verifies the login ticket** before loading a character.
- **The account id is the player's key from the first server milestone,** with a stub login
  until Phase 8, so nothing is keyed twice.
- **The save moves to the server.** Today the HUD writes `BP_Profile` on the player's
  machine after the 15 s save-and-exit countdown. A client-written save is a gear editor.
- **Saved on** disconnect, a timer and server shutdown.
- **Combat logging:** the existing rule is the right one (15 s, the character can't move, a
  hit calls it off). The body stays in the world for those seconds when a player just drops
  the connection.
- **New fields:** worn garments, location, a save version. The profile's verifier asserts it
  has no other field, and changes with it.
- **Duplication:** dropping an item and saving a character must be consistent, or a timed
  disconnect duplicates gear.
- **The replicated inventory is designed serialisable** in Phase 5, so the save in Phase 8
  is not a second rewrite.

### 4.7 Dev tools on a public server

The tuning tabs, debug mode and the all-guns cheat become admin-only or are stripped from
the client. The tuning CSVs become server config.

---

## 5. Developing on a local server

Everything in Phases 0 and 2–8 is developed and proved on localhost, with one server and
two clients. That is enough for replication, PvP damage, teams and saves.

**The development machine** (*verified*): M2 Pro, 10 cores, 16 GB, 82 GB of disk free. Swap
was at 7.5 of 8 GB with two editor processes running, so it is at its limit before any
server exists.

**What the processes use** (*measured* 2026-10-06 by the spike, task M4: `uepy.py --net
--clients 2`, every process the installed editor binary, the editor closed. The figure is
the footprint macOS charges the process, Activity Monitor's "Memory": resident, compressed
and swapped together. Each run prints these lines again, so re-read them rather than trust
this table once the game has grown):

| process | map | memory |
|---|---|---|
| dedicated server (`-server`) | 200 m | 1.9 GB |
| dedicated server | 1 km | 2.5 GB |
| client, `-nullrhi` | 200 m | 1.9 GB |
| client, `-nullrhi` | 1 km | 2.2 GB |
| client, rendered (`--windowed`, 1280x720) | 200 m | 5.8 GB |

Steady from the join on: 90 s of play added nothing to any of them.

**What fits in 16 GB** (sums of the rows above; *measured* where marked, the others added up
from them or still an *estimate*):

| setup | memory | on 16 GB |
|---|---|---|
| server + 2 `-nullrhi` clients, 200 m map | 5.7 GB (*measured*) | fine: the default check |
| server + 2 `-nullrhi` clients, 1 km map | 6.9 GB (*measured*) | fine |
| server + 2 rendered clients, 200 m map | 13.5 GB (*measured*) | runs, and swaps: the machine compressed all three (their resident size fell to 0.1-0.3 GB by the end of a 48 s run) |
| server + 1 rendered and 1 `-nullrhi` client, 200 m map | 9.6 GB (added up) | workable: use it when one view is enough |
| the editor as well as any of these | 6–10 GB more (*estimate*) | no: close it first |
| 8 `-nullrhi` clients and a server, 200 m map | about 17 GB (added up) | no |

**Rules for a multiplayer test on this machine:**

1. Close the editor first. The probe harness already closes editors before a task.
2. Use `Lvl_Forest_200m` for everything but scale work.
3. Run a client `-nullrhi` when the check doesn't need rendering: it is a third of a
   rendered one (1.9 GB against 5.8), and `uepy.py --net` does so unless given `--windowed`.
4. A rendered run has two clients at most, and nothing else open. A packaged Mac client
   (`Binaries/Mac/Otherworld.app`) should be lighter than a rendered editor binary; that is
   an *estimate*, not measured, and the harness does not start one.
5. Don't run dev-team sessions at the same time.

**What does not happen on this machine:**

- the source engine build (well over 100 GB of disk, more than the 82 GB free);
- the Linux server package;
- the 64-bot load test (rented GCP machines for a few hours).

32 GB would remove the juggling. It is not required.

---

## 6. Hosting on GCP

There is no single industry standard. AWS is the most common choice, GCP a mainstream one,
and persistent-world games often rent bare metal because cloud bandwidth charges add up.
GCP is fine for this.

| machine | what | when it runs |
|---|---|---|
| build VM | Linux, about 32 cores, about 300 GB of disk: UE 5.8 source, the project, a copy of `Content/` | only during a build; stopped otherwise |
| game VM | Linux, compute-optimised (fast single core matters more than core count), UDP 7777 open, the server as a service with auto-restart | always |
| storage bucket | the `Content/` copy, save-file backups | always |

One 64-player server is one process on one VM. No Kubernetes and no fleet manager.

**As built** (2026-10-03, *verified*): the build VM exists as `otherworld-build` in project
`play-history-service`, zone `us-central1-a`: 30 vCPUs and 64 GB (the project's quota caps
all regions at 32 vCPUs, 2 in use), spot, 300 GB SSD, Ubuntu 22.04, no service account.
UE `5.8.3-release` is cloned to `/opt/otherworld/engine` with its version stamped to match
the installed engine. The scripts that reproduce all of this are in `Scripts/server/gcp/`
(see its `CLAUDE.md`). The game VM and the bucket do not exist yet.

**Costs** (*estimates*: GCP list prices from memory, roughly $1.50–2.50 an hour for a
32-core VM, not checked on the day; build times not measured for this project):

| item | when | time on 32 cores | cost |
|---|---|---|---|
| UE 5.8 from source | once, and per engine upgrade | 1–2 h | $2–5 |
| first full server build, cook and package | once | 20–40 min | $1–2 |
| routine server rebuild | each release to the server | 5–15 min | $0.15–0.60 |
| build VM's disk | standing | | $30–50 a month |
| game VM | standing | | $100–200 a month, plus bandwidth |

- **Stop the build VM after every build.** Left on all month it is over $1,000; stopped, it
  bills only its disk.
- **Use a spot VM for builds:** about 60–70% cheaper, and an interrupted build is rerun.
- **Builds on GCP are rare.** Day-to-day C++ compiles and tests happen on the Mac. GCP
  builds only when a new version goes to the hosted server.

---

## 7. Task list

The owner can join a server on GCP at the end of Phase 1. The game is playable PvP at the
end of Phase 5 and fully supported at the end of Phase 10. Tasks 15–16, 23 and 39 are C++;
the rest of Phases 2–7 fits the Python-builder workflow once task 2 exists.

**Phase 0 — Foundations** (the Mac, the installed engine)

1. Add a real `Source/` C++ module from the generated targets in `Intermediate/Source`.
   The editor still builds and every verifier still passes.
2. Add the C++ editor helper that sets Server / Client / Multicast / Reliable on a custom
   event, and expose it in `uebp`.
3. Extend `uepy.py` and the probe harness to launch one `-server` process and N clients, and
   to run checks on each side.
4. Spike: a server and 2 clients on `Lvl_Forest_200m`, each player seeing the other walk.
   Record each process's memory in section 5.

**Phase 1 — First join on GCP** (milestone: connect from the Mac and walk around)

5. Create the Linux build VM and build UE 5.8 from source on it (needs the owner's
   Epic-linked GitHub account).
6. Script the sync of `Content/` to the build VM.
7. Cook and package the Linux server; script the build.
8. Create the game VM, open UDP 7777, run the server as a service with auto-restart and
   logs.
9. Add a "join server" row that takes an address. The title menu stops pausing the world.

**Phase 2 — The framework for many players**

10. Move the kill count, the debug flags and the shared state off the GameMode (section
    4.2).
11. Replace every `GetPlayerPawn(0)`: the HUD uses its owning pawn, world actors use an
    overlap or the nearest player.
12. Remove every `SetGamePaused` path.
13. Gate all input polling to the locally controlled pawn.
14. Move gameplay logic out of the HUD graphs (the loot take, inventory drags, save and
    exit, the cheat) into server requests.

**Phase 3 — Movement** (C++)

15. Subclass CharacterMovement with predicted sprint, prone and aim-walk. Stamina moves to
    the server.
16. Replicate stance, aim pitch and the held item's pose so other players animate
    correctly.

**Phase 4 — Health, damage, death**

17. `BP_HealthComponent` is server-owned and replicated, with an instigator on every damage
    event.
18. Player-versus-player damage and kill credit.
19. Death: a ragdoll on every client, gear onto a lootable corpse, respawn at a chosen
    point.
20. Server-only random rolls for loot, gun drops and on-hit effects.

**Phase 5 — Weapons and inventory** (the largest phase; `weapon_component` alone is about
55 modules)

21. Replicate `BP_WeaponItem`, the inventory, slots, ammo and worn garments, server-owned
    and serialisable.
22. Fire, reload, melee, throw and block as server requests, preferably GAS abilities.
23. Server-side shot traces with lag compensation (C++).
24. Multicast cosmetics: shot sounds, impacts, blood, tracers, montages.
25. Pick-up, drop, loot, wear, chop, light, heat and cauterise as server actions.
26. Survival: a replicated ability system; hunger, thirst, cold and bleeding applied on the
    server.

**Phase 6 — Wanderers and world**

27. Target choice among all players for the senses, the stalk, the ward and the melee.
28. A population budget across the map: spawn near players, despawn far from them.
29. Noise as a list or a spatial query.
30. A server-owned day and night clock, campfires and dropped items; cleanup rules for
    what piles up.

**Phase 7 — Teams**

31. A team id on PlayerState, a replicated roster, requests to create, invite, join and
    leave.
32. The team UI, teammate markers, the friendly-fire rule.

**Phase 8 — Accounts and persistence**

33. EOS login accepting Epic and Steam accounts; the server verifies the ticket.
34. The server-side character save keyed to the account id, with worn garments, location
    and a save version.
35. Save on disconnect, on a timer and on shutdown. The body stays in the world through
    the logout countdown.
36. Back the save files up to the storage bucket.

**Phase 9 — Scale to 32–64**

37. Bot clients and a 64-client load test on rented machines; measure the server's tick
    rate.
38. Replication tuning: cull distances, dormancy, Replication Graph or Iris.
39. Move what the load test shows is too slow from Blueprint to C++.
40. Decide the map's size; World Partition streaming and a navmesh strategy for it.

**Phase 10 — Fully supported**

41. A server browser through EOS sessions.
42. Easy Anti-Cheat; strip or admin-gate the tuning tabs and the cheats.
43. Admin commands, and server config files in place of the tuning CSVs.
44. Monitoring, crash reporting, an update procedure that warns the players.
45. A Windows client build pipeline.

---

## 8. Open decisions

| decision | why it matters | needed by |
|---|---|---|
| what death costs (gear only, or the whole character) | today death deletes the profile | Phase 4 |
| does a team survive a logout | it becomes a saved record keyed to account ids | Phase 7 |
| one server or several sharing characters | sharing needs a database, and lets players hop servers out of a fight | Phase 8 |
| map size | spawn budgets, cull distances and streaming all depend on it | Phase 9, and before the tuning in Phase 6 is final |
| EOS terms and platform coverage | identity, the browser and anti-cheat all rest on it | Phase 8 |
