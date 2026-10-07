"""The headshot stamp: HeadshotTime is the game time of the last round or
thrown blade of the player's that struck a head. impact.py and
throw_strike.py call in here once the wound is dealt; the HUD reads it and
draws the X round the reticle (graphics_menu/hit_marker.py).

The wound is dealt on the server (M19, M20), so the stamp travels to the
owning client as a RepNotify (M21), whose OnRep writes THIS machine's game
time over the server's: each machine's clock is its own, and the HUD compares
the stamp with its own GetTimeSeconds.
"""

import unreal

from combat.weapon_component import vars as WV
from uebp import net
from uebp.g import _G
from uebp.graph import _connect, _node, _pin, out, then
from uebp.layout import arrange
from uebp.nodes.math import FN_SELECT_FF
from uebp.nodes.palette import MACRO_SWITCH_AUTHORITY_COMP
from uebp.nodes.system import FN_TIME_SECONDS


def replicate_headshot(bp):
    """HeadshotTime is a RepNotify to the owner, and its arrival (the
    Remote arm: a Blueprint Set runs the OnRep on the server too) stamps it
    with this machine's clock. After every declare, before the compile."""
    ed = net.rep_notify(bp, WV.HeadshotTime, unreal.LifetimeCondition.COND_OWNER_ONLY)
    stale = [n for n in ed.list_all_nodes()
             if not isinstance(n, unreal.K2Node_FunctionEntry)]
    if stale:
        ed.remove_nodes(stale)
    g = _G(ed)
    arrived = g.keep(ed.add_macro_node(MACRO_SWITCH_AUTHORITY_COMP))
    _connect(ed.find_graph_entry_pin(), _pin(arrived, "execute"))
    g.put(WV.HeadshotTime, out(g.call(FN_TIME_SECONDS)), [out(arrived, "Remote")])
    ed.add_comment_to_nodes(
        "A headshot of this player's, dealt on the server: the HUD's X runs off "
        "this machine's clock, so the stamp is rewritten with it here.", g.made)
    arrange(ed)


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
