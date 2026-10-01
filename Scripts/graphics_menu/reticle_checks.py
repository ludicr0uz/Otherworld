"""verify_graphics_menu.py's checks for the crosshair down a gun's sights
(reticle.py): left out there, except in debug mode. Here rather than in the
verifier, which is over its size budget.
"""

import unreal

from combat.seat_tuning import RETICLE_HIDE_SEAT, SEAT_VAR
from graphics_menu import reticle as R

BEL = unreal.BlueprintEditorLibrary
PIN = unreal.BlueprintGraphPinLibrary


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _pins(n):
    return {str(PIN.get_pin_name(p)) for p in BEL.list_input_pins(n)}


def _num(n, pin):
    try:
        return float(BEL.find_input_pin(n, pin).get_pin_value())
    except (ValueError, AttributeError):
        return None


def _after(pin):
    for q in (pin.list_connected_pins() if pin and pin.is_valid() else []):
        return PIN.get_owning_node(q)
    return None


def _feeds(pin):
    """Every node feeding this pin through data links."""
    seen, stack = [], [pin]
    while stack:
        for q in stack.pop().list_connected_pins():
            node = PIN.get_owning_node(q)
            if node not in seen:
                seen.append(node)
                stack.extend(x for x in BEL.list_input_pins(node)
                             if str(PIN.get_pin_name(x)) != "execute")
    return seen


def sights_gate(nodes):
    """The Branch that leaves the crosshair out: the one whose condition
    reads the weapon component's SightSeat. None if there is not exactly one."""
    gates = [n for n in nodes if {"execute", "Condition"} <= _pins(n)
             and f"Get {SEAT_VAR}" in {
                 _title(m) for m in _feeds(BEL.find_input_pin(n, "Condition"))}]
    return gates[0] if len(gates) == 1 else None


def check_reticle_sights(check, bp, nodes):
    # Down a gun's sights the camera runs along the sight line, so the front
    # sight's tip is the middle of the view and the crosshair only covered
    # it. The hip and the shoulder aim keep it.
    gate = sights_gate(nodes)
    check("one Branch on the weapon component's sight camera decides whether "
          "the crosshair is drawn", gate is not None)
    if gate is None:
        return
    fed = _feeds(BEL.find_input_pin(gate, "Condition"))
    names = {_title(n) for n in fed}
    past = [n for n in fed if _num(n, "B") == RETICLE_HIDE_SEAT
            and f"Get {SEAT_VAR}" in {_title(m)
                                      for m in _feeds(BEL.find_input_pin(n, "A"))}]
    check(f"down the sights ({SEAT_VAR} past {RETICLE_HIDE_SEAT:g}: the camera "
          f"nearly on them) the crosshair is not drawn; the gun's own sights "
          f"are on the middle of the view",
          len(past) == 1, str(sorted(names)))
    check("...except in debug mode, where it is drawn over them",
          "Get DebugOn" in names and any("NOT" in t.upper() for t in names),
          str(sorted(names)))
    drawn = _after(BEL.find_else_pin(gate))
    check("...otherwise (the hip, the shoulder aim, the sights on their way "
          "up) the crosshair is drawn",
          drawn is not None and "RectColor" in _pins(drawn)
          and _num(drawn, "ScreenW") == R.RETICLE_ARM,
          _title(drawn) if drawn else "nothing")
    skipped = _after(BEL.find_then_pin(gate))
    check("...and left out, the rest of the frame is still drawn",
          skipped is not None and "RectColor" not in _pins(skipped),
          _title(skipped) if skipped else "nothing")
    scoped = [n for n in nodes if {"execute", "Condition"} <= _pins(n)
              and _after(BEL.find_else_pin(n)) == gate]
    check("...asked only for an unscoped view: it hangs off the scope gate's "
          "other arm, so the glass is never left out with it",
          len(scoped) == 1 and "Get Scoped" in {
              _title(m) for m in _feeds(BEL.find_input_pin(scoped[0], "Condition"))},
          str(len(scoped)))
