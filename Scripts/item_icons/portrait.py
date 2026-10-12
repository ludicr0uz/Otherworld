"""The character's portrait: the I panel's picture of the player's own body,
facing the viewer. One more picture through the icons' pipeline (the same
passes, the same light), of skeletal meshes instead of an item's Blueprint.

Constants only, and no `unreal`: compose.py reads it outside the editor.

The body is the one the player is drawn as: the MetaHuman
(asset_pipeline/metahuman_paths.py), body, face and grooms, in the underwear
its material paints, standing in the first frame of the idle the game plays
under it.

One picture per set of garments that can be seen on the body: the garments
drawn when worn (clothing/specs.py's `worn`: the jacket, the pants, the
boots) each have a bit, in the order of their slots, and PORTRAITS[index]
is the body in the garments whose bits are set. The HUD shows the one whose
index is what the player wears (graphics_menu/wear_portrait.py). The other
five garments, and what is in the hand, change nothing in the picture: they
change nothing on the body either.
"""

from dataclasses import dataclass

from asset_pipeline.gas_bridge_paths import IDLE_CLIP, PLAYER_MESH_GAS, RTG_FROM_UEFN
from asset_pipeline.metahuman_paths import (
    BODY_MATERIAL_BARE, BODY_MESH_WHOLE, FACE_MESH, GROOMS, SOURCED_DIR,
)
from clothing.specs import GARMENTS

PORTRAIT = "Character"              # its name on build_item_icons.py's command line
PORTRAIT_TEXTURE = "T_UI_Portrait"
PORTRAIT_W, PORTRAIT_H = 256, 512   # the texture: a standing body is about 1:2

# The garments a picture can show, lowest bit first.
DRAWN = tuple(sorted((g for g in GARMENTS if g.worn), key=lambda g: g.slot_index))
DRAWN_SLOTS = tuple(g.slot_index for g in DRAWN)     # wear_tuning.WEAR_SLOTS' indices


@dataclass(frozen=True)
class Portrait:
    index: int          # the bits of DRAWN that are worn in it

    @property
    def garments(self):
        return tuple(g for bit, g in enumerate(DRAWN) if self.index >> bit & 1)

    @property
    def texture(self):
        """T_UI_Portrait bare, else named after what is worn in it."""
        return "_".join((PORTRAIT_TEXTURE, *(g.display for g in self.garments)))

    @property
    def passes(self):
        """Its folder of passes: the bare one keeps the command line's name."""
        return "_".join((PORTRAIT, *(g.display for g in self.garments)))

    @property
    def meshes(self):
        return tuple(g.worn[1] for g in self.garments)


PORTRAITS = tuple(Portrait(i) for i in range(1 << len(DRAWN)))


def portrait_index(worn_slots):
    """The picture for a player wearing garments in these slots."""
    return sum(1 << bit for bit, slot in enumerate(DRAWN_SLOTS) if slot in worn_slots)

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
