"""BP_Settings's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE; a row with no type is a component, or a variable declared elsewhere.
"""

from uebp.vars import BOOL, FLOAT, Var, array, struct
from combat.tuning import COMBAT

MouseSensitivity = Var("MouseSensitivity", FLOAT, COMBAT.mouse_sensitivity_default)
# The sniper scope's own multiplier, on top of the zoom's slowdown. A save
# written before this field existed loads it as the default below.
ScopeSensitivity = Var("ScopeSensitivity", FLOAT, COMBAT.ads_scope_sens_scale)
# Indexed, not a struct per bind and not seven separate variables: the
# settings screen walks the rows with one ForEachLoop and one Array_Set, and
# BIND_VARS is what says which index means which action.
Binds = Var("Binds", array(struct("/Script/InputCore.Key")))
# Whether the developer overlays (tracers, wanderer numbers)
# are on. ON by default, and a save written before this field existed loads
# it as the default too. The HUD copies it onto the GameMode's DebugMode at
# BeginPlay and writes it back whenever D flips it.
DebugMode = Var("DebugMode", BOOL, True)

TABLE = (MouseSensitivity, ScopeSensitivity, Binds, DebugMode)
