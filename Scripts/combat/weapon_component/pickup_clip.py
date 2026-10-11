"""The pick-up's clip: the reach down to the ground for an item taken.

The take itself is pickup.py's (the ask, Server_Take). This plays the skin's
pick-up clip (PlayerSkin.pickup, Quaternius UAL2's Farm_Harvest, retargeted
onto the player's skeleton by asset_pipeline/retarget_to_uefn.py) into the
upper-body slot, the way the throw's clip is played (throw_windup.py): the
spine bends and the right arm reaches the floor over the legs the motion
matching keeps walking.

Who plays it (combat/fx_vars.py, PICKUP_CLIP, gate OTHERS): the owner at
once, off the ask (pickup.py: in single player the ask is the take, so the
clip starts the frame the item goes), and the other players' copies at the
server's word, told after a take that went through. A skin with no clip
(PickUpAnim is None) plays nothing: the item is taken as before.

What keeps it in the slot: the ready pose's keep-alive (ready_pose.py) and
the equip the take's NeedsRefresh runs (inventory.py) both ask picking_up()
before they put a pose into the slot, as they ask about the throw's clip,
since a montage just started reads as a quiet slot until it has blended in.
The clip plays through, the slot falls silent, and the keep-alive puts the
pose back.
"""

from combat.anim_blueprint import AIM_SLOT
from combat.fx_vars import OTHERS, PICKUP_CLIP
from combat.pickup_tuning import PICKUP_ANIM_BLEND_S, PICKUP_CLIP_START_S
from combat.weapon_component import fx
from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from uebp.nodes.actor import FN_ANIM_INSTANCE, FN_IS_PLAYING_SLOT, FN_PLAY_SLOT
from uebp.nodes.system import FN_IS_VALID
from combat.weapon_component import vars as WV

PICKUP_ANIM_VAR = WV.PickUpAnim        # the skin's pick-up clip, or None


def _get(ed, var):
    return out(ed.add_get_member_variable_node(var), var)


def picking_up(ed, anim_out, keep=lambda n: n):
    """Is the pick-up clip in the upper-body slot? A bool pin, off the anim
    instance pin given; ``keep`` collects the nodes for a comment. Asked by
    its clip, since a montage just started reads as a quiet slot."""
    playing = keep(_node(ed, FN_IS_PLAYING_SLOT))
    _connect(anim_out, _pin(playing, "self"))
    anim = keep(ed.add_get_member_variable_node(PICKUP_ANIM_VAR))
    _connect(out(anim, PICKUP_ANIM_VAR), _pin(playing, "Asset"))
    _set(playing, "SlotNodeName", AIM_SLOT)
    return out(playing)


def _author_pickup_clip(ed, exec_in):
    """The skin's pick-up clip into the upper-body slot, on from
    PICKUP_CLIP_START_S, behind IsValid of it. Returns (played, no clip):
    the exec pins after. Fx_PickUpClip's body."""
    has = _node(ed, FN_IS_VALID)
    _connect(_get(ed, PICKUP_ANIM_VAR), _pin(has, "Object"))
    clip = ed.add_branch_node()
    _connect(out(has), _pin(clip, "Condition"))
    _connect(exec_in, _pin(clip, "execute"))
    anim = _node(ed, FN_ANIM_INSTANCE)
    _connect(_get(ed, WV.OwnerMesh), _pin(anim, "self"))
    play = _node(ed, FN_PLAY_SLOT)
    _connect(out(anim), _pin(play, "self"))
    _connect(_get(ed, PICKUP_ANIM_VAR), _pin(play, "Asset"))
    _set(play, "SlotNodeName", AIM_SLOT)
    _set(play, "BlendInTime", PICKUP_ANIM_BLEND_S)
    _set(play, "BlendOutTime", PICKUP_ANIM_BLEND_S)
    _set(play, "InPlayRate", 1.0)
    _set(play, "LoopCount", 1)
    _set(play, "InTimeToStartMontageAt", PICKUP_CLIP_START_S)
    _connect(then(clip), _pin(play, "execute"))
    return then(play), else_(clip)


def author_pickup_fx(ed):
    """The pick-up's cosmetic pair (fx.py): the clip, which the owner plays
    off the ask (pickup.py), so only the others owe it. Before the Tick and
    the take's event."""
    fx.pair(ed, PICKUP_CLIP, (), lambda g, e, _ev: _author_pickup_clip(ed, e), OTHERS)
