"""verify.fire -- fire and heat as server requests (task M25;
combat/fire_vars.py): the four Server events and how they travel, and how
the lit stick and the hot blade reach a client (the record's two columns,
the hand's two flags, the picture's row).

What each event asks before it acts is its owner's: verify/light.py,
torch.py and heat.py. Checked on the compiled classes and the wiring;
probes/probe_net_campfire.py is the two-client proof.
"""

from uebp import net
from combat.fire_vars import FIRE_PARAM, SERVER_EVENTS, SERVER_HEAT
from combat.heat_tuning import HOT_VAR
from combat.record_vars import RECORD_COMPONENT, VIEW_ROW
from combat.torch_tuning import LIT_VAR
from combat.verify.common import BEL, PIN, by_pins, check, component_template, out_pins
from combat.verify.fixtures import _is_exec, char, wc, wg
from combat.verify.record import _authority_branches, _feeders, _title, _upstream
from combat.verify.shot import _calls_of, _event


def _only_then(node, gate):
    """``node`` is reached from ``gate``'s true arm and not from its false."""
    above = [node] + _upstream(node)
    arms = {str(PIN.get_pin_name(p)) for p in BEL.list_output_pins(gate)
            if _is_exec(p) and any(PIN.get_owning_node(q) in above
                                   for q in PIN.list_connected_pins(p))}
    return arms == {"then"}


def check_events():
    for name in SERVER_EVENTS:
        check(f"{name} is a reliable Server event: the owning client asks, the server "
              "does", _event(name) is not None
              and net.compiled_rpc(wc, name) == (net.SERVER, True),
              str(net.compiled_rpc(wc, name) if _event(name) else None))
    asks = {name: len(_calls_of(name)) for name in SERVER_EVENTS}
    check("each is asked for in one place, where the keys are",
          all(n == 1 for n in asks.values()), str(asks))
    heat = _event(SERVER_HEAT)
    check(f"{SERVER_HEAT} carries the fire, an actor the server tests itself",
          heat is not None and FIRE_PARAM in out_pins(heat),
          str(out_pins(heat) if heat else None))


def check_told():
    row = _event(VIEW_ROW)
    for var in (LIT_VAR, HOT_VAR):
        fed = [n for n in wg if _title(n) == f"Set {var}" and _feeders(n, var)]
        check(f"a client's picture of an item is told its {var} by its row "
              f"({VIEW_ROW}), and writes it nowhere else",
              len(fed) == 1 and row is not None and _feeders(fed[0], var) == [row]
              and row in _upstream(fed[0]), str(len(fed)))
        # The record is the C++ component's (verify/record.py): it reads the
        # item's flag by name, into the item's row and, for the item in
        # hand, into what everyone but its owner is told.
        part = component_template(char, RECORD_COMPONENT)
        name = str(part.get_editor_property(f"Item{var}Var")) if part else None
        check(f"the record's row has the server's item's {var}, and Hand{var} the "
              "hand's, for everyone but its owner: the record component reads the "
              "item's flag by its name", name == var, str(name))


def run():
    check_events()
    check_told()
