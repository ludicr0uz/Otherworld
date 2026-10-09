"""The graphics benchmark: frame time per preset, and the frame time each
single change buys, standing in the densest tree cluster at noon.

    python3 Scripts/dev/uepy.py --game --windowed --probe-timeout 500 \
        --probe Scripts/probes/probe_perf_audit.py

It needs a rendered window (--windowed): -nullrhi draws nothing to time. It
changes nothing in the project. Each measurement is logged as [BENCH] and the
run's results are written to Saved/uepy/bench/<OUT_NAME>, replacing the last
run's. probe_perf_audit_1km.py is the short form for the 1 km map, and reuses
the helpers here. graphisOptimizationStrategy.md holds the first run's numbers.

The spot is the tree with the most neighbours within 35 m, viewed from 6 m
back, so it is the same place for the same tree scatter (seed), whatever the
tree meshes are.
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # benchmarks the real forest
SYSTEMS = ('load',)
import json
import math
import os
import time

import unreal

from forest_generator.grass_cells import GRASS_TAG
from graphics_menu import gfx_tune_consts as GC
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR
from world.paths import DAY_NIGHT_BP_PATH, DAY_NIGHT_CLASS_PATH
from world.world_config import hour_to_clock
from world import day_night_vars as DV
from graphics_menu import hud_vars as MV

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, MV.Quality), (DAY_NIGHT_BP_PATH, DV.Clock)]
SL = unreal.SystemLibrary
HISM = unreal.HierarchicalInstancedStaticMeshComponent
OUT_DIR = os.path.join(unreal.Paths.convert_relative_path_to_full(
    unreal.Paths.project_saved_dir()), "uepy", "bench")
OUT_NAME = "bench_200m.json"
RESULTS = []
SETTLE, MEASURE = 1.3, 2.2


def _log(msg):
    unreal.log_warning(f"[BENCH] {msg}")


def _cmd(p, text):
    SL.execute_console_command(p.world(), text)


def _root(a):
    return a.get_editor_property("root_component")


def _trees(p):
    return [a for a in unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.Actor)
            if isinstance(_root(a), HISM) and not a.actor_has_tag(GRASS_TAG)]


def _grass(p):
    return list(unreal.GameplayStatics.get_all_actors_with_tag(p.world(), GRASS_TAG))


def _measure(p, cycle, label, hour):
    p.set(cycle, "Clock", hour_to_clock(hour))
    yield SETTLE
    p.set(cycle, "Clock", hour_to_clock(hour))
    f0, t0 = SL.get_frame_count(), time.perf_counter()
    yield MEASURE
    f1, t1 = SL.get_frame_count(), time.perf_counter()
    frames = max(1, f1 - f0)
    ms = (t1 - t0) * 1000.0 / frames
    RESULTS.append({"label": label, "ms": round(ms, 2), "fps": round(1000.0 / ms, 1),
                    "frames": frames})
    _log(f"{label:58s} {ms:7.2f} ms  {1000.0 / ms:6.1f} fps  ({frames} frames)")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, OUT_NAME), "w") as f:
        json.dump(RESULTS, f, indent=1)


def _preset(p, hud, tuner, q):
    p.set(hud, "Quality", q)
    yield lambda: (p.get(hud, GC.GFX_APPLIED_VAR) == q
                   and not p.get(tuner, GC.TUNER_DIRTY_VAR))
    yield 0.3


def _forest_spot(p, trees):
    pts = []
    for a in trees:
        c = _root(a)
        for i in range(c.get_instance_count()):
            t = c.get_instance_transform(i, True)
            pts.append((t.translation.x, t.translation.y, t.translation.z))
    best, best_n = None, -1
    for x, y, z in pts:
        near = [(a, b) for a, b, _ in pts if math.hypot(a - x, b - y) < 3500]
        if len(near) > best_n:
            best, best_n = (x, y, z, near), len(near)
    x, y, z, near = best
    cx = sum(a for a, _ in near) / len(near)
    cy = sum(b for _, b in near) / len(near)
    yaw = math.degrees(math.atan2(cy - y, cx - x))
    # Stand 6 m back from the densest tree, on the far side from the cluster.
    px = x - 600 * math.cos(math.radians(yaw))
    py = y - 600 * math.sin(math.radians(yaw))
    return unreal.Vector(px, py, z + 400), yaw, best_n, len(pts)


def _toggles(p, cycle, prefix, hour, toggles):
    for label, on, off in toggles:
        for c in on:
            _cmd(p, c)
        yield from _measure(p, cycle, f"{prefix} + {label}", hour)
        for c in off:
            _cmd(p, c)


def _hide(p, actors, hidden):
    for a in actors:
        a.set_actor_hidden_in_game(hidden)


def probe(p):
    def live():
        try:
            hud = p.hud()
        except Exception:
            return None
        return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None

    yield lambda: live() is not None
    hud, cycle = live(), p.actor_of(DAY_NIGHT_CLASS_PATH)
    tuner = p.get(hud, GC.TUNER_COMPONENT)
    yield lambda: p.get(hud, GC.GFX_APPLIED_VAR) == 0 and not p.get(tuner, GC.TUNER_DIRTY_VAR)
    _cmd(p, "t.MaxFPS 0")
    _cmd(p, "r.VSync 0")
    yield 4.0       # shaders, streaming
    size = unreal.WidgetLayoutLibrary.get_viewport_size(p.world())
    _log(f"viewport {size.x:.0f}x{size.y:.0f} scale "
         f"{unreal.WidgetLayoutLibrary.get_viewport_scale(p.world())}")
    trees, grass = _trees(p), _grass(p)

    for q, name in ((0, "Low"), (1, "Medium"), (2, "High")):
        yield from _preset(p, hud, tuner, q)
        yield from _measure(p, cycle, f"spawn noon {name}", 12.0)

    spot, yaw, n_near, n_all = _forest_spot(p, trees)
    _log(f"forest spot {spot.x:.0f},{spot.y:.0f} yaw {yaw:.0f}: {n_near} of {n_all} trees in 35 m")
    pawn, pc = p.pawn(), p.controller()
    pawn.set_actor_location(spot, False, True)
    pc.set_control_rotation(unreal.Rotator(pitch=12.0, yaw=yaw, roll=0.0))
    yield 2.5

    for q, name in ((0, "Low"), (1, "Medium"), (2, "High")):
        yield from _preset(p, hud, tuner, q)
        pc.set_control_rotation(unreal.Rotator(pitch=12.0, yaw=yaw, roll=0.0))
        yield from _measure(p, cycle, f"forest noon {name}", 12.0)
        yield from _measure(p, cycle, f"forest midnight {name}", 0.0)

    # ── Medium, one change at a time ──
    yield from _preset(p, hud, tuner, 1)
    yield from _measure(p, cycle, "MED baseline", 12.0)
    _cmd(p, "ProfileGPU")
    yield 1.0
    _hide(p, trees, True)
    yield from _measure(p, cycle, "MED + trees hidden", 12.0)
    _hide(p, grass, True)
    yield from _measure(p, cycle, "MED + trees and grass hidden", 12.0)
    _hide(p, trees, False)
    yield from _measure(p, cycle, "MED + grass hidden", 12.0)
    _hide(p, grass, False)
    yield from _toggles(p, cycle, "MED", 12.0, (
        ("leaf cut-outs off", ["r.Nanite.ProgrammableRaster 0"], ["r.Nanite.ProgrammableRaster 1"]),
        ("shadows off", ["r.ShadowQuality 0"], ["r.ShadowQuality 2"]),
        ("1 cascade", ["r.Shadow.CSM.MaxCascades 1"], ["r.Shadow.CSM.MaxCascades 2"]),
        ("screen 60%", ["r.ScreenPercentage 60"], ["r.ScreenPercentage 85"]),
        ("screen 100%", ["r.ScreenPercentage 100"], ["r.ScreenPercentage 85"]),
        ("TSR at 60%", ["r.AntiAliasingMethod 4", "r.ScreenPercentage 60"],
         ["r.AntiAliasingMethod 2", "r.ScreenPercentage 85"]),
        ("MaxPixelsPerEdge 2", ["r.Nanite.MaxPixelsPerEdge 2"], ["r.Nanite.MaxPixelsPerEdge 1"]),
        ("MaxPixelsPerEdge 4", ["r.Nanite.MaxPixelsPerEdge 4"], ["r.Nanite.MaxPixelsPerEdge 1"]),
        ("sky capture off", ["r.SkyLight.RealTimeReflectionCapture 0"],
         ["r.SkyLight.RealTimeReflectionCapture 1"]),
        ("fog off", ["r.Fog 0"], ["r.Fog 1"]),
        ("volumetric cloud off", ["r.VolumetricCloud 0"], ["r.VolumetricCloud 1"]),
        ("DFAO off", ["r.DistanceFieldAO 0"], ["r.DistanceFieldAO 1"]),
        ("SSAO off", ["r.AmbientOcclusionLevels 0"], ["r.AmbientOcclusionLevels -1"]),
        ("view distance 0.4", ["r.ViewDistanceScale 0.4"], ["r.ViewDistanceScale 0.6"]),
        ("GI+refl method 0", ["r.DynamicGlobalIlluminationMethod 0", "r.ReflectionMethod 0"],
         ["r.DynamicGlobalIlluminationMethod 1", "r.ReflectionMethod 1"]),
    ))
    yield from _measure(p, cycle, "MED baseline (again)", 12.0)

    # ── High, one change at a time ──
    yield from _preset(p, hud, tuner, 2)
    yield from _measure(p, cycle, "HIGH baseline", 12.0)
    _cmd(p, "ProfileGPU")
    yield 1.0
    _hide(p, trees, True)
    yield from _measure(p, cycle, "HIGH + trees hidden", 12.0)
    _hide(p, trees, False)
    yield from _toggles(p, cycle, "HIGH", 12.0, (
        ("Lumen GI+refl off", ["r.DynamicGlobalIlluminationMethod 0", "r.ReflectionMethod 0"],
         ["r.DynamicGlobalIlluminationMethod 1", "r.ReflectionMethod 1"]),
        ("Lumen at sg High(2)", ["sg.GlobalIlluminationQuality 2", "sg.ReflectionQuality 2"],
         ["sg.GlobalIlluminationQuality 3", "sg.ReflectionQuality 3"]),
        ("volumetric fog off", ["r.VolumetricFog 0"], ["r.VolumetricFog 1"]),
        ("shadows off", ["r.ShadowQuality 0"], ["r.ShadowQuality 3"]),
        ("leaf cut-outs off", ["r.Nanite.ProgrammableRaster 0"], ["r.Nanite.ProgrammableRaster 1"]),
        ("screen 67%", ["r.ScreenPercentage 67"], ["r.ScreenPercentage 100"]),
        ("TSR at 67%", ["r.AntiAliasingMethod 4", "r.ScreenPercentage 67"],
         ["r.AntiAliasingMethod 2", "r.ScreenPercentage 100"]),
        ("sky capture off", ["r.SkyLight.RealTimeReflectionCapture 0"],
         ["r.SkyLight.RealTimeReflectionCapture 1"]),
        ("volumetric cloud off", ["r.VolumetricCloud 0"], ["r.VolumetricCloud 1"]),
    ))
    yield from _measure(p, cycle, "HIGH baseline (again)", 12.0)
    p.check("benchmark ran", len(RESULTS) > 30, f"{len(RESULTS)} measurements")
