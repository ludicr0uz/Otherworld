"""verify.dead -- the dead gate at the head of the weapon component's Tick
(weapon_component/dead.py): a dead owner gets none of the Tick, and the dead
arm lets go of what the living Tick was holding.

That the gate shuts in the game, and opens for the living, is
probes/probe_dead_no_actions.py.
"""

from combat.nodes import SPRING_ARM_SOCKET
from combat.seat_tuning import LOOK_VAR, SEAT_VAR
from combat.verify.common import BEL, PIN, by_pins, check, in_pins, num_pin, pin_value
from combat.verify.fixtures import exec_reach, w, wg, wg_dead
from combat.weapon_component.dead import LET_GO_VARS, OWNER_DEAD_VAR
from combat.weapon_component.tick import FIRE_FORCED_VAR


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _execs(n):
    return [p for p in BEL.list_output_pins(n)
            if "exec" in str(PIN.get_pin_type_display_string(p)).lower()]


def _next(pins):
    return [PIN.get_owning_node(q) for p in pins for q in PIN.list_connected_pins(p)]


def _sources(n, pin, limit=40):
    """Every node feeding ``n``'s input ``pin`` through data links."""
    seen, todo = {}, [BEL.find_input_pin(n, pin)]
    while todo and len(seen) < limit:
        for q in PIN.list_connected_pins(todo.pop()):
            f = PIN.get_owning_node(q)
            if f.get_path_name() not in seen:
                seen[f.get_path_name()] = f
                todo += [x for x in BEL.list_input_pins(f)
                         if str(PIN.get_pin_name(x)) != "execute"]
    return list(seen.values())


def check_dead_gate():
    check(f"{OWNER_DEAD_VAR} and the probe's {FIRE_FORCED_VAR} are bools that start false",
          w.get_editor_property(OWNER_DEAD_VAR) is False
          and w.get_editor_property(FIRE_FORCED_VAR) is False)
    ticks = [n for n in wg if _title(n) == "Event Tick"]
    first = _next(_execs(ticks[0])) if len(ticks) == 1 else []
    check("the first thing Tick runs is the cast to the owner's health component",
          len(first) == 1 and "Cast" in _title(first[0]) and "Health" in _title(first[0]),
          f"{[_title(n) for n in first]}")
    if len(first) != 1:
        return
    cast = first[0]
    gates = _next([BEL.find_then_pin(cast)])
    check("...and then one Branch: the dead gate",
          len(gates) == 1 and _title(gates[0]) == "Branch", f"{[_title(n) for n in gates]}")
    if len(gates) != 1:
        return
    gate = gates[0]
    fed = _sources(gate, "Condition")
    # A literal equal to the pin's own default is not saved: 0.0 reads back as
    # "0.0" in the editor that authored it and as "" once loaded from disk.
    zero = [n for n in fed if {"A", "B"} <= in_pins(n)
            and (num_pin(n, "B") == 0.0 or pin_value(n, "B") == "")
            and not PIN.list_connected_pins(BEL.find_input_pin(n, "B"))
            and "Get Health" in [_title(f) for f in _sources(n, "A")]]
    check("the gate shuts on Dead OR Health <= 0, so the frame of the killing "
          "blow is covered whichever component ticks first",
          "Get Dead" in [_title(n) for n in fed] and len(zero) == 1
          and "<=" in _title(zero[0]),
          f"{sorted(_title(n) for n in fed)}")

    # The True arm's first node is the shed's latch (weapon_component/shed.py,
    # verify/player_death.py): a Branch on OwnerDead as it was, whose True arm
    # goes straight on to the setter.
    latch = _next([BEL.find_then_pin(gate)])
    dead = (_next([BEL.find_then_pin(latch[0])])
            if len(latch) == 1 and f"Get {OWNER_DEAD_VAR}" in
            [_title(f) for f in _sources(latch[0], "Condition")] else [])
    live = _next([BEL.find_else_pin(gate)])
    spared = _next([p for p in _execs(cast) if "Failed" in str(PIN.get_pin_name(p))])
    check(f"the True arm marks {OWNER_DEAD_VAR}; the False arm, and an owner with "
          f"no health component, clear it at one setter",
          len(dead) == 1 and _title(dead[0]) == f"Set {OWNER_DEAD_VAR}"
          and pin_value(dead[0], OWNER_DEAD_VAR) == "true"
          and len(live) == 1 and live == spared
          and _title(live[0]) == f"Set {OWNER_DEAD_VAR}"
          and pin_value(live[0], OWNER_DEAD_VAR) == "false",
          f"{[_title(n) for n in dead + live + spared]}")
    if len(dead) != 1 or len(live) != 1:
        return
    living = {n.get_path_name() for n in exec_reach(_execs(live[0]))}
    dying = {n.get_path_name() for n in exec_reach(_execs(dead[0]))}
    polls = [n for n in wg if "Key" in in_pins(n)]
    check("every key the Tick polls is polled by the living Tick",
          len(polls) > 10 and len(living) > 200, f"{len(polls)} polls, {len(living)} nodes")
    check("...and the dead arm runs none of it: no key, no node of the living Tick",
          not (living & dying) and not any("Key" in in_pins(n) for n in wg_dead),
          f"{len(living & dying)} shared")


def check_dead_arm_lets_go():
    for name in LET_GO_VARS:
        sets = [n for n in wg_dead if _title(n) == f"Set {name}"]
        check(f"a dead owner stops {name}",
              len(sets) == 1 and pin_value(sets[0], name) == "false",
              f"{[pin_value(n, name) for n in sets]}")
    for var, what in ((SEAT_VAR, "seat"), (LOOK_VAR, "look")):
        seats = [n for n in wg_dead if _title(n) == f"Set {var}"]
        check(f"...the sight camera's {what} is cleared ({var} 0), so the next "
              f"life starts on the boom",
              len(seats) == 1 and (num_pin(seats[0], var) or 0.0) == 0.0
              and not PIN.list_connected_pins(BEL.find_input_pin(seats[0], var)),
              str(len(seats)))
    fov = by_pins(wg_dead, "InFieldOfView")
    check("...the zoom snaps back to BaseFOV",
          len(fov) == 1 and [_title(f) for f in _sources(fov[0], "InFieldOfView")]
          == ["Get BaseFOV"])
    home = by_pins(wg_dead, "NewLocation")
    sockets = [f for h in home for f in _sources(h, "NewLocation")
               if "InSocketName" in in_pins(f)]
    check(f"...the camera goes home to the boom's {SPRING_ARM_SOCKET}",
          len(home) == 1 and len(sockets) == 1
          and pin_value(sockets[0], "InSocketName") == SPRING_ARM_SOCKET)
    level = by_pins(wg_dead, "NewRotation")
    level = [n for n in level if "setworldrotation" in _title(n).replace(" ", "").lower()]
    sockets = [f for h in level for f in _sources(h, "NewRotation")
               if "InSocketName" in in_pins(f)]
    check("...and level with it again, off the gun's sight line",
          len(level) == 1 and len(sockets) == 1
          and pin_value(sockets[0], "InSocketName") == SPRING_ARM_SOCKET)
    # OwnerMesh's own, and once more in a loop over the parts under it
    # (weapon_component/body_parts.py): both false.
    body = by_pins(wg_dead, "bNewOwnerNoSee")
    check("...the body a scope hid is shown, and what is drawn under it",
          len(body) == 2 and all(pin_value(n, "bNewOwnerNoSee") == "false" for n in body),
          str(len(body)))
    gun = by_pins(wg_dead, "bNewHidden")
    armed = [d for g in gun for d in _next_back(g)]
    check("...and the gun too, behind a Branch on IsValid(Held)",
          len(gun) == 1 and pin_value(gun[0], "bNewHidden") == "false"
          and len(armed) == 1 and _title(armed[0]) == "Branch"
          and any("Is Valid" in _title(f) or "IsValid" in _title(f)
                  for f in _sources(armed[0], "Condition")),
          f"{[_title(n) for n in armed]}")


def _next_back(n):
    """The nodes whose exec output runs ``n``."""
    return [PIN.get_owning_node(q)
            for q in PIN.list_connected_pins(BEL.find_execute_pin(n))]


def run():
    check_dead_gate()
    check_dead_arm_lets_go()
