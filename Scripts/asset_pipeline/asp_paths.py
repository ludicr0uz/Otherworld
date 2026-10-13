"""Where the Animation Starter Pack lies and which of its clips the game
plays.  Pure names, importable outside the editor.

The pack is a Fab pack the user adds at ``/Game/AnimStarterPack``
(fab_library.json has the entry, nothing of it is committed).  Its clips are
on the UE4 mannequin, which is named the mannequin's way but has three spine
joints and one neck joint (CHAINS), so import_asp.py retargets each row of
CLIPS onto the player's skeleton (SK_UEFN_Mannequin) into UEFN_DIR, where
combat/skin.SKIN_GAS looks.  The copy is in place (the plain retargeter drops
the root's travel).
"""

from asset_pipeline.gas_bridge_paths import PLAYER_FAMILY
from asset_pipeline.rig_chains import CHAINS_MANNEQUIN

GAME_ROOT = "/Game/AnimStarterPack"
CONTENT_DIR = "Content/AnimStarterPack"

MANNEQUIN = f"{GAME_ROOT}/UE4_Mannequin/Mesh"
SKELETON = f"{MANNEQUIN}/UE4_Mannequin_Skeleton"
# The mesh the clips are read off: a clip is retargeted as shown on a mesh,
# and a mesh's reference pose is not its skeleton's.
SOURCE_MESH = f"{MANNEQUIN}/SK_Mannequin"

# The UE4 mannequin's chains: the UE5 one's under the same names (so the
# retargeter maps them onto the player's by exact match), with the shorter
# spine and neck.
CHAINS = {**CHAINS_MANNEQUIN,
          "Spine": ("spine_01", "spine_03"),
          "Neck": ("neck_01", "neck_01")}

# Written by import_asp.py, beside the pack and as little committed as it.
RIG_DIR = f"{GAME_ROOT}/Rig"
IK_ASP = f"{RIG_DIR}/IK_ASP_Mannequin_Source"
RTG_UEFN_FROM_ASP = f"{RIG_DIR}/RTG_UEFN_from_ASP"
UEFN_DIR = f"{GAME_ROOT}/{PLAYER_FAMILY}"
UEFN_PREFIX = f"A_{PLAYER_FAMILY}_"

# A long gun's carry (the rifle, the sniper and the shotgun while nothing
# holds the gun up: combat/carry_pose.py): the pack's rifle held low in both
# hands, standing, at a jog and at a sprint.  The upper body's only; the legs
# stay the motion matching's.  Lyra has no such set: its hipfire idle is its
# ADS idle with the hands 0 to 8 cm lower, and it has no sprint.
CARRY_IDLE = f"{GAME_ROOT}/Idle_Rifle_Hip"
CARRY_JOG = f"{GAME_ROOT}/Jog_Fwd_Rifle"
CARRY_SPRINT = f"{GAME_ROOT}/Sprint_Fwd_Rifle"
# The same crouched: the pack's rifle at the hip over a crouch, at rest and
# at the crouch's walk.  The upper body's too: the legs are the sample's
# crouch set.
CARRY_CROUCH_IDLE = f"{GAME_ROOT}/Crouch_Idle_Rifle_Hip"
CARRY_CROUCH_WALK = f"{GAME_ROOT}/Crouch_Walk_Fwd_Rifle_Hip"

# Every clip of the pack the game plays.  A later one is a row here and a
# re-run of import_asp.py.
CLIPS = (CARRY_IDLE, CARRY_JOG, CARRY_SPRINT, CARRY_CROUCH_IDLE, CARRY_CROUCH_WALK)


def uefn_clip(source):
    """Where one of the pack's clips' copy on the UEFN skeleton lands."""
    return f"{UEFN_DIR}/{UEFN_PREFIX}{source.rsplit('/', 1)[1]}"
