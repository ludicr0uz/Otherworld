"""BP_BloodSplash's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE; a row with no type is a component, or a variable declared elsewhere.
"""

from uebp.vars import FLOAT, VECTOR, Var, array, obj

Age = Var("Age", FLOAT)
Blobs = Var("Blobs", array(obj("/Script/Engine.StaticMeshComponent")))
# Launch velocity and untouched size, one entry per component, filled in the
# same loop that fills Blobs -- so the three arrays are in step by
# construction and not by an assumption about component ordering.
Velocity = Var("Velocity", array(VECTOR))
Size = Var("Size", array(FLOAT))
# Gravity, rotated into the actor's own frame once. The actor is spawned
# facing the hit normal and never turns, so this cannot go stale, and doing
# it here keeps a transform inverse out of the per-frame path.
Fall = Var("Fall", VECTOR)

TABLE = (Age, Blobs, Velocity, Size, Fall)
