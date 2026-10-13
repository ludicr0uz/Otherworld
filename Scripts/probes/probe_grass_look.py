"""What the grass costs and how it looks: frame time at Medium and High with the
grass shown and hidden, and pictures of the ground at each preset.

    OW_GRASS_LABEL=after OW_GRASS_SHOTS=1 python3 Scripts/dev/uepy.py --game \
        --windowed --seconds 420 --probe-timeout 400 --probe Scripts/probes/probe_grass_look.py

It needs a rendered window (--windowed): -nullrhi draws nothing to time or to
picture. The spot and the method are probe_perf_audit.py's (the densest tree
cluster, noon), so a number here reads against that table. Each state is
measured twice, shown-hidden-shown-hidden, because two runs of one state differ
by a millisecond; the results go to Saved/uepy/bench/grass_look_<label>.json.

With OW_GRASS_SHOTS set it then pictures the ground from the same spot at noon
and at midnight, at Low, Medium and High, looking across it and looking down:
assets/generated/undergrowth/<OW_GRASS_PREFIX, default g1_><preset>_<hour>_<view>.png.
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # the level whose grass this is about
SYSTEMS = ('load',)
import glob
import os
import shutil

from forest_generator.grass_cells import GRASS_TIERS, tier_tag
from forest_generator.undergrowth_meshes import GRASS_MESHES
from probes import probe_perf_audit as B

WRITABLE = B.WRITABLE
unreal = B.unreal

LABEL = os.environ.get("OW_GRASS_LABEL", "run")
SHOTS = bool(os.environ.get("OW_GRASS_SHOTS"))
PREFIX = os.environ.get("OW_GRASS_PREFIX", "g1_")
PROJECT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SHOTS_DIR = os.path.join(PROJECT, "Saved", "Screenshots", "MacEditor")
OUT_DIR = os.path.join(PROJECT, "assets", "generated", "undergrowth")
PRESETS = ((0, "Low"), (1, "Medium"), (2, "High"))
HOURS = ((12.0, "noon"), (0.0, "night"))
# Pitch of the view: across the ground from standing height, and down at it.
VIEWS = ((-8.0, "across"), (-55.0, "down"))


def _shot(p, name):
    """Take the frame as drawn and move it to OUT_DIR/name."""
    before = set(glob.glob(os.path.join(SHOTS_DIR, "*.png")))
    B._cmd(p, "shot")
    yield lambda: set(glob.glob(os.path.join(SHOTS_DIR, "*.png"))) - before
    yield 0.4       # the file is listed before it is closed
    new = sorted(set(glob.glob(os.path.join(SHOTS_DIR, "*.png"))) - before)
    os.makedirs(OUT_DIR, exist_ok=True)
    shutil.move(new[-1], os.path.join(OUT_DIR, name))


def _grass_cells(p):
    """The grass cells alone: the bushes carry the grass tag too."""
    wanted = {m.mesh for m in GRASS_MESHES}
    cells = []
    for a in B._grass(p):
        mesh = B._root(a).get_editor_property("static_mesh")
        if mesh and mesh.get_path_name().split(".")[0] in wanted:
            cells.append(a)
    return cells


def _tiers(shown):
    """How many of ``shown`` are in each density tier, lowest first."""
    upper = [sum(1 for a in shown if a.actor_has_tag(tier_tag(t)))
             for t in range(1, len(GRASS_TIERS))]
    return [len(shown) - sum(upper)] + upper


def _set_hidden(shown, hidden):
    """Hide or show the cells the preset draws, and no tier it does not."""
    for a in shown:
        a.set_actor_hidden_in_game(hidden)


def probe(p):
    def live():
        try:
            hud = p.hud()
        except Exception:
            return None
        return hud if hud is not None and p.get(hud, B.PROFILE_CHECKED_VAR) else None

    B.OUT_NAME = f"grass_look_{LABEL}.json"
    del B.RESULTS[:]
    yield lambda: live() is not None
    hud, cycle = live(), p.actor_of(B.DAY_NIGHT_CLASS_PATH)
    tuner = p.get(hud, B.GC.TUNER_COMPONENT)
    B._log(f"hud up, preset {p.get(hud, B.GC.GFX_APPLIED_VAR)} applied")
    yield lambda: not p.get(tuner, B.GC.TUNER_DIRTY_VAR)
    B._log("tuner settled")
    B._cmd(p, "t.MaxFPS 0")
    B._cmd(p, "r.VSync 0")
    yield 4.0       # shaders, streaming
    trees, grass = B._trees(p), _grass_cells(p)
    spot, yaw, n_near, n_all = B._forest_spot(p, trees)
    B._log(f"forest spot {spot.x:.0f},{spot.y:.0f} yaw {yaw:.0f}: {n_near} of {n_all} "
           f"trees in 35 m; {len(grass)} grass cells")
    pawn, pc = p.pawn(), p.controller()
    pawn.set_actor_location(spot, False, True)
    pc.set_control_rotation(unreal.Rotator(pitch=12.0, yaw=yaw, roll=0.0))
    yield 2.5

    cost = {}
    for q, name in PRESETS[1:]:
        yield from B._preset(p, hud, tuner, q)
        pc.set_control_rotation(unreal.Rotator(pitch=12.0, yaw=yaw, roll=0.0))
        shown = [a for a in grass if not a.get_editor_property("hidden")]
        for turn in (1, 2):
            yield from B._measure(p, cycle, f"{name} grass shown {turn}", 12.0)
            _set_hidden(shown, True)
            yield from B._measure(p, cycle, f"{name} grass hidden {turn}", 12.0)
            _set_hidden(shown, False)
        ms = {r["label"]: r["ms"] for r in B.RESULTS}
        cost[name] = sum(ms[f"{name} grass shown {t}"] - ms[f"{name} grass hidden {t}"]
                         for t in (1, 2)) / 2.0
        B._log(f"{name}: the grass costs {cost[name]:.2f} ms ({len(shown)} cells drawn, "
               f"by tier {_tiers(shown)})")
    p.check("frame time measured with the grass shown and hidden, at Medium and High",
            len(B.RESULTS) == 8, f"{len(B.RESULTS)} measurements, cost {cost}")

    if not SHOTS:
        return
    taken = []
    for q, name in PRESETS:
        yield from B._preset(p, hud, tuner, q)
        for hour, when in HOURS:
            p.set(cycle, "Clock", B.hour_to_clock(hour))
            yield 1.5       # the exposure settles
            for pitch, view in VIEWS:
                pc.set_control_rotation(unreal.Rotator(pitch=pitch, yaw=yaw, roll=0.0))
                p.set(cycle, "Clock", B.hour_to_clock(hour))
                yield 1.0
                taken.append(f"{PREFIX}{name}_{when}_{view}.png")
                yield from _shot(p, taken[-1])
    there = [n for n in taken if os.path.isfile(os.path.join(OUT_DIR, n))]
    p.check("a picture of the ground at each preset, hour and view",
            len(there) == len(PRESETS) * len(HOURS) * len(VIEWS), f"{len(there)}: {there}")
