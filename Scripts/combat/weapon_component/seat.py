"""The sight camera's seat: how far the camera has gone onto the gun, and how
far it has turned onto the gun's sight line. sights.py places the camera by
what this writes.

    SightSeat   = FInterpTo(SightSeat, SightAiming ? 1 : 0, dt, ads_interp_speed)
    up          = no sight line
                  OR Normal(sight line) . Forward(control rotation) > cos(10 deg)
    SightSeated = SightAiming AND (SightSeated OR up)
    SightLook   = FInterpTo(SightLook, SightSeated ? 1 : 0, dt, ads_interp_speed)

One motion, from the key: SightSeat starts on the sights key and carries the
camera from wherever it is (the boom's end, zoomed by the shoulder aim or
not) to the gun's eye point, and ads.py's zoom goes to the weapon's own on the
same key at the same speed. The camera used to wait on the boom, zooming as
the shoulder aim does, until the gun was up, and travel only then: two moves,
with a stop between them.

Why the turn still waits for the gun: a gun is carried lowered (carry.py), and
the sights key raises it with the ready pose's blend. Its sight line starts
70-95 degrees off the view, and a camera turned onto it by SightSeat looked
down at the hand, then swung up onto the target with the arms. So where the
camera LOOKS is its own blend, SightLook: the control rotation until the
gun's sight line is near where the player is looking, and only the last few
degrees are taken from the gun. The view stays on the target all the way and
the sights come up to it, while the camera is already on its way.

Why SightBlend is kept as it is: sight_pitch.py tips the body by the view's
pitch times SightBlend, and that is part of what brings the gun onto the
view. A blend that waited for the gun would wait for itself.

Why a latch and not the angle alone: a reload with the sights up throws the
gun off the view, and the camera has always stayed on the gun through it.
Once seated it stays seated until the key is let go.

An item with no sight line is seated at once: there is no line to wait for,
and its view keeps the boom's rotation (sights.py).

With empty hands all three are cleared, so the camera is home (_author_unseat).
"""

from combat.graph import BEL, _connect, _loose_pin, _node, _pin, _set
from combat.nodes import (
    FN_AND, FN_BOOL_TO_FLOAT, FN_DOT_VV, FN_FORWARD, FN_GREATER_FF,
    FN_INTERP_FF, FN_NORMAL, FN_NOT, FN_OR,
)
from combat.seat_tuning import LOOK_VAR, SEAT_VAR, SEATED_VAR, SIGHT_SEAT_COS
from combat.tuning import COMBAT


def _author_sight_seat(ed, tick, keep, line_out, has_line_out, boom_rot_out,
                       exec_in):
    """Write SightSeat, SightSeated and SightLook (see the module docstring).
    Held is valid here: the sight line is read off it. Returns (the exec pin
    to carry on from, the seat just written, the look just written)."""
    def out(n, name="ReturnValue"):
        return _pin(n, name, is_input=False)

    def gate2(fn, a, b):
        n = keep(_node(ed, fn))
        _connect(a, _pin(n, "A"))
        _connect(b, _pin(n, "B"))
        return out(n)

    along = keep(_node(ed, FN_NORMAL))
    _connect(line_out, _pin(along, "A"))
    view = keep(_node(ed, FN_FORWARD))
    _connect(boom_rot_out, _pin(view, "InRot"))
    near = keep(_node(ed, FN_GREATER_FF))
    _connect(gate2(FN_DOT_VV, out(along), out(view)), _pin(near, "A"))
    _set(near, "B", SIGHT_SEAT_COS)
    no_line = keep(_node(ed, FN_NOT))
    _connect(has_line_out, _pin(no_line, "A"))
    up = gate2(FN_OR, out(near), out(no_line))

    was = keep(ed.add_get_member_variable_node(SEATED_VAR))
    stay = gate2(FN_OR, out(was, SEATED_VAR), up)
    wanted = keep(ed.add_get_member_variable_node("SightAiming"))
    seated = keep(ed.add_set_member_variable_node(SEATED_VAR))
    _connect(gate2(FN_AND, out(wanted, "SightAiming"), stay), _pin(seated, SEATED_VAR))
    _connect(exec_in, _pin(seated, "execute"))

    def eased(var, toward, after):
        """var = FInterpTo(var, toward ? 1 : 0, dt, ads_interp_speed)."""
        as_float = keep(_node(ed, FN_BOOL_TO_FLOAT))
        _connect(toward, _pin(as_float, "InBool"))
        have = keep(ed.add_get_member_variable_node(var))
        step = keep(_node(ed, FN_INTERP_FF))
        _connect(out(have, var), _pin(step, "Current"))
        _connect(out(as_float), _pin(step, "Target"))
        _connect(out(tick, "DeltaSeconds"), _pin(step, "DeltaTime"))
        _set(step, "InterpSpeed", COMBAT.ads_interp_speed)
        put = keep(ed.add_set_member_variable_node(var))
        _connect(out(step), _pin(put, var))
        _connect(after, _pin(put, "execute"))
        return put

    # The travel starts on the key; the turn waits for the latch.
    seat = eased(SEAT_VAR, out(wanted, "SightAiming"), BEL.find_then_pin(seated))
    look = eased(LOOK_VAR, _loose_pin(seated, "Output_Get", is_input=False),
                 BEL.find_then_pin(seat))
    return (BEL.find_then_pin(look),
            _loose_pin(seat, "Output_Get", is_input=False),
            _loose_pin(look, "Output_Get", is_input=False))


def _author_unseat(ed, keep, exec_in):
    """Clear the latch, the seat and the look at once; returns the exec pin
    after."""
    seated = keep(ed.add_set_member_variable_node(SEATED_VAR))
    _set(seated, SEATED_VAR, "false")
    _connect(exec_in, _pin(seated, "execute"))
    seat = keep(ed.add_set_member_variable_node(SEAT_VAR))
    _set(seat, SEAT_VAR, 0.0)
    _connect(BEL.find_then_pin(seated), _pin(seat, "execute"))
    look = keep(ed.add_set_member_variable_node(LOOK_VAR))
    _set(look, LOOK_VAR, 0.0)
    _connect(BEL.find_then_pin(seat), _pin(look, "execute"))
    return BEL.find_then_pin(look)
