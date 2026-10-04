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
"""

import json
import os
import runpy
import time
import traceback

import unreal

from combat.slot_tuning import SLOT_REQUEST_VAR
from graphics_menu.tune_keep_consts import TUNE_SAVE_SLOTS

from probes import kept_slots
from probes.context import Probe
from probes.runner import DEFAULT_TIMEOUT, Ledger, ProbeRun, Queue

READY_GAME_SECONDS = 0.5    # let BeginPlay and the first ticks settle
READY_TIMEOUT = 120.0       # wall seconds for the level to load and spawn

_state = {"handle": None, "queue": None, "phase": "prepare", "since": 0.0,
          "writable": [], "keep": []}


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


def load_probes(paths):
    """Each file's probe function and WRITABLE list, or a ledger error."""
    loaded = []
    for path in paths:
        name = os.path.splitext(os.path.basename(path))[0]
        ledger = Ledger(name)
        try:
            ns = runpy.run_path(path, run_name=f"probe_{name}")
            fn = ns.get("probe")
            if not callable(fn):
                raise AttributeError(f"{path} defines no probe(p)")
            loaded.append((ledger, fn, list(ns.get("WRITABLE") or ())))
        except Exception:
            ledger.error = traceback.format_exc(limit=4).strip()
            loaded.append((ledger, None, []))
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
    payload = {"probes": results, "setup_errors": setup_errors}
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
    # Before the results: uepy.py kills the game as soon as they appear.
    kept_slots.put_back(_save_dir(), TUNE_SAVE_SLOTS)
    _write_results(queue.results() if queue else [], setup_errors)
    _state["phase"] = "done"
    if _state["handle"] is not None:
        unreal.unregister_slate_post_tick_callback(_state["handle"])
        _state["handle"] = None


def _tick(_delta):
    """Slate post-tick: wait for the level, then drive the queue. Never raises."""
    map_path = os.environ.get("UEPY_PROBE_MAP", "")
    try:
        if _state["phase"] == "prepare":
            _prepare(map_path)
            return
        if _state["phase"] == "load":
            world = _world(map_path)
            pawn = world and unreal.GameplayStatics.get_player_pawn(world, 0)
            if pawn and unreal.GameplayStatics.get_time_seconds(world) >= READY_GAME_SECONDS:
                _log(f"{map_path} is up; running {len(_state['queue'].runs)} probe(s)")
                _state["phase"] = "run"
            elif time.time() - _state["since"] > READY_TIMEOUT:
                _finish([f"{map_path} never came up with a player pawn "
                         f"within {READY_TIMEOUT:.0f} s"])
            return
        if _state["phase"] == "run" and _state["queue"].advance():
            _finish([])
    except Exception:
        _finish([traceback.format_exc(limit=6).strip()])


def start():
    """Called once by init_unreal.py in the -game process."""
    paths = [p for p in os.environ.get("UEPY_PROBES", "").split(os.pathsep) if p]
    map_path = os.environ.get("UEPY_PROBE_MAP", "")
    timeout = float(os.environ.get("UEPY_PROBE_TIMEOUT") or DEFAULT_TIMEOUT)
    game_time = _game_time(map_path)

    # The developer's own tuning (graphics_menu/tune_keep.py) is not the
    # build's: every probe starts from the built tables.
    kept_slots.set_aside(_save_dir(), TUNE_SAVE_SLOTS)
    loaded = load_probes(paths)
    runs = []
    for ledger, fn, _writable in loaded:
        probe = Probe(ledger, map_path, game_time)
        factory = (lambda fn=fn, probe=probe: _hermetic(fn, probe)) if fn else (lambda: None)
        runs.append(ProbeRun(ledger, factory, game_time, time.time, timeout))
    _state["queue"] = Queue(runs)
    _state["since"] = time.time()

    writable = {pair for _l, _f, w in loaded for pair in map(tuple, w)}
    # A write of the weapon component's EquippedIndex is a request for an item
    # in hand (context.hold): the request is what is written.
    writable |= {(bp, SLOT_REQUEST_VAR) for bp, var in writable if var == "EquippedIndex"}
    _state["writable"] = sorted(writable)
    _state["handle"] = unreal.register_slate_post_tick_callback(_tick)


def _prepare(map_path):
    """First tick in Entry: make WRITABLE writable, then open the level.

    On a tick rather than in start(), so the engine has finished starting
    before anything is compiled.
    """
    setup_errors = make_writable(_state["writable"]) if _state["writable"] else []
    if setup_errors:
        _finish(setup_errors)
        return
    # The Entry world is the only one loaded; any world works as the context.
    entry = unreal.find_object(None, "/Engine/Maps/Entry.Entry")
    _log(f"opening {map_path}")
    unreal.GameplayStatics.open_level(entry, map_path, True, "")
    _state["phase"] = "load"
    _state["since"] = time.time()
