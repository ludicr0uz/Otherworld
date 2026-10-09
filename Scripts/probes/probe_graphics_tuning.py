"""Graphics tuning: a quality preset reaches the engine, and the M panel's
graphics tab changes each of its numbers live and saves graphics_tuning.csv.
The table is in a person's units: percentages, and metres of draw distance.

The keys are raised by writing the HUD's GfxTuneRow / GfxTuneNudge /
GfxTuneSaveRequested (a probe has no keyboard); the keys themselves are the
verifier's.

  - with no graphics save, the game starts on the CSV's default preset (Low),
    applied: its console variables, one grass layer, unlit grass. The level
    is reopened first with the player's save set aside, so that is what it
    finds whatever the player last picked;
  - Right on the preset row is Medium: Quality, the cvars, a second layer;
  - a resolution nudge is r.ScreenPercentage; fog off is r.Fog 0, and a
    second nudge down stops at the minimum; leaf cut-outs off is the Nanite
    cvar;
  - grass draw distance up (metres) scales a grass cell's fade and moves its
    max draw distance as far, and leaves the trees alone; tree draw distance
    down does the same to a tree cell and leaves the grass alone;
  - view distance up is r.ViewDistanceScale, and the grass and the trees are
    still drawn as many metres off: the tuner divides the engine's scaling
    of every cull distance back out;
  - grass layers and grass shadows show and light the cells;
  - sunlight and moonlight scale the light that is up, and stars, ambient
    and fog density land on the cycle; brightness is r.ExposureOffset;
  - the look numbers are in every preset's row, so Left back to Low keeps
    them while the resolution goes back to Low's;
  - SAVE DEFAULT writes the table into graphics_tuning.csv, and the picked
    preset as its default;
  - the panel, drawn by hand, shows the preset and the value on its row;
  - Custom, picked and nudged, is in the player's save, and the level
    reopened comes back on Custom with that number, applied, while Medium
    is the built table's again: only Custom is the player's.

graphics_tuning.csv and the player's graphics save (Saved/SaveGames/
OtherworldGraphics.sav) are set aside first and put back.

A headless run draws nothing. For the look of the panel, run it rendered
with OW_GFX_SHOTS=1: `shot showui` saves the M panel with the tab open to
Saved/Screenshots/MacEditor/.

    OW_GFX_SHOTS=1 python3 Scripts/dev/uepy.py --game --windowed \
        --probe Scripts/probes/probe_graphics_tuning.py
"""

SYSTEMS = ('menu',)

import os
import shutil

import unreal

from forest_generator.grass_cells import GRASS_TAG, tier_tag
from graphics_menu import gfx_stats as GS
from graphics_menu import gfx_tune_consts as GC
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR
from graphics_menu.umg_consts import ROW_VALUE
from world.paths import DAY_NIGHT_BP_PATH, DAY_NIGHT_CLASS_PATH
from world import day_night_vars as DV
from graphics_menu import hud_vars as MV

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
TAB = GC.GFX_TAB
WRITABLE = ([(HUD_BP_PATH, v) for v in (TAB.open_var, TAB.row_var, TAB.nudge_var,
                                        TAB.save_var, MV.MenuOpen)]
            + [(DAY_NIGHT_BP_PATH, DV.Clock)])
ROW = {s.column: i + 1 for i, s in enumerate(GS.GFX_STATS)}
STAT = {s.column: s for s in GS.GFX_STATS}
SL = unreal.SystemLibrary
HISM = unreal.HierarchicalInstancedStaticMeshComponent


def _live_hud(p, not_this=None):
    try:
        hud = p.hud()
    except Exception:
        return None
    if hud is None or (not_this is not None and hud == not_this):
        return None
    return hud if p.get(hud, PROFILE_CHECKED_VAR) else None


def _save_file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{GC.GFX_SAVE_SLOT}.sav")


def probe(p):
    backup = GS.CSV_PATH + ".probe-backup"
    shutil.copy2(GS.CSV_PATH, backup)
    save, kept = _save_file(), _save_file() + ".probe-backup"
    if os.path.exists(save):
        shutil.move(save, kept)
    try:
        yield from _run(p, backup)
    finally:
        shutil.move(backup, GS.CSV_PATH)
        if os.path.exists(save):
            os.remove(save)
        if os.path.exists(kept):
            shutil.move(kept, save)


def _reopened(p, hud):
    """Open the level again; wait for its new HUD and that HUD's first
    hand-over to the tuner. Yields; the new HUD is p.hud() afterwards."""
    unreal.GameplayStatics.open_level(p.world(), p.map_path, True, "")
    yield lambda: _live_hud(p, not_this=hud) is not None
    new = p.hud()
    yield lambda: (p.get(new, GC.GFX_APPLIED_VAR) == p.get(new, "Quality")
                   and not p.get(p.get(new, GC.TUNER_COMPONENT), GC.TUNER_DIRTY_VAR))
    yield 0.1


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
    """What the engine is given: the table's number x the stat's scale."""
    return GS.preset_rows()[preset][GS.index_of(stat.column)] * stat.scale


def _cvars_match(preset):
    want = _preset_cvars(preset)
    got = {name: _cvar(name) for name in want}
    return all(abs(got[n] - want[n]) < 1e-3 for n in want), f"{got} vs {want}"


def _run(p, built_csv):
    yield lambda: _live_hud(p) is not None
    # This game's BeginPlay read the player's own save. It is set aside now,
    # so the level reopened is a player with none.
    yield from _reopened(p, _live_hud(p))
    hud, cycle = _live_hud(p), p.actor_of(DAY_NIGHT_CLASS_PATH)
    default = GS.default_preset()
    p.check("with no graphics save the game starts on graphics_tuning.csv's default "
            f"preset ({GS.PRESET_LABELS[default]}), and writes no save for it",
            p.get(hud, "Quality") == default == 0 and not os.path.exists(_save_file()),
            f"Quality {p.get(hud, 'Quality')}, default {default}, "
            f"save on disk {os.path.exists(_save_file())}")
    grass = _tagged(p, GRASS_TAG)
    tiers = {t: _tagged(p, tier_tag(t)) for t in (1, 2, 3)}
    trees = _trees(p)
    ok, detail = _cvars_match(0)
    p.check("...Low, applied: its resolution, shadow quality, view "
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
    gm0, tm0 = _cell(p, 1, "grass_distance"), _cell(p, 1, "tree_distance")
    yield from _nudge(p, hud, ROW["grass_distance"], 1, times=5)
    g1, t1 = _distances(g), _distances(t)
    gm1 = _cell(p, 1, "grass_distance")
    up = gm1 / gm0
    p.check(f"grass draw distance {gm0:g} m -> {gm1:g} m scales a grass cell's fade by "
            "as much, moves its max draw distance as far as the fade's end, and leaves "
            "the trees alone",
            gm1 == gm0 + 5 * STAT["grass_distance"].step
            and abs(g1[0] - up * g0[0]) <= 3 and abs(g1[1] - up * g0[1]) <= 3
            and abs((g1[2] - g0[2]) - (g1[1] - g0[1])) <= 3 and t1 == t0,
            f"grass {g0} -> {g1}, tree {t0} -> {t1}")
    yield from _nudge(p, hud, ROW["tree_distance"], -1, times=5)
    g2, t2 = _distances(g), _distances(t)
    tm1 = _cell(p, 1, "tree_distance")
    down = tm1 / tm0
    p.check(f"tree draw distance {tm0:g} m -> {tm1:g} m does the same to a tree cell, "
            "and leaves the grass",
            tm1 == tm0 - 5 * STAT["tree_distance"].step
            and abs(t2[0] - down * t0[0]) <= 3 and abs(t2[1] - down * t0[1]) <= 3
            and abs((t2[2] - t0[2]) - (t2[1] - t0[1])) <= 3 and g2 == g1,
            f"tree {t0} -> {t2}, grass {g1} -> {g2}")
    # A metre is a metre: the engine multiplies every cull distance by the
    # view distance, so on the ground a fade ends at end x r.ViewDistanceScale.
    v0 = _cvar("r.ViewDistanceScale")
    yield from _nudge(p, hud, ROW["view_distance"], 1, times=2)
    v1 = _cvar("r.ViewDistanceScale")
    g3, t3 = _distances(g), _distances(t)
    on_ground = {"grass": (g2[1] * v0 / 100.0, g3[1] * v1 / 100.0, gm1),
                 "tree": (t2[1] * v0 / 100.0, t3[1] * v1 / 100.0, tm1)}
    p.check("view distance up two steps is r.ViewDistanceScale, and the grass and the "
            "trees still end as many metres off as their rows say",
            abs(v1 - (v0 + 2 * STAT["view_distance"].step * STAT["view_distance"].scale))
            < 1e-6 and g3[1] < g2[1] and t3[1] < t2[1]
            and all(abs(was - m) < 0.2 and abs(now - m) < 0.2
                    for was, now, m in on_ground.values()),
            f"view {v0:g} -> {v1:g}, metres (before, after, row) {on_ground}")

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
    p.check("SAVE DEFAULT writes all four presets into graphics_tuning.csv, Low (the "
            "picked one) still its default",
            p.get(hud, TAB.saved_var) and GS.default_preset() == 0
            and saved.get("Medium", {}).get("resolution_pct") == _cell(p, 1, "resolution_pct")
            and saved.get("Medium", {}).get("grass_layers") == 4.0
            and all(abs(saved.get(label, {}).get("sun_light", 0.0) - 150.0) < 1e-6
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
            and subject == GS.PRESET_LABELS[0] and abs(float(value) - 150.0) < 1e-6,
            f"{panel.get_visibility()} {subject!r} {value!r}")
    if os.environ.get("OW_GFX_SHOTS"):
        yield 0.5
        SL.execute_console_command(p.world(), "shot showui")
        p.note("shot showui: the M panel with the graphics tab open")
        yield 0.5
    yield from _custom(p, hud, built_csv)


def _custom(p, hud, built_csv):
    """Custom is the player's: picked and nudged, it is there after a reopen."""
    custom, medium = GS.CUSTOM_PRESET, 1
    step = STAT["resolution_pct"].step
    built = GS.preset_rows(built_csv)
    res = GS.index_of("resolution_pct")
    yield from _nudge(p, hud, 0, -1)                    # Left from Low wraps to Custom
    yield from _nudge(p, hud, ROW["resolution_pct"], -1, times=3)
    want = built[custom][res] - 3 * step
    p.check("Left from Low is Custom, and three resolution nudges down are its row's "
            "and the console's",
            p.get(hud, "Quality") == custom and _cell(p, custom, "resolution_pct") == want
            and abs(_cvar("r.ScreenPercentage") - want) < 1e-3,
            f"Quality {p.get(hud, 'Quality')}, cell {_cell(p, custom, 'resolution_pct')}, "
            f"console {_cvar('r.ScreenPercentage')}, want {want}")
    kept = unreal.GameplayStatics.load_game_from_slot(GC.GFX_SAVE_SLOT, GC.GFX_SAVE_USER_INDEX)
    table = [float(v) for v in kept.get_editor_property(GC.GFX_SAVE_TABLE_FIELD)] if kept else []
    p.check("the pick and the table are in the player's save at once",
            bool(kept) and kept.get_editor_property(GC.GFX_SAVE_QUALITY_FIELD) == custom
            and len(table) == GC.GFX_SAVE_TABLE_LEN
            and table[custom * GS.STAT_COUNT + res] == want,
            f"{_save_file()}: {os.path.exists(_save_file())}, {len(table)} numbers")
    p.set(hud, TAB.save_var, True)
    yield lambda: not p.get(hud, TAB.save_var)
    p.check("SAVE DEFAULT on Custom makes it the CSV's default preset, with its number",
            GS.default_preset() == custom
            and GS.read_table().get("Custom", {}).get("resolution_pct") == want,
            f"default {GS.default_preset()}, "
            f"{GS.read_table().get('Custom', {}).get('resolution_pct')}")
    session_medium = _cell(p, medium, "resolution_pct")
    p.set(hud, TAB.open_var, False)
    p.set(hud, "MenuOpen", False)

    yield from _reopened(p, hud)
    hud = p.hud()
    p.check("the level reopened is on Custom with the player's number, applied",
            p.get(hud, "Quality") == custom and p.get(hud, TAB.pick_var) == custom
            and _cell(p, custom, "resolution_pct") == want
            and abs(_cvar("r.ScreenPercentage") - want) < 1e-3,
            f"Quality {p.get(hud, 'Quality')}, cell {_cell(p, custom, 'resolution_pct')}, "
            f"console {_cvar('r.ScreenPercentage')}, want {want}")
    p.check("...and only Custom is the player's: Medium, nudged last session, is the "
            "built table's again",
            session_medium != built[medium][res]
            and _cell(p, medium, "resolution_pct") == built[medium][res],
            f"last session {session_medium}, now {_cell(p, medium, 'resolution_pct')}, "
            f"built {built[medium][res]}")


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
    p.check("sunlight 150% is the noon sun 1.5 times as bright, and moonlight 150% "
            "the midnight moon",
            all(was > 0.0 and abs(now / was - 1.5) < 0.02 for was, now in lights.values()),
            str(lights))

    for column in ("stars", "ambient_light", "fog_density", "sun_disc", "moon_disc"):
        yield from _nudge(p, hud, ROW[column], -1)
    yield from _nudge(p, hud, ROW["brightness"], 1)
    got = {STAT[c].target: p.get(cycle, STAT[c].target)
           for c in ("stars", "ambient_light", "fog_density", "sun_disc", "moon_disc")}
    p.check("stars, ambient light, fog density and the two discs, one step down, are "
            "90%: the cycle's multipliers at 0.9; brightness up is r.ExposureOffset",
            all(abs(v - 0.9) < 1e-6 for v in got.values())
            and abs(_cvar("r.ExposureOffset") - STAT["brightness"].step) < 1e-6,
            f"{got}, r.ExposureOffset {_cvar('r.ExposureOffset')}")
    p.check("a look number is written into every preset's row",
            all(abs(_cell(p, i, "sun_light") - 150.0) < 1e-6
                and abs(_cell(p, i, "stars") - 90.0) < 1e-6
                for i in range(len(GS.PRESET_LABELS))),
            str([_cell(p, i, "sun_light") for i in range(len(GS.PRESET_LABELS))]))
