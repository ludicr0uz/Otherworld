"""verify.shot -- the shot and the reload as server requests
(combat/shot_vars.py, weapon_component/shot.py): the events and how they
travel, that the shot's server half is the native base's (task W1: the
class, its Server_Fire and FirePellets, the names it reads the Blueprints
by), what the graph hangs on it, the owning client's prediction, and the
counters that keep a client's rounds its own until the server has answered.

Checked on the compiled class and the wiring; probes/probe_net_fire.py has a
client of a server kill a wanderer and compares the two machines' rounds.
"""

from uebp import net
from combat.record_vars import VIEW_ROW, ViewDirty
from combat.paths import HEALTH_BP_PATH, ITEM_BP_PATH
from combat.shot_vars import (
    AIM_PARAM, FIRE_GRACE_S, NATIVE_FUNCTIONS, PELLET_FLEW, RELOAD_NOW, RELOADED,
    SERVER_EVENTS, SERVER_FIRE, SERVER_RELOAD, SHOT_FIRED, AsksSent, AsksServed, ReloadForced)
from combat import fx_vars as FX
from combat.verify.common import BEL, PIN, cdo, check, graph, in_pins, num_pin, pellet_calls
from combat.verify.fixtures import wc, wc_cdo, wg
from combat.verify.record import _authority_branches, _feeders, _title, _upstream
from combat.weapon_component import native
from combat.weapon_component.firing import SHOT_DIRECTION_VAR
from uebp.nodes.weapon import WEAPON_BASE_CLASS

import unreal


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


# The reload's cosmetic pair, as its call nodes are titled.
_RELOAD_PAIR = FX.events_of(FX.RELOAD)


def check_native():
    """The shot's server half is C++ (task W1): the class, the function and
    the names it reads the Blueprints by."""
    base = unreal.load_class(None, WEAPON_BASE_CLASS)
    check(f"BP_WeaponComponent is a child of the native base ({WEAPON_BASE_CLASS})",
          base is not None and BEL.get_blueprint_parent_class(wc) == base,
          str(BEL.get_blueprint_parent_class(wc)))
    # Python has no method for either (dir() of the base lists none): the
    # compiled class is asked, and the graph for an event of the same name.
    check(f"...which has {SERVER_FIRE}, a reliable Server function, and FirePellets, a "
          "plain one, and the graph has no event named as either",
          base is not None
          and net.compiled_rpc(wc, SERVER_FIRE) == (net.SERVER, True)
          and net.compiled_rpc(wc, "FirePellets") == (net.LOCAL, False)
          and _event(SERVER_FIRE) is None and _event("FirePellets") is None,
          str(net.compiled_rpc(wc, SERVER_FIRE) if base else None))
    got = {name: net.compiled_rpc(wc, name) for name in (SERVER_RELOAD, RELOAD_NOW)}
    check(f"...and the reload (task W2): {SERVER_RELOAD}, a reliable Server function, "
          f"and {RELOAD_NOW}, a plain one (the server's reload and the owning client's "
          "prediction), and the graph has no event named as either",
          base is not None and got == {SERVER_RELOAD: (net.SERVER, True),
                                       RELOAD_NOW: (net.LOCAL, False)}
          and not [n for n in NATIVE_FUNCTIONS if _event(n) is not None], str(got))
    # The pure-node trap this was (root CLAUDE.md, "Evaluation order"): the
    # take is a local of the native ReloadNow, so the graph has nothing to
    # read twice. By name: a variable, a node or a pin.
    stored = [str(v) for v in BEL.list_member_variable_names(wc) if "ReloadTake" in str(v)]
    nodes = [_title(n) for n in wg if "ReloadTake" in _title(n).replace(" ", "")]
    check("...which works out how many rounds move itself: the graph has no ReloadTake, "
          "variable or node", base is not None and not stored and not nodes,
          f"variables {stored}, nodes {nodes}")
    wrong = native.wrong_names(wc)
    check(f"...told the names it reads the Blueprints by ({len(native.NAMES)}: Held, "
          "AsksServed, the item's and the struck body's zone tables), and the cooldown's "
          f"grace ({FIRE_GRACE_S:g} s for uneven packets), and the guard's two names "
          f"for its requests ({SERVER_FIRE}, {SERVER_RELOAD})", not wrong
          and native.NAMES["fire_event_name"] == SERVER_FIRE
          and native.NAMES["reload_event_name"] == SERVER_RELOAD, str(wrong))
    # A name that names nothing reads as false or 0 in C++, silently: each
    # must be a variable of the Blueprint it is read off.
    item = cdo(unreal.load_asset(ITEM_BP_PATH))
    health = cdo(unreal.load_asset(HEALTH_BP_PATH))
    owners = {"held_var": wc_cdo, "asks_served_var": wc_cdo}
    owners.update({p: item for p in native.NAMES if p.startswith("item_")})
    owners.update({p: health for p in native.NAMES
                   if p.startswith(("health_", "head_", "limb_"))})
    missing = []
    for prop, owner in owners.items():
        try:
            owner.get_editor_property(native.NAMES[prop])
        except Exception:                                         # noqa: BLE001
            missing.append(native.NAMES[prop])
    check("...each a variable of the Blueprint it is read off (the health component's "
          "Health, Dead and TakeHit are its own native parent's since W3, and read by no "
          "name)", not missing and not [p for p in native.NAMES if "health" in p
                                        or "take_hit" in p], str(missing))


def check_events():
    reloaded = _event(RELOADED)
    under = [n for n in wg if reloaded is not None and n != reloaded and reloaded in _upstream(n)]
    told = sorted(_title(n) for n in under if _title(n) in _RELOAD_PAIR)
    check(f"the graph hangs a reload on the native base's {RELOADED} (a reload that "
          "moved rounds): the clack, told with authority and predicted without, and "
          "no write of anything", reloaded is not None and told == sorted(_RELOAD_PAIR)
          and not [n for n in under if _title(n).startswith("Set")],
          f"{told} under it")
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
    fired = _event(SHOT_FIRED)
    flew = _event(PELLET_FLEW)
    check(f"the graph hangs a shot on the native base's two events: {SHOT_FIRED} (a shot "
          f"{SERVER_FIRE} let through) and {PELLET_FLEW} (each pellet it flew)",
          fired is not None and flew is not None)
    if fired is None:
        return
    draws = [n for n in wg if _title(n) == f"Set {SHOT_DIRECTION_VAR}"]
    check(f"the shot's draw in the cloud is made under {SHOT_FIRED} alone: one draw, by "
          "the machine that owns the shot", len(draws) == 1
          and fired in _upstream(draws[0])
          and not any("Tick" in _title(n) for n in _upstream(draws[0])),
          f"{len(draws)} draw(s)")
    flown = pellet_calls(wg)
    check("...and the pellets are flown there, by the native FirePellets, which deals "
          "their damage: one call, behind the draw", len(flown) == 1 and bool(draws)
          and draws[0] in _upstream(flown[0]), str(len(flown)))
    served = [n for n in wg if _title(n).startswith("Set")
              and _title(n).endswith(f" {AsksServed}")]
    # Counted between the guard's Allow and its answer, done or refused, in
    # C++ for both requests, by the name check_native holds it to
    # (probes/probe_net_fire.py reads the count come back).
    check(f"{AsksServed} is counted by the native {SERVER_FIRE} and {SERVER_RELOAD} "
          "alone: no node of the graph writes it", not served, f"{len(served)} write(s)")
    # What the server asks before it fires (a valid Held, a living owner, a
    # gun, a round, the cooldown with its grace), the round and the stamp
    # are C++ now: the graph under ShotFired must not spend a second round.
    again = [_title(n) for n in wg if _title(n) in ("Set Loaded", "Set NextFireTime")
             and fired in _upstream(n)]
    check(f"the round and the cooldown are the native {SERVER_FIRE}'s: nothing under "
          f"{SHOT_FIRED} writes Loaded or NextFireTime", not again, str(again))
    aims = [q for q in PIN.list_connected_pins(BEL.find_output_pin(fired, AIM_PARAM))]
    check(f"the shooter's {AIM_PARAM} is read once in the graph: the pellets' direction",
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


def _asked_above(node):
    """Every variable a Branch above ``node`` reads in its condition."""
    return {v for n in _upstream(node) if _title(n) == "Branch"
            for c in _feeders(n, "Condition") for v in _reads_behind(c)}


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
    check(f"{RELOAD_NOW} is called by the graph once, by the Tick without authority: "
          f"the owning client's prediction (the server's call is the native "
          f"{SERVER_RELOAD}'s)", len(now) == 1 and arms == ["else"],
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
    check_native()
    check_events()
    check_server_fires()
    check_client_predicts()
    check_view_waits()
