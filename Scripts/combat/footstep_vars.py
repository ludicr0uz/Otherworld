"""BP_FootstepComponent's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE; a row with no type is a component, or a variable declared elsewhere.
"""

from uebp.vars import FLOAT, Var, array, obj

Travelled = Var("Travelled", FLOAT, 0.0)
StrideCm = Var("StrideCm", FLOAT)
# How loud a step is and how far it carries, as multipliers. 1.0 on every
# wanderer; the player's weapon component writes them from its stance
# every frame (weapon_component/stance.py), so this graph never learns
# what crouching is.
StepVolume = Var("StepVolume", FLOAT, 1.0)
StepNoise = Var("StepNoise", FLOAT, 1.0)
Sounds = Var("Sounds", array(obj("/Script/Engine.SoundBase")))

TABLE = (Travelled, StrideCm, StepVolume, StepNoise, Sounds)
