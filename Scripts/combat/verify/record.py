"""verify.record -- the inventory's record (combat/record_vars.py,
weapon_component/record.py, view.py): what replicates and to whom, that the
server alone issues the loadout, serves the slots and writes the record, and
that a client's item actors are made only by the view's two events.

Checked on the compiled class and the wiring; probes/probe_net_inventory.py
moves an item on a client of a server and reads the server's copy.
"""

from uebp import net
from combat.record_vars import (
    HandClass, RECORD, REPLICATED, VIEW_ROW, VIEW_TRIM, VIEW_WORN, ViewDirty, WornClass)
from combat.slot_tuning import SLOT_WANT_VAR
from combat.verify.common import BEL, PIN, by_pins, check, graph, in_pins
from combat.verify.fixtures import _is_exec, wc, wc_cdo, wg
from combat.weapon_component.inventory import STARTER_CLASS_VARS

OWNER_ONLY, SKIP_OWNER = "COND_OWNER_ONLY", "COND_SKIP_OWNER"


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _feeders(node, pin):
    p = BEL.find_input_pin(node, pin)
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(p)] if p else []


def _upstream(n, limit=600):
    """Every node whose exec reaches ``n``."""
    seen, todo = [], [n]
    while todo and len(seen) < limit:
        cur = todo.pop()
        for p in BEL.list_input_pins(cur):
            if not _is_exec(p):
                continue
            for q in PIN.list_connected_pins(p):
                f = PIN.get_owning_node(q)
                if f not in seen:
                    seen.append(f)
                    todo.append(f)
    return seen


def _arm(node, gate):
    """Which exec output of ``gate`` leads to ``node`` ("" for neither)."""
    above = [node] + _upstream(node)
    for p in BEL.list_output_pins(gate):
        if _is_exec(p) and any(PIN.get_owning_node(q) in above
                               for q in PIN.list_connected_pins(p)):
            return str(PIN.get_pin_name(p))
    return ""


def _authority_branches():
    return [n for n in wg if _title(n) == "Branch" and any(
        "HasAuthority" in _title(c).replace(" ", "") for c in _feeders(n, "Condition"))]


def check_replication():
    declared = {str(v): net.variable_replication(wc, str(v)) for v in REPLICATED}
    want = {str(v): (net.REP_NOTIFY, f"OnRep_{v}",
                     SKIP_OWNER if v == HandClass else OWNER_ONLY) for v in REPLICATED}
    check("the record's four arrays and the worn slots' classes replicate to the owning "
          "client alone, and the class in hand to everyone else; each is a RepNotify",
          {k: (a, b, c.upper()) for k, (a, b, c) in declared.items()} == want, str(declared))
    compiled = {str(v): net.compiled_replication(wc, str(v)) for v in REPLICATED}
    check("...and compiled so", all(k == (net.REP_NOTIFY, f"OnRep_{v}")
                                    for v, k in compiled.items()), str(compiled))
    lone = {}
    for v in REPLICATED:
        nodes = [n for n in graph(wc, f"OnRep_{v}").list_all_nodes()
                 if "FunctionEntry" not in type(n).__name__]
        lone[str(v)] = [_title(n) for n in nodes if "Comment" not in type(n).__name__]
    check(f"each OnRep only raises {ViewDirty}",
          all(t == [f"Set {ViewDirty}"] for t in lone.values()), str(lone))
    check(f"{ViewDirty} starts true (a first record may arrive before BeginPlay), and "
          "the record empty", wc_cdo.get_editor_property(str(ViewDirty)) is True
          and all(len(wc_cdo.get_editor_property(str(v))) == 0
                  for v in RECORD + (WornClass,)))
    check("the weapon component replicates", net.replicates(wc))


def check_server_owns():
    switches = [n for n in wg if "SwitchHasAuthority" in _title(n).replace(" ", "")]
    spawns = [n for n in by_pins(wg, "Class", "SpawnTransform")
              if any(_title(f) in {f"Get {v}" for v in STARTER_CLASS_VARS}
                     for f in _feeders(n, "Class"))]
    arms = sorted({_arm(n, s) for n in spawns for s in switches} - {""})
    check("BeginPlay issues the loadout with authority only (the server, and single "
          "player)", len(spawns) == len(STARTER_CLASS_VARS) and arms == ["Authority"],
          f"{len(spawns)} spawn(s), behind {arms}")
    gates = _authority_branches()
    adds = [n for n in by_pins(wg, "TargetArray", "NewItem")
            if any(_title(f) in {f"Get {v}" for v in RECORD} for f in _feeders(n, "TargetArray"))]
    arms = sorted({_arm(n, g) for n in adds for g in gates} - {""})
    check("the record's rows are written with authority: an Add per column, each off "
          "the true arm of a Branch on HasAuthority",
          len(adds) == len(RECORD) and arms == ["then"], f"{len(adds)} add(s), {arms}")
    worn = [n for n in by_pins(wg, "TargetArray", "NewItem")
            if any(_title(f) == f"Get {WornClass}" for f in _feeders(n, "TargetArray"))]
    arms = sorted({_arm(n, g) for n in worn for g in gates} - {""})
    check(f"{WornClass} is written with authority, a row per slot of Worn: the "
          "garment's class, or none for an empty slot",
          len(worn) == 2 and arms == ["then"]
          and sorted(len(_feeders(n, "NewItem")) for n in worn) == [0, 1],
          f"{len(worn)} add(s), {arms}")
    hands = [n for n in wg if _title(n).endswith(f"Set with Notify {HandClass}")
             or _title(n) == f"Set {HandClass}"]
    check(f"{HandClass} is written by the server alone",
          bool(hands) and all(any(_arm(n, g) == "then" for g in gates) for n in hands),
          str(len(hands)))
    serves = [n for n in wg if _title(n) == f"Set {SLOT_WANT_VAR}"]
    check("a slot request is served with authority only",
          len(serves) == 1 and any(_arm(serves[0], g) == "then" for g in gates),
          str(len(serves)))


def check_view():
    events = {name: graph(wc).find_event_node(name) for name in (VIEW_ROW, VIEW_TRIM)}
    check(f"{VIEW_ROW} and {VIEW_TRIM} exist, plain events of this machine",
          all(events.values()) and all(net.compiled_rpc(wc, n) == (net.LOCAL, False)
                                       for n in events), str(events))
    if not all(events.values()):
        return
    gates = _authority_branches()
    calls = [n for n in wg if _title(n).replace(" ", "") in (VIEW_ROW, VIEW_TRIM)
             and "self" in in_pins(n)]
    dirty = [n for n in wg if _title(n) == "Branch"
             and any(_title(c) == f"Get {ViewDirty}" for c in _feeders(n, "Condition"))]
    check("the picture is remade only without authority, and only when a record arrived "
          f"({ViewDirty})", len(calls) == 5 and len(dirty) == 1
          and all(dirty[0] in _upstream(c) for c in calls)
          and any(_arm(dirty[0], g) == "else" for g in gates),
          f"{len(calls)} call(s), {len(dirty)} gate(s)")
    made = [n for n in by_pins(wg, "Class", "SpawnTransform")
            if events[VIEW_ROW] in _feeders(n, "Class")]
    check(f"a client's item actors are spawned in {VIEW_ROW}, of the row's class",
          len(made) == 1 and events[VIEW_ROW] in _upstream(made[0]), str(len(made)))
    ended = [n for n in wg if "DestroyActor" in _title(n).replace(" ", "")
             and any(e in _upstream(n) for e in events.values())]
    check("...and what the record no longer has is destroyed (a row of another class, "
          "the rows past its end)", len(ended) == 2, str(len(ended)))


def check_view_worn():
    event = graph(wc).find_event_node(VIEW_WORN)
    check(f"{VIEW_WORN} exists, a plain event of this machine",
          bool(event) and net.compiled_rpc(wc, VIEW_WORN) == (net.LOCAL, False))
    if not event:
        return
    gates = _authority_branches()
    calls = [n for n in wg if _title(n).replace(" ", "") == VIEW_WORN and "self" in in_pins(n)]
    dirty = [n for n in wg if _title(n) == "Branch"
             and any(_title(c) == f"Get {ViewDirty}" for c in _feeders(n, "Condition"))]
    check(f"a client's worn slots are remade off {WornClass} only without authority, "
          f"when a record arrived ({ViewDirty})",
          len(calls) == 1 and len(dirty) == 1 and dirty[0] in _upstream(calls[0])
          and any(_arm(dirty[0], g) == "else" for g in gates)
          and any(_title(f) == f"Get {WornClass}" for up in _upstream(calls[0])
                  for f in _feeders(up, "Array")), f"{len(calls)} call(s)")
    made = [n for n in by_pins(wg, "Class", "SpawnTransform") if event in _feeders(n, "Class")]
    after = [_title(n) for m in made for n in wg if m in _upstream(n)]
    check(f"...a garment spawned in {VIEW_WORN}, of the row's class, hidden and not "
          "Dropped", len(made) == 1 and any("Hidden" in t for t in after)
          and any(t.endswith("Dropped") for t in after), str(after))


def run():
    check_view_worn()
    check_replication()
    check_server_owns()
    check_view()
