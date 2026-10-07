"""In-game entry for a probe run: prepare, open the level, drive the probes.

``Scripts/dev/uepy.py --game --probe ...`` boots the game into the engine's
empty ``/Engine/Maps/Entry`` with a plain GameModeBase, and sets

    UEPY_PROBES          the probe files, os.pathsep-separated
    UEPY_PROBE_MAP       the level to test, e.g. /Game/Maps/Lvl_Forest_200m
    UEPY_PROBE_RESULTS   where to write the JSON results
    UEPY_PROBE_TIMEOUT   wall seconds allowed per probe

Content/Python/init_unreal.py sees UEPY_PROBES and calls ``start()``.

Why boot into Entry first: init_unreal.py runs only *after* the command-line
map has loaded and begun play. Every variable a probe declared in WRITABLE is
made Instance Editable and its Blueprint recompiled -- in memory, never saved
-- which only reaches actors spawned afterwards. Doing that in Entry, then
opening the real level, means every actor under test is built from the
recompiled class, with no reinstancing of live actors and no rebuild on disk.

When the last probe finishes the results file appears; uepy.py is polling for
it and kills the game at once rather than sitting out the timer.

A network run (``uepy.py --net``, probes/net.py) starts this in every process,
probes or none. The server opens the level and posts that it listens; a client
waits in Entry for that, then opens the server's address. The probes start on
the server once every client's player has joined, and on a client once it has
its pawn. A dedicated server has no Slate, so there the tick is the core
ticker's.

``--title`` leaves the title menu up (UEPY_TITLE): the level counts as up
once the title has paused it, and a network run's client opens the level
alone, its probe joining the server through the menu. The probes outlive the
travel: they are driven from the engine's tick, not from the level.
"""

import json
import os
import runpy
import time
import traceback

import unreal

from combat.record_vars import SlotForced
from graphics_menu.tune_keep_consts import TUNE_SAVE_SLOTS

from probes import bots, kept_slots
from probes.context import Probe
from probes.net import LISTENING, SERVER, STANDALONE, Where, pick_probe
from probes.runner import DEFAULT_TIMEOUT, Ledger, ProbeRun, Queue

READY_GAME_SECONDS = 0.5    # let BeginPlay and the first ticks settle
# uepy.py --title: the game keeps its title menu (no -nomenu), and a network
# run's clients start alone on the level instead of joining.
TITLE = bool(os.environ.get("UEPY_TITLE"))
READY_TIMEOUT = 120.0       # wall seconds for the level to load and spawn
NET_READY_TIMEOUT = 240.0   # ... and, in a network run, for everyone to boot and join

_state = {"handle": None, "queue": None, "phase": "prepare", "since": 0.0,
          "writable": [], "keep": [], "where": Where()}


def _log(text):
    unreal.log_warning(f"[PROBE] {text}")


def _world(map_path):
    name = map_path.rsplit("/", 1)[-1]
    return unreal.find_object(None, f"{map_path}.{name}")


def _game_time(map_path):
    def now():
        world = _world(map_path)
        return unreal.GameplayStatics.get_time_seconds(world) if world else 0.0
    return now


def load_probes(paths, where):
    """Each file's probe function, WRITABLE list and TIMEOUT (wall seconds,
    None for the run's default), or a ledger error. A file whose RUNS_ON
    leaves this process out is not loaded here; in a single-player run that
    is an error, since it then runs nowhere."""
    loaded = []
    for path in paths:
        name = os.path.splitext(os.path.basename(path))[0]
        ledger = Ledger(name)
        try:
            ns = runpy.run_path(path, run_name=f"probe_{name}")
            if not where.matches(ns.get("RUNS_ON")):
                if where.networked:
                    continue
                raise RuntimeError(f"{name} has RUNS_ON = {ns.get('RUNS_ON')!r}: it is "
                                   f"a network probe, run it with uepy.py --net")
            fn = pick_probe(ns, where)
            if fn is None:
                raise AttributeError(f"{path} defines no probe(p)")
            loaded.append((ledger, fn, list(ns.get("WRITABLE") or ()), ns.get("TIMEOUT")))
        except Exception:
            ledger.error = traceback.format_exc(limit=4).strip()
            loaded.append((ledger, None, [], None))
    return loaded


def make_writable(pairs):
    """Instance Editable + compile, unsaved. Returns a list of failures."""
    bel = unreal.BlueprintEditorLibrary
    problems, compiled = [], {}
    for bp_path, var in pairs:
        bp = compiled.get(bp_path) or unreal.load_asset(bp_path)
        if bp is None:
            problems.append(f"WRITABLE: no Blueprint at {bp_path}")
            continue
        try:
            bel.set_blueprint_variable_instance_editable(bp, var, True)
        except Exception as exc:
            problems.append(f"WRITABLE: {bp_path}.{var}: {exc}")
            continue
        compiled[bp_path] = bp
    for bp in compiled.values():
        bel.compile_blueprint(bp)
        # Hold them: opening the level garbage-collects everything unreferenced,
        # and a collected Blueprint reloads from disk without the edit.
        _state["keep"].extend([bp, bel.generated_class(bp)])
    if compiled:
        _log(f"made writable for this run: "
             + ", ".join(f"{p.rsplit('/', 1)[-1]}.{v}" for p, v in pairs))
    return problems


def _write_results(results, setup_errors):
    path = os.environ.get("UEPY_PROBE_RESULTS")
    payload = {"probes": results, "setup_errors": setup_errors,
               "where": _state["where"].name}
    for probe in results:
        for c in probe["checks"]:
            _log(f"{'PASS' if c['ok'] else 'FAIL'}  {probe['name']}: {c['label']}"
                 + (f" -- {c['detail']}" if c["detail"] else ""))
        if probe["error"]:
            _log(f"ERROR {probe['name']}: {probe['error']}")
    if path:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp, path)


def _save_dir():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames")


def _hermetic(fn, probe):
    """The probe, and then nothing of its nudges left in the tabs' slots."""
    try:
        result = fn(probe)
        if hasattr(result, "send"):      # a plain function ran already
            yield from result
    finally:
        kept_slots.clear(_save_dir(), TUNE_SAVE_SLOTS)


def _finish(setup_errors):
    queue = _state["queue"]
    # Before the results: uepy.py kills the game as soon as they appear. In a
    # network run the others may still be playing: uepy.py puts them back.
    if not _state["where"].networked:
        kept_slots.put_back(_save_dir(), TUNE_SAVE_SLOTS)
    _write_results(queue.results() if queue else [], setup_errors)
    _state["phase"] = "done"
    if _state["handle"] is not None:
        unreal.unregister_slate_post_tick_callback(_state["handle"])
        _state["handle"] = None


def _ready(world, where):
    """Is the level up, with whoever this process waits for in it?"""
    if not world:
        return False
    # A run on the real title (uepy.py --title) is paused a quarter second
    # in, and game time stops there: the pause is the title being up.
    titled = TITLE and unreal.GameplayStatics.is_game_paused(world)
    if unreal.GameplayStatics.get_time_seconds(world) < READY_GAME_SECONDS and not titled:
        return False
    if where.role == SERVER:
        if not where.posted(SERVER, LISTENING):
            _log(f"server is listening on {world.get_name()}")
            where.post(LISTENING)
            # The load test's bots (uepy.py --net --bots N): spawned as soon
            # as the level is up, whether or not a client has joined yet.
            bots.start(world)
        return unreal.GameplayStatics.get_num_player_controllers(world) >= where.clients
    return bool(unreal.GameplayStatics.get_player_pawn(world, 0))


def _awaited(where):
    return (f"{where.clients} joined player(s)" if where.role == SERVER
            else "a player pawn")


def _tick(_delta):
    """Once a frame: wait for the level, then drive the queue. Never raises."""
    map_path = os.environ.get("UEPY_PROBE_MAP", "")
    where = _state["where"]
    limit = NET_READY_TIMEOUT if where.networked else READY_TIMEOUT
    try:
        if _state["phase"] == "prepare":
            _prepare(map_path)
            return
        if _state["phase"] == "await server":
            if where.posted(SERVER, LISTENING):
                # On the title the client starts alone, and its probe joins.
                _open(map_path if TITLE else where.address)
            elif time.time() - _state["since"] > limit:
                _finish([f"the server never listened within {limit:.0f} s"])
            return
        if _state["phase"] == "load":
            if _ready(_world(map_path), where):
                _log(f"{map_path} is up; running {len(_state['queue'].runs)} probe(s)")
                _state["phase"] = "run"
            elif time.time() - _state["since"] > limit:
                _finish([f"{map_path} never came up with {_awaited(where)} "
                         f"within {limit:.0f} s"])
            return
        if _state["phase"] == "run" and _state["queue"].advance():
            _finish([])
    except Exception:
        _finish([traceback.format_exc(limit=6).strip()])


def start():
    """Called once by init_unreal.py in the -game process."""
    paths = [p for p in os.environ.get("UEPY_PROBES", "").split(os.pathsep) if p]
    map_path = os.environ.get("UEPY_PROBE_MAP", "")
    where = _state["where"] = Where.from_env(os.environ)
    timeout = float(os.environ.get("UEPY_PROBE_TIMEOUT") or DEFAULT_TIMEOUT)
    game_time = _game_time(map_path)

    # The developer's own tuning (graphics_menu/tune_keep.py) is not the
    # build's: every probe starts from the built tables.
    # In a network run the processes share the save folder: the server, which
    # is up before any client is in the level, sets them aside for all.
    if where.role in (STANDALONE, SERVER):
        kept_slots.set_aside(_save_dir(), TUNE_SAVE_SLOTS)
    loaded = load_probes(paths, where)
    runs = []
    for ledger, fn, _writable, own_timeout in loaded:
        probe = Probe(ledger, map_path, game_time, where)
        factory = (lambda fn=fn, probe=probe: _hermetic(fn, probe)) if fn else (lambda: None)
        runs.append(ProbeRun(ledger, factory, game_time, time.time,
                             float(own_timeout or timeout)))
    _state["queue"] = Queue(runs)
    _state["since"] = time.time()

    writable = {pair for _l, _f, w, _t in loaded for pair in map(tuple, w)}
    if where.role == SERVER and bots.count():
        writable |= set(map(tuple, bots.WRITABLE))
    # A write of the weapon component's EquippedIndex is a request for an item
    # in hand (context.hold): what is written is the ask's forced slot, which
    # the owning machine's Tick sends to the server (slot_moves.py).
    writable |= {(bp, str(SlotForced)) for bp, var in writable if var == "EquippedIndex"}
    _state["writable"] = sorted(writable)
    if where.networked:
        unreal.register_ticker_callback(_ticker)
    else:
        _state["handle"] = unreal.register_slate_post_tick_callback(_tick)


def _ticker(delta):
    """The core ticker's callback: true keeps it ticking."""
    _tick(delta)
    return _state["phase"] != "done"


def _prepare(map_path):
    """First tick in Entry: make WRITABLE writable, then open the level.

    On a tick rather than in start(), so the engine has finished starting
    before anything is compiled.
    """
    setup_errors = make_writable(_state["writable"]) if _state["writable"] else []
    if setup_errors:
        _finish(setup_errors)
        return
    if _state["where"].role == "client":
        _state["phase"] = "await server"
        _state["since"] = time.time()
        return
    _open(map_path)


def _open(url):
    """Leave Entry for the level, or for the server that runs it."""
    # The Entry world is the only one loaded; any world works as the context.
    entry = unreal.find_object(None, "/Engine/Maps/Entry.Entry")
    _log(f"opening {url}")
    unreal.GameplayStatics.open_level(entry, url, True, "")
    _state["phase"] = "load"
    _state["since"] = time.time()
