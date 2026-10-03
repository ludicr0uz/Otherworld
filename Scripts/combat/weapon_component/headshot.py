"""The headshot stamp: HeadshotTime is the game time of the last round or
thrown blade of the player's that struck a head. impact.py and
throw_strike.py call in here once the wound is dealt; the HUD reads it and
draws the X round the reticle (graphics_menu/hit_marker.py).
"""

from combat.weapon_component import vars as WV
from uebp.graph import _connect, _node, _pin, out, then
from uebp.nodes.math import FN_SELECT_FF
from uebp.nodes.system import FN_TIME_SECONDS


def _author_headshot(ed, in_head, execs):
    """HeadshotTime = now if ``in_head`` (a bool pin: the bone struck is one
    of the target's HeadBones), else what it was. One Set on the chain rather
    than a Branch round it, so the caller's exec stays one line. Returns the
    exec pin after it, and the nodes."""
    now = _node(ed, FN_TIME_SECONDS)
    was = ed.add_get_member_variable_node(WV.HeadshotTime)
    when = _node(ed, FN_SELECT_FF)
    _connect(out(now), _pin(when, "A"))
    _connect(out(was, WV.HeadshotTime), _pin(when, "B"))
    _connect(in_head, _pin(when, "bPickA"))
    mark = ed.add_set_member_variable_node(WV.HeadshotTime)
    _connect(out(when), _pin(mark, WV.HeadshotTime))
    for pin in execs:
        _connect(pin, _pin(mark, "execute"))
    return then(mark), [now, was, when, mark]
