"""The dry-fire click.

The reload was here until W2: it is the native base's ReloadNow now (C++,
OtherworldWeaponComponentBase; shot.py has what the graph hangs on it), and
the take it stored so that no pure node recomputed it is a local there.
"""

from uebp.graph import _connect, _node, _pin, else_, out, then
from combat.tuning import SMG_FIRE_INTERVAL
from combat.weapon_component.common import _prop
from uebp.nodes.math import FN_AND, FN_NOT
from uebp.nodes.system import FN_PLAY_SOUND
from combat import item_vars as IV


def _author_dry_fire(ed, held, muzzle, has_ammo, cooled, tapped, exec_in):
    """The trigger was pulled on an empty chamber: click, and nothing else.

    Hangs off the False arm of the ready gate, which is the one place in the
    graph that knows the trigger was pulled and the shot did not happen. Three
    reasons now lead here and only one of them is worth a sound:

        no ammunition   the player has to *do* something (reload, or switch)
                        and nothing on screen says so -- the ammo readout is
                        four digits in the corner of a slot. This is the cue.
        still cooling   the weapon is working exactly as designed. Clicking
                        here would mean clicking on every frame a held trigger
                        outruns the interval, which on the SMG is most of them.
        held, not tapped  a semi-automatic with the button still down. Nothing
                        has gone wrong; the player has simply not let go.

    So the condition is "empty AND cooled AND tapped". The third term arrived
    with automatic fire and is not optional: the outer gate now opens on a HELD
    button, so without it, holding the mouse on an empty shotgun would click
    sixty times a second. Tapped also gives the automatics the right behaviour
    for free -- an empty SMG clicks once per pull rather than at its own fire
    rate, because it is out of ammunition, not out of cooldown.

    All three inputs are the same pure pins the ready gate itself used:
    re-reading them costs three re-evaluations of plain reads, and nothing has
    written to Held between the gate and here -- precisely because nothing
    fired.

    No cooldown is stamped, and with the tap requirement none is needed: one
    click of the mouse is one click of the hammer however long it is held.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    empty = keep(_node(ed, FN_NOT))
    _connect(has_ammo, _pin(empty, "A"))
    settled = keep(_node(ed, FN_AND))
    _connect(out(empty), _pin(settled, "A"))
    _connect(cooled, _pin(settled, "B"))
    worth = keep(_node(ed, FN_AND))
    _connect(out(settled), _pin(worth, "A"))
    _connect(tapped, _pin(worth, "B"))

    click = keep(ed.add_branch_node())
    _connect(out(worth), _pin(click, "Condition"))
    _connect(exec_in, _pin(click, "execute"))

    dry_pin, dry_n = _prop(ed, IV.DryFireSound, held)
    keep(dry_n)
    play = keep(_node(ed, FN_PLAY_SOUND))
    _connect(dry_pin, _pin(play, "Sound"))
    # At the muzzle, like the shot it is standing in for, so the click comes
    # from the same place in the mix as the bang the player expected.
    _connect(muzzle, _pin(play, "Location"))
    _connect(then(click), _pin(play, "execute"))

    ed.add_comment_to_nodes(
        "Empty chamber: the click. Gated on \"out of ammunition\" AND \"off "
        "cooldown\" AND \"pressed this frame\", so the weapon clicks when the "
        "player needs to be told to reload, stays silent while it is merely "
        f"between shots (every {SMG_FIRE_INTERVAL:.2f}s on the SMG), and clicks "
        "once per pull rather than once per frame now that a HELD button opens "
        "the gate above.",
        made)
    return (then(play), else_(click))
