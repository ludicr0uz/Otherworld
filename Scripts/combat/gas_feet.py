"""The motion-matching graph's feet are off while the player lies down.

The sample's graph ends in Foot Placement and Leg IK (gas_locomotion_consts.py,
"THE SERVER BRANCH"), which trace the ground under two feet that stand on it.
A body lying down has no such feet: with the prone clips' legs flat behind it
(P1, stance_clips.py) Foot Placement carried the hips 8 cm up off the ground
and let them drift, and before the clips' IK feet followed their feet
(asset_pipeline/ik_follow.py) Leg IK folded both legs under the body. So each
of the two nodes takes its Alpha from OwFeetAlpha, which the properties
function writes: 0 while the movement says prone (GetStance == 2, the same
answer on every machine), else 1. The alpha snaps; the stance's own blend
(PoseProne) eases the pose under it.
"""
import unreal

from combat.gas_locomotion_consts import FEET_ALPHA, FEET_CLASSES
from uebp.graph import _connect, _pin, out
from uebp.nodes.math import FN_EQ_II, FN_SELECT_FF
from uebp.nodes.move import FN_GET_STANCE
from uebp.pose_share import fed

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary
ALPHA_PIN = "Alpha"
PRONE = "2"   # GetStance: 0 standing, 1 crouched, 2 prone


def author_feet_alpha(g, char, execs):
    """OwFeetAlpha = prone ? 0 : 1, after ``execs``; returns its then pin."""
    lying = g.call(FN_EQ_II, A=out(g.call(FN_GET_STANCE, Character=char)), B=PRONE)
    # A is the float's default, 0.0: the alpha while lying down.
    return g.put(FEET_ALPHA, out(g.call(FN_SELECT_FF, B="1.0", bPickA=out(lying))), execs)


def feet_nodes(ed):
    return [n for n in ed.list_all_nodes()
            if n.get_class().get_name() in FEET_CLASSES]


def alpha_sources(node):
    """The titles of the nodes that feed a feet node's Alpha."""
    return [str(BEL.get_node_title(PIN.get_owning_node(q)))
            for q in fed(_pin(node, ALPHA_PIN))]


def remove_feet_alpha(ed):
    ed.remove_nodes([n for n in ed.list_all_nodes()
                     if str(BEL.get_node_title(n)) == f"Get {FEET_ALPHA}"])


def link_feet_alpha(ed):
    """Each feet node's Alpha from OwFeetAlpha (a getter each)."""
    nodes = feet_nodes(ed)
    if len(nodes) != len(FEET_CLASSES):
        raise RuntimeError(f"expected {FEET_CLASSES}, found {len(nodes)} of them")
    made = []
    for node in nodes:
        flag = ed.add_get_member_variable_node(FEET_ALPHA)
        _connect(out(flag, FEET_ALPHA), _pin(node, ALPHA_PIN))
        made.append(flag)
    ed.add_comment_to_nodes(
        f"{FEET_ALPHA}: 0 while the player lies down (a prone body has no feet under it "
        "for these to plant: they lifted its hips and folded its legs). "
        "Scripts/combat/gas_feet.py.", made)
