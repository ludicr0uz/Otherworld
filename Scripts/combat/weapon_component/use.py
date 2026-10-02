"""The use key: with an item that has no sights in hand, the sights key uses
it instead of aiming it.

    key        = IsInputKeyDown(KeySights) OR SightsForced
    Using      = key AND NOT Sprinting AND IsValid(Held) AND NOT Held.HasSights
    UsePressed = Using AND NOT last frame's Using        (the press)

A gun keeps the key for its sights (ads.py, which reads Using to tell the two
apart: the key aims only while it is not using). Everything else has no
sights to bring up, so the key is free, and what it does is the held item's
own: each kind of use is a fragment in KINDS, run every frame after Using and
UsePressed are written, which asks its own question of Held (a flag on
BP_WeaponItem, read behind a Branch on Using or UsePressed, where Held is
known valid). Today there is one kind: a stick that Burns (torch.py). An
item no kind answers for does nothing on the key.

Held.HasSights is read on the true arm of an IsValid(Held) Branch, never in
a folded condition: a pure Get off a null Held is an Accessed None a frame.
Not while sprinting, for the reason the aim is not (ads.py): the hands are
running. SightsForced is the probes' stand-in for the key, as it is for the
sights.

To add a use, write its fragment `(ed, held, owner, exec_ins, x0, y0) ->
exits` in a module of its own and add it to KINDS. Don't poll the key
anywhere else.
"""

from combat.graph import BEL, _at, _connect, _node, _pin, _set
from combat.nodes import FN_AND, FN_IS_KEY_DOWN, FN_NOT, FN_OR
from combat.seat_tuning import HAS_SIGHTS_VAR, SIGHTS_FORCED_VAR
from combat.use_tuning import USE_PRESSED_VAR, USE_WAS_VAR, USING_VAR
from combat.weapon_component.common import _prop
from combat.weapon_component.torch import _author_torch

# One fragment per kind of use, run in this order every frame.
KINDS = (_author_torch,)
KIND_PITCH = 2000   # graph units between two kinds' rows of nodes


def _out(node, name="ReturnValue"):
    return _pin(node, name, is_input=False)


def _author_use(ed, pc_out, owner_out, held, armed_out, sights_key, exec_ins,
                x0, y0):
    """Write Using and UsePressed, then run each kind of use. Returns (the
    exits, the key's pin: held or forced, which ads.py aims a gun on, so the
    key is polled once)."""
    made = []

    def keep(n):
        made.append(n)
        return n

    def get(name, x, y):
        return _out(keep(_at(ed.add_get_member_variable_node(name), x, y)), name)

    def gate2(fn, a, b, x, y):
        n = keep(_at(_node(ed, fn), x, y))
        _connect(a, _pin(n, "A"))
        _connect(b, _pin(n, "B"))
        return _out(n)

    def negate(a, x, y):
        n = keep(_at(_node(ed, FN_NOT), x, y))
        _connect(a, _pin(n, "A"))
        return _out(n)

    down = keep(_at(_node(ed, FN_IS_KEY_DOWN), x0, y0 + 200))
    _connect(pc_out, _pin(down, "self"))
    _connect(sights_key, _pin(down, "Key"))
    key = gate2(FN_OR, _out(down), get(SIGHTS_FORCED_VAR, x0, y0 + 340),
                x0 + 260, y0 + 240)
    free = gate2(FN_AND, key, negate(get("Sprinting", x0, y0 + 460), x0 + 260, y0 + 460),
                 x0 + 520, y0 + 300)

    gate = keep(_at(ed.add_branch_node(), x0 + 780, y0))
    _connect(armed_out, _pin(gate, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(gate, "execute"))
    # True arm: Held is valid, so it can be asked whether it has sights.
    sighted, sighted_n = _prop(ed, HAS_SIGHTS_VAR, held, x0 + 780, y0 + 300)
    keep(sighted_n)
    mark = keep(_at(ed.add_set_member_variable_node(USING_VAR), x0 + 1300, y0))
    _connect(gate2(FN_AND, free, negate(sighted, x0 + 1040, y0 + 300), x0 + 1040, y0 + 180),
             _pin(mark, USING_VAR))
    _connect(BEL.find_then_pin(gate), _pin(mark, "execute"))
    idle = keep(_at(ed.add_set_member_variable_node(USING_VAR), x0 + 1300, y0 + 500))
    _set(idle, USING_VAR, "false")
    _connect(BEL.find_else_pin(gate), _pin(idle, "execute"))

    # The press: read against last frame's Using before that is overwritten.
    using = get(USING_VAR, x0 + 1560, y0 + 300)
    press = keep(_at(ed.add_set_member_variable_node(USE_PRESSED_VAR), x0 + 2080, y0))
    _connect(gate2(FN_AND, using, negate(get(USE_WAS_VAR, x0 + 1560, y0 + 440),
                                         x0 + 1820, y0 + 440), x0 + 1820, y0 + 300),
             _pin(press, USE_PRESSED_VAR))
    for e in (BEL.find_then_pin(mark), BEL.find_then_pin(idle)):
        _connect(e, _pin(press, "execute"))
    was = keep(_at(ed.add_set_member_variable_node(USE_WAS_VAR), x0 + 2340, y0))
    _connect(using, _pin(was, USE_WAS_VAR))
    _connect(BEL.find_then_pin(press), _pin(was, "execute"))

    ed.add_comment_to_nodes(
        f"The use key (use.py). With an item that has no sights in hand, the "
        f"sights key uses it: {USING_VAR} while it is held (not sprinting), "
        f"{USE_PRESSED_VAR} on the frame it goes down. A gun keeps the key for "
        f"its sights (ads.py). What a use does is each kind's own, below.",
        made)

    exits = (BEL.find_then_pin(was),)
    for i, kind in enumerate(KINDS):
        exits = kind(ed, held, owner_out, exits, x0, y0 - (i + 1) * KIND_PITCH)
    return exits, key
