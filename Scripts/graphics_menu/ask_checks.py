"""The verifier's checks that the HUD asks (ask.py) rather than acts: the
shared lookups, and the rule itself."""

import unreal

from combat import ask_consts as AC
from combat.slot_tuning import (
    DROP_REQUEST_VAR, MOVE_FROM_VAR, MOVE_TO_VAR, NEXT_REQUEST_VAR, SLOT_REQUEST_VAR)
from combat.wear_tuning import TAKE_OFF_TO_VAR, TAKE_OFF_VAR, WEAR_REQUEST_VAR
from loot.consts import BODY_ARRAYS

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary

# What only the weapon component writes: its requests, its countdown, what
# is carried, and what a body carries.
COMPONENT_ONLY = (
    SLOT_REQUEST_VAR, NEXT_REQUEST_VAR, MOVE_FROM_VAR, MOVE_TO_VAR, DROP_REQUEST_VAR,
    TAKE_OFF_VAR, TAKE_OFF_TO_VAR, WEAR_REQUEST_VAR, AC.EXIT_PENDING_VAR, AC.EXIT_AT_VAR,
    AC.EXIT_STARTED_VAR, AC.EXIT_CALLED_OFF_VAR, AC.EXIT_DUE_VAR)


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _pins(n):
    return {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(n)}


def feeders(n, pin):
    p = BEL.find_input_pin(n, pin)
    return [PIN.get_owning_node(q) for q in (p.list_connected_pins() if p else [])]


def asks(nodes, name):
    """The calls of the weapon component's event ``name``, on a cast of it."""
    return [n for n in nodes if "self" in _pins(n) and "execute" in _pins(n)
            and _title(n).split(" ")[0] == name
            and any("Cast" in _title(f) for f in feeders(n, "self"))]


def fed(n, pin):
    """The titles of what feeds ``pin`` of ``n``."""
    return [_title(f) for f in feeders(n, pin)]


def check_asks(check, nodes):
    counts = {name: len(asks(nodes, name)) for name in AC.ALL_ASKS}
    # AskNext is the Q key's, on the component: no screen asks it.
    want = {AC.ASK_SLOT: 2, AC.ASK_MOVE: 1, AC.ASK_NEXT: 0, AC.ASK_TAKE_OFF: 2, AC.ASK_WEAR: 1,
            AC.ASK_DROP: 1, AC.ASK_LOOT_TAKE: 1, AC.ASK_SAVE_EXIT: 1}
    check("the HUD asks the weapon component for each thing the player does through "
          "a screen: a slot to hand and a take-off (the keys, and the mouse), a move, "
          "a wear, a drop, a loot take, save and exit", counts == want, str(counts))
    writes = sorted(_title(n) for n in nodes
                    if _title(n) in {f"Set {v}" for v in COMPONENT_ONLY})
    check("...and writes none of its requests or its countdown itself", not writes,
          str(writes))
    removes = sorted(t for n in nodes if "IndexToRemove" in _pins(n)
                     for t in fed(n, "TargetArray")
                     if t in {f"Get {v}" for v in BODY_ARRAYS})
    moves = [n for n in nodes if "DisableMovement" in _title(n).replace(" ", "")
             or "NewMovementMode" in _pins(n)]
    check("...takes nothing out of a body, and neither stops nor frees the character",
          not removes and not moves, f"{removes}, {len(moves)} movement calls")
