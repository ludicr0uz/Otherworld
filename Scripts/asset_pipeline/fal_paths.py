"""Where the Free Animation Library lies and which of its clips the game
plays.  Pure names, importable outside the editor.

The pack is a Fab pack the user adds at ``/Game/FreeAnimationLibrary``
(fab_library.json has the entry, nothing of it is committed).  Its clips are
on its own copy of the UE5 mannequin, so import_fal.py retargets each row of
CLIPS onto the player's skeleton (SK_UEFN_Mannequin) into UEFN_DIR, where
combat/skin.SKIN_GAS looks.  The copy is in place (the plain retargeter drops
the root's travel) and its IK feet are keyed onto its feet (ik_follow.py).
"""

from asset_pipeline.gas_bridge_paths import PLAYER_FAMILY

GAME_ROOT = "/Game/FreeAnimationLibrary"
CONTENT_DIR = "Content/FreeAnimationLibrary"

MANNEQUIN = f"{GAME_ROOT}/Demo/Characters/Mannequins/Meshes"
SKELETON = f"{MANNEQUIN}/SK_Mannequin"
# The mesh the clips are read off: a clip is retargeted as shown on a mesh,
# and a mesh's reference pose is not its skeleton's.
SOURCE_MESH = f"{MANNEQUIN}/SKM_Manny_Simple"
PRONE = f"{GAME_ROOT}/Animations/UnarmedProne"

# Written by import_fal.py, beside the pack and as little committed as it.
RIG_DIR = f"{GAME_ROOT}/Rig"
IK_FAL = f"{RIG_DIR}/IK_FAL_Mannequin_Source"
RTG_UEFN_FROM_FAL = f"{RIG_DIR}/RTG_UEFN_from_FAL"
UEFN_DIR = f"{GAME_ROOT}/{PLAYER_FAMILY}"
UEFN_PREFIX = f"A_{PLAYER_FAMILY}_"

# Lying down (P1): propped on the elbows, a 1 s loop, and the crawl forward,
# a 1 s loop that carries PRONE_FWD_TRAVEL_CM on its root bone.
PRONE_IDLE = f"{PRONE}/anim_Prone_Idle"
PRONE_FWD = f"{PRONE}/anim_Prone_Fwd_Loop_R"
# What the pack's forward loop covers in its second, read off its root bone
# (17.56 -> 80.59 cm): what combat/stance_clips.py picks the play rate from.
PRONE_FWD_TRAVEL_CM = 63.0

# The crawl by direction (P2): a loop each to the side and on the forward
# diagonals.  Backwards is the forward ones played in reverse (the pack's own
# three backward clips are those with the asset's rate scale at -1, so they
# are not imported): back is PRONE_FWD, back and left PRONE_FWD_RIGHT, back
# and right PRONE_FWD_LEFT.
PRONE_LEFT = f"{PRONE}/anim_Prone_Left_loop"
PRONE_RIGHT = f"{PRONE}/anim_Prone_Right_Loop"
PRONE_FWD_LEFT = f"{PRONE}/anim_Prone_Fwd_Left_Loop"
PRONE_FWD_RIGHT = f"{PRONE}/anim_Prone_Fwd_Right_Loop"
# What each covers and in how long, read off the pack's rig: the side loops
# 38.4 cm in 2.27 s (two shuffles; anim_Prone_Left_loop's root bone goes
# right as the right one's does and its body 73 cm left off it, so the 38.4
# is its pelvis's), the diagonals 52.3 cm in 2.0 s, 37 degrees off forward
# (31.4 cm across, 41.9 on).
PRONE_SIDE_TRAVEL_CM, PRONE_SIDE_S = 38.4, 2.27
PRONE_DIAG_TRAVEL_CM, PRONE_DIAG_S = 52.3, 2.0

# Every clip of the pack the game plays.  A later one is a row here and a
# re-run of import_fal.py.
CLIPS = (PRONE_IDLE, PRONE_FWD, PRONE_LEFT, PRONE_RIGHT, PRONE_FWD_LEFT, PRONE_FWD_RIGHT)


def uefn_clip(source):
    """Where one of the pack's clips lands on the UEFN skeleton."""
    return f"{UEFN_DIR}/{UEFN_PREFIX}{source.rsplit('/', 1)[1]}"
