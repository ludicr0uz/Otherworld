"""verify.shot -- the shot and the reload as server requests
(combat/shot_vars.py, weapon_component/shot.py): the events and how they
travel, that a pellet is traced and a body hurt only inside Server_Fire, what
the server asks before it fires, the owning client's prediction, and the
counters that keep a client's rounds its own until the server has answered.

Checked on the compiled class and the wiring; probes/probe_net_fire.py has a
client of a server kill a wanderer and compares the two machines' rounds.
"""

from uebp import net
from combat.record_vars import VIEW_ROW, ViewDirty
from combat.shot_vars import (
    AIM_PARAM, FIRE_GRACE_S, RELOAD_NOW, SERVER_EVENTS, SERVER_FIRE, SERVER_RELOAD,
    AsksSent, AsksServed, ReloadForced)
from combat.verify.common import BEL, PIN, by_pins, check, graph, in_pins, num_pin
from combat.verify.fixtures import wc, wc_cdo, wg
from combat.verify.record import _authority_branches, _feeders, _title, _upstream
from combat.weapon_component.firing import SHOT_DIRECTION_VAR


def _event(name):
    return graph(wc).find_event_node(name)


def _calls(name):
    """The call nodes of one of the component's own events."""
    return [n for n in wg if _title(n).replace(" ", "") == name.replace("_", "")
            or _title(n) == name or _title(n).replace(" ", "") == name]


def _calls_of(name):
    event = _event(name)
    return [n for n in _calls(name) if n != event and "self" in in_pins(n)]


def _gate_arm(node, gates):
    """The arm of an authority Branch ``node`` hangs off, up a chain of single
    exec links ("" if it hangs off none): the nearest gate, not any above."""
    cur = node
    for _ in range(6):
        pins = PIN.list_connected_pins(BEL.find_input_pin(cur, "execute"))
        if len(pins) != 1:
            return ""
        owner = PIN.get_owning_node(pins[0])
        if owner in gates:
            return str(PIN.get_pin_name(pins[0]))
        cur = owner
    return ""


def check_events():
    for name in SERVER_EVENTS:
        check(f"{name} is a reliable Server event: the owning client asks, the server "
              "does", _event(name) is not None
              and net.compiled_rpc(wc, name) == (net.SERVER, True),
              str(net.compiled_rpc(wc, name) if _event(name) else None))
    check(f"{RELOAD_NOW} is a plain event: the server's reload, and the owning "
          "client's prediction", _event(RELOAD_NOW) is not None
          and net.compiled_rpc(wc, RELOAD_NOW) == (net.LOCAL, False))
    declared = net.variable_replication(wc, str(AsksServed))
    check(f"{AsksServed} replicates to the owning client alone, a RepNotify",
          declared[:2] == (net.REP_NOTIFY, f"OnRep_{AsksServed}")
          and declared[2].upper() == "COND_OWNER_ONLY"
          and net.compiled_replication(wc, str(AsksServed))
          == (net.REP_NOTIFY, f"OnRep_{AsksServed}"), str(declared))
    nodes = [_title(n) for n in graph(wc, f"OnRep_{AsksServed}").list_all_nodes()
             if "FunctionEntry" not in type(n).__name__ and "Comment" not in type(n).__name__]
    check(f"...whose arrival raises {ViewDirty}: the answer to the last ask is always "
          "taken", nodes == [f"Set {ViewDirty}"], str(nodes))
    check(f"{AsksSent} is the client's own count and does not travel",
          net.variable_replication(wc, str(AsksSent))[0] == net.NONE)
    check("the counters start at 0 and no key is forced",
          wc_cdo.get_editor_property(str(AsksSent)) == 0
          and wc_cdo.get_editor_property(str(AsksServed)) == 0
          and wc_cdo.get_editor_property(str(ReloadForced)) is False)


def check_server_fires():
    fire = _event(SERVER_FIRE)
    if fire is None:
        return
    draws = [n for n in wg if _title(n) == f"Set {SHOT_DIRECTION_VAR}"]
    check(f"the shot's draw in the cloud is made in {SERVER_FIRE} alone: one draw, by "
          "the machine that owns the shot", len(draws) == 1
          and fire in _upstream(draws[0])
          and not any("Tick" in _title(n) for n in _upstream(draws[0])),
          f"{len(draws)} draw(s)")
    hits = [n for n in wg if _title(n).replace(" ", "") == "TakeHit" and fire in _upstream(n)]
    check("...and the pellets' damage is dealt there", len(hits) >= 1, str(len(hits)))
    served = [n for n in wg if _title(n).startswith("Set")
              and _title(n).endswith(f" {AsksServed}")]
    first = [f for n in served for f in _feeders(n, "execute")]
    check(f"both Server events count themselves served first, fired or refused "
          f"({AsksServed})", len(served) == 2 and len(first) == 2
          and all(_event(e) in first for e in SERVER_EVENTS), f"{len(served)} write(s)")
    if not draws:
        return
    above = _upstream(draws[0])
    asked = {v for n in above if _title(n) == "Branch"
             for c in _feeders(n, "Condition")
             for v in _reads_behind(c)}
    want = {"Held", "Dead", "Health", "Melee", "Consumable", "Lights", "UsesAmmo", "Loaded",
            "NextFireTime"}
    check("the server asks before it fires: a valid Held, a living owner, a gun (not "
          "Melee, Consumable or Lights), a round and the cooldown", want <= asked,
          f"missing {sorted(want - asked)}")
    graces = [n for n in by_pins(wg, "A", "B") if abs((num_pin(n, "B") or 0.0) - FIRE_GRACE_S)
              < 1e-9 and any("GetTimeSeconds" in _title(f).replace(" ", "")
                             for f in _feeders(n, "A"))]
    check(f"...the cooldown with {FIRE_GRACE_S:g} s of grace for uneven packets",
          len(graces) == 1, str(len(graces)))
    stamps = [n for n in wg if _title(n) == "Set NextFireTime" and fire in _upstream(n)]
    late = [f for n in stamps for a in _feeders(n, "NextFireTime") for f in _feeders(a, "A")
            if _title(f).lower().startswith("max")]
    check("...and stamped from the later of now and the old deadline, so the grace "
          "never raises the gun's rate", len(stamps) == 1 and len(late) == 1,
          f"{len(stamps)} stamp(s), {len(late)} Max")
    aims = [q for q in PIN.list_connected_pins(BEL.find_output_pin(fire, AIM_PARAM))]
    check(f"the shooter's {AIM_PARAM} is read once: the pellets' direction",
          len(aims) == 1, str(len(aims)))


def _reads_behind(node, depth=4):
    """The variables read by the pure nodes feeding ``node``."""
    names, todo = set(), [(node, 0)]
    while todo:
        cur, d = todo.pop()
        title = _title(cur)
        if title.startswith("Get "):
            names.add(title[4:])
        if title.replace(" ", "") == "IsValid":
            names.update(_title(f)[4:] for f in _feeders(cur, "Object")
                         if _title(f).startswith("Get "))
        if d >= depth:
            continue
        for p in BEL.list_input_pins(cur):
            if str(PIN.get_pin_name(p)) in ("execute", "self", "Object"):
                continue
            todo.extend((PIN.get_owning_node(q), d + 1) for q in PIN.list_connected_pins(p))
    return names


def check_client_predicts():
    gates = _authority_branches()
    asks = {name: _calls_of(name) for name in SERVER_EVENTS}
    check("the Tick asks for a shot and a reload in one place each, where the keys "
          "are", all(len(v) == 1 for v in asks.values()),
          str({k: len(v) for k, v in asks.items()}))
    sent = [n for n in wg if _title(n) == f"Set {AsksSent}"]
    check(f"an ask is counted ({AsksSent}) only without authority: a client's "
          "prediction, never single player's", len(sent) == 2
          and all(_gate_arm(n, gates) == "else" for n in sent), str(len(sent)))
    predicted = [n for n in wg if _title(n) in ("Set Loaded", "Set NextFireTime")
                 and _gate_arm(n, gates) == "else"]
    check("the owning client spends its own round and stamps its own cooldown, off "
          "the authority Branch's false arm", sorted(_title(n) for n in predicted)
          == ["Set Loaded", "Set NextFireTime"], str([_title(n) for n in predicted]))
    now = _calls_of(RELOAD_NOW)
    arms = sorted(_gate_arm(n, gates) for n in now)
    check(f"{RELOAD_NOW} is called by {SERVER_RELOAD}, and by the Tick without "
          "authority alone", len(now) == 2 and arms == ["", "else"]
          and any(_event(SERVER_RELOAD) in _upstream(n) for n in now),
          f"{len(now)} call(s), arms {arms}")
    forced = [n for n in wg if _title(n) == f"Get {ReloadForced}"]
    check(f"a probe's {ReloadForced} stands in for the reload key", len(forced) == 1,
          str(len(forced)))


def check_view_waits():
    rows = [n for n in _calls_of(VIEW_ROW)
            if any({"A", "B", "bPickA"} <= in_pins(f) for f in _feeders(n, "Loaded"))]
    picks = [f for n in rows for f in _feeders(n, "Loaded")]
    reads = {v for s in picks for c in _feeders(s, "bPickA") for v in _reads_behind(c, 1)}
    check("the view takes a row's rounds only once the server has answered every ask "
          f"({AsksServed} >= {AsksSent}): a record older than the client's own shots "
          "hands no round back", len(rows) == 1 and reads == {str(AsksSent), str(AsksServed)}
          and all((num_pin(s, "B") or 0) == -1 for s in picks), f"{len(rows)} row(s), {reads}")


def run():
    check_events()
    check_server_fires()
    check_client_predicts()
    check_view_waits()
