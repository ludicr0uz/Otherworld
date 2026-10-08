"""The player's motion-matching locomotion (task G3): its names, its one
switch and its numbers. Constants only; gas_locomotion.py authors the anim
Blueprint, verify/gas_locomotion.py checks it.

The player's base movement is Epic's Game Animation Sample ("GAS" here: its
motion matching, nothing to do with the ability system): the sample's
SandboxCharacter_CMC_ABP and its CHT_PoseSearchDatabases chooser, on the
sample's own mannequin (asset_pipeline/CLAUDE.md, "The skeleton bridge").
The anim Blueprint is patched where it lies, under /Game/GAS (a row of
gas_paths.PATCHED), and not copied: the sample's choosers take an object of
its class and of no other (a copy ran, read the character, and was handed no
database: "ContextData entry 0 expects an object of type
SandboxCharacter_CMC_ABP_C").
"""

from asset_pipeline.gas_bridge_paths import ABP_RETARGET_UEFN, PLAYER_MESH_GAS
from asset_pipeline.gas_paths import ABP as SAMPLE_ABP
from asset_pipeline.gas_paths import GAME_ROOT
from asset_pipeline.metahuman_paths import SOURCED_DIR
from uebp.vars import BOOL, FLOAT, VECTOR, Var

# THE SWITCH. True: the player wears the motion-matching anim Blueprint on the
# UEFN mannequin (combat/skin.SKIN_GAS). False: the mannequin and ABP_Unarmed,
# as before G3, with nothing else to change.
GAS_LOCOMOTION = True

# The weapon, hold, aim and hit-reaction layers on the motion-matching base.
# False for G3: they are still built, on the mannequin's rig and into
# ABP_Unarmed (combat/skin.player_skin), which the player no longer wears, and
# the graph's one montage slot is taken out of its pose line, so nothing the
# weapon component plays reaches the body. G4 puts them back over this base
# and removes the flag.
WEAPON_LAYERS = False

# What the player wears (git-ignored, as all of the sample is: a checkout
# without it wears the mannequin).
ABP_LOCOMOTION = SAMPLE_ABP
MESH = PLAYER_MESH_GAS
ABP_RETARGET = ABP_RETARGET_UEFN
# What else must be here for it to run.
CHOOSER = (f"{GAME_ROOT}/Characters/UEFN_Mannequin/Animations/MotionMatchingData/"
           "CHT_PoseSearchDatabases")

# The sample's foley component (its clips' foot, jump and land notifies look
# for it on the owner, and play their own sound in 2D when it is not there).
# The player wears it with a sound bank that holds no sound: the notifies fire
# into it and are silent, and the game's footsteps stay BP_FootstepComponent's.
# (No bank at all logs an "Accessed None" at every footfall: the component
# asks its bank before it asks whether there is one.)
FOLEY_COMPONENT_BP = f"{GAME_ROOT}/Audio/Foley/AC_FoleyEvents"
FOLEY_COMPONENT = "GasFoley"
FOLEY_BANK_VAR = "FoleyEventBank"
# The sample's bank, which the silent one is a copy of with its table emptied.
FOLEY_BANK_SOURCE = f"{GAME_ROOT}/Audio/Foley/DefaultFoleyEventAudioBank"
FOLEY_SILENT_BANK = f"{SOURCED_DIR}/DA_SilentFoleyBank"
FOLEY_BANK_TABLE = "Assets"

# The function that reads the character. As shipped it asks its pawn through
# an interface (BPI_SandboxCharacter_Pawn); as patched it reads the
# CharacterMovementComponent itself, on every machine, so the character
# Blueprint implements nothing and replicates nothing for it.
PROPERTIES_GRAPH = "Update_PropertiesFromCharacter"
PROPERTIES_VAR = "CharacterProperties"

# A gait is the pace the movement component is held to, not the speed of the
# moment: under this (the aim's walk is 200, the jog 400) it is a walk.
WALK_BELOW_CMS = 300.0
# How long after touching down the landing clips may be picked (the sample's
# character holds its JustLanded for this long).
JUST_LANDED_SECONDS = 0.3

# What the patch adds to the sample's variables: the landing, which the sample's
# character kept and its anim Blueprint only read.
WAS_FALLING = Var("OwWasFalling", BOOL, False)
FALL_VELOCITY = Var("OwFallVelocity", VECTOR)
LAND_VELOCITY = Var("OwLandVelocity", VECTOR)
LANDED_AT = Var("OwLandedAt", FLOAT, 0.0)
ADDED_VARS = (WAS_FALLING, FALL_VELOCITY, LAND_VELOCITY, LANDED_AT)

# The struct's fields (S_CharacterPropertiesForAnimation), as the Make node
# names its pins: each is followed by an id, so a pin is matched by its head.
FIELDS_SET = ("ActorTransform", "AimingRotation", "OrientationIntent", "Velocity",
              "InputAcceleration", "CurrentMaxAcceleration", "CurrentMaxDeceleration",
              "GroundNormal", "Gait", "MovementMode", "RotationMode", "InputState",
              "JustLanded", "LandVelocity")
# Left at the struct's defaults: Stance (Stand: the crouch is G5's), the
# sample's own MovementDirection, SteeringTime, GroundLocation and
# BasedMovementDelta (its character sets none of them either).

# The montage slot of the sample's graph, and the node it sits in front of.
SLOT_NAME = "DefaultSlot"
SLOT_CLASS = "AnimGraphNode_Slot"
AFTER_SLOT_CLASS = "AnimGraphNode_OffsetRootBone"

# THE SERVER BRANCH (task A4, server_anim_consts.py). The sample's graph ends
#   ... -> Remap Curves -> LocalToComponent -> Foot Placement -> Leg IK
#       -> ComponentToLocal -> Pose History -> Output
# and the feet are for the eye: Foot Placement and Leg IK trace the ground
# under both feet, as the old graph's Control Rig did. A dedicated server
# takes the pose from before them. Everything upstream moves a hit-box bone
# (the motion matching, the lean, the aim offset, the root's offset) and the
# pose history after it is what the next frame's search reads, so both are on
# both arms.
HISTORY_CLASS = "AnimGraphNode_PoseSearchHistoryCollector"
EYE_CLASSES = ("AnimGraphNode_ComponentToLocalSpace", "AnimGraphNode_LegIK",
               "AnimGraphNode_FootPlacement", "AnimGraphNode_LocalToComponentSpace")
