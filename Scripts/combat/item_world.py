"""An item loose in the world is an actor every client is sent (tasks M20,
M23).

What a player carries is the server's item actors, which do not replicate: a
client's are a picture of the record (weapon_component/record.py, view.py).
An item in the world is the server's actor, made a replicated one as it
gets there:

    into the world    InWorld = true, SetReplicateMovement(true),
                      SetReplicates(true): every client is sent the actor,
                      where it is, what it is attached to (a blade left in
                      a body rides its bone), its Dropped and Lodged, and
                      whether it burns or is hot (Lit, Hot)
      the throw's release (author_into_world, in the component's graph)
      lying there Dropped: the item's own Tick, on the server
        (author_world_view), which is every other way in: set down with the
        drop key or dragged out of the inventory, placed in the level, left
        by a kill, cut from a tree, spawned by anything written later. No
        graph that makes an item lie in the world has to remember to.
    out of it         InWorld = false: the server's actor goes into an
    (the take)        inventory, attached to a hand or hidden in a bag

An item placed in the level is loaded by every machine. The server's starts
replicating on its first Tick, and the client's own copy of it becomes the
server's (a level actor is named the same on both, so the engine joins them,
not spawns a second): from then on its Dropped and InWorld are the server's.
A take of one destroys the server's actor and puts a fresh one of its class
in the inventory (weapon_component/pickup.py): the engine tells every client,
and every client that joins later, of a destroyed level actor, where a
hidden one would stand in a late joiner's level as the level has it (task
A2). A take of a spawned item (set down, thrown, dropped by a kill) keeps the
one actor, hidden on each client while it is not InWorld.

The actor sleeps while the item lies still or is carried (task A2): its own
Tick on the server sets NetDormancy DormantAll while Dropped or not InWorld,
and Awake in flight (_author_rest; Dormant remembers which, so the engine is
told on the change alone). A dormant actor is sent to a connection once, and
its channel closed until it is woken: FlushNetDormancy, which author_wake
authors, after each write of its replicated state while it lies there (into
and out of the world here; a lying stick burning out, stick.py; a lying blade
cooling, heat.py). The server's replication graph (Source/Otherworld/Public/
OtherworldReplicationGraph.h) keeps a dormant actor in its grid cell as a
still one, and relevance_item writes how far an item is sent and how often
(net/relevancy_consts.py). In standalone a dormant actor still ticks and
nothing is culled.

Replication is never switched off again. This project replicates through the
engine's generic driver (not Iris), where SetReplicates(false) leaves each
client's copy standing where it last was, for good. A client's copy hides
itself while the item is not InWorld (its Tick, behind HasAuthority's false
arm), whatever the server's own hidden flag says: the carrier's hand is drawn
from the record's picture, not from this copy. The engine closes the channel
of a hidden actor with no collision by itself, so a copy of an item in a bag
is gone a few seconds on.

Left for M31: what else a late joiner is told of (corpses, chopped trees),
and a cleanup rule for what lies in a long-running world.
"""

from combat import item_vars as IV
from combat.heat_tuning import HOT_VAR
from combat.paths import ITEM_CLASS_PATH
from combat.torch_tuning import LIT_VAR
from uebp import net
from uebp.g import _G
from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from net import relevancy
from net.relevancy_consts import ITEM
from uebp.nodes.actor import (
    FN_FLUSH_NET_DORMANCY, FN_HAS_AUTHORITY, FN_SET_HIDDEN, FN_SET_NET_DORMANCY,
    FN_SET_REPLICATE_MOVEMENT, FN_SET_REPLICATES)
from uebp.nodes.math import FN_AND, FN_NEQ_BB, FN_NOT, FN_OR
from uebp.nodes.system import FN_IS_SERVER

# The enum literals SetNetDormancy's pin takes.
DORMANT, AWAKE = "DORM_DormantAll", "DORM_Awake"

# Lit and Hot: a burning stick or a hot blade lying there is seen so by
# everyone (task M25, combat/fire_vars.py).
REPLICATED = (IV.Dropped, IV.Lodged, IV.InWorld, LIT_VAR, HOT_VAR)


def replicate_item(bp):
    """BP_WeaponItem's world state travels to everyone. After every declare,
    which drops the flags (uebp/CLAUDE.md). The class itself does not
    replicate: an item starts when it enters the world."""
    for var in REPLICATED:
        net.replicate(bp, var)


def relevance_item(bp):
    """How far an item in the world is sent, and how often: the ITEM row of
    net/relevancy_consts.py, on the class defaults. After a compile."""
    relevancy.apply(bp, ITEM)


def author_wake(ed, exec_ins, item=None):
    """With authority: ``item`` (this actor, given none) is sent once more
    though dormant (FlushNetDormancy). After a write of its replicated state
    while it lies in the world. Returns the exec pin after it."""
    g = _G(ed, ITEM_CLASS_PATH)
    woke = g.call(FN_FLUSH_NET_DORMANCY, exec_ins, **({"self": item} if item is not None else {}))
    return then(woke)


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
    flow = g.iput(item, IV.InWorld, "false", exec_ins)
    # The item lay dormant: the lowered InWorld is sent, or no client would
    # ever hide its copy.
    return author_wake(ed, [flow], item)


def _author_enter_world(ed, exec_in):
    """In the item's own Tick, with authority: an item lying Dropped that is
    not yet the world's becomes it, on the server (and in single player,
    where it is sent to no one). Not on a client, whose own copy of a placed
    item has authority until the server's reaches it. Returns the exec pins
    to carry on from."""
    lying = _node(ed, FN_AND)
    _connect(out(ed.add_get_member_variable_node(IV.Dropped), IV.Dropped), _pin(lying, "A"))
    kept = _node(ed, FN_NOT)
    _connect(out(ed.add_get_member_variable_node(IV.InWorld), IV.InWorld), _pin(kept, "A"))
    _connect(out(kept), _pin(lying, "B"))
    here = _node(ed, FN_AND)
    _connect(out(lying), _pin(here, "A"))
    _connect(out(_node(ed, FN_IS_SERVER)), _pin(here, "B"))
    enter = ed.add_branch_node()
    _connect(out(here), _pin(enter, "Condition"))
    _connect(exec_in, _pin(enter, "execute"))
    flag = ed.add_set_member_variable_node(IV.InWorld)
    _set(flag, IV.InWorld, True)
    _connect(then(enter), _pin(flag, "execute"))
    moves = _node(ed, FN_SET_REPLICATE_MOVEMENT)
    _set(moves, "bInReplicateMovement", True)
    _connect(then(flag), _pin(moves, "execute"))
    sent = _node(ed, FN_SET_REPLICATES)
    _set(sent, "bInReplicates", True)
    _connect(then(moves), _pin(sent, "execute"))
    # Set down again after a carry, it is where it lies now, not where it
    # went dormant: sent once more.
    woke = _node(ed, FN_FLUSH_NET_DORMANCY)
    _connect(then(sent), _pin(woke, "execute"))
    ed.add_comment_to_nodes(
        "An item lying Dropped is the world's (item_world.py): on the server, "
        "the first Tick it is found so makes it InWorld and a replicated actor, "
        "however it came to lie there (set down, placed in the level, left by a "
        "kill), and sends it once more if it lay dormant.",
        [lying, kept, here, enter, flag, moves, sent, woke])
    return (else_(enter), then(woke))


def _author_rest(ed, exec_ins):
    """In the item's own Tick, with authority: the actor sleeps (NetDormancy
    DormantAll) while the item lies still or is carried, and is awake in
    flight: Dropped, or not InWorld. Dormant remembers what was last set, so
    the engine is told on the change alone. Returns the exec pins to carry
    on from."""
    g = _G(ed, ITEM_CLASS_PATH)
    still = out(g.call(FN_OR, A=g.get(IV.Dropped),
                       B=out(g.call(FN_NOT, A=g.get(IV.InWorld)))))
    changed, same = g.branch(out(g.call(FN_NEQ_BB, A=still, B=g.get(IV.Dormant))), exec_ins)
    rest, wake = g.branch(still, [changed])
    sleep = g.call(FN_SET_NET_DORMANCY, [rest], NewDormancy=DORMANT)
    asleep = g.put(IV.Dormant, "true", [then(sleep)])
    up = g.call(FN_SET_NET_DORMANCY, [wake], NewDormancy=AWAKE)
    awake = g.put(IV.Dormant, "false", [then(up)])
    ed.add_comment_to_nodes(
        f"The actor sleeps while the item lies still or is carried ({IV.Dropped}, "
        f"or not {IV.InWorld}): NetDormancy {DORMANT}, so it is sent to a client "
        f"once and its channel closed until a graph wakes it (item_world.py). In "
        f"flight it is {AWAKE}. {IV.Dormant} remembers which, so the engine is "
        "told on the change alone.", g.made)
    return (same, asleep, awake)


def author_world_view(ed, exec_ins):
    """In the item's own Tick: the server's item lying Dropped enters the
    world (_author_enter_world), and a client's copy of a replicated item is
    shown only while the item is InWorld. Returns the exec pins to carry on
    from."""
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
    return _author_rest(ed, list(_author_enter_world(ed, then(gate)))) + (then(hide),)
