"""Using a consumable: the fire key, pressed while the held item is flagged
Consumable, eats or drinks it instead of firing it.

The weapon component does not know what eating is. It announces the use as a
Gameplay Ability System event -- CONSUME_EVENT_TAG, with the item as the
payload's OptionalObject -- and then spends the item: out of Inventory and out
of the world. What the use *does* is up to whichever ability the owner's
AbilitySystemComponent has granted for that tag (GA_ConsumeItem, built by
Scripts/survival), which is the standard GAS shape for "use an item" and keeps
this package free of any reference to hunger or thirst. An owner with no
ability system, or none granted, simply loses the item.

The event goes out BEFORE the item is destroyed, and that order is load-bearing:
SendGameplayEventToActor activates the triggered ability synchronously, and the
ability reads HungerRestore/ThirstRestore off the payload. Destroyed first, it
would read them off an actor that is already pending kill.

The press that eats an item is spent: TRIGGER_SPENT is set with the item gone,
and the fire gate stays shut until the key comes up. Without it, the item that
slides into the emptied slot is equipped the same frame and the press still
held down fires it -- an automatic on the next frame, anything on a press that
is still reported.
"""

from uebp.graph import BEL, _connect, _loose_pin, _node, _palette, _pin, _set, else_, out, then
from combat.tuning import CONSUME_EVENT_TAG
from combat.weapon_component.common import _prop
from combat.paths import ITEM_CLASS_PATH
from Sound.play import _author_random_sound
from uebp.nodes.actor import FN_ACTOR_LOC, FN_DESTROY
from uebp.nodes.array import FN_ARR_LEN, FN_ARR_REMOVE
from uebp.nodes.gas import FN_SEND_GAMEPLAY_EVENT
from uebp.nodes.math import FN_AND, FN_MIN_II, FN_NOT, FN_SUB_II
from uebp.nodes.palette import NODE_MAKE_EVENT_DATA
from combat import item_vars as IV
from combat.weapon_component import vars as WV

# The fire press that used an item, still held. Declared in build.py.
TRIGGER_SPENT = "TriggerSpent"


def _author_trigger_latch(ed, holding, exec_ins):
    """Re-arm the trigger once the fire key is up: TriggerSpent &= holding.

    One unconditional Set per frame, before the fire gate. Returns the exit
    pin and a NOT TriggerSpent pin for the fire gate's condition; that Get is
    pulled when the gate runs, after this Set, so the release frame is
    already armed.
    """
    spent = ed.add_get_member_variable_node(TRIGGER_SPENT)
    spent_out = out(spent, TRIGGER_SPENT)
    still = _node(ed, FN_AND)
    _connect(spent_out, _pin(still, "A"))
    _connect(holding, _pin(still, "B"))
    latch = ed.add_set_member_variable_node(TRIGGER_SPENT)
    _connect(out(still), _pin(latch, TRIGGER_SPENT))
    for exit_pin in exec_ins:
        _connect(exit_pin, _pin(latch, "execute"))
    free = _node(ed, FN_NOT)
    _connect(spent_out, _pin(free, "A"))
    ed.add_comment_to_nodes(
        "The press that ate an item stays spent until the fire key is up, so it "
        "cannot also fire the weapon that is equipped in the item's place.",
        [spent, still, latch, free])
    return (then(latch), out(free))


def _author_use_gate(ed, held, owner, tap, exec_in, not_edible, wear_gate):
    """Branch a Consumable off the fire gate; a tap uses it.

    A Consumable is used rather than fired, and only on the tap: a held button
    must not eat a stack of mushrooms at frame rate. Inside the fire gate for
    the same reason the ammunition test is -- Consumable is read off Held --
    and so it also inherits "not while sprinting". A non-consumable goes on to
    `not_edible` (the ready gate). Returns the exits: [eaten, worn], and not
    tapped.
    """
    edible, edible_n = _prop(ed, IV.Consumable, held)
    use_gate = ed.add_branch_node()
    _connect(edible, _pin(use_gate, "Condition"))
    _connect(exec_in, _pin(use_gate, "execute"))
    _connect(else_(use_gate), not_edible)
    use_tap = ed.add_branch_node()
    _connect(tap, _pin(use_tap, "Condition"))
    _connect(then(use_gate), _pin(use_tap, "execute"))
    # A garment is Consumable too, and its use is wearing it: `wear_gate`
    # (wear._author_wear_gate, handed in by tick.py) takes the tap and hands
    # back what is not a garment, which is eaten.
    worn, not_garment = wear_gate(ed, held, then(use_tap))
    consumed = _author_consume(ed, held, owner, not_garment)
    ed.add_comment_to_nodes(
        "The held item is Consumable: a tap uses it (consume.py) instead of "
        "firing it, and a held button does nothing. A garment's use is to "
        "wear it (wear.py).",
        [edible_n, use_gate, use_tap])
    return [consumed, worn], else_(use_tap)


def _author_consume(ed, held, owner, exec_in):
    """Send the use event, then remove and destroy the held item.

    Returns the exec pin to carry on from. The equipped index stays where it
    was, clamped to the shorter inventory, so eating one of a stack of
    mushrooms leaves the next one in hand -- and an emptied inventory clamps to
    -1, which the equip loop matches against nothing, leaving the hands empty.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    payload = keep(_palette(ed, NODE_MAKE_EVENT_DATA))
    _connect(held, _loose_pin(payload, "OptionalObject"))
    _connect(owner, _loose_pin(payload, "Instigator"))
    _connect(owner, _loose_pin(payload, "Target"))

    # Heard first, while the item is still there to be asked for its takes:
    # one of its UseSounds (food's eating; an item with none is silent).
    takes = keep(ed.add_get_member_variable_node(IV.UseSounds, ITEM_CLASS_PATH))
    _connect(held, _pin(takes, "self"))
    here = keep(_node(ed, FN_ACTOR_LOC))
    _connect(owner, _pin(here, "self"))
    sounded, heard = _author_random_sound(ed, IV.UseSounds, out(here), exec_in,
                                          source=out(takes, IV.UseSounds))
    made.extend(sounded)

    send = keep(_node(ed, FN_SEND_GAMEPLAY_EVENT))
    _connect(owner, _pin(send, "Actor"))
    _set(send, "EventTag", f'(TagName="{CONSUME_EVENT_TAG}")')
    _connect(BEL.list_output_pins(payload)[0], _pin(send, "Payload"))
    _connect(heard, _pin(send, "execute"))

    inv = keep(ed.add_get_member_variable_node(WV.Inventory))
    inv_out = out(inv, WV.Inventory)
    idx = keep(ed.add_get_member_variable_node(WV.EquippedIndex))
    idx_out = out(idx, WV.EquippedIndex)
    remove = keep(_node(ed, FN_ARR_REMOVE))
    _connect(inv_out, _pin(remove, "TargetArray"))
    _connect(idx_out, _pin(remove, "IndexToRemove"))
    _connect(then(send), _pin(remove, "execute"))

    gone = keep(_node(ed, FN_DESTROY))
    _connect(held, _pin(gone, "self"))
    _connect(then(remove), _pin(gone, "execute"))

    # Held is set with its input pin left unconnected: that clears it to None,
    # the same way dropping does.
    clear = keep(ed.add_set_member_variable_node(WV.Held))
    _connect(then(gone), _pin(clear, "execute"))

    # Min(EquippedIndex, Length - 1). Length is pure, so it is read here --
    # after the removal above -- and sees the shorter array.
    count = keep(_node(ed, FN_ARR_LEN))
    _connect(inv_out, _pin(count, "TargetArray"))
    last = keep(_node(ed, FN_SUB_II))
    _connect(out(count), _pin(last, "A"))
    _set(last, "B", 1)
    clamp = keep(_node(ed, FN_MIN_II))
    _connect(idx_out, _pin(clamp, "A"))
    _connect(out(last), _pin(clamp, "B"))
    stay = keep(ed.add_set_member_variable_node(WV.EquippedIndex))
    _connect(out(clamp), _pin(stay, WV.EquippedIndex))
    _connect(then(clear), _pin(stay, "execute"))

    dirty = keep(ed.add_set_member_variable_node(WV.NeedsRefresh))
    _set(dirty, WV.NeedsRefresh, True)
    _connect(then(stay), _pin(dirty, "execute"))

    # The press is spent; _author_trigger_latch re-arms it on release.
    spend = keep(ed.add_set_member_variable_node(TRIGGER_SPENT))
    _set(spend, TRIGGER_SPENT, True)
    _connect(then(dirty), _pin(spend, "execute"))

    ed.add_comment_to_nodes(
        f"A Consumable is used, not fired: one of its UseSounds is heard, then send {CONSUME_EVENT_TAG} to the owner "
        "with the item as OptionalObject (GA_ConsumeItem answers it), THEN take "
        "it out of Inventory and destroy it -- the ability reads the item's "
        "restore values synchronously inside the send. The press is then "
        "spent, so it cannot fire whatever is equipped next.",
        made)
    return then(spend)
