"""The inventory's and the clothing's asks: one custom event each, which the
HUD calls in place of writing the component's request variables.

    AskSlot(Slot)          SlotRequest := Slot
    AskMove(From, To)      MoveTo := To, MoveFrom := From
    AskTakeOff(Slot, To)   TakeOffTo := To, TakeOffSlot := Slot
    AskWear(From)          WearRequest := From
    AskDrop(From)          DropRequest := From

Each raises the request the component's own Tick already serves (slot_moves.py,
wear.py, wear_drag.py, drop_request.py), where what fits where is decided, so
nothing about a move changed: the event is the one door a screen comes
through. The request that gates the serve is written last (MoveFrom,
TakeOffSlot), after the one it is read with. A probe may still write the
request variables themselves.
"""

from uebp.graph import _connect, _pin, out, then
from uebp.net import custom_event
from uebp.vars import INT
from combat.ask_consts import (
    ASK_DROP, ASK_MOVE, ASK_SLOT, ASK_TAKE_OFF, ASK_WEAR, FROM_PARAM, INT_ASKS, SLOT_PARAM,
    TO_PARAM,
)
from combat.slot_tuning import DROP_REQUEST_VAR, MOVE_FROM_VAR, MOVE_TO_VAR, SLOT_REQUEST_VAR
from combat.wear_tuning import TAKE_OFF_TO_VAR, TAKE_OFF_VAR, WEAR_REQUEST_VAR

# event -> the (request variable, the parameter it takes), in write order.
WRITES = {
    ASK_SLOT: ((SLOT_REQUEST_VAR, SLOT_PARAM),),
    ASK_MOVE: ((MOVE_TO_VAR, TO_PARAM), (MOVE_FROM_VAR, FROM_PARAM)),
    ASK_TAKE_OFF: ((TAKE_OFF_TO_VAR, TO_PARAM), (TAKE_OFF_VAR, SLOT_PARAM)),
    ASK_WEAR: ((WEAR_REQUEST_VAR, FROM_PARAM),),
    ASK_DROP: ((DROP_REQUEST_VAR, FROM_PARAM),),
}


def author_asks(ed):
    """The five events (see the module docstring)."""
    for name, params in INT_ASKS:
        event = custom_event(ed, name, [(p, INT) for p in params])
        made, flow = [event], then(event)
        for var, param in WRITES[name]:
            put = ed.add_set_member_variable_node(var)
            _connect(out(event, param), _pin(put, var))
            _connect(flow, _pin(put, "execute"))
            made.append(put)
            flow = then(put)
        ed.add_comment_to_nodes(
            f"{name}: what a screen asks; this component's Tick serves it (asks.py).", made)
