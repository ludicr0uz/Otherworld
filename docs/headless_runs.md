# Headless runs and probes

Moved verbatim out of the root `CLAUDE.md`: its "Headless runs and probes" gotchas, and
the details of `uepy.py`'s `--title` and `--net` runs from "Run a script — fast".

<a id="probes"></a>
## Headless runs and probes


**Checking behaviour in the running game: write a probe.** Don't hand-roll a `-game` run plus
inbox polling. One command boots the level, runs the probe once the player exists, prints each
check and ends the run as soon as the probe does (about 20 s):

```bash
python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_consume_heal.py
```

- **Shape:** a probe defines `probe(p)`, a generator. `yield 0.3` waits 0.3 s of game time,
  `yield lambda: cond()` waits for a condition, and `p.check(label, ok, detail)` records a
  result. `p` has the lookups (`pawn`, `component`, `game_mode`, `hud`, `actor_of`,
  `send_event`, `get`, `set`). `Scripts/probes/probe_consume_heal.py` is the model.
- **Writing a Blueprint variable on a live instance:** list it in the probe's
  `WRITABLE = [(bp_path, var)]`. `probes/boot.py` makes it Instance Editable and recompiles, in
  memory for that run only, before the level loads. Nothing on disk changes and no builder
  re-run is needed.
- **A network probe** (`uepy.py --net`) is the same file run in every process, the server and
  each client. `Scripts/probes/probe_net_join.py` is the model; `probes/net.py` has the rules.
  - **Where it runs:** `RUNS_ON = ("server", "client")`, or `"client 1"` for that client alone.
    Absent, it runs everywhere, single player too. A file may define `probe_server(p)` and
    `probe_client(p)` instead of one `probe(p)`.
  - **Where it is:** `p.where` (`"server"`, `"client 2"`, `"standalone"`), `p.is_server`,
    `p.client` (1..N), `p.clients`. `p.players()` is every player's controller: all of them on
    the server, its own on a client.
  - **When it starts:** on the server once every client's player has joined, on a client once
    it has its pawn.
  - **From one process to another:** `p.post("shot")` on one side,
    `yield lambda: p.posted("server", "shot")` on the other. The processes share nothing else.
  - **A dedicated server has no Slate,** so nothing registered with
    `register_slate_post_tick_callback` ever runs there. Use `unreal.register_ticker_callback`
    (the callback returns True to keep ticking), as `probes/boot.py` does.
- **Keep probes:** they are checked in, so the next change to the same behaviour re-runs them.
- **Poking a running game by hand:** start `uepy.py --game --seconds 120` and send scripts with
  `uepy.py --in-game <script>`. A game has its own inbox, `Saved/uepy/game`, so it never takes a
  job meant for the editor.

- **World time in `-nullrhi -game` advances by a fixed tiny step per frame.**
  - A 2–3 s `Delay` may never elapse in a 30 s run. Keep probe delays well under a second, and
    measure upstream of long delays.
  - Heavy per-frame logging slows the game itself, so gate probes down to one actor.
  - Cross-check `GetTimeSeconds` against wall clock before reading "it did not happen".
- **Isolate the thing under test.** For example, kill the player at BeginPlay rather than waiting
  for the pack: 40 decisive seconds instead of 3 inconclusive minutes.
- **A `-game` process runs `init_unreal.py`.** That is how probes start, and how
  `uepy.py --in-game` reaches a running game.
  - There is no world context there, and `EditorLevelLibrary.get_game_world` SIGSEGVs. Use
    `unreal.find_object(None, "/Game/Maps/<L>.<L>")` to get the world.
- **Python can't write a Blueprint variable on an instance** unless it is Instance Editable, and
  the `Set*PropertyByName` functions aren't exported. Probes handle this with `WRITABLE` (above).
  What that rests on:
  - **Instance Editable plus compile, unsaved, works in `-game`**, but only if the Blueprint
    stays referenced. Opening a level garbage-collects an unreferenced Blueprint, and it
    reloads from disk without the edit. `boot.py` holds them.
  - **Write with `set_editor_property(name, value, PropertyAccessChangeNotifyMode.NEVER)`.**
    The default notifies PostEditChange, which on a live component re-runs the owner's
    construction script. The actor gets fresh components, so the one you wrote is a dead copy
    that never ticks again.
  - **Never use the console's `set <Class> <Prop> <value>` in a game.** It writes every object
    of the class, including the CDO, and re-runs construction scripts: it set off an endless
    NPC respawn storm. `setnopec` did nothing to a PIE instance and logged nothing.
  - PIE started from Python begins **paused**. Call `GameplayStatics.set_game_paused(w, False)`.
- **A `-game` inbox heartbeat can go quiet for seconds.** The game beats once a frame, and a
  headless frame can be slow. uepy allows a game 30 s (an editor 6 s), and it treats a beat from
  a dead pid as silence.
- **In a cold run, `print()` doesn't reach the log.** Use `unreal.log_warning`. The inbox captures
  both.
- **Sort numbered actors on their trailing integer, never on the label string,** or `_10` lands
  between `_1` and `_2`.
- **Killing a `-game` run on a timer** produces a `SIGSEGV` with `GracefulTerminationHandler` in
  the stack. That isn't a gameplay fault.
- **`-nullrhi` can't prove anything that touches the window or viewport.** `--game
  --windowed` renders: widgets get their geometry and the engine calls `DrawHUD` itself
  (`probe_menu_cursor_window.py`). Python still reads a widget's cached geometry as zeros.
- **Diagnosing a frozen editor:** run `sample <pid> 5 -file /tmp/hang.txt` and read the
  `GameThread` stack. `ps -o %cpu` separates a spin (100%) from a deadlock (0%).
<a id="title"></a>
## `--title`

- **`--title`** (with `--game` or `--net`) keeps the title menu: no `-nomenu`, so the game
  opens paused on it and a probe works it (`Scripts/probes/title.py`). With `--net` each
  client starts alone on the level and its probe joins through the Multiplayer page
  (`probe_net_title.py`). Every `--game` and `--net` process is told the run's level is
  `GameDefaultMap`, which is where a failed join or a left server returns it.

<a id="net"></a>
## `--net`: the report, lag, bots, files, memory

Under the root's `--net --clients N` bullet:

  - **The report:** one row per process (its joins, Blueprint runtime errors, `Accessed None`
    and network failures), then each probe's checks, process by process. Any error, a client
    that did not join, a process that died or a failed check fails the run. One
    exception: a client the server's RPC guard kicked (`RPC-KICKED` in the server's log)
    is forgiven its lost connection, and its row says so (`probe_net_guard.py`).
  - **`--lag MS`** delays every packet a client sends (the engine's `Net PktLag`), and the
    row's last column counts the movement corrections that process logged
    (`MOVE-CORRECTION`: the server pulling a client back, rubber-banding when the client
    predicted wrong). The count fails nothing by itself; a probe says how many a run may
    have (`probe_net_move_states.py`: none through a sprint, prone or an aim).
  - **`--bots N`** has the server spawn N more player characters driven by simple AI
    (`probes/bots.py`: walk, crouch, fire at the nearest body through the same Server events
    a client asks with), the load test's players; `--trace` writes the server's Unreal
    Insights trace (`-trace=net,cpu`) as `server.utrace` in the run's folder.
    `probe_net_load.py` records the numbers (frame and world-tick time, bytes and actor
    channels per connection, the hit history's size); `Scripts/net/CLAUDE.md`, "Measured at
    scale", holds them for N = 8, 16, 32 and 62 and the three largest costs. Every
    performance decision is made against a number from this harness.
  - **The files:** one log per process (`server.log`, `client1.log`, ...) in
    `Saved/uepy/net/<stamp>/`, the last ten runs kept.
  - **Clients are `-nullrhi`** unless `--windowed`. With no probe everyone plays for
    `--seconds` (default 20) after the last join; with one the run ends when the last process
    has finished its probes.
  - **Memory:** the report has a line per process with what it used (`uepylib/net_memory.py`).
    Measured on the 200 m map before the motion matching: a server or a `-nullrhi` client
    was 1.9 GB, a `--windowed` client 5.8 GB. With the sample's databases loaded (G3) a
    server or a `-nullrhi` client peaks at 4.2–4.3 GB, so a server and two `-nullrhi`
    clients are 12.9 GB of this machine's 16; a rendered client was not measured again.
    Close the editor first, and run one at a time.
