"""The graphics tuning table: what a quality preset is, number by number, and
graphics_tuning.csv beside this module, one row per preset.

A preset (Low / Medium / High / Ultra) is one row of GFX_STATS. The M
panel's GRAPHICS TUNING tab ([P], gfx_tune_*.py) shows the picked preset's
row, changes a number live and saves the whole table to the CSV; the next
build_graphics_menu.py bakes it into the HUD's table, so git shows what moved.
BP_GraphicsTuner (gfx_tuner.py) is what turns a row into the engine's state.

Two kinds of row:

  performance   each preset has its own number (what makes Low cheaper)
  look          one number for all four presets: brightness, the sun, the
                moon, the stars, the fog. A nudge writes it into every
                preset's row, and the CSV reads it from the first row.

The defaults are what the presets did before the tab existed: the engine's
scalability level (High and Ultra both run Epic, 3; BaseScalability.ini's
view and shadow distance scales and volumetric fog for that level), the two
console overrides, and the grass layers and grass lighting per preset.

Pure Python (no unreal import): the game's save and the probe import it.
"""

import csv
import os
from collections import namedtuple

from forest_generator.grass_cells import GRASS_TIERS

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "graphics_tuning.csv")
PRESET_COLUMN = "preset"
PRESET_LABELS = ("Low", "Medium", "High", "Ultra")

# How BP_GraphicsTuner applies a stat (Stat.how); Stat.target says to what.
LEVEL = "level"                  # GameUserSettings' overall scalability level
CVAR = "cvar"                    # a console variable, named by target
GRASS_DISTANCE = "grass_distance"    # the grass and bush cells' cull distances
TREE_DISTANCE = "tree_distance"      # the tree cells' cull distances
GRASS_LAYERS = "grass_layers"    # how many density tiers are shown
GRASS_SHADOWS = "grass_shadows"  # grass and bushes cast shadows and take GI
CYCLE = "cycle"                  # a BP_DayNightCycle variable, named by target

# column: the CSV's; label: the tab's row; step, lo, hi: one nudge and the
# limits; kind: int stats are rounded on the way out; defaults: per preset.
Stat = namedtuple("Stat", "column label step lo hi kind how target defaults")


def _same(value):
    return (value,) * len(PRESET_LABELS)


# A preset p draws every grass tier whose min_preset is at most p.
_LAYERS = tuple(sum(1 for t in GRASS_TIERS if t.min_preset <= p)
                for p in range(len(PRESET_LABELS)))

PERFORMANCE_STATS = (
    Stat("engine_quality", "engine quality (0-3)", 1, 0, 3, int, LEVEL, "", (0, 1, 3, 3)),
    Stat("resolution_pct", "resolution (%)", 5, 25, 200, int, CVAR,
         "r.ScreenPercentage", (70, 85, 100, 100)),
    Stat("shadow_quality", "shadow quality (0-5)", 1, 0, 5, int, CVAR,
         "r.ShadowQuality", (1, 2, 3, 3)),
    Stat("shadow_distance", "shadow distance (x)", 0.1, 0.1, 3.0, float, CVAR,
         "r.Shadow.DistanceScale", (0.6, 0.7, 1.0, 1.0)),
    Stat("view_distance", "view distance (x)", 0.1, 0.1, 3.0, float, CVAR,
         "r.ViewDistanceScale", (0.4, 0.6, 1.0, 1.0)),
    Stat("grass_distance", "grass draw distance (x)", 0.1, 0.1, 4.0, float,
         GRASS_DISTANCE, "", _same(1.0)),
    Stat("tree_distance", "tree draw distance (x)", 0.1, 0.1, 4.0, float,
         TREE_DISTANCE, "", _same(1.0)),
    Stat("grass_layers", f"grass density (layers 1-{len(GRASS_TIERS)})", 1, 1,
         len(GRASS_TIERS), int, GRASS_LAYERS, "", _LAYERS),
    Stat("grass_shadows", "grass shadows (0/1)", 1, 0, 1, int, GRASS_SHADOWS, "",
         (0, 0, 0, 1)),
    # Leaves are masked cards: off, every leaf card draws solid (cheaper).
    Stat("leaf_cutouts", "leaf cut-outs (0/1)", 1, 0, 1, int, CVAR,
         "r.Nanite.ProgrammableRaster", _same(1)),
    # The triangle edge Nanite aims for, in pixels: higher is a coarser canopy.
    Stat("tree_coarseness", "tree coarseness (px)", 0.25, 0.25, 8.0, float, CVAR,
         "r.Nanite.MaxPixelsPerEdge", _same(1.0)),
    Stat("fog", "fog (0/1)", 1, 0, 1, int, CVAR, "r.Fog", _same(1)),
    Stat("volumetric_fog", "volumetric fog (0/1)", 1, 0, 1, int, CVAR,
         "r.VolumetricFog", (0, 0, 1, 1)),
    Stat("global_illumination", "GI (0 off, 1 Lumen)", 1, 0, 1, int, CVAR,
         "r.DynamicGlobalIlluminationMethod", _same(1)),
    Stat("reflections", "reflections (0, 1 Lumen, 2 SSR)", 1, 0, 2, int, CVAR,
         "r.ReflectionMethod", _same(1)),
    Stat("anti_aliasing", "AA (0, 1 FXAA, 2 TAA, 4 TSR)", 1, 0, 4, int, CVAR,
         "r.AntiAliasingMethod", _same(2)),
)
LOOK_STATS = (
    # A cheat cvar: it moves in the editor binary, not in a shipping build.
    Stat("brightness", "brightness (EV)", 0.25, -5.0, 5.0, float, CVAR,
         "r.ExposureOffset", _same(0.0)),
    Stat("sun_light", "sunlight (x)", 0.1, 0.0, 5.0, float, CYCLE, "SunScale", _same(1.0)),
    Stat("sun_disc", "sun disc (x)", 0.1, 0.0, 5.0, float, CYCLE, "SunDiscScale",
         _same(1.0)),
    Stat("moon_light", "moonlight (x)", 0.1, 0.0, 10.0, float, CYCLE, "MoonScale",
         _same(1.0)),
    Stat("moon_disc", "moon disc (x)", 0.1, 0.0, 5.0, float, CYCLE, "MoonDiscScale",
         _same(1.0)),
    Stat("stars", "stars (x)", 0.1, 0.0, 5.0, float, CYCLE, "StarScale", _same(1.0)),
    Stat("ambient_light", "ambient light (x)", 0.1, 0.0, 5.0, float, CYCLE,
         "AmbientScale", _same(1.0)),
    Stat("fog_density", "fog density (x)", 0.1, 0.0, 10.0, float, CYCLE, "FogScale",
         _same(1.0)),
)
GFX_STATS = PERFORMANCE_STATS + LOOK_STATS
GFX_COLUMNS = tuple(s.column for s in GFX_STATS)
STAT_COUNT = len(GFX_STATS)
# The look stats are the tail of a row: index LOOK_FROM and up.
LOOK_FROM = len(PERFORMANCE_STATS)

assert len(set(GFX_COLUMNS)) == STAT_COUNT
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


def table_values(path=CSV_PATH):
    """preset_rows(), flattened: values[preset * STAT_COUNT + stat]."""
    return [v for row in preset_rows(path) for v in row]


def format_value(value, kind):
    """Ints bare, floats without float noise (0.1 stepped three times is 0.3)."""
    if kind is int:
        return str(int(round(value)))
    return f"{round(float(value), 6):g}"


def write_table(rows, path=CSV_PATH):
    """rows: one list of STAT_COUNT numbers per preset, in PRESET_LABELS order."""
    with open(path, "w", newline="") as f:
        out = csv.writer(f, lineterminator="\n")
        out.writerow((PRESET_COLUMN,) + GFX_COLUMNS)
        for label, row in zip(PRESET_LABELS, rows):
            out.writerow([label] + [format_value(v, s.kind)
                                    for v, s in zip(row, GFX_STATS)])
