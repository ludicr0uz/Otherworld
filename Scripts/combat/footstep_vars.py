"""BP_FootstepComponent's member variables, named once: each row is
the name, the pin type and the default (uebp/vars.py). The builder declares
TABLE; a row with no type is a component, or a variable declared elsewhere.
"""

from uebp.vars import BOOL, FLOAT, Var, array, obj

Travelled = Var("Travelled", FLOAT, 0.0)
StrideCm = Var("StrideCm", FLOAT)
# How loud a step is and how far it carries, as multipliers. 1.0 on every
# wanderer; the player's weapon component writes them from its stance
# every frame (weapon_component/stance.py), so this graph never learns
# what crouching is.
StepVolume = Var("StepVolume", FLOAT, 1.0)
StepNoise = Var("StepNoise", FLOAT, 1.0)
Sounds = Var("Sounds", array(obj("/Script/Engine.SoundBase")))
# Going through a bush rustles (Sound/sound_world.py): the ground covered
# since the bushes were last asked and how much of it between two askings,
# the takes, the
# meshes that are bushes, the level's bush components (found at BeginPlay)
# and whether this footfall is in one.
RustleSounds = Var("RustleSounds", array(obj("/Script/Engine.SoundBase")))
BushMeshes = Var("BushMeshes", array(obj("/Script/Engine.StaticMesh")))
Bushes = Var("Bushes", array(obj("/Script/Engine.InstancedStaticMeshComponent")))
InBush = Var("InBush", BOOL, False)
RustleTravelled = Var("RustleTravelled", FLOAT, 0.0)
RustleStrideCm = Var("RustleStrideCm", FLOAT)

TABLE = (Travelled, StrideCm, StepVolume, StepNoise, Sounds, RustleSounds, BushMeshes, Bushes, InBush,
         RustleTravelled, RustleStrideCm)
