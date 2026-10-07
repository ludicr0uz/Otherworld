"""The inventory's and the clothing's asks: one custom event each, which the
HUD calls in place of writing the component's request variables.

    AskSlot(Slot)          SlotRequest := Slot
    AskMove(From, To)      MoveTo := To, MoveFrom := From
    AskNext()              NextRequest := 1 (the Q key: the bag's next item)
    AskTakeOff(Slot, To)   TakeOffTo := To, TakeOffSlot := Slot
    AskWear(From)          WearRequest := From
    AskDrop(From)          DropRequest := From

Each raises the request the component's own Tick already serves (slot_moves.py,
wear.py, wear_drag.py, drop_request.py), where what fits where is decided, so
nothing about a move changed: the event is the one door a screen comes
through. The request that gates the serve is written last (MoveFrom,
TakeOffSlot), after the one it is read with. A probe may still write the
request variables themselves, on the machine that serves them.

The slots' three and the drop (ask_consts.SERVER_ASKS: AskSlot, AskMove,
AskNext, M18; AskDrop, M23) are reliable Server events: the owning client's
HUD and its keys call them, the request is raised on the server's copy, and
the server's Tick serves it (slot_moves.py, drop_request.py), where a slot
out of range, an empty one or an item that does not fit is refused. In
single player a Server event is a plain call, so nothing there changed.
"""

from uebp.graph import _connect, _pin, _set, out, then
from uebp.net import custom_event, server_event
from uebp.vars import INT
from combat.ask_consts import (
    ASK_DROP, ASK_MOVE, ASK_NEXT, ASK_SLOT, ASK_TAKE_OFF, ASK_WEAR, FROM_PARAM, INT_ASKS,
    SERVER_ASKS, SLOT_PARAM, TO_PARAM,
)
from combat.slot_tuning import (
    DROP_REQUEST_VAR, MOVE_FROM_VAR, MOVE_TO_VAR, NEXT_REQUEST_VAR, SLOT_REQUEST_VAR)
from combat.wear_tuning import TAKE_OFF_TO_VAR, TAKE_OFF_VAR, WEAR_REQUEST_VAR

# event -> the (request variable, the parameter it takes), in write order. A
# literal in a parameter's place is what the event writes, asked nothing.
RAISED = "1"
WRITES = {
    ASK_SLOT: ((SLOT_REQUEST_VAR, SLOT_PARAM),),
    ASK_MOVE: ((MOVE_TO_VAR, TO_PARAM), (MOVE_FROM_VAR, FROM_PARAM)),
    ASK_NEXT: ((NEXT_REQUEST_VAR, RAISED),),
    ASK_TAKE_OFF: ((TAKE_OFF_TO_VAR, TO_PARAM), (TAKE_OFF_VAR, SLOT_PARAM)),
    ASK_WEAR: ((WEAR_REQUEST_VAR, FROM_PARAM),),
    ASK_DROP: ((DROP_REQUEST_VAR, FROM_PARAM),),
}


def author_asks(ed):
    """The events (see the module docstring). Before the Tick, whose keys
    call the slots' by name."""
    for name, params in INT_ASKS:
        make = server_event if name in SERVER_ASKS else custom_event
        event = make(ed, name, [(p, INT) for p in params])
        made, flow = [event], then(event)
        for var, param in WRITES[name]:
            put = ed.add_set_member_variable_node(var)
            if param in params:
                _connect(out(event, param), _pin(put, var))
            else:
                _set(put, var, param)
            _connect(flow, _pin(put, "execute"))
            made.append(put)
            flow = then(put)
        ed.add_comment_to_nodes(
            f"{name}: what a screen asks; this component's Tick serves it (asks.py).", made)
