"""How a HUD graph changes the game: it asks the player's weapon component.

    ask(ed, wc, ASK_MOVE, execs, made, From=pin, To=pin)

is a call of that component's custom event (combat/ask_consts.py names them).
A HUD graph writes none of the component's variables and spawns nothing: it
shows state, and what the player picks goes through one of these. A server
has no HUD, and these calls are what the later tasks send to it.
"""

from uebp.graph import _connect, _node, _pin, _set, then
from combat.paths import WEAPON_COMP_CLASS_PATH


def ask(ed, wc, name, in_execs, made, **params):
    """Call the weapon component's event ``name`` on ``wc`` (its cast pin).
    A parameter is a pin, or an int literal. Returns the call's then pin."""
    n = _node(ed, f"{WEAPON_COMP_CLASS_PATH}:{name}")
    _connect(wc, _pin(n, "self"))
    for param, value in params.items():
        if isinstance(value, int):
            _set(n, param, value)
        else:
            _connect(value, _pin(n, param))
    for e in in_execs:
        _connect(e, _pin(n, "execute"))
    made.append(n)
    return then(n)
