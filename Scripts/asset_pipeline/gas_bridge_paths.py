"""gas_bridge_paths -- the skeleton bridge between the Game Animation
Sample's clips and the player's MetaHuman: what the hidden mesh becomes, and
what build_gas_bridge.py writes.  Constants only (no ``unreal``).

The choice (Scripts/asset_pipeline/CLAUDE.md, "The skeleton bridge"): the
hidden mesh becomes the sample's own SKM_UEFN_Mannequin, so its clips, its
databases and its anim blueprint play as shipped, and the MetaHuman's
retargeter gets a second source rig on that skeleton.
"""

from asset_pipeline.gas_paths import UEFN
from asset_pipeline.metahuman_paths import SOURCED_DIR

# What the player's hidden mesh component wears on the GAS side of the bridge.
HIDDEN_MESH_GAS = f"{UEFN}/Meshes/SKM_UEFN_Mannequin"
HIDDEN_SKELETON_GAS = f"{UEFN}/Meshes/SK_UEFN_Mannequin"

# What the player's hidden mesh component wears once the game is on the bridge
# (gas_player_mesh.py): a copy of that mesh, on the same skeleton, with the
# sockets the game attaches to.  The sample's own mesh is left a byte copy.
PLAYER_MESH_GAS = f"{SOURCED_DIR}/SKM_UEFN_Player"
# Where those sockets are read from: the mannequin the game was built on.
SOCKETS_FROM = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
PLAYER_SOCKETS = ("HandGrip_R", "HandGrip_L", "weapon_r_muzzle",
                  "foot_l_Socket", "foot_r_Socket")

# The one clip the proof plays: the sample's standing idle.
IDLE_CLIP = f"{UEFN}/Animations/Idle/M_Neutral_Stand_Idle_Loop"

# What build_gas_bridge.py writes, beside the mannequin's bridge.
IK_UEFN = f"{SOURCED_DIR}/IK_UEFN_Mannequin_Source"
RTG_FROM_UEFN = f"{SOURCED_DIR}/RTG_MetaHuman_from_UEFN"
ABP_RETARGET_UEFN = f"{SOURCED_DIR}/ABP_MetaHuman_Retarget_UEFN"
# The minimal anim blueprint on SK_UEFN_Mannequin: one sequence player.
ABP_GAS_IDLE = f"{SOURCED_DIR}/ABP_GasIdle"
# Its variable, which the sequence player reads its clip from.
IDLE_VAR = "IdleClip"

# The game's own clips on this skeleton (retarget_to_uefn.py): what the weapon
# layers play over the motion matching.  The name the folders and the clips
# carry is the player mesh's, less its SKM_: combat/hit_reaction.hit_reactions
# finds a body's flinches by its mesh's name.
PLAYER_FAMILY = PLAYER_MESH_GAS.rsplit("/SKM_", 1)[1]
RTG_UEFN_FROM_MANNEQUIN = f"{SOURCED_DIR}/RTG_UEFN_from_Mannequin"
# The mannequin the player wore before the bridge: the mesh those clips were
# seen on, and so the one they are read off.
CLIPS_FROM_MESH = SOCKETS_FROM
