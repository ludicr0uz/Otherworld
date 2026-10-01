"""The pick-up: the key takes ONE dropped item, the one nearest the reticle.

Every Dropped item within PICKUP_RADIUS of the player is a candidate. The loop
takes none of them: it only keeps the candidate nearest AimPoint, the point
the reticle rests on (aim.py resolves it every frame, armed or not), in
PickBest. The take runs once, after the loop, on that one item. Standing on a
pile, the player picks the item they are looking at, and a second press takes
the next.

PickupForced is the probe's stand-in for the key press: no key can be injected
into a headless game (probes/probe_pickup.py). It is OR'd with the key, the
press clears it, and it is false in every real game.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from combat.nodes import (
    FN_ACTOR_LOC, FN_ALL_ACTORS, FN_AND, FN_ARR_ADD, FN_ARR_LEN, FN_DISTANCE,
    FN_IS_VALID, FN_LESS_FF, FN_LESS_II, FN_OR, MACRO_FOR_EACH,
)
from combat.paths import ITEM_CLASS_PATH
from combat.tuning import INVENTORY_SIZE, PICKUP_KEY, PICKUP_RADIUS
from combat.weapon_component.common import _prop

PICK_BEST_VAR = "PickBest"          # the nearest candidate so far, or None
PICK_GAP_VAR = "PickBestGap"        # its distance to AimPoint, cm
PICKUP_FORCED_VAR = "PickupForced"  # a probe pressing the key
# What PickBestGap starts a search at: farther than any candidate can be from
# the aim point, which is at most the aim trace's kilometre out.
PICK_NO_GAP = 1.0e9


def _out(node, name):
    return _pin(node, name, is_input=False)


def _author_pickup(ed, owner, pressed, exec_ins, x0, y0):
    """E: take the dropped item nearest the reticle's point, if there is room.

    Returns (taken, idle): the exec pins a press that took an item leaves by,
    and the ones every other frame leaves by.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    forced = keep(_at(ed.add_get_member_variable_node(PICKUP_FORCED_VAR), x0 - 560, y0 + 280))
    wants = keep(_at(_node(ed, FN_OR), x0 - 280, y0 + 160))
    _connect(pressed, _pin(wants, "A"))
    _connect(_out(forced, PICKUP_FORCED_VAR), _pin(wants, "B"))
    gate = keep(_at(ed.add_branch_node(), x0, y0))
    _connect(_out(wants, "ReturnValue"), _pin(gate, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(gate, "execute"))

    spent = keep(_at(ed.add_set_member_variable_node(PICKUP_FORCED_VAR), x0 + 260, y0))
    _set(spent, PICKUP_FORCED_VAR, "false")
    _connect(BEL.find_then_pin(gate), _pin(spent, "execute"))
    # PickBest is set with its input pin left unconnected, which is how a
    # Blueprint object variable is cleared to None.
    forget = keep(_at(ed.add_set_member_variable_node(PICK_BEST_VAR), x0 + 520, y0))
    _connect(BEL.find_then_pin(spent), _pin(forget, "execute"))
    far = keep(_at(ed.add_set_member_variable_node(PICK_GAP_VAR), x0 + 780, y0))
    _set(far, PICK_GAP_VAR, PICK_NO_GAP)
    _connect(BEL.find_then_pin(forget), _pin(far, "execute"))

    cls = keep(_at(ed.add_get_member_variable_node("ItemClass"), x0 + 780, y0 + 240))
    every = keep(_at(_node(ed, FN_ALL_ACTORS), x0 + 1040, y0))
    _connect(_out(cls, "ItemClass"), _pin(every, "ActorClass"))
    _connect(BEL.find_then_pin(far), _pin(every, "execute"))

    loop = ed.add_macro_node(MACRO_FOR_EACH)
    if not loop:
        raise RuntimeError("could not create the ForEachLoop macro node")
    keep(_at(loop, x0 + 1320, y0))
    _connect(_out(every, "OutActors"), _loose_pin(loop, "Array"))
    _connect(BEL.find_then_pin(every), _loose_pin(loop, "Exec"))
    element = _loose_pin(loop, "ArrayElement", is_input=False)

    cast = keep(_at(_palette(ed, "Utilities|Casting|CastToBP_WeaponItem"), x0 + 1620, y0))
    _connect(element, _pin(cast, "Object"))
    _connect(_loose_pin(loop, "LoopBody", is_input=False), _pin(cast, "execute"))
    item = _loose_pin(cast, "AsBPWeaponItem", is_input=False)

    dropped_pin, dropped_n = _prop(ed, "Dropped", item, x0 + 1900, y0 + 260)
    keep(dropped_n)

    there = keep(_at(_node(ed, FN_ACTOR_LOC), x0 + 1900, y0 + 400))
    _connect(item, _pin(there, "self"))
    here = keep(_at(_node(ed, FN_ACTOR_LOC), x0 + 1900, y0 + 520))
    _connect(owner, _pin(here, "self"))
    gap = keep(_at(_node(ed, FN_DISTANCE), x0 + 2160, y0 + 440))
    _connect(_out(there, "ReturnValue"), _pin(gap, "V1"))
    _connect(_out(here, "ReturnValue"), _pin(gap, "V2"))
    near = keep(_at(_node(ed, FN_LESS_FF), x0 + 2400, y0 + 440))
    _connect(_out(gap, "ReturnValue"), _pin(near, "A"))
    _set(near, "B", PICKUP_RADIUS)

    # How far the candidate lies from the point the reticle rests on. Pure, so
    # the Branch and the Set below each compute it, from inputs that do not
    # change in between.
    aim = keep(_at(ed.add_get_member_variable_node("AimPoint"), x0 + 1900, y0 + 660))
    aim_gap = keep(_at(_node(ed, FN_DISTANCE), x0 + 2160, y0 + 620))
    _connect(_out(there, "ReturnValue"), _pin(aim_gap, "V1"))
    _connect(_out(aim, "AimPoint"), _pin(aim_gap, "V2"))
    best_gap = keep(_at(ed.add_get_member_variable_node(PICK_GAP_VAR), x0 + 2160, y0 + 780))
    closer = keep(_at(_node(ed, FN_LESS_FF), x0 + 2400, y0 + 620))
    _connect(_out(aim_gap, "ReturnValue"), _pin(closer, "A"))
    _connect(_out(best_gap, PICK_GAP_VAR), _pin(closer, "B"))

    and1 = keep(_at(_node(ed, FN_AND), x0 + 2640, y0 + 340))
    _connect(dropped_pin, _pin(and1, "A"))
    _connect(_out(near, "ReturnValue"), _pin(and1, "B"))
    and2 = keep(_at(_node(ed, FN_AND), x0 + 2880, y0 + 420))
    _connect(_out(and1, "ReturnValue"), _pin(and2, "A"))
    _connect(_out(closer, "ReturnValue"), _pin(and2, "B"))

    # The loop body only remembers. Taking inside it is how one press used to
    # pick up every item in reach.
    better = keep(_at(ed.add_branch_node(), x0 + 3120, y0))
    _connect(_out(and2, "ReturnValue"), _pin(better, "Condition"))
    _connect(BEL.find_then_pin(cast), _pin(better, "execute"))
    remember = keep(_at(ed.add_set_member_variable_node(PICK_BEST_VAR), x0 + 3380, y0))
    _connect(item, _pin(remember, PICK_BEST_VAR))
    _connect(BEL.find_then_pin(better), _pin(remember, "execute"))
    at_gap = keep(_at(ed.add_set_member_variable_node(PICK_GAP_VAR), x0 + 3640, y0))
    _connect(_out(aim_gap, "ReturnValue"), _pin(at_gap, PICK_GAP_VAR))
    _connect(BEL.find_then_pin(remember), _pin(at_gap, "execute"))

    # --- after the loop: take the one that was kept ---------------------------
    y1 = y0 + 1000
    best_get = keep(_at(ed.add_get_member_variable_node(PICK_BEST_VAR), x0 + 1320, y1 + 260))
    best = _out(best_get, PICK_BEST_VAR)
    any_best = keep(_at(_node(ed, FN_IS_VALID), x0 + 1580, y1 + 260))
    _connect(best, _pin(any_best, "Object"))
    found = keep(_at(ed.add_branch_node(), x0 + 1840, y1))
    _connect(_out(any_best, "ReturnValue"), _pin(found, "Condition"))
    _connect(_loose_pin(loop, "Completed", is_input=False), _pin(found, "execute"))

    inv = keep(_at(ed.add_get_member_variable_node("Inventory"), x0 + 1580, y1 + 420))
    count = keep(_at(_node(ed, FN_ARR_LEN), x0 + 1840, y1 + 420))
    _connect(_out(inv, "Inventory"), _pin(count, "TargetArray"))
    fits = keep(_at(_node(ed, FN_LESS_II), x0 + 2080, y1 + 420))
    _connect(_out(count, "ReturnValue"), _pin(fits, "A"))
    _set(fits, "B", INVENTORY_SIZE)
    room = keep(_at(ed.add_branch_node(), x0 + 2320, y1))
    _connect(_out(fits, "ReturnValue"), _pin(room, "Condition"))
    _connect(BEL.find_then_pin(found), _pin(room, "execute"))

    clear = keep(_at(ed.add_set_member_variable_node("Dropped", ITEM_CLASS_PATH),
                     x0 + 2580, y1))
    _connect(best, _pin(clear, "self"))
    _set(clear, "Dropped", "false")
    _connect(BEL.find_then_pin(room), _pin(clear, "execute"))

    inv2 = keep(_at(ed.add_get_member_variable_node("Inventory"), x0 + 2580, y1 + 300))
    add = keep(_at(_node(ed, FN_ARR_ADD), x0 + 2840, y1))
    _connect(_out(inv2, "Inventory"), _pin(add, "TargetArray"))
    _connect(best, _pin(add, "NewItem"))
    _connect(BEL.find_then_pin(clear), _pin(add, "execute"))

    # A pick-up goes into the bag and whatever is in the hand stays there.
    # Only empty hands take it up: after dropping or eating the last item,
    # Held is None and EquippedIndex may be -1, so nothing would be shown.
    # Array_Add's ReturnValue is the new item's index (an exec node's output,
    # read once).
    held = keep(_at(ed.add_get_member_variable_node("Held"), x0 + 2840, y1 + 300))
    armed = keep(_at(_node(ed, FN_IS_VALID), x0 + 3100, y1 + 300))
    _connect(_out(held, "Held"), _pin(armed, "Object"))
    empty = keep(_at(ed.add_branch_node(), x0 + 3100, y1))
    _connect(_out(armed, "ReturnValue"), _pin(empty, "Condition"))
    _connect(BEL.find_then_pin(add), _pin(empty, "execute"))
    at = keep(_at(ed.add_set_member_variable_node("EquippedIndex"), x0 + 3360, y1 + 120))
    _connect(_out(add, "ReturnValue"), _pin(at, "EquippedIndex"))
    _connect(BEL.find_else_pin(empty), _pin(at, "execute"))

    ed.add_comment_to_nodes(
        f"{PICKUP_KEY} picks up ONE item: of those flagged Dropped within "
        f"{PICKUP_RADIUS:.0f} cm of the player, the one nearest AimPoint, the "
        "point the reticle rests on. The loop only remembers it (PickBest); "
        f"the take runs once, after the loop, while fewer than {INVENTORY_SIZE} "
        "are carried. It goes into the inventory without switching to it: the "
        "held item stays held. Only empty hands (Held is None) take it up.",
        made)
    taken = (BEL.find_then_pin(empty), BEL.find_then_pin(at))
    idle = (BEL.find_else_pin(gate), BEL.find_else_pin(found), BEL.find_else_pin(room))
    return taken, idle
