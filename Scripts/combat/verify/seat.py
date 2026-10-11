"""verify.seat -- the sight camera's seat (weapon_component/seat.py): SightSeat 1
at once while the sights key is held and eased home off it, SightSeated latching
on the gun's line coming near the view, SightLook eased toward the latch, and
all three clear with empty hands. Split out of verify.sights, which was over
its size budget.
"""

from combat.seat_tuning import (
    LOOK_VAR, SEAT_VAR, SEATED_VAR, SIGHT_SEAT_COS, SIGHT_SEAT_DEG,
)
from combat.tuning import COMBAT
from combat.weapon_component.sights import SIGHT_LINE_MIN_CM
from combat.verify.fixtures import w, wg
from combat.verify.sights import _feeds, _title
from combat.verify.common import BEL, PIN, check, in_pins, num_pin, pin_value


def check_sight_seat():
    """At once from the key (weapon_component/seat.py): SightSeat, which
    places the camera, is 1 while the sights key is held and eases home off
    it. SightSeated latches on the gun's sight line coming near the view, and
    SightLook, which turns the camera onto that line, eases toward the latch."""
    def writes(var):
        sets = [n for n in wg if _title(n) == f"Set {var}"]
        wired = [n for n in sets
                 if PIN.list_connected_pins(BEL.find_input_pin(n, var))]
        return sets, wired

    latches, wired = writes(SEATED_VAR)
    check(f"{SEATED_VAR} is written twice by the living Tick: armed, and false "
          f"with empty hands",
          len(latches) == 2 and len(wired) == 1
          and all(pin_value(n, SEATED_VAR) == "false"
                  for n in latches if n not in wired),
          f"{len(latches)} writes, {len(wired)} wired")
    fed = _feeds(BEL.find_input_pin(wired[0], SEATED_VAR)) if wired else set()
    names = {_title(n) for n in fed}
    check("...armed, it is the sights held AND (already seated OR the gun up): "
          "a latch, so a reload with the sights up keeps the camera on the gun",
          {"Get SightAiming", f"Get {SEATED_VAR}"} <= names, str(sorted(names)))
    near = [n for n in fed
            if abs((num_pin(n, "B") or 0.0) - SIGHT_SEAT_COS) < 1e-5
            and "A" in in_pins(n) and len(in_pins(n)) == 2]
    behind = ({_title(n) for n in _feeds(BEL.find_input_pin(near[0], "A"))}
              if near else set())
    check(f"...the gun is up when its sight line is within {SIGHT_SEAT_DEG:g} deg "
          f"of the view: the line's direction dotted with the boom's (the "
          f"control rotation's) forward, against cos",
          len(near) == 1 and "Get SightAim" in behind and "Get SightOffset" in behind
          and any("dot" in t.lower() for t in behind)
          and any("InSocketName" in in_pins(n)
                  for n in _feeds(BEL.find_input_pin(near[0], "A"))),
          str(sorted(behind)))
    gates = [n for n in fed
             if abs((num_pin(n, "B") or 0.0) - SIGHT_LINE_MIN_CM) < 1e-9
             and "A" in in_pins(n) and len(in_pins(n)) == 2]
    check("...and an item with no sight line is seated at once: there is no "
          "line to wait for", len(gates) == 1, str(len(gates)))

    seats, wired = writes(SEAT_VAR)
    check(f"{SEAT_VAR} is written twice by the living Tick: armed, and zero "
          f"with empty hands",
          len(seats) == 2 and len(wired) == 1
          and all((num_pin(n, SEAT_VAR) or 0.0) == 0.0
                  for n in seats if n not in wired),
          f"{len(seats)} writes, {len(wired)} wired")
    fed = _feeds(BEL.find_input_pin(wired[0], SEAT_VAR)) if wired else set()
    names = {_title(n) for n in fed}
    eases = [n for n in fed if {"Current", "Target", "InterpSpeed"} <= in_pins(n)]
    check(f"...eased home off the sights key (SightAiming) by an FInterpTo at "
          f"the zoom's speed ({COMBAT.ads_interp_speed:g}), and not waiting "
          f"for {SEATED_VAR}",
          len(eases) == 1 and {f"Get {SEAT_VAR}", "Get SightAiming"} <= names
          and not {f"Set {SEATED_VAR}", f"Get {SEATED_VAR}"} & names
          and abs((num_pin(eases[0], "InterpSpeed") or 0.0)
                  - COMBAT.ads_interp_speed) < 1e-9,
          str(sorted(names)))
    # The frame the key goes down, the seat is 1: a SelectFloat straight
    # into the Set, the literal 1 on B, picking the ease only while the key
    # is up (NOT SightAiming on bPickA).
    picks = [PIN.get_owning_node(q) for q in PIN.list_connected_pins(
        BEL.find_input_pin(wired[0], SEAT_VAR))] if wired else []
    snap = [n for n in picks if {"A", "B", "bPickA"} <= in_pins(n)
            and abs((num_pin(n, "B") or 0.0) - 1.0) < 1e-9]
    picked = ([_title(n) for n in _feeds(BEL.find_input_pin(snap[0], "bPickA"))]
              if snap else [])
    check("...and 1 at once while the key is held: a SelectFloat into the "
          "write, its B 1, the ease picked only on NOT SightAiming, so the "
          "camera is in the sights' view on the frame of the key and the gun "
          "rises into it",
          len(snap) == 1 and "Get SightAiming" in picked
          and any("not" in t.lower() for t in picked)
          and eases[0] in _feeds(BEL.find_input_pin(snap[0], "A")) if eases else False,
          f"{len(snap)} snaps, picked by {sorted(picked)}")

    looks, wired = writes(LOOK_VAR)
    check(f"{LOOK_VAR} is written twice by the living Tick: armed, and zero "
          f"with empty hands",
          len(looks) == 2 and len(wired) == 1
          and all((num_pin(n, LOOK_VAR) or 0.0) == 0.0
                  for n in looks if n not in wired),
          f"{len(looks)} writes, {len(wired)} wired")
    fed = _feeds(BEL.find_input_pin(wired[0], LOOK_VAR)) if wired else set()
    names = {_title(n) for n in fed}
    eases = [n for n in fed if {"Current", "Target", "InterpSpeed"} <= in_pins(n)]
    check(f"...eased toward {SEATED_VAR} at the same speed: the view turns onto "
          f"the gun's sight line only once the gun is up",
          len(eases) == 1 and {f"Get {LOOK_VAR}", f"Set {SEATED_VAR}"} <= names
          and abs((num_pin(eases[0], "InterpSpeed") or 0.0)
                  - COMBAT.ads_interp_speed) < 1e-9,
          str(sorted(names)))
    got = (w.get_editor_property(SEATED_VAR), w.get_editor_property(SEAT_VAR),
           w.get_editor_property(LOOK_VAR))
    check("...and all three start clear: the camera begins on the boom",
          got[0] is False and all(isinstance(g, float) and g == 0.0
                                  for g in got[1:]), repr(got))


def run():
    check_sight_seat()
