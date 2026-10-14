"""The graphics tuning table: what a quality preset is, number by number, and
graphics_tuning.csv beside this module, one row per preset.

A preset (Low / Medium / High / Custom) is one row of GFX_STATS. The M
panel's GRAPHICS SETTINGS tab (gfx_tune_*.py) shows the picked preset's
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

That one level was a row, "engine quality", until it was split: a row per
engine quality group (GROUP_STATS, each 0-3 and each starting at the level
its preset had), and the shadow group's three numbers that set the size of
the shadow maps as rows of their own (SHADOW_BY_LEVEL). A Custom row saved
before the split is spread over them (LEGACY_COLUMNS, migrate_row).

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
GROUP = "group"                  # one engine quality group: target is its
                                 # GameUserSettings setter
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


# The engine quality level each preset's groups default to (Medium was 1
# until G2).
_LEVELS = (0, 2, 3, 3)


def _group(column, label, setter):
    return Stat(column, f"{label} (0-3)", 1, 0, 3, int, GROUP, setter, _LEVELS)


# One row per group of BaseScalability.ini that has cvars. Not here: the
# resolution quality (its one cvar, r.ScreenPercentage, is the resolution
# row's) and the landscape quality (no section in the ini, no landscape).
# The view distance and anti-aliasing groups each hold cvars no row drives
# (r.SkeletalMeshLODBias; r.TemporalAA.Quality, r.FXAA.Quality, r.TSR.*), so
# they keep a row: without one those would stay wherever the session began.
GROUP_STATS = (
    _group("gi_quality", "Lumen GI quality", "SetGlobalIlluminationQuality"),
    _group("reflection_quality", "reflection quality", "SetReflectionQuality"),
    _group("shadow_detail", "shadow detail", "SetShadowQuality"),
    _group("post_quality", "post-processing", "SetPostProcessingQuality"),
    _group("effects_quality", "effects", "SetVisualEffectQuality"),
    _group("texture_quality", "textures", "SetTextureQuality"),
    _group("shading_quality", "shading", "SetShadingQuality"),
    _group("foliage_quality", "foliage", "SetFoliageQuality"),
    _group("aa_quality", "AA quality", "SetAntiAliasingQuality"),
    _group("character_lod", "character LOD", "SetViewDistanceQuality"),
)

# The shadow group's numbers that size the shadow maps, per engine quality
# level 0-3 (BaseScalability.ini, [ShadowQuality@N], UE 5.8). All three
# differ between the tiers. The sun's and the moon's cascades are sized by
# MaxCSMResolution; MaxResolution is every other light's (the fire's).
SHADOW_BY_LEVEL = {
    "shadow_resolution": (512, 1024, 2048, 2048),         # r.Shadow.MaxCSMResolution
    "light_shadow_resolution": (512, 1024, 1024, 2048),   # r.Shadow.MaxResolution
    "shadow_cascades": (1, 1, 4, 10),                     # r.Shadow.CSM.MaxCascades
}


def _by_level(column):
    return tuple(SHADOW_BY_LEVEL[column][level] for level in _LEVELS)


PERFORMANCE_STATS = GROUP_STATS + (
    Stat("resolution_pct", "resolution (%)", 5, 25, 200, int, CVAR,
         "r.ScreenPercentage", (70, 85, 100, 100)),
    Stat("shadow_quality", "shadow quality (0-5)", 1, 0, 5, int, CVAR,
         "r.ShadowQuality", (1, 2, 3, 3)),
    Stat("shadow_resolution", "shadow resolution (px)", 512, 512, 4096, int, CVAR,
         "r.Shadow.MaxCSMResolution", _by_level("shadow_resolution")),
    Stat("light_shadow_resolution", "lamp shadow resolution (px)", 256, 256, 4096, int,
         CVAR, "r.Shadow.MaxResolution", _by_level("light_shadow_resolution")),
    Stat("shadow_cascades", "shadow cascades (1-10)", 1, 1, 10, int, CVAR,
         "r.Shadow.CSM.MaxCascades", _by_level("shadow_cascades")),
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
    # programmable raster); past the distance an instance stands still. Only
    # Custom (once Ultra) pays for it.
    Stat("wind", "wind (0 off, 1 on)", 1, 0, 1, int, WIND, "", (0, 0, 0, 1)),
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


# A row as it was before the one engine quality row was split (a saved
# Custom row of that length is one of these: gfx_save.py).
LEGACY_LEVEL_COLUMN = "engine_quality"
LEGACY_COLUMNS = (
    LEGACY_LEVEL_COLUMN, "resolution_pct", "shadow_quality", "shadow_distance",
    "view_distance", "grass_distance", "tree_distance", "grass_layers", "grass_shadows",
    "leaf_cutouts", "tree_coarseness", "fog", "volumetric_fog", "global_illumination",
    "reflections", "anti_aliasing", "wind", "wind_distance", "brightness", "sun_light",
    "sun_disc", "moon_light", "moon_disc", "stars", "ambient_light", "fog_density",
    "wind_strength", "wind_speed")
LEGACY_STAT_COUNT = len(LEGACY_COLUMNS)
LEGACY_LEVEL_INDEX = LEGACY_COLUMNS.index(LEGACY_LEVEL_COLUMN)
# In SHADOW_BY_LEVEL's order: the stats read off the old level by a table.
BY_LEVEL_COLUMNS = tuple(SHADOW_BY_LEVEL)
LEVEL_COUNT = len(next(iter(SHADOW_BY_LEVEL.values())))

assert LEGACY_STAT_COUNT != STAT_COUNT
assert all(s.column in LEGACY_COLUMNS or s.how == GROUP or s.column in SHADOW_BY_LEVEL
           for s in GFX_STATS)


def legacy_sources():
    """For each stat of today's row, the cell of a legacy row it is read
    from: its own old column, or the old engine quality (a group's level; and
    the by-level stats, which by_level_values() then turns into their number)."""
    return [LEGACY_COLUMNS.index(s.column) if s.column in LEGACY_COLUMNS
            else LEGACY_LEVEL_INDEX for s in GFX_STATS]


def by_level_values():
    """SHADOW_BY_LEVEL flattened: values[k * LEVEL_COUNT + level] for the
    k-th of BY_LEVEL_COLUMNS."""
    return [float(v) for column in BY_LEVEL_COLUMNS for v in SHADOW_BY_LEVEL[column]]


def migrate_row(old):
    """A legacy row as today's: what gfx_save's load does in the HUD's graph."""
    row = [float(old[src]) for src in legacy_sources()]
    level = max(0, min(LEVEL_COUNT - 1, int(round(old[LEGACY_LEVEL_INDEX]))))
    for k, column in enumerate(BY_LEVEL_COLUMNS):
        row[index_of(column)] = by_level_values()[k * LEVEL_COUNT + level]
    return row


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
