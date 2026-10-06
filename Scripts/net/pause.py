"""Pause is a single-player feature: every SetGamePaused in the game is
authored here, and a pause sits behind a Branch on IsStandalone.

    author_pause    exec in --> Branch IsStandalone --true--> SetGamePaused(true) --> out
                                                    --false-----------------------> out
    author_unpause  exec in --> SetGamePaused(false) --> out

A shared world cannot stop for one player (`serversupportsysdesign.md` 4.8,
the mode table's pause row). In standalone the pause is the plain call it
replaces. On a client and on a server it does nothing and the flow goes on:
the menu that would have paused is an overlay over a running world, and what
keeps the character still under it is the menu's own hold on the input
(`graphics_menu/menu_still.py`, `cursor.author_hold_fire`), which never
depended on the pause.

The engine already refuses a client's pause (APlayerController::SetPause),
and a dedicated server has no local controller to ask it. The Branch is here
so the rule is in the graph, where a listen server or a later engine cannot
change it, and so a reader of the graph sees which mode pauses.

The unpause has no Branch. Outside standalone nothing ever paused, so it
changes nothing there; and in standalone it must come however the world got
paused (a level opened paused stays paused for good), so nothing may stand
between it and the row that asks for it.
"""

from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from uebp.nodes.system import FN_IS_STANDALONE, FN_SET_PAUSED


def author_pause(ed, in_execs, made=None):
    """SetGamePaused(true) in standalone, nothing elsewhere.

    ``in_execs`` run it; ``made`` collects the nodes for the caller's comment.
    Returns ``(call, tails)``: the SetGamePaused node, and the exec pins to
    wire on from, both of them (the call's then first)."""
    alone = _node(ed, FN_IS_STANDALONE)
    gate = ed.add_branch_node()
    _connect(out(alone), _pin(gate, "Condition"))
    for e in in_execs:
        _connect(e, _pin(gate, "execute"))
    call = _node(ed, FN_SET_PAUSED)
    _set(call, "bPaused", True)
    _connect(then(gate), _pin(call, "execute"))
    if made is not None:
        made.extend([alone, gate, call])
    return call, [then(call), else_(gate)]


def author_unpause(ed, in_execs, made=None):
    """SetGamePaused(false), in any mode (see the module docstring). Returns
    the call's then pin."""
    call = _node(ed, FN_SET_PAUSED)
    _set(call, "bPaused", False)
    for e in in_execs:
        _connect(e, _pin(call, "execute"))
    if made is not None:
        made.append(call)
    return then(call)
