"""BP_ForestWandererAI's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE; a row with no type is a component, or a variable declared elsewhere.
"""

from uebp.vars import FLOAT, Var

# Each NPC's swing timer. Zero is the right default -- it means "may attack
# immediately" -- which is just as well, since add_member_variable's own
# default-value argument silently does not apply (see CLAUDE.md).
NextAttackTime = Var("NextAttackTime", FLOAT)

TABLE = (NextAttackTime,)
