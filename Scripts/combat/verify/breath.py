"""verify.breath -- the sway's per-gun rate and the held breath: the numbers,
the bind, the variables, each gun's SwayRate, and the graph that copies the
rate behind IsValid(Held) and holds, spends and refills the breath.
"""

import unreal

from combat.breath_tuning import (
    BREATH_EASE_SPEED, BREATH_FORCED_VAR, BREATH_HELD_VAR, BREATH_HOLD_S,
    BREATH_RECOVER_S, BREATH_SCALE_VAR, BREATH_SWAY_SCALE, BREATH_VAR,
    BREATH_WINDED_SCALE, HOLD_BREATH_KEY, WINDED_VAR, breath_step,
)
from combat.paths import ITEM_BP_PATH
from combat.sway_tuning import (
    SWAY_PITCH_VAR, SWAY_RATE, SWAY_RATE_COLUMN, SWAY_RATE_VAR, SWAY_TIME_VAR,
    SWAY_YAW_VAR,
)
from combat.tuning import BIND_VARS
from combat.verify.common import BEL, PIN, check, in_pins, load, num_pin
from combat.verify.fixtures import w, wg
from combat.verify.sights import _feeds, _title
from combat.weapon_specs import _weapon_specs


def _item_cdo(path):
    return unreal.get_default_object(BEL.generated_class(load(path)))


def _sets(var):
    return [n for n in wg if _title(n) == f"Set {var}"]


def _fed(var):
    sets = _sets(var)
    return (_feeds(BEL.find_input_pin(sets[0], var)) if len(sets) == 1 else set()), sets


def _holds(nodes, pin, value):
    return any(abs((num_pin(n, pin) or 0.0) - value) < 1e-6
               for n in nodes if pin in in_pins(n))


def check_breath_numbers():
    check(f"the sway runs slower than its periods: SwayRate {SWAY_RATE:g}",
          0.0 < SWAY_RATE < 1.0, str(SWAY_RATE))
    check("holding the breath all but stills the sway; winded shakes it harder",
          0.0 < BREATH_SWAY_SCALE < 0.5 < 1.0 < BREATH_WINDED_SCALE <= 2.0,
          f"{BREATH_SWAY_SCALE} / {BREATH_WINDED_SCALE}")
    # One breath held to the end, at 60 fps: how long it lasts, and how long
    # the player is winded after.
    dt, b, winded, t, held_for = 1.0 / 60.0, BREATH_HOLD_S, False, 0.0, 0.0
    while not winded and t < 60.0:
        b, winded, held = breath_step(b, winded, True, True, dt)
        held_for += dt if held else 0.0
        t += dt
    check(f"...a full breath holds {BREATH_HOLD_S:g} s, then the player is winded",
          winded and abs(held_for - BREATH_HOLD_S) < 0.05, f"{held_for:.2f} s")
    gasp = 0.0
    while winded and gasp < 60.0:
        b, winded, held = breath_step(b, winded, True, True, dt)
        gasp += dt
        if held:
            break
    check(f"...and, key still held, cannot hold it again until it is full: "
          f"{BREATH_RECOVER_S:g} s",
          not held and abs(gasp - BREATH_RECOVER_S) < 0.05, f"{gasp:.2f} s")
    _b, _w, idle = breath_step(BREATH_HOLD_S, False, True, False, dt)
    check("...and the key does nothing off the sights", not idle)


def check_breath_bind():
    names = [v for v, _k in BIND_VARS]
    check(f"holding the breath is its own bind, {HOLD_BREATH_KEY} by default, "
          f"appended last so no saved bind changes meaning",
          names[-1] == "KeyHoldBreath"
          and w.get_editor_property("KeyHoldBreath").export_text() == HOLD_BREATH_KEY,
          str(names[-3:]))


def check_breath_vars():
    want = {SWAY_RATE_VAR: SWAY_RATE, BREATH_VAR: BREATH_HOLD_S, BREATH_SCALE_VAR: 1.0,
            BREATH_HELD_VAR: False, WINDED_VAR: False, BREATH_FORCED_VAR: False}
    got = {k: w.get_editor_property(k) for k in want}
    check("the component starts with a full breath, not held, not winded, the "
          "sway at its full width and the default rate",
          all(type(got[k]) is type(v) and got[k] == v for k, v in want.items()),
          str(got))
    base = _item_cdo(ITEM_BP_PATH).get_editor_property(SWAY_RATE_VAR)
    bad = [f"{sp['display']}={got} spec {sp[SWAY_RATE_COLUMN]}"
           for sp in _weapon_specs()
           for got in [_item_cdo(sp["path"]).get_editor_property(SWAY_RATE_VAR)]
           if abs(got - float(sp[SWAY_RATE_COLUMN])) > 1e-4]
    check(f"every gun holds its own sway rate, the GUN TUNING tab's "
          f"`{SWAY_RATE_COLUMN}` (the base's is {SWAY_RATE:g})",
          isinstance(base, float) and abs(base - SWAY_RATE) < 1e-9 and not bad,
          "; ".join(bad) or str(base))


def check_breath_graph():
    fed, sets = _fed(SWAY_RATE_VAR)
    gets = [n for n in fed if _title(n) == f"Get {SWAY_RATE_VAR}"]
    selves = [_title(PIN.get_owning_node(q)) for n in gets
              for q in PIN.list_connected_pins(BEL.find_input_pin(n, "self"))]
    gate = ([PIN.get_owning_node(q) for q in
             PIN.list_connected_pins(BEL.find_input_pin(sets[0], "execute"))]
            if len(sets) == 1 else [])
    cond = ({_title(n) for n in _feeds(BEL.find_input_pin(gate[0], "Condition"))}
            if len(gate) == 1 and "Condition" in in_pins(gate[0]) else set())
    check("the component's SwayRate is Held's, read behind a Branch on "
          "IsValid(Held) (never off a null Held)",
          len(sets) == 1 and selves == ["Get Held"] and "IsValid" in cond,
          f"{selves} behind {sorted(cond)}")

    fed, sets = _fed(BREATH_HELD_VAR)
    names = {_title(n) for n in fed}
    check("the breath is held by the key (or BreathForced), down the sights, "
          "not winded",
          len(sets) == 1 and {"Get KeyHoldBreath", f"Get {BREATH_FORCED_VAR}",
                              "Get SightAiming", f"Get {WINDED_VAR}"} <= names,
          str(sorted(names)))

    fed, sets = _fed(BREATH_VAR)
    check(f"...spent a second a second while held, refilled in "
          f"{BREATH_RECOVER_S:g} s, kept within 0..{BREATH_HOLD_S:g}",
          len(sets) == 1 and f"Get {BREATH_HELD_VAR}" in {_title(n) for n in fed}
          and _holds(fed, "A", -1.0) and _holds(fed, "B", BREATH_HOLD_S / BREATH_RECOVER_S)
          and _holds(fed, "Max", BREATH_HOLD_S),
          str(sorted(_title(n) for n in fed)))

    fed, sets = _fed(WINDED_VAR)
    check("...winded once it is spent, until it is whole again",
          len(sets) == 1 and f"Get {BREATH_VAR}" in {_title(n) for n in fed}
          and _holds(fed, "B", 0.0) and _holds(fed, "B", BREATH_HOLD_S),
          str(sorted(_title(n) for n in fed)))

    fed, sets = _fed(BREATH_SCALE_VAR)
    check(f"BreathScale eases (at {BREATH_EASE_SPEED:g}) to {BREATH_SWAY_SCALE:g} "
          f"held, {BREATH_WINDED_SCALE:g} winded, 1 otherwise",
          len(sets) == 1 and _holds(fed, "InterpSpeed", BREATH_EASE_SPEED)
          and _holds(fed, "A", BREATH_SWAY_SCALE) and _holds(fed, "A", BREATH_WINDED_SCALE),
          str(sorted(_title(n) for n in fed)))

    order = []
    for var in (SWAY_RATE_VAR, BREATH_HELD_VAR, BREATH_VAR, WINDED_VAR, BREATH_SCALE_VAR):
        order.extend(_sets(var))
    check("...each stored before the next reads it, in that order",
          len(order) == 5 and all(
              order[i] in [PIN.get_owning_node(q) for q in PIN.list_connected_pins(
                  BEL.find_input_pin(order[i + 1], "execute"))]
              for i in range(1, 4)),
          str([_title(n) for n in order]))

    names = set()
    for var in (SWAY_YAW_VAR, SWAY_PITCH_VAR):
        fed, _s = _fed(var)
        names |= {_title(n) for n in fed}
    clock, _s = _fed(SWAY_TIME_VAR)
    check("the sway's width is times BreathScale, and its clock runs at SwayRate",
          f"Get {BREATH_SCALE_VAR}" in names
          and f"Get {SWAY_RATE_VAR}" in {_title(n) for n in clock},
          str(sorted(names)))


def run():
    check_breath_numbers()
    check_breath_bind()
    check_breath_vars()
    check_breath_graph()
