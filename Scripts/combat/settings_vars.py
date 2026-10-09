"""BP_Settings's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE; a row with no type is a component, or a variable declared elsewhere.
"""

from uebp.vars import BOOL, FLOAT, INT, STRING, Var, array, struct
from combat.difficulty import DIFFICULTY_VAR
from combat.tuning import COMBAT
from net.session_consts import DEFAULT_SERVER_ADDRESS, SERVER_ADDRESS_VAR

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

# The server the title's Multiplayer page joins, as the player last typed it
# (graphics_menu/mode_draw.py). Local settings, not the character's profile;
# a save written before this field existed loads it as the default.
ServerAddress = Var(SERVER_ADDRESS_VAR, STRING, DEFAULT_SERVER_ADDRESS)
# The difficulty, an index into combat.difficulty.DIFFICULTY_LABELS. A save
# written before this field existed loads it as the default (EASY), which
# the builder writes.
Difficulty = Var(DIFFICULTY_VAR, INT)

TABLE = (MouseSensitivity, ScopeSensitivity, Binds, DebugMode, ServerAddress, Difficulty)
