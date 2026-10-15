"""The sight camera's seat: how far the camera has gone onto the gun, and how
far it has turned onto the gun's sight line. sights.py places the camera by
what this writes.

    SightSeat   = SightSnapped ? 1
                  : FInterpTo(SightSeat, SightSnapped ? 1 : 0, dt, AdsSpeed)
    up          = no sight line
                  OR Normal(sight line) . Forward(control rotation) > cos(10 deg)
    SightSeated = SightSnapped AND (SightSeated OR up)
    SightLook   = FInterpTo(SightLook, SightSeated ? 1 : 0, dt, AdsSpeed)

A cut, after a glimpse of the zoom: for the player's SightZoomIn after the
sights key goes down the camera stays on the boom while ads.py eases the
zoom in; then SightSnapped (ads.py) and SightSeat is 1 on that frame, with
the zoom landed on the weapon's own, so the camera is in the sights' view
(at the anchor, sights.py, zoomed) before the gun has moved, and the gun is
what is seen to move: the carry raises it on the same frame (SightPending,
carry.py) and it rises from below and to the right of the view onto the
crosshair. Letting go eases home at the same speed, the zoom-in's inverse:
a cut back to the boom from a scope would be a jolt, and the carry and
SightBlend read the seat on its way down (SEAT_HOLD). The camera used to
ease to the eye point over a fifth of a second, zooming as it went, and the
raise was half hidden behind the travel; before that it waited on the boom
until the gun was up, and travelled only then; and before the zoom-in it
cut on the key's own frame.

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

from uebp.graph import _connect, _loose_pin, _node, _pin, _set, then
from combat.seat_tuning import LOOK_VAR, SEAT_VAR, SEATED_VAR, SIGHT_SEAT_COS
from uebp.nodes.math import (
    FN_AND, FN_BOOL_TO_FLOAT, FN_DOT_VV, FN_FORWARD, FN_GREATER_FF, FN_INTERP_FF, FN_NORMAL,
    FN_NOT, FN_OR, FN_SELECT_FF)
from combat.weapon_component import vars as WV


def _author_sight_seat(ed, tick, keep, line_out, has_line_out, boom_rot_out,
                       exec_ins):
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
    wanted = keep(ed.add_get_member_variable_node(WV.SightSnapped))
    seated = keep(ed.add_set_member_variable_node(SEATED_VAR))
    _connect(gate2(FN_AND, out(wanted, WV.SightSnapped), stay), _pin(seated, SEATED_VAR))
    for e in exec_ins:
        _connect(e, _pin(seated, "execute"))

    def eased(var, toward, after, snap_up=False):
        """var = FInterpTo(var, toward ? 1 : 0, dt, AdsSpeed); with snap_up,
        1 at once while toward is true (the ease is the way down)."""
        as_float = keep(_node(ed, FN_BOOL_TO_FLOAT))
        _connect(toward, _pin(as_float, "InBool"))
        have = keep(ed.add_get_member_variable_node(var))
        step = keep(_node(ed, FN_INTERP_FF))
        _connect(out(have, var), _pin(step, "Current"))
        _connect(out(as_float), _pin(step, "Target"))
        _connect(out(tick, "DeltaSeconds"), _pin(step, "DeltaTime"))
        rate = keep(ed.add_get_member_variable_node(WV.AdsSpeed))
        _connect(out(rate, WV.AdsSpeed), _pin(step, "InterpSpeed"))
        value = out(step)
        if snap_up:
            # The literal 1 is on B, the pin a Kismet node lets hold one, so
            # the pick is NOT toward: the ease when the key is up.
            easing = keep(_node(ed, FN_NOT))
            _connect(toward, _pin(easing, "A"))
            pick = keep(_node(ed, FN_SELECT_FF))
            _connect(value, _pin(pick, "A"))
            _set(pick, "B", 1.0)
            _connect(out(easing), _pin(pick, "bPickA"))
            value = out(pick)
        put = keep(ed.add_set_member_variable_node(var))
        _connect(value, _pin(put, var))
        _connect(after, _pin(put, "execute"))
        return put

    # The camera is on the sights from the cut; the turn waits for the latch.
    seat = eased(SEAT_VAR, out(wanted, WV.SightSnapped), then(seated), snap_up=True)
    look = eased(LOOK_VAR, _loose_pin(seated, "Output_Get", is_input=False), then(seat))
    return (then(look),
            _loose_pin(seat, "Output_Get", is_input=False),
            _loose_pin(look, "Output_Get", is_input=False))


def _author_unseat(ed, keep, exec_in):
    """Clear the latch, the seat and the look at once; returns the exec pin
    after."""
    seated = keep(ed.add_set_member_variable_node(SEATED_VAR))
    _set(seated, SEATED_VAR, False)
    _connect(exec_in, _pin(seated, "execute"))
    seat = keep(ed.add_set_member_variable_node(SEAT_VAR))
    _set(seat, SEAT_VAR, 0.0)
    _connect(then(seated), _pin(seat, "execute"))
    look = keep(ed.add_set_member_variable_node(LOOK_VAR))
    _set(look, LOOK_VAR, 0.0)
    _connect(then(seat), _pin(look, "execute"))
    return then(look)
