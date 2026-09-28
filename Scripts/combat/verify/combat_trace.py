"""verify.combat_trace -- the GameMode's CombatTrace flag and its two console
events (combat/combat_trace.py). The line the wanderers write is checked per
controller in npc/verify.py.
"""

from combat.game_state import (
    COMBAT_TRACE_OFF_EVENT, COMBAT_TRACE_ON_EVENT, COMBAT_TRACE_VAR,
)
from combat.tuning import COMBAT_TRACE_DEFAULT
from combat.verify.common import BEL, PIN, cdo, check, graph, pin_value, titled
from combat.verify.fixtures import gm


def check_combat_trace_switch():
    value = cdo(gm).get_editor_property(COMBAT_TRACE_VAR)
    check(f"the GameMode's {COMBAT_TRACE_VAR} defaults to {COMBAT_TRACE_DEFAULT}",
          value is COMBAT_TRACE_DEFAULT, repr(value))
    nodes = graph(gm).list_all_nodes()
    for event, want in ((COMBAT_TRACE_ON_EVENT, "true"),
                        (COMBAT_TRACE_OFF_EVENT, "false")):
        found = titled(nodes, event)
        sets = [PIN.get_owning_node(q) for e in found
                for q in PIN.list_connected_pins(BEL.find_then_pin(e))]
        ok = (len(found) == 1 and len(sets) == 1
              and str(BEL.get_node_title(sets[0])) == f"Set {COMBAT_TRACE_VAR}"
              and pin_value(sets[0], COMBAT_TRACE_VAR).lower() == want)
        check(f"`ke * {event}` sets {COMBAT_TRACE_VAR} to {want}", ok)


def run():
    check_combat_trace_switch()
