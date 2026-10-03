"""Reloading and the dry-fire click.
"""

from combat.graph import BEL, _connect, _node, _pin, _set
from combat.nodes import (
    FN_ACTOR_LOC, FN_ADD_FF, FN_ADD_II, FN_AND, FN_GREATER_II, FN_MIN_II,
    FN_NOT, FN_PLAY_SOUND, FN_SELECT_II, FN_SUB_II, FN_TIME_SECONDS,
)
from combat.paths import ITEM_CLASS_PATH
from combat.tuning import RELOAD_KEY, SMG_FIRE_INTERVAL
from combat.weapon_component.common import _prop


def _author_reload(ed, held, exec_in):
    """R: top the magazine up from the reserve, and stand still for a moment.

    How many rounds move is worked out ONCE and stored in ReloadTake before
    anything is written. The arithmetic is pure, so a second read of
    ``Min(MagazineSize - Loaded, Reserve)`` after Loaded has been raised would
    quietly return a different (smaller) number, and the reserve would be
    charged less than the magazine gained -- the pure-node trap this file keeps
    running into, in its most expensive form yet: free ammunition.

    There is no reloading *state*. The cost is a deadline pushed out on the
    weapon's own NextFireTime, which is the same field the interval between
    shots uses, so "cannot fire yet" has exactly one meaning in the whole
    system and nothing has to decide which of two rules is in force.

    A weapon with InfiniteReserve (the pistol) stands the whole gap in for its
    reserve, so the magazine always fills -- even from a negative Loaded left
    by an older save, when the pistol spent rounds it never counted -- and its
    Reserve is written back unchanged rather than charged.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    mag, mag_n = _prop(ed, "MagazineSize", held)
    have, have_n = _prop(ed, "Loaded", held)
    keep(mag_n), keep(have_n)
    gap = keep(_node(ed, FN_SUB_II))
    _connect(mag, _pin(gap, "A"))
    _connect(have, _pin(gap, "B"))
    spare, spare_n = _prop(ed, "Reserve", held)
    keep(spare_n)
    # Min, so a reserve of one tops a magazine that is four short up by one and
    # not by four -- and so the reserve can never be driven negative.
    endless, endless_n = _prop(ed, "InfiniteReserve", held)
    keep(endless_n)
    source = keep(_node(ed, FN_SELECT_II))
    _connect(_pin(gap, "ReturnValue", is_input=False), _pin(source, "A"))
    _connect(spare, _pin(source, "B"))
    _connect(endless, _pin(source, "bPickA"))
    moving = keep(_node(ed, FN_MIN_II))
    _connect(_pin(gap, "ReturnValue", is_input=False), _pin(moving, "A"))
    _connect(_pin(source, "ReturnValue", is_input=False), _pin(moving, "B"))
    pin_take = keep(ed.add_set_member_variable_node("ReloadTake"))
    _connect(_pin(moving, "ReturnValue", is_input=False), _pin(pin_take, "ReloadTake"))
    _connect(exec_in, _pin(pin_take, "execute"))

    uses, uses_n = _prop(ed, "UsesAmmo", held)
    keep(uses_n)
    take_get = keep(ed.add_get_member_variable_node("ReloadTake"))
    any_left = keep(_node(ed, FN_GREATER_II))
    _connect(_pin(take_get, "ReloadTake", is_input=False), _pin(any_left, "A"))
    _set(any_left, "B", 0)
    worth = keep(_node(ed, FN_AND))
    _connect(uses, _pin(worth, "A"))
    _connect(_pin(any_left, "ReturnValue", is_input=False), _pin(worth, "B"))

    # A weapon without ammunition and a full magazine both take the False arm, and both
    # skip the pause -- a reload that cost 1.6 s and moved nothing would be a
    # way to punish the player for pressing a key that did not apply.
    does = keep(ed.add_branch_node())
    _connect(_pin(worth, "ReturnValue", is_input=False), _pin(does, "Condition"))
    _connect(BEL.find_then_pin(pin_take), _pin(does, "execute"))

    # The clack, on the True arm only. On the False arm nothing moves, so a
    # sound there would be the game telling the player it had done something it
    # had not -- which is worse than silence, because the pause that normally
    # follows a reload would not happen either.
    #
    # Placed at the weapon rather than at the player: the gun is in the
    # player's hands, so the two are the same position to within a few
    # centimetres, and reading the weapon's transform needs no owner cast.
    at = keep(_node(ed, FN_ACTOR_LOC))
    _connect(held, _pin(at, "self"))
    clack_pin, clack_n = _prop(ed, "ReloadSound", held)
    keep(clack_n)
    clack = keep(_node(ed, FN_PLAY_SOUND))
    _connect(clack_pin, _pin(clack, "Sound"))
    _connect(_pin(at, "ReturnValue", is_input=False), _pin(clack, "Location"))
    _connect(BEL.find_then_pin(does), _pin(clack, "execute"))

    take_a = keep(ed.add_get_member_variable_node("ReloadTake"))
    was, was_n = _prop(ed, "Loaded", held)
    keep(was_n)
    filled = keep(_node(ed, FN_ADD_II))
    _connect(was, _pin(filled, "A"))
    _connect(_pin(take_a, "ReloadTake", is_input=False), _pin(filled, "B"))
    load = keep(ed.add_set_member_variable_node("Loaded", ITEM_CLASS_PATH))
    _connect(held, _pin(load, "self"))
    _connect(_pin(filled, "ReturnValue", is_input=False), _pin(load, "Loaded"))
    _connect(BEL.find_then_pin(clack), _pin(load, "execute"))

    take_b = keep(ed.add_get_member_variable_node("ReloadTake"))
    kept, kept_n = _prop(ed, "Reserve", held)
    keep(kept_n)
    fewer = keep(_node(ed, FN_SUB_II))
    _connect(kept, _pin(fewer, "A"))
    _connect(_pin(take_b, "ReloadTake", is_input=False), _pin(fewer, "B"))
    # An infinite reserve is written back as it was: one Set Reserve on both
    # kinds of weapon, rather than a branch around it.
    free, free_n = _prop(ed, "InfiniteReserve", held)
    keep(free_n)
    after = keep(_node(ed, FN_SELECT_II))
    _connect(kept, _pin(after, "A"))
    _connect(_pin(fewer, "ReturnValue", is_input=False), _pin(after, "B"))
    _connect(free, _pin(after, "bPickA"))
    charge = keep(ed.add_set_member_variable_node("Reserve", ITEM_CLASS_PATH))
    _connect(held, _pin(charge, "self"))
    _connect(_pin(after, "ReturnValue", is_input=False), _pin(charge, "Reserve"))
    _connect(BEL.find_then_pin(load), _pin(charge, "execute"))

    now = keep(_node(ed, FN_TIME_SECONDS))
    takes, takes_n = _prop(ed, "ReloadSeconds", held)
    keep(takes_n)
    ready = keep(_node(ed, FN_ADD_FF))
    _connect(_pin(now, "ReturnValue", is_input=False), _pin(ready, "A"))
    _connect(takes, _pin(ready, "B"))
    pause = keep(ed.add_set_member_variable_node("NextFireTime", ITEM_CLASS_PATH))
    _connect(held, _pin(pause, "self"))
    _connect(_pin(ready, "ReturnValue", is_input=False), _pin(pause, "NextFireTime"))
    _connect(BEL.find_then_pin(charge), _pin(pause, "execute"))

    ed.add_comment_to_nodes(
        f"{RELOAD_KEY} reloads. ReloadTake is computed once and stored because "
        "the arithmetic behind it is pure: read it again after Loaded has gone "
        "up and the reserve is charged less than the magazine gained. The cost "
        "is the weapon's own ReloadSeconds pushed onto NextFireTime -- the same "
        "field the interval between shots uses, so there is only ever one rule "
        "saying when the weapon may fire. An InfiniteReserve weapon (the "
        "pistol) fills the whole gap and is never charged. "
        "The clack plays on the True arm only, "
        "because a reload that moved nothing has nothing to announce.",
        made)
    return (BEL.find_then_pin(pause), BEL.find_else_pin(does))


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
    _connect(_pin(empty, "ReturnValue", is_input=False), _pin(settled, "A"))
    _connect(cooled, _pin(settled, "B"))
    worth = keep(_node(ed, FN_AND))
    _connect(_pin(settled, "ReturnValue", is_input=False), _pin(worth, "A"))
    _connect(tapped, _pin(worth, "B"))

    click = keep(ed.add_branch_node())
    _connect(_pin(worth, "ReturnValue", is_input=False), _pin(click, "Condition"))
    _connect(exec_in, _pin(click, "execute"))

    dry_pin, dry_n = _prop(ed, "DryFireSound", held)
    keep(dry_n)
    play = keep(_node(ed, FN_PLAY_SOUND))
    _connect(dry_pin, _pin(play, "Sound"))
    # At the muzzle, like the shot it is standing in for, so the click comes
    # from the same place in the mix as the bang the player expected.
    _connect(muzzle, _pin(play, "Location"))
    _connect(BEL.find_then_pin(click), _pin(play, "execute"))

    ed.add_comment_to_nodes(
        "Empty chamber: the click. Gated on \"out of ammunition\" AND \"off "
        "cooldown\" AND \"pressed this frame\", so the weapon clicks when the "
        "player needs to be told to reload, stays silent while it is merely "
        f"between shots (every {SMG_FIRE_INTERVAL:.2f}s on the SMG), and clicks "
        "once per pull rather than once per frame now that a HELD button opens "
        "the gate above.",
        made)
    return (BEL.find_then_pin(play), BEL.find_else_pin(click))
