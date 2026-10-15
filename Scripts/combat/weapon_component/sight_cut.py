"""The cut to the sights keeps the point aimed at: on the cut's frame
(SightCut, ads.py) the view is turned from the anchor onto ViewPoint.

    if SightCut:
        look = MakeRotFromX(ViewPoint - anchor)
        PC.SetControlRotation(look)
    view = SightCut ? look : the boom's rotation

Why: before the cut the camera is on the boom, behind and beside the
shoulder, and the crosshair is on what its trace hit (ViewPoint, aim.py).
The cut puts the camera at the head bone (sights.py); with the boom's
rotation kept, the middle of the view moved by the shoulder's offset, and
what was under the crosshair jumped aside (by a few degrees at a few metres).
Looking from the anchor at the same point instead, the target stays under
the crosshair and the gun rises onto it.

Why the control rotation and not the camera alone: the mouse, the body's
pitch and yaw, the gun and the shot all follow the control rotation, so the
turn is the player's from the cut on, and the owning client's moves carry it
to the server. The boom has already ticked this frame with the old one, so
the camera, and the seat's check of the gun against the view, take the new
rotation from here on the cut's frame (the returned pin) rather than the
boom's.

Letting go is not turned back: the camera eases home off the gun, and the
point under the crosshair drifts the same offset back over that ease.
"""

from uebp.graph import _connect, _node, _pin, else_, out, then
from uebp.nodes.actor import FN_SET_CONTROL_ROT
from uebp.nodes.math import FN_ROT_FROM_X, FN_SELECT_ROT, FN_SUB_VV
from combat.weapon_component import vars as WV


def author_cut_turn(ed, keep, pc_out, anchor_out, boom_rot_out, exec_ins):
    """Turn the view onto ViewPoint on the cut's frame (see the module
    docstring). Returns (the exec pins to carry on from, the view's rotation
    this frame)."""
    cut = keep(ed.add_get_member_variable_node(WV.SightCut))
    cut_out = out(cut, WV.SightCut)
    gate = keep(ed.add_branch_node())
    _connect(cut_out, _pin(gate, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(gate, "execute"))

    point = keep(ed.add_get_member_variable_node(WV.ViewPoint))
    toward = keep(_node(ed, FN_SUB_VV))
    _connect(out(point, WV.ViewPoint), _pin(toward, "A"))
    _connect(anchor_out, _pin(toward, "B"))
    look = keep(_node(ed, FN_ROT_FROM_X))
    _connect(out(toward), _pin(look, "X"))
    turn = keep(_node(ed, FN_SET_CONTROL_ROT))
    _connect(pc_out, _pin(turn, "self"))
    _connect(out(look), _pin(turn, "NewRotation"))
    _connect(then(gate), _pin(turn, "execute"))

    view = keep(_node(ed, FN_SELECT_ROT))
    _connect(out(look), _pin(view, "A"))
    _connect(boom_rot_out, _pin(view, "B"))
    _connect(cut_out, _pin(view, "bPickA"))
    return (then(turn), else_(gate)), out(view)
