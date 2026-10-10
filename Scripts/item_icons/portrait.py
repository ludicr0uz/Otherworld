"""The character's portrait: the I panel's picture of the player's own body,
facing the viewer. One more picture through the icons' pipeline (the same
passes, the same light), of skeletal meshes instead of an item's Blueprint.

Constants only, and no `unreal`: compose.py reads it outside the editor.

The body is the one the player is drawn as: the MetaHuman
(asset_pipeline/metahuman_paths.py), body, face and grooms, in the underwear
its material paints, standing in the first frame of the idle the game plays
under it. It is the same picture whatever the player wears.
"""

from asset_pipeline.gas_bridge_paths import IDLE_CLIP, PLAYER_MESH_GAS, RTG_FROM_UEFN
from asset_pipeline.metahuman_paths import (
    BODY_MATERIAL_BARE, BODY_MESH_WHOLE, FACE_MESH, GROOMS, SOURCED_DIR,
)

PORTRAIT = "Character"              # its name on build_item_icons.py's command line
PORTRAIT_TEXTURE = "T_UI_Portrait"
PORTRAIT_W, PORTRAIT_H = 256, 512   # the texture: a standing body is about 1:2

# What is pictured: combat/metahuman_body.py's tree, less the garment slots.
PORTRAIT_MESH = BODY_MESH_WHOLE
PORTRAIT_MATERIAL = BODY_MATERIAL_BARE
PORTRAIT_FACE = FACE_MESH
PORTRAIT_GROOMS = GROOMS
# The pose: the idle is a clip on the hidden mesh's skeleton, which the game
# retargets onto the body every frame. Nothing ticks in the capture, so the
# clip is retargeted once, into a folder that is deleted after the picture.
PORTRAIT_POSE = IDLE_CLIP
PORTRAIT_POSE_MESH = PLAYER_MESH_GAS
PORTRAIT_RETARGETER = RTG_FROM_UEFN
PORTRAIT_SCRATCH = f"{SOURCED_DIR}/PortraitScratch"
# Where the camera stands, in the mesh's own frame: a skeletal mesh faces its
# +Y, so on that side looking back at it, level with it.
PORTRAIT_YAW = 90.0
