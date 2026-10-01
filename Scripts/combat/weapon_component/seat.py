"""The sight camera's seat: whether the camera may be on the gun yet, and how
far onto it it has gone. sights.py places the camera by what this writes.

    up          = no sight line
                  OR Normal(sight line) . Forward(control rotation) > cos(10 deg)
    SightSeated = SightAiming AND (SightSeated OR up)
    SightSeat   = FInterpTo(SightSeat, SightSeated ? 1 : 0, dt, ads_interp_speed)

Why the camera waits for the gun: a gun is carried lowered (carry.py), and the
sights key raises it with the ready pose's blend. SightBlend starts on the
key, so a camera placed by it reached the gun while the gun was still at the
hip: the view dropped to the hand, then swung up onto the target with the
arms. Held on the boom until the gun's sight line is near where the player is
looking, the camera keeps the target in the middle of the view and the sights
come up to it.

Why SightBlend is kept as it is: sight_pitch.py tips the body by the view's
pitch times SightBlend, and that is part of what brings the gun onto the
view. A blend that waited for the gun would wait for itself.

Why a latch and not the angle alone: a reload with the sights up throws the
gun off the view, and the camera has always stayed on the gun through it.
Once seated it stays seated until the key is let go.

An item with no sight line (the knife) is seated at once: there is no line to
wait for, and its view keeps the boom's rotation (sights.py).

With empty hands both are cleared, so the camera is home (_author_unseat).
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _pin, _set
from combat.nodes import (
    FN_AND, FN_BOOL_TO_FLOAT, FN_DOT_VV, FN_FORWARD, FN_GREATER_FF,
    FN_INTERP_FF, FN_NORMAL, FN_NOT, FN_OR,
)
from combat.seat_tuning import SEAT_VAR, SEATED_VAR, SIGHT_SEAT_COS
from combat.tuning import COMBAT


def _author_sight_seat(ed, tick, keep, line_out, has_line_out, boom_rot_out,
                       exec_in, x, y):
    """Write SightSeated and SightSeat (see the module docstring). Held is
    valid here: the sight line is read off it. Returns (the exec pin to carry
    on from, the seat just written)."""
    def out(n, name="ReturnValue"):
        return _pin(n, name, is_input=False)

    def gate2(fn, a, b, px, py):
        n = keep(_at(_node(ed, fn), px, py))
        _connect(a, _pin(n, "A"))
        _connect(b, _pin(n, "B"))
        return out(n)

    along = keep(_at(_node(ed, FN_NORMAL), x, y + 300))
    _connect(line_out, _pin(along, "A"))
    view = keep(_at(_node(ed, FN_FORWARD), x, y + 440))
    _connect(boom_rot_out, _pin(view, "InRot"))
    near = keep(_at(_node(ed, FN_GREATER_FF), x + 520, y + 300))
    _connect(gate2(FN_DOT_VV, out(along), out(view), x + 260, y + 300),
             _pin(near, "A"))
    _set(near, "B", SIGHT_SEAT_COS)
    no_line = keep(_at(_node(ed, FN_NOT), x + 520, y + 440))
    _connect(has_line_out, _pin(no_line, "A"))
    up = gate2(FN_OR, out(near), out(no_line), x + 780, y + 360)

    was = keep(_at(ed.add_get_member_variable_node(SEATED_VAR), x + 780, y + 220))
    stay = gate2(FN_OR, out(was, SEATED_VAR), up, x + 1040, y + 300)
    wanted = keep(_at(ed.add_get_member_variable_node("SightAiming"), x + 1040, y + 180))
    seated = keep(_at(ed.add_set_member_variable_node(SEATED_VAR), x + 1560, y))
    _connect(gate2(FN_AND, out(wanted, "SightAiming"), stay, x + 1300, y + 240),
             _pin(seated, SEATED_VAR))
    _connect(exec_in, _pin(seated, "execute"))

    as_float = keep(_at(_node(ed, FN_BOOL_TO_FLOAT), x + 1820, y + 240))
    _connect(_loose_pin(seated, "Output_Get", is_input=False),
             _pin(as_float, "InBool"))
    have = keep(_at(ed.add_get_member_variable_node(SEAT_VAR), x + 1820, y + 380))
    step = keep(_at(_node(ed, FN_INTERP_FF), x + 2080, y + 240))
    _connect(out(have, SEAT_VAR), _pin(step, "Current"))
    _connect(out(as_float), _pin(step, "Target"))
    _connect(out(tick, "DeltaSeconds"), _pin(step, "DeltaTime"))
    _set(step, "InterpSpeed", COMBAT.ads_interp_speed)
    seat = keep(_at(ed.add_set_member_variable_node(SEAT_VAR), x + 2340, y))
    _connect(out(step), _pin(seat, SEAT_VAR))
    _connect(BEL.find_then_pin(seated), _pin(seat, "execute"))
    return BEL.find_then_pin(seat), _loose_pin(seat, "Output_Get", is_input=False)


def _author_unseat(ed, keep, exec_in, x, y):
    """Clear the latch and the seat at once; returns the exec pin after."""
    seated = keep(_at(ed.add_set_member_variable_node(SEATED_VAR), x, y))
    _set(seated, SEATED_VAR, "false")
    _connect(exec_in, _pin(seated, "execute"))
    seat = keep(_at(ed.add_set_member_variable_node(SEAT_VAR), x + 260, y))
    _set(seat, SEAT_VAR, 0.0)
    _connect(BEL.find_then_pin(seated), _pin(seat, "execute"))
    return BEL.find_then_pin(seat)
