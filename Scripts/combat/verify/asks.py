"""What a screen asks of the weapon component: the Ask events
(combat/ask_consts.py), the loot take and save and exit's countdown."""

from uebp import net
from combat import ask_consts as AC
from combat.game_state import LAST_DAMAGE_VAR
from combat import item_vars as IV
from combat.fire_vars import SERVER_LIGHT
from combat.light_tuning import LIGHTS_VAR
from combat.slot_tuning import HAS_ROOM_VAR
from combat.tuning import SERVER_CONSUME
from combat.wear_tuning import CLOTHING_SLOT_VAR
from combat.weapon_component import vars as WV
from combat.verify.common import BEL, PIN, check, graph, in_pins, pin_value
from combat.verify.fixtures import _is_exec, wc, wc_cdo, wg, wg_dead
from combat.weapon_component.asks import WRITES
from combat.weapon_component.dead import OWNER_DEAD_VAR
from net import state_consts as S
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
    # The slots' (M18), the drop and the loot take (M23) and the garments'
    # two (M24) are Server events; M35 makes the last so.
    kinds = {n: net.compiled_rpc(wc, n) for n in AC.ALL_ASKS}
    check(f"...each compiled as a function of the class: the slots', the drop, "
          f"the loot take and the garments' ({', '.join(AC.SERVER_ASKS)}) reliable Server events, the "
          "rest plain calls yet",
          all(k == ((net.SERVER, True) if n in AC.SERVER_ASKS else (net.LOCAL, False))
              for n, k in kinds.items()), str(kinds))
    for name, params in AC.INT_ASKS:
        event = _event(name)
        sets = _after(event)
        if name in AC.SERVER_ASKS:
            # The guard's Allow and its Branch head a Server event (verify/guard.py).
            sets = sets[2:] if [_title(s) for s in sets[:2]] == ["Allow", "Branch"] else []
        got = [(_title(s), [str(PIN.get_pin_name(q)) for q in PIN.list_connected_pins(
            BEL.find_input_pin(s, var))]) for s, (var, _) in zip(sets, WRITES[name])]
        want = [(f"Set {var}", [param] if param in params else [])
                for var, param in WRITES[name]]
        check(f"{name}({', '.join(params)}) raises the request the Tick serves, and "
              f"nothing else ({', '.join(v for v, _ in WRITES[name])}, in that order)",
              len(sets) == len(want) and got == want, str(got))


def check_use_held():
    """use_held.py: a screen's use of what is in hand."""
    event = _event(AC.USE_HELD)
    if not event:
        return
    run = _after(event)
    names = [_title(n).replace(" ", "").replace("_", "") for n in run]
    gates = [n for n in run if "Condition" in in_pins(n)]
    reads = [_title(g) for b in gates for c in _feeders(b, "Condition")
             for g in [c, *_feeders(c, "A"), *_feeders(c, "Object")]]
    check(f"{AC.USE_HELD} uses what is in hand as the fire key's tap does: only a valid "
          f"{WV.Held}; food and drink ({IV.Consumable}, not a garment: "
          f"{CLOTHING_SLOT_VAR}) are asked of the server ({SERVER_CONSUME}), the matches "
          f"({LIGHTS_VAR}) struck ({SERVER_LIGHT}), and nothing else is done",
          names.count(SERVER_CONSUME.replace("_", "")) == 1
          and names.count(SERVER_LIGHT.replace("_", "")) == 1
          and {n for n in names if n != "Branch"}
          == {SERVER_CONSUME.replace("_", ""), SERVER_LIGHT.replace("_", ""),
              "PlaySoundAtLocation", f"Set{WV.TriggerSpent}"}
          and {f"Get {WV.Held}", f"Get {IV.Consumable}", f"Get {CLOTHING_SLOT_VAR}",
               f"Get {LIGHTS_VAR}"} <= set(reads),
          f"{len(gates)} gates reading {sorted(set(reads))}; calls {names}")
    garment = [b for b in gates for c in _feeders(b, "Condition")
               if f"Get {CLOTHING_SLOT_VAR}" in [_title(g) for g in _feeders(c, "A")]]
    arms = [(len(PIN.list_connected_pins(BEL.find_then_pin(b))),
             len(PIN.list_connected_pins(BEL.find_else_pin(b)))) for b in garment]
    check("...a garment in hand is not its business (the screen asks that worn): the "
          "garment's arm goes nowhere, and what is not one is eaten",
          arms == [(0, 1)], str(arms))


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
          len(gates) == 7 and {f"Get {OWNER_DEAD_VAR}", f"Get {HAS_ROOM_VAR}",
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
    # The Branch the hit compare feeds, through its ORs: a hit, a move key
    # (the pawn's last movement input has a length) or the trigger's tap.
    def leaves(n):
        if _title(n) == "OR Boolean":
            return [l for pin in ("A", "B") for f in _feeders(n, pin) for l in leaves(f)]
        return [n]
    def gated(n):
        """The Branches a bool reaches, down through its ORs."""
        nexts = [PIN.get_owning_node(q) for p in BEL.list_output_pins(n)
                 for q in PIN.list_connected_pins(p)]
        return [b for o in nexts
                for b in ([o] if "Condition" in in_pins(o) else
                          gated(o) if _title(o) == "OR Boolean" else [])]
    branches = [b for n in hits for b in gated(n)]
    tips = [l for b in branches for c in _feeders(b, "Condition") for l in leaves(c)]
    moved = [l for l in tips if _title(l) == "float > float"
             and [_title(f) for f in _feeders(l, "A")] == ["Vector Length"]
             and [_title(g) for f in _feeders(l, "A") for g in _feeders(f, "A")]
             == ["GetLastMovementInputVector"]]
    tapped = [l for l in tips if _title(l) == "Equal (Float)"
              and {_title(f) for f in _feeders(l, "A") + _feeders(l, "B")}
              == {"Get FirePressedAt", "GetTimeSeconds"}]
    check("a move key calls it off too (the pawn's last movement input has a length), "
          "and so does the trigger (FirePressedAt this frame, or FireForced): OR'd with "
          "the hit into one Branch",
          len(branches) == 1 and len(moved) == 1 and len(tapped) == 1
          and sorted(_title(l) for l in tips)
          == ["Equal (Float)", "Get FireForced", "NOT Boolean", "float > float",
              "float > float"],
          f"{len(branches)} Branch; {[_title(l) for l in tips]}")
    aloft = [_title(f) for l in tips if _title(l) == "NOT Boolean" for f in _feeders(l, "A")]
    check("...and so does leaving the ground (the movement not IsMovingOnGround: a "
          "jump, a climb, an exit asked for in the air)",
          [t.replace(" ", "") for t in aloft] == ["IsMovingOnGround"], str(aloft))
    stops = [n for n in wg if "DisableMovement" in _title(n).replace(" ", "")
             or "NewMovementMode" in in_pins(n)]
    check("the countdown never disables the movement or sets its mode: out of the "
          "walking mode the Foot Placement node stops fitting the feet to the ground "
          "(the legs snapped flat on a slope)",
          not stops, f"{len(stops)} DisableMovement or SetMovementMode calls")
    dues = [n for n in wg if _title(n) == f"Set {AC.EXIT_DUE_VAR}"
            and pin_value(n, AC.EXIT_DUE_VAR) == "true"]
    over = [b for n in dues for s in _feeders(n, "execute") for b in _feeders(s, "execute")
            if f"Get {AC.EXIT_AT_VAR}" in {_title(g) for c in _feeders(b, "Condition")
                                           for g in _feeders(c, "B")}]
    check(f"the time up, the component says so and no more ({AC.EXIT_DUE_VAR}: the "
          "save and the leaving are the watcher's)",
          len(dues) == 1 and len(over) == 1
          and not [n for n in wg if "SlotName" in in_pins(n) or "LevelName" in in_pins(n)],
          f"{len(dues)} Set {AC.EXIT_DUE_VAR} true, {len(over)} on the countdown's Branch")
    lowered = [n for n in wg_dead if _title(n) == f"Set {AC.EXIT_PENDING_VAR}"]
    check("a death calls the exit off (the dead gate lowers ExitPending)",
          len(lowered) == 1 and pin_value(lowered[0], AC.EXIT_PENDING_VAR) in ("false", ""),
          str(len(lowered)))


def check_tune_ask():
    """tune_ask.py: a client's tuning table, taken only where the server allows."""
    event = _event(AC.ASK_TUNE)
    if not event:
        return
    run = _after(event)
    gates = [n for n in run if "Condition" in in_pins(n)]
    allowed = [g for g in gates if f"Get {S.DevTuning}" in map(_title, _feeders(g, "Condition"))]
    check(f"{AC.ASK_TUNE} goes on only where the GameState's {S.DevTuning} is true (a "
          "server started with -AllowDevTuning): one Branch on it, after the guard's",
          len(allowed) == 1 and gates.index(allowed[0]) == 1,
          f"{len(allowed)} of {len(gates)} gates")
    for i, inbox in enumerate(S.TUNED):
        sets = [n for n in run if _title(n) == f"Set {inbox}"]
        tests = [pin_value(c, "B") or "0" for n in sets for g in _feeders(n, "execute")
                 for c in _feeders(g, "Condition")]
        fed = [str(PIN.get_pin_name(q)) for n in sets
               for q in PIN.list_connected_pins(BEL.find_input_pin(n, inbox))]
        check(f"...table {i} ({AC.TUNE_TABLES[i]}) into the GameState's {inbox}, whole: the "
              "inbox its tuner takes (graphics_menu/game_tuner.py)",
              tests == [str(i)] and fed == [AC.VALUES_PARAM], f"{tests}, {fed}")
    writes = sorted(_title(n) for n in run if _title(n).startswith("Set "))
    check("...and writes nothing else: the table is checked and applied by the tuner",
          writes == sorted(f"Set {v}" for v in S.TUNED), str(writes))


def run():
    check_asks()
    check_use_held()
    check_ask_loot_take()
    check_ask_save_exit()
    check_tune_ask()
