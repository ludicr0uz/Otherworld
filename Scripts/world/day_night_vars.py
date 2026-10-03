"""BP_DayNightCycle's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE; a row with no type is a component, or a variable declared elsewhere.
"""

from uebp.vars import Var

Clock = Var("Clock")
DayAmount = Var("DayAmount")
DayGrade = Var("DayGrade")
DayLengthSeconds = Var("DayLengthSeconds")
Fog = Var("Fog")
Moon = Var("Moon")
NightLengthSeconds = Var("NightLengthSeconds")
SkyDome = Var("SkyDome")
SkyLight = Var("SkyLight")
Sun = Var("Sun")

TABLE = ()
