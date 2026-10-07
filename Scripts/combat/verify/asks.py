"""What a screen asks of the weapon component: the Ask events
(combat/ask_consts.py), the loot take and save and exit's countdown."""

from uebp import net
from combat import ask_consts as AC
from combat.game_state import LAST_DAMAGE_VAR
from combat.slot_tuning import HAS_ROOM_VAR
from combat.verify.common import BEL, PIN, check, graph, in_pins, pin_value
from combat.verify.fixtures import _is_exec, wc, wc_cdo, wg, wg_dead
from combat.weapon_component.asks import WRITES
from combat.weapon_component.dead import OWNER_DEAD_VAR
from loot.consts import BODY_ARRAYS, LOOT_TAKE_REACH_CM, LOOT_VAR


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _feeders(node, pin):
    p = BEL.find_input_pin(node, pin)
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(p)] if p else []


def _after(node, limit=60):
    """Every node an exec output of ``node`` reaches, breadth first."""
    seen, todo = [], [node]
    while todo and len(seen) < limit:
        cur = todo.pop(0)
        for p in BEL.list_output_pins(cur):
            if not _is_exec(p):
                continue
            for q in PIN.list_connected_pins(p):
                n = PIN.get_owning_node(q)
                if n not in seen:
                    seen.append(n)
                    todo.append(n)
    return seen


def _event(name):
    return graph(wc).find_event_node(name)


def check_asks():
    missing = [n for n in AC.ALL_ASKS if not _event(n)]
    check(f"the weapon component has an event for each thing a screen asks "
          f"({', '.join(AC.ALL_ASKS)})", not missing, str(missing))
    if missing:
        return
    # The slots' (M18), the drop and the loot take (M23) are Server events;
    # M24 and M35 make the rest so.
    kinds = {n: net.compiled_rpc(wc, n) for n in AC.ALL_ASKS}
    check(f"...each compiled as a function of the class: the slots', the drop and "
          f"the loot take ({', '.join(AC.SERVER_ASKS)}) reliable Server events, the "
          "rest plain calls yet",
          all(k == ((net.SERVER, True) if n in AC.SERVER_ASKS else (net.LOCAL, False))
              for n, k in kinds.items()), str(kinds))
    for name, params in AC.INT_ASKS:
        event = _event(name)
        sets = _after(event)
        got = [(_title(s), [str(PIN.get_pin_name(q)) for q in PIN.list_connected_pins(
            BEL.find_input_pin(s, var))]) for s, (var, _) in zip(sets, WRITES[name])]
        want = [(f"Set {var}", [param] if param in params else [])
                for var, param in WRITES[name]]
        check(f"{name}({', '.join(params)}) raises the request the Tick serves, and "
              f"nothing else ({', '.join(v for v, _ in WRITES[name])}, in that order)",
              len(sets) == len(want) and got == want, str(got))


def check_ask_loot_take():
    event = _event(AC.ASK_LOOT_TAKE)
    if not event:
        return
    run = _after(event)
    gates = [n for n in run if "Condition" in in_pins(n)]
    reads = {_title(g) for b in gates for c in _feeders(b, "Condition")
             for g in [c, *_feeders(c, "A"), *_feeders(c, "Object"), *_feeders(c, "TargetArray")]}
    check(f"{AC.ASK_LOOT_TAKE} takes only for a living owner, from a valid body, with "
          f"room ({HAS_ROOM_VAR}) and something at that row of its {LOOT_VAR}",
          len(gates) == 6 and {f"Get {OWNER_DEAD_VAR}", f"Get {HAS_ROOM_VAR}",
                               f"Get {LOOT_VAR}"} <= reads,
          f"{len(gates)} gates reading {sorted(reads)}")
    reach = [pin_value(c, "B") for b in gates for c in _feeders(b, "Condition")
             if any({"V1", "V2"} <= in_pins(d) for d in _feeders(c, "A"))]
    check(f"...only a body within {LOOT_TAKE_REACH_CM:g} cm of the taker on the machine "
          "that serves it: a client is not taken at its word",
          len(reach) == 1 and abs(float(reach[0] or 0) - LOOT_TAKE_REACH_CM) < 1e-6,
          str(reach))
    same = [c for b in gates for c in _feeders(b, "Condition")
            if event in _feeders(c, "B")
            and any(_title(g) == f"Get {LOOT_VAR}"
                    for a in _feeders(c, "A") for g in _feeders(a, "TargetArray"))]
    check(f"...and only the item asked for ({AC.WANT_PARAM}): a row another player "
          "took first is gone, and what moved up into it is not taken instead",
          len(same) == 1, str(len(same)))
    spawns = [n for n in run if {"Class", "SpawnTransform"} <= in_pins(n)
              and any(_title(g) == f"Get {LOOT_VAR}"
                      for f in _feeders(n, "Class") for g in _feeders(f, "TargetArray"))]
    check("...it spawns the item class read out of the body's Loot",
          len(spawns) == 1, str(len(spawns)))
    dropped = [n for n in run if _title(n) == "Set Dropped"]
    adds = [n for n in run if {"TargetArray", "NewItem"} <= in_pins(n)]
    check("...carried, not lying in the world (Dropped false), into Inventory",
          len(dropped) == 1 and pin_value(dropped[0], "Dropped") == "false"
          and [_title(f) for a in adds for f in _feeders(a, "TargetArray")]
          == ["Get Inventory"], f"{len(dropped)} Dropped, {len(adds)} adds")
    removes = [n for n in run if "IndexToRemove" in in_pins(n)]
    emptied = sorted(_title(g) for n in removes for g in _feeders(n, "TargetArray"))
    check("...and taken out of every one of the body's arrays at that row",
          emptied == sorted(f"Get {v}" for v in BODY_ARRAYS)
          and all(f == event for n in removes for f in _feeders(n, "IndexToRemove")),
          str(emptied))


def check_ask_save_exit():
    wrong = {v: wc_cdo.get_editor_property(v) for v, want in (
        (AC.EXIT_PENDING_VAR, False), (AC.EXIT_DUE_VAR, False),
        (AC.EXIT_STARTED_VAR, AC.NEVER), (AC.EXIT_CALLED_OFF_VAR, AC.NEVER))
        if wc_cdo.get_editor_property(v) != want}
    check("the save-and-exit countdown starts idle", not wrong, str(wrong))
    event = _event(AC.ASK_SAVE_EXIT)
    if not event:
        return
    run = _after(event)
    gate = [n for n in run[:1] if "Condition" in in_pins(n)]
    busy = {_title(g) for b in gate for c in _feeders(b, "Condition")
            for g in _feeders(c, "A") + _feeders(c, "B")}
    check(f"{AC.ASK_SAVE_EXIT} starts the countdown only with none running and the "
          "owner alive",
          busy == {f"Get {AC.EXIT_PENDING_VAR}", f"Get {OWNER_DEAD_VAR}"}
          and [_title(n) for n in run[1:]] == [
              f"Set {AC.EXIT_PENDING_VAR}", f"Set {AC.EXIT_STARTED_VAR}",
              f"Set {AC.EXIT_AT_VAR}", f"Set {AC.EXIT_DUE_VAR}"],
          f"{sorted(busy)}; {[_title(n) for n in run]}")
    ends = [n for n in run if _title(n) == f"Set {AC.EXIT_AT_VAR}"]
    lengths = [pin_value(a, "B") for n in ends for a in _feeders(n, AC.EXIT_AT_VAR)]
    check(f"...and it runs for {AC.EXIT_SECONDS:.0f} s",
          len(lengths) == 1 and abs(float(lengths[0] or 0) - AC.EXIT_SECONDS) < 1e-6,
          str(lengths))

    hits = [n for n in wg if in_pins(n) == {"A", "B"}
            and {_title(f) for f in _feeders(n, "A")} == {f"Get {LAST_DAMAGE_VAR}"}]
    check("a hit after the start calls it off (LastDamageTime > ExitStartedAt)",
          len(hits) == 1 and {_title(f) for f in _feeders(hits[0], "B")}
          == {f"Get {AC.EXIT_STARTED_VAR}"}, str(len(hits)))
    stops = [n for n in wg if "DisableMovement" in _title(n).replace(" ", "")]
    waits = [b for n in stops for b in _feeders(n, "execute")
             if f"Get {AC.EXIT_AT_VAR}" in {_title(g) for c in _feeders(b, "Condition")
                                            for g in _feeders(c, "B")}]
    check("the character can't move while the exit counts down "
          "(DisableMovement every Tick it waits)",
          len(stops) == 1 and len(waits) == 1,
          f"{len(stops)} DisableMovement, {len(waits)} on the countdown's wait")
    walks = [n for n in wg if "NewMovementMode" in in_pins(n)]
    check("...and walks again when a hit calls the exit off",
          len(walks) == 1 and "Walking" in pin_value(walks[0], "NewMovementMode")
          and any(_title(f) == f"Set {AC.EXIT_CALLED_OFF_VAR}"
                  for f in _feeders(walks[0], "execute")),
          str([(pin_value(n, "NewMovementMode"), [_title(f) for f in _feeders(n, "execute")])
               for n in walks]))
    dues = [n for n in wg if _title(n) == f"Set {AC.EXIT_DUE_VAR}"
            and pin_value(n, AC.EXIT_DUE_VAR) == "true"]
    over = [b for n in dues for s in _feeders(n, "execute") for b in _feeders(s, "execute")
            if b in [x for st in stops for x in _feeders(st, "execute")]]
    check(f"the time up, the component says so and no more ({AC.EXIT_DUE_VAR}: the "
          "save and the leaving are the watcher's)",
          len(dues) == 1 and len(over) == 1
          and not [n for n in wg if "SlotName" in in_pins(n) or "LevelName" in in_pins(n)],
          f"{len(dues)} Set {AC.EXIT_DUE_VAR} true, {len(over)} on the countdown's Branch")
    lowered = [n for n in wg_dead if _title(n) == f"Set {AC.EXIT_PENDING_VAR}"]
    check("a death calls the exit off (the dead gate lowers ExitPending)",
          len(lowered) == 1 and pin_value(lowered[0], AC.EXIT_PENDING_VAR) in ("false", ""),
          str(len(lowered)))


def run():
    check_asks()
    check_ask_loot_take()
    check_ask_save_exit()
