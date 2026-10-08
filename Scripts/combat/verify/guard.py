"""verify.guard -- the RPC guard (task A5; net/guard.py, net/guard_consts.py,
C++ UOtherworldRpcGuard): the component on the player and its numbers, that
the table and the Server events are in step, and that every Server event asks
the guard first.

A Server event without the fragment fails here, as does one with no row in
the table and a row with no event. Checked on the graphs and the component's
template; probes/probe_net_guard.py has a client fire behind itself, hold the
trigger and flood an ask.

    server_events(nodes)   the Server events among a graph's nodes
    guard_of(event)        the (Allow, Branch) at an event's head, or None
"""

import os

import unreal

from uebp import net
from combat.paths import WEAPON_COMP_BP_PATH
from combat.shot_vars import AIM_PARAM, SERVER_FIRE
from combat.verify.common import BEL, PIN, check, component_template, graph, in_pins, pin_value
from combat.verify.fixtures import _is_exec, char, wc
from combat.verify.record import _feeders, _title, _upstream
from combat.weapon_component.firing import SHOT_DIRECTION_VAR
from net import guard_consts as GC
from net.owner_checks import ALSO
from net.state_checks import _packages
from uebp.nodes.guard import GUARD_CLASS

BGE = unreal.BlueprintGraphEditor
SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Not builders: the authoring library, the probes and the dev tooling.
NOT_BUILDERS = ("uebp/", "dev/", "probes/")
FRAGMENTS = ("author_guard(", "author_allow(")


def server_events(nodes):
    return [n for n in nodes if "CustomEvent" in type(n).__name__
            and net.event_rpc(n)[0] == net.SERVER]


def _execs_out(node):
    """The nodes ``node``'s exec outputs run."""
    return [PIN.get_owning_node(q) for p in BEL.list_output_pins(node) if _is_exec(p)
            for q in PIN.list_connected_pins(p)]


def guard_of(event):
    """``(Allow, Branch)`` when the event's one exec link runs Allow with the
    event's own name on the owner's guard, and its answer is what the next
    Branch (past at most one Set: the shot's counter) asks. None otherwise."""
    first = _execs_out(event)
    if len(first) != 1 or _title(first[0]) != "Allow" or "Name" not in in_pins(first[0]):
        return None
    allow = first[0]
    if pin_value(allow, "Name") != _title(event):
        return None
    if not any(pin_value(f, "ComponentClass") == GUARD_CLASS for f in _feeders(allow, "self")):
        return None
    step = _execs_out(allow)
    if len(step) == 1 and _title(step[0]).startswith("Set"):
        step = _execs_out(step[0])
    if len(step) != 1 or allow not in _feeders(step[0], "Condition"):
        return None
    return allow, step[0]


def scan_blueprints():
    """{Blueprint name: its Server events' names}, over every Blueprint."""
    found = {}
    for package in sorted({*_packages(), *ALSO}):
        bp = unreal.load_asset(package)
        if not bp or not BEL.generated_class(bp):
            continue
        for name in BEL.list_graph_names(bp):
            ed = BGE.get_graph_editor_by_name(bp, str(name))
            events = server_events(ed.list_all_nodes()) if ed else []
            if events:
                found.setdefault(package.rsplit("/", 1)[-1], []).extend(
                    _title(e) for e in events)
    return found


def scan_sources():
    """The builder modules that make a Server event, and those of them that
    name the fragment."""
    makes, guards = [], []
    for root, _dirs, files in os.walk(SCRIPTS):
        for f in sorted(files):
            rel = os.path.relpath(os.path.join(root, f), SCRIPTS)
            if not f.endswith(".py") or rel.startswith(NOT_BUILDERS) or "verify" in rel:
                continue
            with open(os.path.join(root, f), encoding="utf-8") as fh:
                text = fh.read()
            if "server_event(" in text:
                makes.append(rel)
                if any(name in text for name in FRAGMENTS):
                    guards.append(rel)
    return sorted(makes), sorted(guards)


def check_component():
    template = component_template(char, GC.GUARD_COMPONENT)
    check(f"the player has the RPC guard ({GC.GUARD_COMPONENT}: C++, {GUARD_CLASS})",
          template is not None and template.get_class().get_path_name() == GUARD_CLASS,
          str(template))
    if template is None:
        return
    rates = {str(k): float(v) for k, v in template.get_editor_property("rates").items()}
    check("...told the table (net/guard_consts.py): each Server event's asks a second",
          rates.keys() == GC.RATES.keys()
          and all(abs(rates[k] - GC.RATES[k]) < 1e-4 for k in GC.RATES),
          str(sorted(set(rates) ^ set(GC.RATES))))
    got = {p: float(template.get_editor_property(p)) for p in GC.NUMBERS}
    check(f"...the burst, the default rate, the kick (more than {GC.KICK_REFUSALS} "
          f"refusals in {GC.KICK_S:g} s) and the aim's cone ({GC.AIM_CONE_DEG:g} deg)",
          all(abs(got[p] - v) < 1e-3 for p, v in GC.NUMBERS.items()), str(got))
    fastest = 1.0 / GC.FASTEST_INTERVAL_S
    check(f"the table: {SERVER_FIRE} at the fastest gun's rate plus 20 %, the asks at "
          f"{GC.ASK_RATE:g}/s, the look at {GC.LOOK_RATE:g}/s, the rest at "
          f"{GC.DEFAULT_RATE:g}/s",
          abs(GC.RATES[SERVER_FIRE] - fastest * 1.2) < 1e-6 and GC.RATES[SERVER_FIRE] > fastest
          and all(r > 0 for r in GC.RATES.values()), f"{GC.RATES[SERVER_FIRE]:.2f}/s")


def check_in_step():
    found = scan_blueprints()
    here = WEAPON_COMP_BP_PATH.rsplit("/", 1)[-1]
    events = sorted(found.get(here, []))
    check("every Server event of the weapon component has a row in the guard's table, "
          "and every row an event", events == sorted(GC.RATES),
          f"no row: {sorted(set(events) - set(GC.RATES))}; "
          f"no event: {sorted(set(GC.RATES) - set(events))}")
    elsewhere = {b: e for b, e in found.items() if b != here}
    check("...and no other Blueprint has a Server event: the guard is asked on the "
          "weapon component's alone", not elsewhere, str(elsewhere))
    makes, guards = scan_sources()
    check("every builder module that makes a Server event names the guard's fragment "
          "(net/guard.py)", bool(makes) and makes == guards,
          f"without: {sorted(set(makes) - set(guards))}")


def check_fragment():
    events = server_events(graph(wc).list_all_nodes())
    bare = sorted(_title(e) for e in events if guard_of(e) is None)
    check(f"every Server event ({len(events)}) asks the guard first: Allow, with its own "
          "name, on the owner's guard, and a Branch on the answer before anything else",
          bool(events) and not bare, f"without the fragment: {bare}")
    fire = graph(wc).find_event_node(SERVER_FIRE)
    guard = guard_of(fire) if fire else None
    if not guard:
        return
    allowed = [PIN.get_owning_node(q)
               for q in PIN.list_connected_pins(BEL.find_then_pin(guard[1]))]
    aims = [n for n in allowed if _title(n).replace(" ", "") == "AimAllowed"]
    draws = [n for n in graph(wc).list_all_nodes() if _title(n) == f"Set {SHOT_DIRECTION_VAR}"]
    gated = [b for a in aims for b in _execs_out(a) if a in _feeders(b, "Condition")]
    check(f"{SERVER_FIRE} asks AimAllowed of the client's {AIM_PARAM} next, and the shot "
          "is drawn only behind its Branch",
          len(aims) == 1 and fire in _feeders(aims[0], AIM_PARAM) and len(gated) == 1
          and len(draws) == 1 and gated[0] in _upstream(draws[0]),
          f"{len(aims)} AimAllowed, {len(gated)} Branch")


def run():
    check_component()
    check_in_step()
    check_fragment()
