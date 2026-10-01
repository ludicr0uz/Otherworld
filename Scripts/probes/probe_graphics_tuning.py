"""Graphics tuning: a quality preset reaches the engine, and the M panel's [P]
tab changes each of its numbers live and saves graphics_tuning.csv.

The keys are raised by writing the HUD's GfxTuneRow / GfxTuneNudge /
GfxTuneSaveRequested (a probe has no keyboard); the keys themselves are the
verifier's.

  - the game starts on Low, applied: its console variables, one grass layer,
    unlit grass;
  - Right on the preset row is Medium: Quality, the cvars, a second layer;
  - a resolution nudge is r.ScreenPercentage; fog off is r.Fog 0, and a
    second nudge down stops at the minimum; leaf cut-outs off is the Nanite
    cvar;
  - grass draw distance up scales a grass cell's fade and moves its max draw
    distance as far, and leaves the trees alone; tree draw distance down does
    the same to a tree cell and leaves the grass alone;
  - grass layers and grass shadows show and light the cells;
  - sunlight and moonlight scale the light that is up, and stars, ambient
    and fog density land on the cycle; brightness is r.ExposureOffset;
  - the look numbers are in every preset's row, so Left back to Low keeps
    them while the resolution goes back to Low's;
  - the save writes the table into graphics_tuning.csv;
  - the panel, drawn by hand, shows the preset and the value on its row.

graphics_tuning.csv is set aside first and put back.

A headless run draws nothing. For the look of the panel, run it rendered
with OW_GFX_SHOTS=1: `shot showui` saves the M panel with the tab open to
Saved/Screenshots/MacEditor/.

    OW_GFX_SHOTS=1 python3 Scripts/dev/uepy.py --game --windowed \
        --probe Scripts/probes/probe_graphics_tuning.py
"""

import os
import shutil

import unreal

from forest_generator.grass_cells import GRASS_TAG, tier_tag
from graphics_menu import gfx_stats as GS
from graphics_menu import gfx_tune_consts as GC
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR
from graphics_menu.umg_consts import ROW_VALUE
from world.paths import DAY_NIGHT_BP_PATH, DAY_NIGHT_CLASS_PATH

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
TAB = GC.GFX_TAB
WRITABLE = ([(HUD_BP_PATH, v) for v in (TAB.open_var, TAB.row_var, TAB.nudge_var,
                                        TAB.save_var, "MenuOpen")]
            + [(DAY_NIGHT_BP_PATH, "Clock")])
ROW = {s.column: i + 1 for i, s in enumerate(GS.GFX_STATS)}
STAT = {s.column: s for s in GS.GFX_STATS}
SL = unreal.SystemLibrary
HISM = unreal.HierarchicalInstancedStaticMeshComponent


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def probe(p):
    backup = GS.CSV_PATH + ".probe-backup"
    shutil.copy2(GS.CSV_PATH, backup)
    try:
        yield from _run(p)
    finally:
        shutil.move(backup, GS.CSV_PATH)


def _nudge(p, hud, row, step, times=1):
    p.set(hud, TAB.row_var, row)
    for _ in range(times):
        p.set(hud, TAB.nudge_var, step)
        yield lambda: p.get(hud, TAB.nudge_var) == 0
    yield 0.15          # the hand-over on the next Tick, then the tuner's Tick


def _cvar(name):
    return SL.get_console_variable_float_value(name)


def _cell(p, preset, column):
    values = list(p.get(p.hud(), TAB.values_var))
    return float(values[preset * GS.STAT_COUNT + GS.index_of(column)])


def _root(actor):
    return actor.get_editor_property("root_component")


def _tagged(p, tag):
    return list(unreal.GameplayStatics.get_all_actors_with_tag(p.world(), tag))


def _trees(p):
    return [a for a in unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.Actor)
            if isinstance(_root(a), HISM) and not a.actor_has_tag(GRASS_TAG)]


def _hidden(actors):
    return sorted({bool(a.get_editor_property("hidden")) for a in actors})


def _distances(comp):
    return (comp.get_editor_property("instance_start_cull_distance"),
            comp.get_editor_property("instance_end_cull_distance"),
            comp.get_editor_property("ld_max_draw_distance"))


def _preset_cvars(preset):
    return {s.target: _cell_default(preset, s) for s in GS.GFX_STATS
            if s.how == GS.CVAR and s.column in ("resolution_pct", "shadow_quality",
                                                 "view_distance", "volumetric_fog")}


def _cell_default(preset, stat):
    return GS.preset_rows()[preset][GS.index_of(stat.column)]


def _cvars_match(preset):
    want = _preset_cvars(preset)
    got = {name: _cvar(name) for name in want}
    return all(abs(got[n] - want[n]) < 1e-3 for n in want), f"{got} vs {want}"


def _run(p):
    yield lambda: _live_hud(p) is not None
    hud, cycle = _live_hud(p), p.actor_of(DAY_NIGHT_CLASS_PATH)
    tuner = p.get(hud, GC.TUNER_COMPONENT)
    yield lambda: p.get(hud, GC.GFX_APPLIED_VAR) == 0 and not p.get(tuner, GC.TUNER_DIRTY_VAR)
    yield 0.1
    grass = _tagged(p, GRASS_TAG)
    tiers = {t: _tagged(p, tier_tag(t)) for t in (1, 2, 3)}
    trees = _trees(p)
    ok, detail = _cvars_match(0)
    p.check("the game starts on Low, applied: its resolution, shadow quality, view "
            "distance and volumetric fog are the console's",
            p.get(hud, "Quality") == 0 and ok, detail)
    p.check("...one grass layer drawn, and no grass casting shadows",
            bool(grass) and all(tiers.values()) and bool(trees)
            and all(_hidden(tiers[t]) == [True] for t in tiers)
            and not any(_root(a).get_editor_property("cast_shadow") for a in grass),
            f"{len(grass)} grass cells, {len(trees)} tree cells, "
            f"{ {t: _hidden(a) for t, a in tiers.items()} }")

    p.set(hud, "MenuOpen", True)
    p.set(hud, TAB.open_var, True)
    yield from _nudge(p, hud, 0, 1)
    ok, detail = _cvars_match(1)
    p.check("Right on the preset row is Medium: Quality, the pick and its cvars",
            p.get(hud, "Quality") == 1 and p.get(hud, TAB.pick_var) == 1 and ok, detail)
    p.check("...and a second grass layer",
            _hidden(tiers[1]) == [False] and _hidden(tiers[2]) == [True]
            and _hidden(tiers[3]) == [True], str({t: _hidden(a) for t, a in tiers.items()}))

    before = _cvar("r.ScreenPercentage")
    yield from _nudge(p, hud, ROW["resolution_pct"], 1)
    p.check("a resolution nudge is r.ScreenPercentage, one step up",
            abs(_cvar("r.ScreenPercentage") - (before + STAT["resolution_pct"].step)) < 1e-3
            and abs(_cell(p, 1, "resolution_pct") - _cvar("r.ScreenPercentage")) < 1e-3,
            f"{before} -> {_cvar('r.ScreenPercentage')}")
    yield from _nudge(p, hud, ROW["fog"], -1, times=2)
    yield from _nudge(p, hud, ROW["leaf_cutouts"], -1)
    p.check("fog off is r.Fog 0 (held at the minimum by a second nudge), and leaf "
            "cut-outs off is r.Nanite.ProgrammableRaster 0",
            _cvar("r.Fog") == 0.0 and _cell(p, 1, "fog") == 0.0
            and _cvar("r.Nanite.ProgrammableRaster") == 0.0,
            f"r.Fog {_cvar('r.Fog')}, cell {_cell(p, 1, 'fog')}, "
            f"raster {_cvar('r.Nanite.ProgrammableRaster')}")
    yield from _nudge(p, hud, ROW["fog"], 1, times=2)
    yield from _nudge(p, hud, ROW["leaf_cutouts"], 1)
    p.check("...and back on, held at the maximum", _cvar("r.Fog") == 1.0
            and _cell(p, 1, "fog") == 1.0 and _cvar("r.Nanite.ProgrammableRaster") == 1.0,
            f"r.Fog {_cvar('r.Fog')}, cell {_cell(p, 1, 'fog')}")

    g, t = _root(grass[0]), _root(trees[0])
    g0, t0 = _distances(g), _distances(t)
    yield from _nudge(p, hud, ROW["grass_distance"], 1, times=5)
    g1, t1 = _distances(g), _distances(t)
    p.check("grass draw distance x1.5 scales a grass cell's fade, moves its max draw "
            "distance as far as the fade's end, and leaves the trees alone",
            abs(g1[0] - 1.5 * g0[0]) <= 3 and abs(g1[1] - 1.5 * g0[1]) <= 3
            and abs((g1[2] - g0[2]) - (g1[1] - g0[1])) <= 3 and t1 == t0,
            f"grass {g0} -> {g1}, tree {t0} -> {t1}")
    yield from _nudge(p, hud, ROW["tree_distance"], -1, times=5)
    g2, t2 = _distances(g), _distances(t)
    p.check("tree draw distance x0.5 does the same to a tree cell, and leaves the grass",
            abs(t2[0] - 0.5 * t0[0]) <= 3 and abs(t2[1] - 0.5 * t0[1]) <= 3
            and abs((t2[2] - t0[2]) - (t2[1] - t0[1])) <= 3 and g2 == g1,
            f"tree {t0} -> {t2}, grass {g1} -> {g2}")

    yield from _nudge(p, hud, ROW["grass_layers"], 1, times=2)
    yield from _nudge(p, hud, ROW["grass_shadows"], 1)
    p.check("grass layers 4 draws every tier, and grass shadows 1 lights every cell",
            all(_hidden(tiers[t]) == [False] for t in tiers)
            and all(_root(a).get_editor_property("cast_shadow") for a in grass),
            str({t: _hidden(a) for t, a in tiers.items()}))

    yield from _look(p, hud, cycle)

    yield from _nudge(p, hud, 0, -1)
    ok, detail = _cvars_match(0)
    p.check("Left back to Low: its own resolution and layers, the look kept",
            p.get(hud, "Quality") == 0 and ok and _hidden(tiers[1]) == [True]
            and abs(p.get(cycle, "SunScale") - 1.5) < 1e-6
            and abs(_cvar("r.ExposureOffset") - STAT["brightness"].step) < 1e-6,
            f"{detail}, SunScale {p.get(cycle, 'SunScale')}")

    p.set(hud, TAB.save_var, True)
    yield lambda: not p.get(hud, TAB.save_var)
    saved = GS.read_table()
    p.check("the save writes all four presets into graphics_tuning.csv",
            p.get(hud, TAB.saved_var)
            and saved.get("Medium", {}).get("resolution_pct") == _cell(p, 1, "resolution_pct")
            and saved.get("Medium", {}).get("grass_layers") == 4.0
            and all(abs(saved.get(label, {}).get("sun_light", 0.0) - 1.5) < 1e-6
                    for label in GS.PRESET_LABELS)
            and saved.get("Low", {}).get("resolution_pct") == STAT["resolution_pct"].defaults[0],
            str({k: v.get("resolution_pct") for k, v in saved.items()}))

    ui = p.get(hud, "UiPause")
    panel, rows = (ui.get_editor_property(n) for n in (TAB.panel, TAB.rows_box))
    p.set(hud, TAB.row_var, ROW["sun_light"])
    hud.call_method("ReceiveDrawHUD", (1920, 1080))
    subject = str(rows.get_child_at(0).get_editor_property(ROW_VALUE).get_text())
    value = str(rows.get_child_at(ROW["sun_light"]).get_editor_property(ROW_VALUE).get_text())
    p.check("drawn, the panel shows the preset and the sunlight on its row",
            "COLLAPSED" not in str(panel.get_visibility()).upper()
            and subject == GS.PRESET_LABELS[0] and abs(float(value) - 1.5) < 1e-6,
            f"{panel.get_visibility()} {subject!r} {value!r}")
    if os.environ.get("OW_GFX_SHOTS"):
        yield 0.5
        SL.execute_console_command(p.world(), "shot showui")
        p.note("shot showui: the M panel with the graphics tab open")
        yield 0.5
    p.set(hud, TAB.open_var, False)
    p.set(hud, "MenuOpen", False)


def _look(p, hud, cycle):
    """The look rows: the cycle's multipliers and the exposure offset."""
    lights = {}
    for name, clock in (("Sun", 0.5 * p.get(cycle, "DayLengthSeconds")),
                        ("Moon", p.get(cycle, "DayLengthSeconds")
                         + 0.5 * p.get(cycle, "NightLengthSeconds"))):
        p.set(cycle, "Clock", clock)
        yield 0.1
        light = p.get(cycle, name)
        lights[name] = [light.get_editor_property("intensity")]
    yield from _nudge(p, hud, ROW["sun_light"], 1, times=5)
    yield from _nudge(p, hud, ROW["moon_light"], 1, times=5)
    for name, clock in (("Sun", 0.5 * p.get(cycle, "DayLengthSeconds")),
                        ("Moon", p.get(cycle, "DayLengthSeconds")
                         + 0.5 * p.get(cycle, "NightLengthSeconds"))):
        p.set(cycle, "Clock", clock)
        yield 0.1
        lights[name].append(p.get(cycle, name).get_editor_property("intensity"))
    p.check("sunlight x1.5 is the noon sun 1.5 times as bright, and moonlight x1.5 "
            "the midnight moon",
            all(was > 0.0 and abs(now / was - 1.5) < 0.02 for was, now in lights.values()),
            str(lights))

    for column in ("stars", "ambient_light", "fog_density", "sun_disc", "moon_disc"):
        yield from _nudge(p, hud, ROW[column], -1)
    yield from _nudge(p, hud, ROW["brightness"], 1)
    got = {STAT[c].target: p.get(cycle, STAT[c].target)
           for c in ("stars", "ambient_light", "fog_density", "sun_disc", "moon_disc")}
    p.check("stars, ambient light, fog density and the two discs, one step down, are "
            "the cycle's multipliers at 0.9; brightness up is r.ExposureOffset",
            all(abs(v - 0.9) < 1e-6 for v in got.values())
            and abs(_cvar("r.ExposureOffset") - STAT["brightness"].step) < 1e-6,
            f"{got}, r.ExposureOffset {_cvar('r.ExposureOffset')}")
    p.check("a look number is written into every preset's row",
            all(abs(_cell(p, i, "sun_light") - 1.5) < 1e-6
                and abs(_cell(p, i, "stars") - 0.9) < 1e-6
                for i in range(len(GS.PRESET_LABELS))),
            str([_cell(p, i, "sun_light") for i in range(len(GS.PRESET_LABELS))]))
