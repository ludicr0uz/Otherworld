"""verify.fx -- the fight as everyone sees and hears it (combat/fx_vars.py,
weapon_component/fx.py): every cosmetic is a pair of events on the weapon
component, Fx_<Name> holding the one copy of its nodes and Multicast_<Name>,
an unreliable Multicast whose gate asks whether this copy owes it, counts it
and calls Fx_<Name>; the owning client predicts the five it can; and the
headshot's stamp is a RepNotify to the owner, rewritten with its clock.

The helpers (``nodes_of``, ``calls``, ``predicts``) are what the other
sections use to find a cosmetic's nodes now that they hang off an event
rather than off the stage that tells it. Proof in the running game is
probes/probe_net_fx.py.
"""

import functools

from combat import fx_vars as FX
from combat.verify.common import BEL, PIN, check, graph, in_pins
from combat.verify.fixtures import exec_reach, wc, wc_cdo, wg
from combat.verify.record import _authority_branches, _feeders, _title
from combat.verify.shot import _gate_arm
from combat.weapon_component import vars as WV
from uebp import net


def _squash(s):
    return s.replace(" ", "").replace("_", "")


def event(name):
    return graph(wc).find_event_node(name)


def _pure_feeds(node):
    seen, stack = [], [node]
    while stack:
        for pin in BEL.list_input_pins(stack.pop()):
            if str(PIN.get_pin_name(pin)) == "execute":
                continue
            for q in PIN.list_connected_pins(pin):
                src = PIN.get_owning_node(q)
                if src in seen:
                    continue
                seen.append(src)
                if "execute" not in in_pins(src):
                    stack.append(src)
    return seen


@functools.lru_cache(maxsize=None)
def nodes_of(name):
    """Every node of the cosmetic's two events: the events, what their exec
    runs, and the pure nodes feeding those."""
    found = []
    for ev in (event(FX.fx_event(name)), event(FX.multicast_event(name))):
        if ev is None:
            continue
        found.append(ev)
        found += exec_reach([p for p in BEL.list_output_pins(ev)
                             if "exec" in str(PIN.get_pin_type_display_string(p)).lower()])
    for n in list(found):
        found += [f for f in _pure_feeds(n) if f not in found]
    return tuple(found)


def _paths(name):
    return {n.get_path_name() for n in nodes_of(name)}


def in_fx(name, nodes):
    paths = _paths(name)
    return [n for n in nodes if n.get_path_name() in paths]


def is_fx_node(node):
    return any(node.get_path_name() in _paths(name) for name in FX.COSMETICS)


def _calls_named(event_name):
    """The call nodes of a custom event, by name (the event itself has no self)."""
    return [n for n in wg if _squash(_title(n)) == _squash(event_name) and "self" in in_pins(n)]


def calls(name):
    """The server's tells: the calls of Multicast_<name>."""
    return _calls_named(FX.multicast_event(name))


def predicts(name):
    """The owning client's own: the calls of Fx_<name> outside its pair."""
    paths = _paths(name)
    return [n for n in _calls_named(FX.fx_event(name)) if n.get_path_name() not in paths]


def _reads(node):
    return {_title(n) for n in _pure_feeds(node)}


# ─── the checks ──────────────────────────────────────────────────────────────

GATE_READS = {
    FX.UNPREDICTED: ({"HasAuthority", f"Get {WV.LocalInput}"}, set()),
    FX.OTHERS: ({f"Get {WV.LocalInput}"}, {"HasAuthority"}),
    FX.SCREEN: ({"IsDedicatedServer"}, {"HasAuthority", f"Get {WV.LocalInput}"}),
}


def check_pairs():
    for name, (params, gate) in FX.COSMETICS.items():
        fx, cast = FX.fx_event(name), FX.multicast_event(name)
        check(f"{fx} is a plain event and {cast} an unreliable Multicast: the cosmetic "
              "once, and the server's word of it to everyone",
              event(fx) is not None and event(cast) is not None
              and net.compiled_rpc(wc, fx) == (net.LOCAL, False)
              and net.compiled_rpc(wc, cast) == (net.MULTICAST, False),
              f"{net.compiled_rpc(wc, fx) if event(fx) else None}, "
              f"{net.compiled_rpc(wc, cast) if event(cast) else None}")
        if event(cast) is None or event(fx) is None:
            continue
        gates = [n for n in _feeders_then(event(cast)) if _title(n) == "Branch"]
        want, forbid = GATE_READS[gate]
        asked = set().union(*[{_squash(t) for t in _reads(n)} for n in gates]) if gates else set()
        check(f"...{cast} asks its gate first ('{gate}': {', '.join(sorted(want))})",
              len(gates) == 1 and {_squash(t) for t in want} <= asked
              and not ({_squash(t) for t in forbid} & asked), str(sorted(asked)))
        if len(gates) != 1:
            continue
        counted = _feeders_then(gates[0])
        inner = [n for n in _calls_named(fx) if n.get_path_name() in _paths(name)]
        check(f"...and on its true arm counts {FX.FxPlayed} up one, then calls {fx} with "
              "every parameter", len(counted) == 1 and _title(counted[0]) == f"Set {FX.FxPlayed}"
              and len(inner) == 1 and _feeders(inner[0], "execute") == counted
              and all(_feeders(inner[0], p) == [event(cast)] for p, _t in params),
              f"{[_title(n) for n in counted]}, {len(inner)} inner call(s)")
        told = calls(name)
        mine = predicts(name)
        if name in FX.PREDICTED:
            arms = [_gate_arm(n, _authority_branches()) for n in mine]
            check(f"...the owning client predicts {name}: one call of {fx} off an "
                  f"authority Branch's false arm, and {cast} is told at least once",
                  len(mine) == 1 and arms == ["else"] and len(told) >= 1,
                  f"{len(mine)} prediction(s) on {arms}, {len(told)} tell(s)")
        elif name == FX.THROW_CLIP:
            check(f"...the thrower plays {name} itself in both modes (the wind-up), and "
                  f"{cast} is told once", len(mine) == 1 and len(told) == 1,
                  f"{len(mine)} own, {len(told)} tell(s)")
        else:
            check(f"...nobody predicts {name}: {fx} is called by its Multicast alone, "
                  f"which is told at least once", not mine and len(told) >= 1,
                  f"{len(mine)} prediction(s), {len(told)} tell(s)")
        check(f"...no tell of {cast} sits on an authority Branch's false arm (a client "
              "calling a Multicast reaches no one)",
              all(_gate_arm(n, _authority_branches()) != "else" for n in told))


def _feeders_then(node):
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(BEL.find_then_pin(node))]


def check_counter():
    check(f"{FX.FxPlayed} starts at 0 and does not travel: each copy's own count, a "
          "probe's readout", wc_cdo.get_editor_property(str(FX.FxPlayed)) == 0
          and net.variable_replication(wc, str(FX.FxPlayed))[0] == net.NONE)


def check_headshot_travels():
    declared = net.variable_replication(wc, str(WV.HeadshotTime))
    check(f"{WV.HeadshotTime} is a RepNotify to the owning client alone: the wound "
          "is dealt on the server, the X is drawn by its shooter",
          declared[:2] == (net.REP_NOTIFY, f"OnRep_{WV.HeadshotTime}")
          and declared[2].upper() == "COND_OWNER_ONLY"
          and net.compiled_replication(wc, str(WV.HeadshotTime))
          == (net.REP_NOTIFY, f"OnRep_{WV.HeadshotTime}"), str(declared))
    on_rep = graph(wc, f"OnRep_{WV.HeadshotTime}")
    nodes = on_rep.list_all_nodes() if on_rep else []
    sets = [n for n in nodes if _title(n).startswith("Set")
            and _title(n).endswith(f" {WV.HeadshotTime}")]
    switch = [n for n in nodes if "Authority" in _title(n)]
    fed = [_title(f) for n in sets for f in _feeders(n, str(WV.HeadshotTime))]
    arm = [str(PIN.get_pin_name(q)) for n in sets
           for q in PIN.list_connected_pins(BEL.find_input_pin(n, "execute"))]
    check("...whose arrival (the Remote arm) rewrites it with this machine's clock: "
          "the HUD compares it with its own GetTimeSeconds",
          len(sets) == 1 and len(switch) == 1 and arm == ["Remote"]
          and any("Time" in t for t in fed), f"{len(sets)} write(s) on {arm}, fed by {fed}")


def run():
    check_pairs()
    check_counter()
    check_headshot_travels()
