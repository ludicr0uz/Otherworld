"""verify.sway -- the sight sway: its numbers, the three variables, and the
graph that turns the view by the sway's change and only then stores it.
"""

from combat.sway_tuning import (
    SWAY_CROUCH_SCALE, SWAY_MIN_STEP_DEG, SWAY_PITCH_DEG, SWAY_PITCH_PERIOD_S,
    SWAY_PITCH_VAR, SWAY_PRONE_SCALE, SWAY_TIME_VAR, SWAY_VARS, SWAY_YAW_DEG,
    SWAY_YAW_PERIOD_S, SWAY_YAW_VAR, sway_at, sway_rate,
)
from combat.verify.common import BEL, PIN, check, in_pins, num_pin
from combat.verify.fixtures import w, wg
from combat.verify.sights import _feeds, _title

# AController::SetControlRotation takes no change smaller than this (degrees).
CONTROLLER_TOLERANCE_DEG = 1e-3


def _holds(nodes, pin, value):
    return any(abs((num_pin(n, pin) or 0.0) - value) < 1e-9
               for n in nodes if pin in in_pins(n))


def check_sway_numbers():
    check("the sway is small and slow: under half a degree, seconds a swing",
          0.0 < SWAY_PITCH_DEG <= SWAY_YAW_DEG <= 0.5
          and min(SWAY_YAW_PERIOD_S, SWAY_PITCH_PERIOD_S) >= 2.0,
          f"{SWAY_YAW_DEG} / {SWAY_PITCH_DEG} deg, "
          f"{SWAY_YAW_PERIOD_S} / {SWAY_PITCH_PERIOD_S} s")
    ratio = SWAY_YAW_PERIOD_S / SWAY_PITCH_PERIOD_S
    check("...its two periods share no small multiple, so the path does not "
          "visibly repeat",
          all(abs(ratio * k - round(ratio * k)) > 0.05 for k in range(1, 5)),
          f"{ratio:.3f}")
    check("...steadier crouched, steadiest prone",
          0.0 < SWAY_PRONE_SCALE < SWAY_CROUCH_SCALE < 1.0,
          f"{SWAY_CROUCH_SCALE} / {SWAY_PRONE_SCALE}")
    check("...nothing at the hip (SightBlend 0), all of it down the sights",
          sway_at(1.0, 0.0) == (0.0, 0.0)
          and abs(sway_at(SWAY_YAW_PERIOD_S / 4.0, 1.0)[0] - SWAY_YAW_DEG) < 1e-9,
          str(sway_at(SWAY_YAW_PERIOD_S / 4.0, 1.0)))
    check("...and a step is taken only once the controller would keep it",
          SWAY_MIN_STEP_DEG > CONTROLLER_TOLERANCE_DEG, str(SWAY_MIN_STEP_DEG))
    for name in SWAY_VARS:
        got = w.get_editor_property(name)
        check(f"{name} is a float on the component, starting at zero",
              isinstance(got, float) and abs(got) < 1e-9, repr(got))


def check_sway_graph():
    clocks = [n for n in wg if _title(n) == f"Set {SWAY_TIME_VAR}"]
    up = ({_title(n) for n in _feeds(BEL.find_input_pin(clocks[0], SWAY_TIME_VAR))}
          if clocks else set())
    check("the sway's clock is advanced once a frame by the frame's time",
          len(clocks) == 1 and f"Get {SWAY_TIME_VAR}" in up
          and any("Tick" in t for t in up), str(sorted(up)))

    stores = {}
    for var, degrees, period in ((SWAY_YAW_VAR, SWAY_YAW_DEG, SWAY_YAW_PERIOD_S),
                                 (SWAY_PITCH_VAR, SWAY_PITCH_DEG, SWAY_PITCH_PERIOD_S)):
        sets = [n for n in wg if _title(n) == f"Set {var}"]
        fed = _feeds(BEL.find_input_pin(sets[0], var)) if sets else set()
        names = {_title(n) for n in fed}
        check(f"{var} is stored once: {degrees:g} deg x Sin(clock x 2pi / "
              f"{period:g} s)",
              len(sets) == 1 and f"Get {SWAY_TIME_VAR}" in names
              and any(t.lower().startswith("sin") for t in names)
              and _holds(fed, "B", degrees) and _holds(fed, "B", sway_rate(period)),
              str(sorted(names)))
        check("...times SightBlend and the stance's steadying",
              "Get SightBlend" in names and "Get Stance" in names
              and _holds(fed, "A", SWAY_CROUCH_SCALE)
              and _holds(fed, "A", SWAY_PRONE_SCALE), str(sorted(names)))
        stores[var] = sets[0] if sets else None

    def before(node):
        return [PIN.get_owning_node(q) for q in
                PIN.list_connected_pins(BEL.find_input_pin(node, "execute"))]

    yaw, pitch = stores[SWAY_YAW_VAR], stores[SWAY_PITCH_VAR]
    turn = before(yaw) if yaw else []
    check("the view is turned (SetControlRotation) BEFORE the two offsets are "
          "stored, so the step reads what was applied last",
          len(turn) == 1 and "SetControlRotation" in _title(turn[0]).replace(" ", "")
          and pitch is not None and before(pitch) == [yaw],
          str([_title(n) for n in turn]))
    if len(turn) != 1:
        return
    fed = _feeds(BEL.find_input_pin(turn[0], "NewRotation"))
    names = {_title(n) for n in fed}
    check("...by the sway now less the sway applied, on top of the control "
          "rotation as it stands (the mouse's and the recoil's)",
          {f"Get {SWAY_YAW_VAR}", f"Get {SWAY_PITCH_VAR}"} <= names
          and any("GetControlRotation" in t.replace(" ", "") for t in names),
          str(sorted(names)))
    gate = before(turn[0])
    cond = (_feeds(BEL.find_input_pin(gate[0], "Condition"))
            if len(gate) == 1 and "Condition" in in_pins(gate[0]) else set())
    steps = [n for n in cond
             if abs((num_pin(n, "B") or 0.0) - SWAY_MIN_STEP_DEG) < 1e-12]
    check(f"...and only once either axis has {SWAY_MIN_STEP_DEG:g} deg to take: "
          f"a smaller change is dropped by the controller, and counting it "
          f"would drift the view",
          len(steps) == 2 and before(gate[0]) == clocks,
          f"{len(steps)} thresholds behind {[_title(n) for n in gate]}")


def run():
    check_sway_numbers()
    check_sway_graph()
