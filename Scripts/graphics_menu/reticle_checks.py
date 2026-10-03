"""verify_graphics_menu.py's checks for the crosshair (reticle.py): left out
down a gun's sights, except in debug mode; always white; and the headshot's
X round it (hit_marker.py). Here rather than in the
verifier, which is over its size budget.
"""

import unreal

from combat.headshot_tuning import HEADSHOT_MARK_SECONDS, HEADSHOT_TIME_VAR
from combat.seat_tuning import RETICLE_HIDE_SEAT, SEAT_VAR
from graphics_menu import hit_marker as M
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


def _colour(n, pin):
    """A LinearColor pin's literal as four floats; None if it is linked."""
    p = BEL.find_input_pin(n, pin)
    if p is None or not p.is_valid() or p.list_connected_pins():
        return None
    try:
        return tuple(round(float(part.split("=")[1]), 3)
                     for part in str(p.get_pin_value()).strip("()").split(","))
    except (IndexError, ValueError):
        return None


def check_reticle_white(check, nodes):
    # The crosshair is one white, always. It turned red while the muzzle's
    # line was blocked (AimBlocked through a SelectColor), which the player
    # could not read; nothing on the HUD picks its colour off the aim now.
    sizes = {R.RETICLE_ARM, R.RETICLE_THICK, R.RETICLE_DOT}
    rects = [n for n in nodes if "RectColor" in _pins(n)
             and _num(n, "ScreenW") in sizes and _num(n, "ScreenH") in sizes]
    white = _colour_of(R.COL_RETICLE)
    check("the reticle is four ticks and a dot, each drawn in the one white: "
          "a literal, not a colour picked off the aim",
          len(rects) == 5 and all(_colour(n, "RectColor") == white for n in rects),
          str([_colour(n, "RectColor") for n in rects]))
    check("...and the HUD does not read AimBlocked: a blocked muzzle no "
          "longer turns it red",
          not [n for n in nodes if _title(n) == "Get AimBlocked"]
          and not hasattr(R, "COL_RETICLE_BLOCKED"))


def _colour_of(text):
    return tuple(round(float(part.split("=")[1]), 3)
                 for part in text.strip("()").split(","))


def check_headshot_mark(check, nodes):
    # An X round the centre for a moment after a headshot (hit_marker.py).
    gates = [n for n in nodes if {"execute", "Condition"} <= _pins(n)
             and f"Get {HEADSHOT_TIME_VAR}" in {
                 _title(m) for m in _feeds(BEL.find_input_pin(n, "Condition"))}]
    check(f"one Branch on the weapon component's {HEADSHOT_TIME_VAR} decides "
          f"whether the headshot's X is drawn", len(gates) == 1, str(len(gates)))
    if len(gates) != 1:
        return
    gate = gates[0]
    fed = _feeds(BEL.find_input_pin(gate, "Condition"))
    names = {_title(n) for n in fed}
    check(f"...for {HEADSHOT_MARK_SECONDS:g} s of game time after it",
          any(_num(n, "B") == HEADSHOT_MARK_SECONDS for n in fed)
          and any("Time" in t and "Seconds" in t.replace(" ", "") for t in names),
          str(sorted(names)))
    strokes, at = [], _after(BEL.find_then_pin(gate))
    while at is not None and "StartScreenX" in _pins(at):
        strokes.append(at)
        at = _after(BEL.find_then_pin(at))

    def by(n, pin):
        """The pixels this coordinate stands off the centre: its Add's B."""
        adds = [m for m in (_after(BEL.find_input_pin(n, pin)),) if m is not None]
        return _num(adds[0], "B") if adds else None

    ends = [(by(n, "StartScreenX"), by(n, "StartScreenY"),
             by(n, "EndScreenX"), by(n, "EndScreenY")) for n in strokes]
    whole = [e for e in ends if None not in e]
    check("...four strokes, one out along each diagonal: an X with the "
          "reticle in its open middle",
          len(strokes) == 4 and len(whole) == 4
          and {(e[0] > 0, e[1] > 0) for e in whole}
          == {(a, b) for a in (False, True) for b in (False, True)}
          and all(abs(e[0]) == abs(e[1]) == M.MARK_INNER
                  and abs(e[2]) == abs(e[3]) == M.MARK_OUTER
                  and e[0] * e[2] > 0 and e[1] * e[3] > 0 for e in whole),
          str(ends))
    check("...in the reticle's own white",
          bool(strokes) and all(_colour(n, "LineColor") == _colour_of(R.COL_RETICLE)
                                for n in strokes)
          and M.COL_MARK == R.COL_RETICLE,
          str([_colour(n, "LineColor") for n in strokes]))
    arms = BEL.find_input_pin(gate, "execute").list_connected_pins()
    before = [PIN.get_owning_node(q) for q in arms]
    sights = sights_gate(nodes)
    check("...asked on every arm of the reticle that has the weapon "
          "component: the crosshair drawn, the crosshair left out down the "
          "sights, the scope, and empty hands",
          len(arms) == 4 and sights in before
          and any("RectColor" in _pins(n) and _num(n, "ScreenW") == R.RETICLE_DOT
                  for n in before),
          str([_title(n) for n in before]))
