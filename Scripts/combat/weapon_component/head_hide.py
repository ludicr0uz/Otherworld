"""Down the sights, the player's own head is out of the view.

    if SightSeat > HEAD_HIDE_SEAT:  OwnerMesh.HideBoneByName(skin.head)
    else:                           OwnerMesh.UnHideBoneByName(skin.head)

The sight camera sits at the held gun's eye point (sights.py), a few
centimetres behind its rear sight. A gun at the shoulder has the head right
there: the AK's eye point is inside the hair, and pieces of the head stood in
its sight picture. Where the eye lands differs by gun, pose and stance, so
moving each gun's eye clear of the head is a per-weapon fix that the next gun
or the next ready pose breaks again. The head is taken out instead, whatever
is held: no gun, present or future, has it in its sights.

HideBoneByName, not OwnerNoSee (the scope's way, sights.py): the arms and the
gun are the sight picture and must stay. A hidden bone is a render-side zero
scale on that bone and its children; the game thread's pose, the sockets and
the physics bodies (PBO_None: hit_bodies.py's head stays where it is) are
untouched. It is not per-view, so the body's shadow is headless meanwhile.

Read off SightSeat, the camera's own share of the sights (seat.py), after
sights.py has written it this frame -- on both of its arms, so with empty
hands (SightSeat 0) the head is back. Written every frame, like the camera:
no latch to forget. The dead gate shows it too (dead.py), since this never
runs for a dead owner.
"""

import unreal

from combat.graph import BEL, _assets, _connect, _node, _pin, _set
from combat.nodes import FN_GREATER_FF, FN_HIDE_BONE, FN_UNHIDE_BONE
from combat.seat_tuning import HEAD_HIDE_SEAT, SEAT_VAR
from combat.skin import player_skin

# The bone's physics body is left alone: only the picture changes.
PHYS_BODY_OP = "PBO_None"


def head_bone():
    """The wearer's head bone, checked against the mesh's skeleton.

    HideBoneByName on a name the skeleton does not have does nothing, and
    says nothing.
    """
    skin = player_skin()
    mesh = _assets().load_asset(skin.mesh)
    if not mesh:
        raise RuntimeError(f"could not load {skin.mesh}")
    skeleton = mesh.get_editor_property("skeleton")
    bones = {str(b) for b in unreal.AnimPoseExtensions.get_bone_names(
        unreal.AnimPoseExtensions.get_reference_pose(skeleton))}
    if skin.head not in bones:
        raise RuntimeError(f"{skeleton.get_name()} has no {skin.head!r}; the "
                           "head would stay in the sights")
    return skin.head


def _author_head_shown(ed, keep, exec_in):
    """OwnerMesh.UnHideBoneByName(head). Returns the exec pin to carry on from."""
    body = keep(ed.add_get_member_variable_node("OwnerMesh"))
    show = keep(_node(ed, FN_UNHIDE_BONE))
    _connect(_pin(body, "OwnerMesh", is_input=False), _pin(show, "self"))
    _set(show, "BoneName", head_bone())
    _connect(exec_in, _pin(show, "execute"))
    return BEL.find_then_pin(show)


def _author_head_hide(ed, exec_ins):
    """See the module docstring. Returns the exec pins to carry on from."""
    made = []

    def keep(n):
        made.append(n)
        return n

    seat = keep(ed.add_get_member_variable_node(SEAT_VAR))
    past = keep(_node(ed, FN_GREATER_FF))
    _connect(_pin(seat, SEAT_VAR, is_input=False), _pin(past, "A"))
    _set(past, "B", HEAD_HIDE_SEAT)
    on_sights = keep(ed.add_branch_node())
    _connect(_pin(past, "ReturnValue", is_input=False), _pin(on_sights, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(on_sights, "execute"))

    body = keep(ed.add_get_member_variable_node("OwnerMesh"))
    hide = keep(_node(ed, FN_HIDE_BONE))
    _connect(_pin(body, "OwnerMesh", is_input=False), _pin(hide, "self"))
    _set(hide, "BoneName", head_bone())
    _set(hide, "PhysBodyOption", PHYS_BODY_OP)
    _connect(BEL.find_then_pin(on_sights), _pin(hide, "execute"))
    shown = _author_head_shown(ed, keep, BEL.find_else_pin(on_sights))

    ed.add_comment_to_nodes(
        f"Down the sights (SightSeat > {HEAD_HIDE_SEAT:g}) the player's own "
        f"head ({head_bone()} and its children) is hidden: the camera is at "
        "the gun's eye point, inside or beside it, and it stood in the sight "
        "picture. Whatever gun is held, so no weapon needs an eye point that "
        "clears the head. Render only: the pose and the hit bodies stay. "
        "Shown again the frame the camera is back off the gun.", made)
    return (BEL.find_then_pin(hide), shown)
