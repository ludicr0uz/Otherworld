"""The graphics tuning table: what a quality preset is, number by number, and
graphics_tuning.csv beside this module, one row per preset.

A preset (Low / Medium / High / Custom) is one row of GFX_STATS. The M
panel's GRAPHICS TUNING tab (gfx_tune_*.py) shows the picked preset's
row and changes a number live; its SAVE DEFAULT row saves the whole table to
the CSV, and the next build_graphics_menu.py bakes it into the HUD's table,
so git shows what moved. BP_GraphicsTuner (gfx_tuner.py) is what turns a row
into the engine's state.

The CSV is the defaults, all of them: each preset's numbers, and in its
"default" column (1 on one row) the preset a player with no save starts on.
Custom is the player's own row: the CSV has what it starts as, and what the
player makes of it is kept between sessions (gfx_save.py), with the preset
they picked. Custom took Ultra's place and its defaults.

Two kinds of row:

  performance   each preset has its own number (what makes Low cheaper)
  look          one number for all four presets: brightness, the sun, the
                moon, the stars, the fog, the wind's strength and speed. A nudge writes it into every
                preset's row, and the CSV reads it from the first row.

The defaults are what the presets did before the tab existed: the engine's
scalability level (High and Custom both run Epic, 3; BaseScalability.ini's
view and shadow distance scales and volumetric fog for that level), the two
console overrides, and the grass layers and grass lighting per preset.

Units are the ones a person reads, not the engine's. A scale is a
percentage (100 is the engine's own), and Stat.scale (0.01) is what turns
it back into the number a cvar or the cycle takes. The grass and tree draw
distances are metres: how far off the grass's base layer (the thicker
layers and the bushes keep their proportion to it) and the trees have faded
out. The engine multiplies every cull distance by the view distance, so the
tuner divides it back out (gfx_tuner_foliage.py): 28 m is 28 m at any view
distance. The defaults are the levels' own distances (FULL_VIEW_M, at a
view distance of 100%) at each preset's view distance.

Pure Python (no unreal import): the game's save and the probe import it.
"""

import csv
import os
from collections import namedtuple

from forest_generator.grass_cells import GRASS_TIERS
from forest_generator.tree_cells import TREE_CULL_END_CM
from forest_generator.wind import MAX_STRENGTH, PARAM_SPEED, PARAM_STRENGTH

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "graphics_tuning.csv")
PRESET_COLUMN = "preset"
PRESET_LABELS = ("Low", "Medium", "High", "Custom")
# The player's own preset, kept between sessions (gfx_save.py).
CUSTOM_PRESET = PRESET_LABELS.index("Custom")
# 1 on the row of the preset a player with no save starts on.
DEFAULT_COLUMN = "default"
FALLBACK_DEFAULT_PRESET = 0  # Low: no CSV, or no row marked

# How BP_GraphicsTuner applies a stat (Stat.how); Stat.target says to what.
LEVEL = "level"                  # GameUserSettings' overall scalability level
CVAR = "cvar"                    # a console variable, named by target
GRASS_DISTANCE = "grass_distance"    # the grass and bush cells' cull distances
TREE_DISTANCE = "tree_distance"      # the tree cells' cull distances
GRASS_LAYERS = "grass_layers"    # how many density tiers are shown
GRASS_SHADOWS = "grass_shadows"  # grass and bushes cast shadows and take GI
CYCLE = "cycle"                  # a BP_DayNightCycle variable, named by target
WIND = "wind"                    # the grass and tree cells' world-position offset
WIND_PARAM = "wind_param"        # an MPC_Wind scalar, named by target

# column: the CSV's; label: the tab's row; step, lo, hi: one nudge and the
# limits; kind: int stats are rounded on the way out; defaults: per preset;
# scale: the table's number x scale is what the engine is given.
Stat = namedtuple("Stat", "column label step lo hi kind how target defaults scale",
                  defaults=(1.0,))
PERCENT = 0.01


def _same(value):
    return (value,) * len(PRESET_LABELS)


# A preset p draws every grass tier whose min_preset is at most p.
_LAYERS = tuple(sum(1 for t in GRASS_TIERS if t.min_preset <= p)
                for p in range(len(PRESET_LABELS)))

# Each preset's view distance, and how far the level's own cull distances
# reach at 100% of it: the grass's base tier and the trees, in metres.
_VIEW_PCT = (40, 60, 100, 100)
FULL_VIEW_M = {"grass_distance": GRASS_TIERS[0].cull_end_cm / 100.0,
               "tree_distance": TREE_CULL_END_CM / 100.0}


def _metres(column):
    return tuple(round(FULL_VIEW_M[column] * pct * PERCENT) for pct in _VIEW_PCT)


PERFORMANCE_STATS = (
    Stat("engine_quality", "engine quality (0-3)", 1, 0, 3, int, LEVEL, "", (0, 1, 3, 3)),
    Stat("resolution_pct", "resolution (%)", 5, 25, 200, int, CVAR,
         "r.ScreenPercentage", (70, 85, 100, 100)),
    Stat("shadow_quality", "shadow quality (0-5)", 1, 0, 5, int, CVAR,
         "r.ShadowQuality", (1, 2, 3, 3)),
    Stat("shadow_distance", "shadow distance (%)", 10, 10, 300, int, CVAR,
         "r.Shadow.DistanceScale", (60, 70, 100, 100), PERCENT),
    Stat("view_distance", "view distance (%)", 10, 10, 300, int, CVAR,
         "r.ViewDistanceScale", _VIEW_PCT, PERCENT),
    Stat("grass_distance", "grass draw distance (m)", 2, 10, 300, int,
         GRASS_DISTANCE, "", _metres("grass_distance")),
    Stat("tree_distance", "tree draw distance (m)", 10, 30, 1200, int,
         TREE_DISTANCE, "", _metres("tree_distance")),
    Stat("grass_layers", f"grass density (layers 1-{len(GRASS_TIERS)})", 1, 1,
         len(GRASS_TIERS), int, GRASS_LAYERS, "", _LAYERS),
    Stat("grass_shadows", "grass shadows (0 off, 1 on)", 1, 0, 1, int, GRASS_SHADOWS, "",
         (0, 0, 0, 1)),
    # Leaves are masked cards: off, every leaf card draws solid (cheaper).
    Stat("leaf_cutouts", "leaf cut-outs (0 off, 1 on)", 1, 0, 1, int, CVAR,
         "r.Nanite.ProgrammableRaster", _same(1)),
    # The triangle edge Nanite aims for, in pixels: higher is a coarser canopy.
    Stat("tree_coarseness", "tree coarseness (px)", 0.25, 0.25, 8.0, float, CVAR,
         "r.Nanite.MaxPixelsPerEdge", _same(1.0)),
    Stat("fog", "fog (0 off, 1 on)", 1, 0, 1, int, CVAR, "r.Fog", _same(1)),
    Stat("volumetric_fog", "volumetric fog (0 off, 1 on)", 1, 0, 1, int, CVAR,
         "r.VolumetricFog", (0, 0, 1, 1)),
    Stat("global_illumination", "GI (0 off, 1 Lumen)", 1, 0, 1, int, CVAR,
         "r.DynamicGlobalIlluminationMethod", _same(1)),
    Stat("reflections", "reflections (0, 1 Lumen, 2 SSR)", 1, 0, 2, int, CVAR,
         "r.ReflectionMethod", _same(1)),
    Stat("anti_aliasing", "AA (0, 1 FXAA, 2 TAA, 4 TSR)", 1, 0, 4, int, CVAR,
         "r.AntiAliasingMethod", _same(2)),
    # Wind is world-position offset: off, the cells skip it (and Nanite its
    # programmable raster); past the distance an instance stands still.
    Stat("wind", "wind (0 off, 1 on)", 1, 0, 1, int, WIND, "", _same(1)),
    Stat("wind_distance", "wind distance (m)", 10, 10, 500, int, WIND, "",
         (50, 80, 120, 200)),
)
LOOK_STATS = (
    # A cheat cvar: it moves in the editor binary, not in a shipping build.
    Stat("brightness", "brightness (EV)", 0.25, -5.0, 5.0, float, CVAR,
         "r.ExposureOffset", _same(0.0)),
    Stat("sun_light", "sunlight (%)", 10, 0, 500, int, CYCLE, "SunScale", _same(100),
         PERCENT),
    Stat("sun_disc", "sun disc (%)", 10, 0, 500, int, CYCLE, "SunDiscScale",
         _same(100), PERCENT),
    Stat("moon_light", "moonlight (%)", 10, 0, 1000, int, CYCLE, "MoonScale",
         _same(100), PERCENT),
    Stat("moon_disc", "moon disc (%)", 10, 0, 500, int, CYCLE, "MoonDiscScale",
         _same(100), PERCENT),
    Stat("stars", "stars (%)", 10, 0, 500, int, CYCLE, "StarScale", _same(100),
         PERCENT),
    Stat("ambient_light", "ambient light (%)", 10, 0, 500, int, CYCLE,
         "AmbientScale", _same(100), PERCENT),
    Stat("fog_density", "fog density (%)", 10, 0, 1000, int, CYCLE, "FogScale",
         _same(100), PERCENT),
    # How far the grass and the trees bend, and how fast (forest_generator/wind.py).
    Stat("wind_strength", "wind strength (%)", 10, 0, round(MAX_STRENGTH * 100), int,
         WIND_PARAM, PARAM_STRENGTH, _same(100), PERCENT),
    Stat("wind_speed", "wind speed (%)", 10, 10, 500, int, WIND_PARAM, PARAM_SPEED,
         _same(100), PERCENT),
)
GFX_STATS = PERFORMANCE_STATS + LOOK_STATS
GFX_COLUMNS = tuple(s.column for s in GFX_STATS)
STAT_COUNT = len(GFX_STATS)
# The look stats are the tail of a row: index LOOK_FROM and up.
LOOK_FROM = len(PERFORMANCE_STATS)

assert len(set(GFX_COLUMNS)) == STAT_COUNT and DEFAULT_COLUMN not in GFX_COLUMNS
assert all(len(s.defaults) == len(PRESET_LABELS) and s.lo <= min(s.defaults)
           and max(s.defaults) <= s.hi for s in GFX_STATS)
assert all(len(set(s.defaults)) == 1 for s in LOOK_STATS)


def index_of(column):
    return GFX_COLUMNS.index(column)


def stats_by(how):
    """[(index, stat)] of every stat applied one way."""
    return [(i, s) for i, s in enumerate(GFX_STATS) if s.how == how]


def read_table(path=CSV_PATH):
    """{preset: {column: value}} for the known presets and columns; {} with
    no file."""
    if not os.path.exists(path):
        return {}
    table = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            preset = (row.get(PRESET_COLUMN) or "").strip()
            if preset in PRESET_LABELS:
                table[preset] = {c: float(v) for c, v in row.items()
                                 if c in GFX_COLUMNS and (v or "").strip()}
    return table


def preset_rows(path=CSV_PATH):
    """One list of STAT_COUNT floats per preset: the defaults with the CSV
    laid over them, and each look stat as the first preset has it."""
    table = read_table(path)
    rows = [[float(table.get(label, {}).get(s.column, s.defaults[p])) for s in GFX_STATS]
            for p, label in enumerate(PRESET_LABELS)]
    for row in rows[1:]:
        row[LOOK_FROM:] = rows[0][LOOK_FROM:]
    return rows


def default_preset(path=CSV_PATH):
    """The index of the preset the CSV marks as the default: the first row
    whose "default" column is not 0."""
    if os.path.exists(path):
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                preset = (row.get(PRESET_COLUMN) or "").strip()
                mark = (row.get(DEFAULT_COLUMN) or "").strip()
                if preset in PRESET_LABELS and mark and float(mark) != 0.0:
                    return PRESET_LABELS.index(preset)
    return FALLBACK_DEFAULT_PRESET


def table_values(path=CSV_PATH):
    """preset_rows(), flattened: values[preset * STAT_COUNT + stat]."""
    return [v for row in preset_rows(path) for v in row]


def format_value(value, kind):
    """Ints bare, floats without float noise (0.1 stepped three times is 0.3)."""
    if kind is int:
        return str(int(round(value)))
    return f"{round(float(value), 6):g}"


def write_table(rows, default=None, path=CSV_PATH):
    """rows: one list of STAT_COUNT numbers per preset, in PRESET_LABELS order.
    default: the preset to mark as the default; None keeps the file's."""
    if default is None:
        default = default_preset(path)
    with open(path, "w", newline="") as f:
        out = csv.writer(f, lineterminator="\n")
        out.writerow((PRESET_COLUMN, DEFAULT_COLUMN) + GFX_COLUMNS)
        for p, (label, row) in enumerate(zip(PRESET_LABELS, rows)):
            out.writerow([label, int(p == default)]
                         + [format_value(v, s.kind) for v, s in zip(row, GFX_STATS)])
