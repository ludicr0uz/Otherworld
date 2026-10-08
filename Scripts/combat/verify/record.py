"""verify.record -- the inventory's record (combat/record_vars.py,
combat/dirty.py, weapon_component/record.py, view.py): what replicates and to
whom, that the server alone issues the loadout and serves the slots, that the
record is held by its own component on the character and written by no graph
(the Tick's rewrite is gone), that every node which changes what is carried
is followed by the mark that has it written, and that a client's item actors
are made only by the view's two events.

Checked on the compiled class and the wiring; probes/probe_net_inventory.py
moves an item on a client of a server and reads the server's copy.
"""

from uebp import net
from graphics_menu.umg_consts import HUD_BP_PATH
from combat.paths import AMMO_BP_PATH, AXE_BP_PATH, KNIFE_BP_PATH, STICK_BP_PATH
from combat.record_vars import (
    CARRIED_ARRAYS, HAND, ITEM_STATE, RECORD, RECORD_COMPONENT, RECORD_COMPONENT_CLASS,
    RECORD_HAND_SLOT, RECORD_MIRROR, RECORD_SOURCE, REPLICATED, VIEW_ROW, VIEW_TRIM, VIEW_WORN,
    ViewDirty, WornClass)
from combat.slot_tuning import SLOT_WANT_VAR
from combat.verify.common import (
    BEL, PIN, by_pins, check, component_template, graph, in_pins, load)
from combat.verify.fixtures import _is_exec, char, wc, wc_cdo, wg
from combat.weapon_component.inventory import STARTER_CLASS_VARS

OWNER_ONLY, SKIP_OWNER = "COND_OWNER_ONLY", "COND_SKIP_OWNER"
MARK_CARRIER, MARK_ITEM = "MarkInventoryDirty", "MarkCarriedItemDirty"
# Every other Blueprint whose graph changes what a player carries, and what
# of it: the items' own clocks, the rounds a pick-up hands a carried gun, and
# the HUD's single-player writes (the profile's load, the dev-all-guns cheat).
OTHER_SITES = (
    ("the stick's burn-out", STICK_BP_PATH, {"Lit"}),
    ("the knife's cooling", KNIFE_BP_PATH, {"Hot"}),
    ("the axe's cooling", AXE_BP_PATH, {"Hot"}),
    ("the ammo pick-up", AMMO_BP_PATH, {"Reserve"}),
    ("the HUD", HUD_BP_PATH, {"Inventory", "Loaded", "Reserve", "Slot"}),
)


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
                     SKIP_OWNER if v in HAND else OWNER_ONLY) for v in REPLICATED}
    check("the record's arrays and the worn slots' classes replicate to the owning "
          "client alone, and the class in hand, with whether it burns or is hot, to "
          "everyone else; each is a RepNotify",
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
    serves = [n for n in wg if _title(n) == f"Set {SLOT_WANT_VAR}"]
    check("a slot request is served with authority only",
          len(serves) == 1 and any(_arm(serves[0], g) == "then" for g in gates),
          str(len(serves)))


def _sites(nodes):
    """``(node, what)`` for every node that changes what is carried: a Set of
    an item's Slot, Loaded, Reserve, Lit or Hot, and anything with an exec pin
    that takes Inventory or Worn as its TargetArray."""
    gets = {f"Get {a}": a for a in CARRIED_ARRAYS}
    found = []
    for n in nodes:
        name = _title(n)
        if "VariableSet" in type(n).__name__:
            found += [(n, v) for v in ITEM_STATE
                      if name.startswith("Set") and name.endswith(f" {v}")]
        elif "TargetArray" in in_pins(n) and any(_is_exec(p) for p in BEL.list_output_pins(n)):
            found += [(n, gets[_title(f)]) for f in _feeders(n, "TargetArray")
                      if _title(f) in gets]
    return found


def _marks(node):
    """The titles of what the node's ``then`` runs, and those nodes."""
    after = [PIN.get_owning_node(q) for p in BEL.list_output_pins(node)
             if _is_exec(p) and str(PIN.get_pin_name(p)) == "then"
             for q in PIN.list_connected_pins(p)]
    return [_title(n).replace(" ", "") for n in after], after


def check_record_component():
    part = component_template(char, RECORD_COMPONENT)
    cls = part.get_class().get_path_name() if part else None
    check(f"the player carries {RECORD_COMPONENT}, the C++ component that holds the "
          "record, and it replicates", cls == RECORD_COMPONENT_CLASS
          and bool(part.get_editor_property("replicates")), str(cls))
    if not part:
        return
    names = {k: str(part.get_editor_property(k)) for k in {**RECORD_SOURCE, **RECORD_MIRROR}}
    check("it reads the weapon component's arrays and each item's variables by the "
          "builders' own names, and mirrors to the variables the old view reads",
          names == {**RECORD_SOURCE, **RECORD_MIRROR}
          and part.get_editor_property(RECORD_HAND_SLOT[0]) == RECORD_HAND_SLOT[1],
          str({k: v for k, v in names.items()
               if v != {**RECORD_SOURCE, **RECORD_MIRROR}[k]}))


def check_no_rewrite():
    every = list(graph(wc).list_all_nodes())
    mirror = {str(v) for v in REPLICATED}
    sets = [_title(n) for n in every if "VariableSet" in type(n).__name__
            and any(_title(n).startswith("Set") and _title(n).endswith(f" {v}") for v in mirror)]
    writes = [_title(n) for n in every if "TargetArray" in in_pins(n)
              and any(_is_exec(p) for p in BEL.list_output_pins(n))
              and any(_title(f) in {f"Get {v}" for v in mirror}
                      for f in _feeders(n, "TargetArray"))]
    check("no graph of the weapon component writes the record: the Tick's rewrite (an "
          "Add per column per item, every frame) is gone, and so is the shed's clear",
          not sets and not writes, f"{sets + writes}")
    lone = [n for n in every if _title(n).replace(" ", "") in (MARK_CARRIER, MARK_ITEM)
            and any("EventTick" in _title(f).replace(" ", "") for f in _feeders(n, "execute"))]
    check("...and no mark hangs straight off the Tick event: the record is written "
          "on a frame that changed something, not on every one", not lone, str(len(lone)))


def check_marks():
    sites = _sites(list(graph(wc).list_all_nodes()))
    bare = []
    for n, what in sites:
        names, after = _marks(n)
        owner = [_title(f).replace(" ", "") for m in after for f in _feeders(m, "Carrier")]
        if names != [MARK_CARRIER] or owner != ["GetOwner"]:
            bare.append(f"{_title(n)} ({what}) -> {names}")
    tally = {v: sum(1 for _n, w in sites if w == v) for v in CARRIED_ARRAYS + ITEM_STATE}
    check("every node of the weapon component that changes what is carried (a write of "
          "Inventory or Worn, a Set of an item's Slot, Loaded, Reserve, Lit or Hot) runs "
          f"{MARK_CARRIER}(the owner) next, and nothing else", bool(sites) and not bare,
          f"{len(sites)} site(s) {tally}; unmarked {bare}")
    check("...and each kind of change has a site: the serve and the sync (Slot), the "
          "take, the drop, the throw and the shed (Inventory), the wear (Worn), the "
          "shot and the reload (Loaded, Reserve), the stick lit and the blade heated "
          "(Lit, Hot)", all(tally.values()), str(tally))
    for label, path, want in OTHER_SITES:
        found = _sites(list(graph(load(path)).list_all_nodes()))
        bare = [f"{_title(n)} -> {_marks(n)[0]}" for n, what in found
                if _marks(n)[0] != [MARK_ITEM if what in ITEM_STATE else MARK_CARRIER]]
        check(f"{label} marks the record of whoever carries what it changes "
              f"({', '.join(sorted(want))})", {w for _n, w in found} == want and not bare,
              f"{len(found)} site(s) {sorted({w for _n, w in found})}; unmarked {bare}")


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
    check_record_component()
    check_no_rewrite()
    check_marks()
    check_view()
