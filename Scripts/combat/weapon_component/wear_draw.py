"""Clothing drawn on the body: a worn garment's mesh on the component it fills.

    DrawWorn(Item, On), a plain event, called where Worn changes (wear.py,
    wear_drag.py, drop_request.py). Nothing on a dedicated server, which
    draws no one, nor for an Item that is gone or has no WornMesh (the hat):
        every SkeletalMeshComponent under OwnerMesh whose name is
        Item.WornPart (metahuman_body's Torso, Legs, Feet; a mannequin skin
        has none, and nothing is drawn):
            On:  its mesh = Item.WornMesh
                 its leader pose = its attach parent, the body, when both
                 are on one skeleton (the jeans), else none
                 posed whether or not it is rendered, shown
            off: no leader pose, no mesh, hidden

How the mesh follows the body is the MetaHuman's own two ways, and
MetaHumanComponentUE sets them only at BeginPlay, when these components are
bare, so it is done here with the mesh. A garment on the body's skeleton
(metahuman_base_skel) takes the body's bones as they are: leader pose. One on
a skeleton of its own (the hoodie, the shoes) carries a post-process anim
Blueprint on its mesh, the sample's copy pose from the attach parent
(ABP_Clothing_PostProcess's kind), and the component starts it when the mesh
is set: a leader pose would stop it, so it is cleared.

Posed whether or not it is rendered, as the body is (metahuman_body.py):
MetaHumanComponentUE leaves the garments OnlyTickPoseWhenRendered, which
freezes one behind the scope, where the body is hidden from its own camera
and still casts a shadow, and in a headless game, where nothing renders.

The callers pass an Item they hold in a variable, or call before Worn's
slot is rewritten: Worn[slot] is a pure read.
"""

from combat.paths import ITEM_CLASS_PATH
from combat.wear_tuning import DRAW_WORN, WORN_MESH_VAR, WORN_PART_VAR
from combat.weapon_component.body_parts import author_for_parts
from combat.weapon_component.slot_nodes import valid
from uebp.g import _G
from uebp.graph import _connect, _loose_pin, _node, _palette, _pin, _set, out, then
from uebp.net import custom_event
from uebp.nodes.actor import (
    FN_ATTACH_PARENT, FN_SET_HIDDEN_IN_GAME, FN_SET_LEADER_POSE, FN_SET_SKELETAL_MESH,
    FN_SET_VISIBILITY, FN_SKELETAL_MESH_OF, FN_SKELETON_OF,
)
from uebp.nodes.math import FN_EQ_OO
from uebp.nodes.system import FN_EQ_SS, FN_IS_DEDICATED_SERVER, FN_NAME_TO_STRING, FN_OBJECT_NAME
from uebp.vars import BOOL, obj

ITEM_PARAM, ON_PARAM = "Item", "On"
DRAW_PARAMS = ((ITEM_PARAM, obj(ITEM_CLASS_PATH)), (ON_PARAM, BOOL))

NODE_CAST_SKELETAL = "Utilities|Casting|CastToSkeletalMeshComponent"
AS_SKELETAL = "AsSkeletal Mesh Component"
SKINNED_CLASS = "/Script/Engine.SkinnedMeshComponent"
TICK_OPTION_VAR = "VisibilityBasedAnimTickOption"
TICK_ALWAYS = "AlwaysTickPoseAndRefreshBones"


def draw_worn(g, item, on, execs):
    """A call of DrawWorn(item, on) from ``execs``. Returns its then."""
    n = g.keep(_node(g.ed, DRAW_WORN))
    _connect(item, _pin(n, ITEM_PARAM))
    _set(n, ON_PARAM, bool(on))
    for e in execs:
        _connect(e, _pin(n, "execute"))
    return then(n)


def _shown(g, part, shown, execs):
    """SetVisibility and SetHiddenInGame on ``part``. Returns the then."""
    see = g.call(FN_SET_VISIBILITY, execs, self=part)
    _set(see, "bNewVisibility", shown)
    hide = g.call(FN_SET_HIDDEN_IN_GAME, [then(see)], self=part)
    _set(hide, "NewHidden", not shown)
    return then(hide)


def _author_part(g, part, exec_in, item, on):
    """What DrawWorn does to one component under the mannequin."""
    ed = g.ed
    mesh = g.iget(item, WORN_MESH_VAR)
    named = g.call(FN_EQ_SS, A=out(g.call(FN_OBJECT_NAME, Object=part)),
                   B=out(g.call(FN_NAME_TO_STRING, InName=g.iget(item, WORN_PART_VAR))))
    mine, _other = g.branch(out(named), [exec_in])
    dress, bare = g.branch(on, [mine])

    # On: the mesh, then how it follows the body.
    put = g.call(FN_SET_SKELETAL_MESH, [dress], self=part, NewMesh=mesh)
    cast = g.keep(_palette(ed, NODE_CAST_SKELETAL))
    _connect(out(g.call(FN_ATTACH_PARENT, self=part)), _pin(cast, "Object"))
    _connect(then(put), _pin(cast, "execute"))
    body = _loose_pin(cast, AS_SKELETAL, is_input=False)
    same = g.call(FN_EQ_OO,
                  A=out(g.call(FN_SKELETON_OF, self=out(g.call(FN_SKELETAL_MESH_OF, self=body)))),
                  B=out(g.call(FN_SKELETON_OF, self=mesh)))
    shared, own = g.branch(out(same), [then(cast)])
    led = g.call(FN_SET_LEADER_POSE, [shared], self=part, NewLeaderBoneComponent=body)
    # NewLeaderBoneComponent left unconnected: no leader, the mesh's own
    # post-process anim Blueprint copies the body's pose.
    free = g.call(FN_SET_LEADER_POSE, [own, _loose_pin(cast, "CastFailed", is_input=False)], self=part)
    flow = g.iput(part, TICK_OPTION_VAR, TICK_ALWAYS, [then(led), then(free)],
                  class_path=SKINNED_CLASS)
    _shown(g, part, True, [flow])

    # Off: as metahuman_body leaves it.
    loose = g.call(FN_SET_LEADER_POSE, [bare], self=part)
    off = g.call(FN_SET_SKELETAL_MESH, [then(loose)], self=part)
    _shown(g, part, False, [then(off)])


def author_draw_worn_event(ed):
    """DrawWorn (see the module docstring). Before the events and the Tick
    that call it by name."""
    g = _G(ed, ITEM_CLASS_PATH)
    event = g.keep(custom_event(ed, DRAW_WORN, DRAW_PARAMS))
    item, on = out(event, ITEM_PARAM), out(event, ON_PARAM)
    _server, drawn = g.branch(out(g.call(FN_IS_DEDICATED_SERVER)), [then(event)])
    there, _gone = g.branch(valid(g, item), [drawn])
    # Nested: WornMesh is read off an Item known to be there.
    meshed, _plain = g.branch(valid(g, g.iget(item, WORN_MESH_VAR)), [there])
    author_for_parts(ed, g.keep, meshed, NODE_CAST_SKELETAL, AS_SKELETAL,
                     lambda part, exec_pin: _author_part(g, part, exec_pin, item, on))
    ed.add_comment_to_nodes(
        f"{DRAW_WORN} (wear_draw.py): a worn garment's {WORN_MESH_VAR} is set on the "
        f"component under the body named by its {WORN_PART_VAR} and shown, following "
        "the body by leader pose on its skeleton, else by the mesh's own copy pose; "
        "off, the component is bare and hidden again. Not on a dedicated server.",
        g.made)
