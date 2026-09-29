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
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from combat.nodes import (
    FN_ARR_LEN, FN_ARR_REMOVE, FN_DESTROY, FN_MIN_II, FN_SEND_GAMEPLAY_EVENT,
    FN_SUB_II, NODE_MAKE_EVENT_DATA,
)
from combat.tuning import CONSUME_EVENT_TAG


def _author_consume(ed, held, owner, exec_in, x0, y0):
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

    payload = keep(_at(_palette(ed, NODE_MAKE_EVENT_DATA), x0, y0 + 300))
    _connect(held, _loose_pin(payload, "OptionalObject"))
    _connect(owner, _loose_pin(payload, "Instigator"))
    _connect(owner, _loose_pin(payload, "Target"))

    send = keep(_at(_node(ed, FN_SEND_GAMEPLAY_EVENT), x0 + 320, y0))
    _connect(owner, _pin(send, "Actor"))
    _set(send, "EventTag", f'(TagName="{CONSUME_EVENT_TAG}")')
    _connect(BEL.list_output_pins(payload)[0], _pin(send, "Payload"))
    _connect(exec_in, _pin(send, "execute"))

    inv = keep(_at(ed.add_get_member_variable_node("Inventory"), x0 + 320, y0 + 300))
    inv_out = _pin(inv, "Inventory", is_input=False)
    idx = keep(_at(ed.add_get_member_variable_node("EquippedIndex"), x0 + 320, y0 + 420))
    idx_out = _pin(idx, "EquippedIndex", is_input=False)
    remove = keep(_at(_node(ed, FN_ARR_REMOVE), x0 + 620, y0))
    _connect(inv_out, _pin(remove, "TargetArray"))
    _connect(idx_out, _pin(remove, "IndexToRemove"))
    _connect(BEL.find_then_pin(send), _pin(remove, "execute"))

    gone = keep(_at(_node(ed, FN_DESTROY), x0 + 900, y0))
    _connect(held, _pin(gone, "self"))
    _connect(BEL.find_then_pin(remove), _pin(gone, "execute"))

    # Held is set with its input pin left unconnected: that clears it to None,
    # the same way dropping does.
    clear = keep(_at(ed.add_set_member_variable_node("Held"), x0 + 1180, y0))
    _connect(BEL.find_then_pin(gone), _pin(clear, "execute"))

    # Min(EquippedIndex, Length - 1). Length is pure, so it is read here --
    # after the removal above -- and sees the shorter array.
    count = keep(_at(_node(ed, FN_ARR_LEN), x0 + 900, y0 + 300))
    _connect(inv_out, _pin(count, "TargetArray"))
    last = keep(_at(_node(ed, FN_SUB_II), x0 + 1180, y0 + 300))
    _connect(_pin(count, "ReturnValue", is_input=False), _pin(last, "A"))
    _set(last, "B", 1)
    clamp = keep(_at(_node(ed, FN_MIN_II), x0 + 1440, y0 + 300))
    _connect(idx_out, _pin(clamp, "A"))
    _connect(_pin(last, "ReturnValue", is_input=False), _pin(clamp, "B"))
    stay = keep(_at(ed.add_set_member_variable_node("EquippedIndex"), x0 + 1440, y0))
    _connect(_pin(clamp, "ReturnValue", is_input=False), _pin(stay, "EquippedIndex"))
    _connect(BEL.find_then_pin(clear), _pin(stay, "execute"))

    dirty = keep(_at(ed.add_set_member_variable_node("NeedsRefresh"), x0 + 1700, y0))
    _set(dirty, "NeedsRefresh", "true")
    _connect(BEL.find_then_pin(stay), _pin(dirty, "execute"))

    ed.add_comment_to_nodes(
        f"A Consumable is used, not fired: send {CONSUME_EVENT_TAG} to the owner "
        "with the item as OptionalObject (GA_ConsumeItem answers it), THEN take "
        "it out of Inventory and destroy it -- the ability reads the item's "
        "restore values synchronously inside the send.",
        made)
    return BEL.find_then_pin(dirty)
