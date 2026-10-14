"""Checks for the turn-in-place (combat/gas_turn.py), run by the gas_locomotion
section on the motion-matching anim Blueprint: the flag that offers the sample's turn
clips is filled, and the root's offset is released by a traversal alone."""
from combat.gas_locomotion_consts import TRAVERSING
from combat.gas_turn import (
    FIELD, PRONE, ROOT_MODE_GRAPHS, SLOT_PIN, STANDING_BELOW_CMS, release_flags)
from combat.verify.common import check
from uebp.graph import BEL, BGE, PIN
from uebp.pose_share import fed as linked


def _title(node):
    return str(BEL.get_node_title(node))


def _feeding(node, pin):
    return [PIN.get_owning_node(q) for q in linked(BEL.find_input_pin(node, pin))]


def _under(node, depth):
    """The title, spaces out, of the node ``depth`` links up the A pins."""
    for _ in range(depth):
        pin = BEL.find_input_pin(node, "A")
        above = [PIN.get_owning_node(q) for q in linked(pin)] if pin else []
        if not above:
            return ""
        node = above[0]
    return _title(node).replace(" ", "")


def _literal(node, pin="B"):
    return str(PIN.get_pin_value(BEL.find_input_pin(node, pin)))


def check_turn(bp, properties):
    makes = [n for n in properties.list_all_nodes() if "Input State" in _title(n)
             and n.get_class().get_name() == "K2Node_MakeStruct"]
    pins = [p for m in makes for p in BEL.list_input_pins(m)
            if str(PIN.get_pin_name(p)).split("_")[0] == FIELD]
    both = [PIN.get_owning_node(q) for p in pins for q in linked(p)]
    asks = [a for n in both for pin in ("A", "B") for a in _feeding(n, pin)]
    speeds = [a for a in asks if "Velocity" in _under(a, 2)]
    stances = [a for a in asks if _under(a, 1) == "GetStance"]
    check(f"the input state's {FIELD} is filled, which offers the sample's turn-in-place "
          f"clips: the pawn stands (under {STANDING_BELOW_CMS:g} cm/s over the ground) and "
          f"GetStance is not {PRONE} (prone)",
          len(pins) == 1 and len(both) == 1 and len(asks) == 2
          and len(speeds) == 1 and float(_literal(speeds[0]) or 0.0) == STANDING_BELOW_CMS
          and "<" in _title(speeds[0])
          and len(stances) == 1 and _literal(stances[0]) == PRONE
          and "Not" in _title(stances[0]).replace("!=", "Not"),
          f"{[_title(n) for n in both]} of {[(_title(a), _literal(a)) for a in asks]}")
    found = {}
    for name in ROOT_MODE_GRAPHS:
        ed = BGE.get_graph_editor_by_name(bp, name)
        slots = [n for n in ed.list_all_nodes() if SLOT_PIN in
                 {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(n)}] if ed else None
        found[name] = (None if ed is None else
                       [_title(source) for _branch, source in release_flags(ed)],
                       None if slots is None else len(slots))
    check(f"the root's offset is released while {TRAVERSING} and not while a slot of the "
          "sample's name is busy (the raised gun's pose is in one: its legs spun with "
          "the capsule)",
          all(v == ([f"Get {TRAVERSING}"], 0) for v in found.values()), str(found))
