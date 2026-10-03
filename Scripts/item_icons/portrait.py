"""The character's portrait: the I panel's picture of the player's own body,
facing the viewer. One more picture through the icons' pipeline (the same
passes, the same light), of a skeletal mesh instead of an item's Blueprint.

Constants only, and no `unreal`: compose.py reads it outside the editor.

The body is the one the player wears (asset_pipeline/player_body.py), standing
in its idle clip's first frame rather than its bind pose. A body swapped in
(swap_player_body.py) gets its portrait from a re-run of build_item_icons.py.
"""

from asset_pipeline.player_body import PLAYER_NAME

PORTRAIT = "Character"              # its name on build_item_icons.py's command line
PORTRAIT_TEXTURE = "T_UI_Portrait"
PORTRAIT_W, PORTRAIT_H = 256, 512   # the texture: a standing body is about 1:2

PORTRAIT_MESH = f"/Game/Sourced/Characters/SKM_{PLAYER_NAME}/SKM_{PLAYER_NAME}"
PORTRAIT_POSE = f"/Game/Sourced/Characters/Anims/{PLAYER_NAME}/A_{PLAYER_NAME}_MM_Idle"
# Where the camera stands, in the mesh's own frame: a skeletal mesh faces its
# +Y, so on that side looking back at it, level with it.
PORTRAIT_YAW = 90.0
