"""verify.clock -- one world clock (world_clock.py, M30): the server's cycle
keeps time and publishes it, a client's reads it, and the draw of the start
hour and the wind's time follow the same owner."""

import unreal

from combat.verify.common import BEL, by_pins, check, graph, load, pin_value
from forest_generator.wind import MPC_NAME, PARAM_TIME_OFFSET
from net import state_consts as S
from world import day_night_vars as DV
from world.paths import DAY_NIGHT_BP_PATH

PINS = unreal.BlueprintGraphPinLibrary


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _before(node, limit=40):
    """Every (node title, exec output pin name) that leads to ``node``, walking
    back along the exec wires: the arms and switches it sits behind."""
    seen, found, todo = set(), [], [node]
    while todo and len(seen) < limit:
        n = todo.pop()
        pin = BEL.find_input_pin(n, "execute")
        for q in (pin.list_connected_pins() if pin else []):
            m = PINS.get_owning_node(q)
            found.append((_title(m), str(PINS.get_pin_name(q))))
            if m.get_name() not in seen:
                seen.add(m.get_name())
                todo.append(m)
    return found


def _sources(pin, depth=6):
    """Titles of the nodes feeding ``pin``, through the pure sums behind it."""
    titles = []
    for q in pin.list_connected_pins():
        m = PINS.get_owning_node(q)
        titles.append(_title(m))
        if depth:
            for p in BEL.list_input_pins(m):
                if str(PINS.get_pin_name(p)) != "execute":
                    titles += _sources(p, depth - 1)
    return titles


def _sets(nodes, var):
    return [n for n in nodes
            if _title(n).startswith("Set") and _title(n).endswith(f" {var}")]


def _arm(node):
    """Which arm of an authority switch ``node`` is behind, if any."""
    arms = {pin for title, pin in _before(node) if "Switch Has Authority" in title}
    return arms.pop() if len(arms) == 1 else None


def _check_clock(nodes):
    clocks = _sets(nodes, DV.Clock)
    fed = {n.get_name(): _sources(BEL.find_input_pin(n, DV.Clock)) for n in clocks}
    drawn = [n for n in clocks if any("Random" in t for t in fed[n.get_name()])]
    kept = [n for n in clocks if any("Event Tick" in t for t in fed[n.get_name()])]
    read = [n for n in clocks
            if any("ServerWorldTime" in t.replace(" ", "") for t in fed[n.get_name()])]
    check("the cycle writes Clock in three places: the start's draw, the "
          "server's advance by the frame's time, a client's read of the server's",
          len(clocks) == 3 and len(drawn) == len(kept) == len(read) == 1,
          str({k: v[:4] for k, v in fed.items()}))
    check("...the draw of the start hour with authority only (net/random_consts.py)",
          len(drawn) == 1 and _arm(drawn[0]) == "Authority",
          str(_before(drawn[0])[:3] if drawn else ""))
    check("...the advance with authority only: a server, and single player",
          len(kept) == 1 and _arm(kept[0]) == "Authority",
          str(_before(kept[0])[:3] if kept else ""))
    theirs = f"Get {S.WORLD_CLOCK_OFFSET_VAR}"
    check("...and a client's Clock is the GameState's WorldClockOffset plus the "
          "server's world time, behind the cast and the wait for the lengths",
          len(read) == 1 and _arm(read[0]) == "Remote"
          and theirs in fed[read[0].get_name()]
          and any("Cast" in t for t, _pin in _before(read[0]))
          and any(t == "Branch" for t, _pin in _before(read[0])),
          str(_before(read[0])[:4] if read else ""))
    for var, gs_var in ((DV.DayLengthSeconds, S.WORLD_DAY_LENGTH_VAR),
                        (DV.NightLengthSeconds, S.WORLD_NIGHT_LENGTH_VAR)):
        took = _sets(nodes, var)
        check(f"...with the server's {var} beside it (the GameState's {gs_var})",
              len(took) == 1 and _arm(took[0]) == "Remote"
              and f"Get {gs_var}" in _sources(BEL.find_input_pin(took[0], var), 0),
              str(len(took)))


def _check_publish(nodes):
    wrong = []
    for var in S.WORLD_CLOCK:
        writes = _sets(nodes, var)
        behind = _before(writes[0]) if len(writes) == 1 else []
        if not (len(writes) == 1 and _arm(writes[0]) == "Authority"
                and ("Branch", "then") in behind
                and any("Cast" in t for t, _pin in behind)):
            wrong.append(f"{var}: {len(writes)} write(s) {behind[:3]}")
    check("the server publishes the clock on the GameState (WorldClockOffset and "
          "the two lengths), with authority, and behind a Branch: only when what "
          "is there is out of date, never every frame", not wrong, "; ".join(wrong))


def _check_wind(nodes):
    writes = [n for n in by_pins(nodes, "Collection", "ParameterName", "ParameterValue")
              if MPC_NAME in pin_value(n, "Collection")]
    check(f"Tick writes {MPC_NAME}.{PARAM_TIME_OFFSET} once, from {DV.WindTimeOffset}, "
          "on every machine (behind no authority switch)",
          len(writes) == 1 and pin_value(writes[0], "ParameterName") == PARAM_TIME_OFFSET
          and f"Get {DV.WindTimeOffset}" in _sources(
              BEL.find_input_pin(writes[0], "ParameterValue"), 0)
          and _arm(writes[0]) is None
          and bool(BEL.find_input_pin(writes[0], "execute").list_connected_pins()),
          str([(pin_value(n, "Collection"), pin_value(n, "ParameterName")) for n in writes]))
    stores = _sets(nodes, DV.WindTimeOffset)
    check(f"...and {DV.WindTimeOffset} is the server's world time less this machine's, "
          "stored on both arms",
          sorted(_arm(n) or "" for n in stores) == ["Authority", "Remote"]
          and all(any("ServerWorldTime" in t.replace(" ", "")
                      for t in _sources(BEL.find_input_pin(n, DV.WindTimeOffset)))
                  for n in stores), str(len(stores)))


def run():
    bp = load(DAY_NIGHT_BP_PATH)
    if bp is None:
        check("BP_DayNightCycle exists (the world clock)", False, DAY_NIGHT_BP_PATH)
        return
    nodes = graph(bp).list_all_nodes()
    _check_clock(nodes)
    _check_publish(nodes)
    _check_wind(nodes)
