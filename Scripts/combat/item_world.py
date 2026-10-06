"""An item loose in the world is an actor every client is sent (task M20).

What a player carries is the server's item actors, which do not replicate: a
client's are a picture of the record (weapon_component/record.py, view.py).
An item that leaves a hand for the world is the same actor on the server,
made a replicated one on the way out:

    into the world    InWorld = true, SetReplicateMovement(true),
    (the throw's      SetReplicates(true): every client is sent the actor,
    release)          where it is, what it is attached to (a blade left in
                      a body rides its bone), and its Dropped and Lodged
    out of it         InWorld = false: the server's actor goes into an
    (the take)        inventory, attached to a hand or hidden in a bag

Replication is never switched off again. This project replicates through the
engine's generic driver (not Iris), where SetReplicates(false) leaves each
client's copy standing where it last was, for good. A client's copy hides
itself while the item is not InWorld (its Tick, behind HasAuthority's false
arm), whatever the server's own hidden flag says: the carrier's hand is drawn
from the record's picture, not from this copy. The engine closes the channel
of a hidden actor with no collision by itself, so a copy of an item in a bag
is gone a few seconds on.

Thrown items only, for now: an item dropped, placed or left by a kill is
still each machine's own (M23), and what its drop must do is call
author_into_world.
"""

from combat import item_vars as IV
from combat.paths import ITEM_CLASS_PATH
from uebp import net
from uebp.g import _G
from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from uebp.nodes.actor import (
    FN_HAS_AUTHORITY, FN_SET_HIDDEN, FN_SET_REPLICATE_MOVEMENT, FN_SET_REPLICATES)
from uebp.nodes.math import FN_NOT

REPLICATED = (IV.Dropped, IV.Lodged, IV.InWorld)


def replicate_item(bp):
    """BP_WeaponItem's world state travels to everyone. After every declare,
    which drops the flags (uebp/CLAUDE.md). The class itself does not
    replicate: an item starts when it enters the world."""
    for var in REPLICATED:
        net.replicate(bp, var)


def author_into_world(ed, item, exec_ins):
    """In a component's graph, with authority: ``item`` leaves for the world.
    Returns the exec pin after it."""
    g = _G(ed, ITEM_CLASS_PATH)
    flow = g.iput(item, IV.InWorld, "true", exec_ins)
    moves = g.call(FN_SET_REPLICATE_MOVEMENT, [flow], self=item, bInReplicateMovement="true")
    sent = g.call(FN_SET_REPLICATES, [then(moves)], self=item, bInReplicates="true")
    ed.add_comment_to_nodes(
        "The item is the world's now (item_world.py): InWorld, and the server's "
        "actor replicates from here on, with its movement and what it is "
        "attached to.", g.made)
    return then(sent)


def author_out_of_world(ed, item, exec_ins):
    """In a component's graph, with authority: ``item`` is taken out of the
    world. Each client's copy of it hides itself. Returns the exec pin after
    it."""
    g = _G(ed, ITEM_CLASS_PATH)
    return g.iput(item, IV.InWorld, "false", exec_ins)


def author_world_view(ed, exec_ins):
    """In the item's own Tick: a client's copy of a replicated item is shown
    only while the item is InWorld. Returns the exec pins to carry on from."""
    owns = _node(ed, FN_HAS_AUTHORITY)
    gate = ed.add_branch_node()
    _connect(out(owns), _pin(gate, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(gate, "execute"))
    carried = _node(ed, FN_NOT)
    _connect(out(ed.add_get_member_variable_node(IV.InWorld), IV.InWorld), _pin(carried, "A"))
    hide = _node(ed, FN_SET_HIDDEN)
    _connect(out(carried), _pin(hide, "bNewHidden"))
    _connect(else_(gate), _pin(hide, "execute"))
    ed.add_comment_to_nodes(
        "A client's copy of a replicated item (item_world.py) is shown only "
        "while the item is InWorld: carried, the hand that holds it is drawn "
        "from the record's picture, not from this copy.", [owns, gate, carried, hide])
    return (then(gate), then(hide))
