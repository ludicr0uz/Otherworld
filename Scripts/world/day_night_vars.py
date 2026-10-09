"""BP_DayNightCycle's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE; a row with no type is a component.
"""

from uebp.vars import BOOL, FLOAT, Var, obj
from world import world_config as cfg

# Components.
Sun = Var("Sun")
Moon = Var("Moon")
SkyLight = Var("SkyLight")
SkyDome = Var("SkyDome")
Fog = Var("Fog")
DayGrade = Var("DayGrade")

# The two lengths, Clock, the night's cold, the item highlight and RandomStart
# are Instance Editable, so a level can run a different day, or start at a set
# hour, without a rebuild.
DayLengthSeconds = Var("DayLengthSeconds", FLOAT, float(cfg.DAY_LENGTH_S))
NightLengthSeconds = Var("NightLengthSeconds", FLOAT, float(cfg.NIGHT_LENGTH_S))
Clock = Var("Clock", FLOAT, float(cfg.START_CLOCK_S))
# night_cold.py reads it.
NightTemperatureDropPerSecond = Var("NightTemperatureDropPerSecond", FLOAT,
                                    float(cfg.NIGHT_TEMPERATURE_DROP_PER_S))
# item_highlight.py reads it.
ItemHighlight = Var("ItemHighlight", FLOAT, float(cfg.ITEM_HIGHLIGHT))
CONFIG = (DayLengthSeconds, NightLengthSeconds, Clock, NightTemperatureDropPerSecond,
          ItemHighlight)
# BeginPlay picks Clock anywhere in the cycle.
RandomStart = Var("RandomStart", BOOL, bool(cfg.RANDOM_START))

# State the Tick graph writes.
DayAmount = Var("DayAmount", FLOAT)
IsDay = Var("IsDay", BOOL)
SkyMaterial = Var("SkyMaterial", obj("/Script/Engine.MaterialInstanceDynamic"))

# The look multipliers, all 1 as built: the Tick graph scales the sun's and
# the moon's light, the stars, the sky light, the fog's density and the two
# discs by them. The M panel's GRAPHICS SETTINGS tab writes them
# (graphics_menu/gfx_tuner_sky.py); nothing else does.
SunScale = Var("SunScale", FLOAT, 1.0)
MoonScale = Var("MoonScale", FLOAT, 1.0)
StarScale = Var("StarScale", FLOAT, 1.0)
AmbientScale = Var("AmbientScale", FLOAT, 1.0)
FogScale = Var("FogScale", FLOAT, 1.0)
SunDiscScale = Var("SunDiscScale", FLOAT, 1.0)
MoonDiscScale = Var("MoonDiscScale", FLOAT, 1.0)
LOOK_SCALES = (SunScale, MoonScale, StarScale, AmbientScale, FogScale, SunDiscScale,
               MoonDiscScale)

# In the order they have always been declared: the floats, the bools, the sky.
TABLE = (*CONFIG, DayAmount, *LOOK_SCALES, IsDay, RandomStart, SkyMaterial)
