"""verify.world_items -- an item in the world is the server's (task M23): the
drop key and a drag out of the inventory ask (AskDrop, a Server event), the
server's Tick sets the item down, and an item lying Dropped makes itself a
replicated actor in its own Tick, on the server (item_world.py).

The take of one is verify/pickup.py's, and the loot window's verify/asks.py's.
"""

from combat import ask_consts as AC
from combat import item_vars as IV
from combat.paths import ITEM_BP_PATH
from combat.record_vars import DropForced
from combat.slot_tuning import DROP_REQUEST_VAR, HAND
from combat.verify.common import BEL, PIN, check, graph, in_pins, load, pin_value
from combat.verify.fixtures import wg
from combat.verify.record import _authority_branches, _feeders, _title, _upstream
from combat.verify.shot import _calls_of, _gate_arm
from combat.verify.wear import _gated_on


def _data_upstream(node, limit=40):
    """Every node a data input of ``node`` is computed from."""
    seen, todo = [], [node]
    while todo and len(seen) < limit:
        cur = todo.pop()
        for p in BEL.list_input_pins(cur):
            for q in PIN.list_connected_pins(p):
                f = PIN.get_owning_node(q)
                if f not in seen and "execute" not in in_pins(f):
                    seen.append(f)
                    todo.append(f)
    return seen


def check_drop_is_asked():
    calls = _calls_of(AC.ASK_DROP)
    fed = [[_title(f) for f in _feeders(n, AC.FROM_PARAM)] for n in calls]
    # "" too: a literal equal to its pin's default is not saved (CLAUDE.md).
    keyed = [n for n in calls if not _feeders(n, AC.FROM_PARAM)
             and pin_value(n, AC.FROM_PARAM) in (str(HAND), "")]
    check(f"the drop key asks the server to set the hand's item down "
          f"({AC.ASK_DROP}({HAND})), and a probe's {DropForced} asks the same way: "
          "the Tick sets nothing down where the keys are",
          len(calls) == 2 and len(keyed) == 1 and [f"Get {DropForced}"] in fed,
          f"{len(calls)} call(s), fed {fed}")
    serves = _gated_on(DROP_REQUEST_VAR)
    arms = [_gate_arm(n, _authority_branches()) for n in serves]
    check(f"{DROP_REQUEST_VAR} is served with authority alone: the item set down is "
          "the server's", arms == ["then"], str(arms))
    lying = [n for n in wg if _title(n) == f"Set {IV.Dropped}"
             and pin_value(n, IV.Dropped) == "true"]
    local = [n for n in lying if not any(b in _upstream(n) for b in _authority_branches())]
    check("...and nothing in the living Tick makes an item Dropped off the server",
          not local, str(len(local)))


def check_item_enters_world():
    nodes = list(graph(load(ITEM_BP_PATH)).list_all_nodes())
    raised = [n for n in nodes if _title(n) == f"Set {IV.InWorld}"
              and pin_value(n, IV.InWorld) == "true"]
    gates = [b for n in raised for b in _feeders(n, "execute")]
    reads = {_title(f).replace(" ", "") for b in gates for c in _feeders(b, "Condition")
             for f in [c, *_data_upstream(c)]}
    check(f"an item lying {IV.Dropped} and not yet {IV.InWorld} enters the world in "
          "its own Tick, on the server alone, however it came to lie there",
          len(raised) == 1 and len(gates) == 1
          and {f"Get{IV.Dropped}", f"Get{IV.InWorld}", "IsServer"} <= reads,
          f"{len(raised)} Set, gated on {sorted(reads)}")
    after = [_title(n).replace(" ", "") for n in nodes
             if any(r in _upstream(n) for r in raised)
             and {"bInReplicates", "bInReplicateMovement"} & in_pins(n)]
    check("...where it becomes a replicated actor, with its movement",
          sorted(after) == ["SetReplicateMovement", "SetReplicates"], str(after))
    owned = [b for b in gates for g in _feeders(b, "execute")
             if any("HasAuthority" in _title(c).replace(" ", "")
                    for c in _feeders(g, "Condition"))]
    check("...off the authority arm of the Branch whose other arm hides a client's "
          "copy of a carried item", len(owned) == 1, str(len(owned)))


def run():
    check_drop_is_asked()
    check_item_enters_world()
