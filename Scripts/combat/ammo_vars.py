"""BP_AmmoPickup's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE; a row with no type is a component, or a variable declared elsewhere.
"""

from uebp.vars import BOOL, INT, Var

Shells = Var("Shells", INT)
Credited = Var("Credited", BOOL)

TABLE = (Shells, Credited)
