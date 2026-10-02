"""verify.throw_melee -- a melee weapon's throw: flat and fast where every
other item is lobbed, and spinning forward, edge first (throw_tuning.MELEE_THROW
on the knife and the axe; throw_flight._author_square at the release).
"""

from combat.paths import AXE_BP_PATH, ITEM_BP_PATH, KNIFE_BP_PATH
from combat.throw_tuning import (
    MELEE_THROW, THROW_ARC_SIM_S, THROW_EDGE_ON_VAR, THROW_MELEE_PITCH_UP_DEG,
    THROW_MELEE_SPEED, THROW_MELEE_SPIN_DEG_S, THROW_PITCH_UP_DEG, THROW_SPEED,
    THROW_SPEED_VAR, THROW_SPIN_DEG_S, THROW_SPIN_VAR,
)
from combat.verify.common import BEL, PIN, by_pins, check
from combat.verify.fixtures import wg
from combat.verify.throw import _carry, _item_cdo, _title, _upstream
from combat.weapon_component.throw_flight import THROW_VELOCITY_VAR
from combat.weapon_specs import _weapon_specs


def check_melee_throw():
    """A melee weapon is thrown flat and fast and spins forward, edge first."""
    base = _item_cdo(ITEM_BP_PATH)
    got = {v: base.get_editor_property(v)
           for v in (THROW_SPEED_VAR, THROW_SPIN_VAR, THROW_EDGE_ON_VAR)}
    check(f"every item leaves at {THROW_SPEED:g} cm/s, tumbling "
          f"{THROW_SPIN_DEG_S:g} degrees a second and as the hand held it, "
          "unless it says otherwise",
          isinstance(got[THROW_SPEED_VAR], float) and isinstance(got[THROW_SPIN_VAR], float)
          and got == {THROW_SPEED_VAR: THROW_SPEED, THROW_SPIN_VAR: THROW_SPIN_DEG_S,
                      THROW_EDGE_ON_VAR: False}
          and 180.0 <= THROW_SPIN_DEG_S <= 1080.0, str(got))
    bad = [f"{sp['display']}: {v}={got}" for sp in _weapon_specs()
           for v, want in ((THROW_SPEED_VAR, THROW_SPEED),
                           (THROW_SPIN_VAR, THROW_SPIN_DEG_S),
                           (THROW_EDGE_ON_VAR, False))
           for got in [_item_cdo(sp["path"]).get_editor_property(v)] if got != want]
    check("...which no gun does", not bad, "; ".join(bad))
    for name, path in (("knife", KNIFE_BP_PATH), ("axe", AXE_BP_PATH)):
        cdo = _item_cdo(path)
        got = {v: cdo.get_editor_property(v) for v in MELEE_THROW}
        check(f"the {name} is thrown as a melee weapon: "
              f"{THROW_MELEE_PITCH_UP_DEG:g} degrees up at {THROW_MELEE_SPEED:g} "
              f"cm/s, {THROW_MELEE_SPIN_DEG_S:g} degrees a second, edge on",
              cdo.get_editor_property("Melee") is True and got == MELEE_THROW, str(got))
    far, rise, t = _carry(THROW_MELEE_SPEED, THROW_MELEE_PITCH_UP_DEG)
    lob_far, lob_rise, lob_t = _carry(THROW_SPEED, THROW_PITCH_UP_DEG)
    check("a melee weapon's throw is direct: under a third of the lob's rise "
          "over the hand, at least as far, in less time",
          rise < lob_rise / 3.0 and far >= lob_far and t < lob_t
          and 500.0 <= far * 100.0 <= 2000.0 and t < THROW_ARC_SIM_S,
          f"{far:.1f} m rising {rise:.0f} cm in {t:.2f} s; the lob "
          f"{lob_far:.1f} m rising {lob_rise:.0f} cm in {lob_t:.2f} s")
    check("...and spins faster than the tumble, at a rate a frame can show",
          THROW_SPIN_DEG_S < THROW_MELEE_SPIN_DEG_S <= 1440.0,
          f"{THROW_MELEE_SPIN_DEG_S:g}")
    turns = [n for n in by_pins(wg, "NewRotation", "bTeleportPhysics")
             if any(_title(PIN.get_owning_node(q)) == "Get Held"
                    for q in PIN.list_connected_pins(BEL.find_input_pin(n, "self")))]
    check("the release turns the held item once", len(turns) == 1, str(len(turns)))
    if len(turns) != 1:
        return
    src = _upstream(turns[0], "NewRotation")
    check("...squaring it up to the throw: its X along the stored velocity, "
          "no roll, so its blade's plane is the plane it flies in",
          f"Get {THROW_VELOCITY_VAR}" in src
          and any("MakeRotFromX" in t.replace(" ", "") for t in src),
          str(sorted(src)))
    gates = [PIN.get_owning_node(q) for q in
             PIN.list_connected_pins(BEL.find_input_pin(turns[0], "execute"))]
    asks = [_title(PIN.get_owning_node(q)) for g in gates
            for q in PIN.list_connected_pins(BEL.find_input_pin(g, "Condition"))]
    check(f"...only an item whose {THROW_EDGE_ON_VAR} is set",
          [_title(g) for g in gates] == ["Branch"]
          and asks == [f"Get {THROW_EDGE_ON_VAR}"], f"{asks}")
    # Walk the exec chain back from the gate: the store is upstream of it.
    before, stack = set(), list(gates)
    while stack and len(before) < 12:
        for q in PIN.list_connected_pins(BEL.find_input_pin(stack.pop(), "execute")):
            node = PIN.get_owning_node(q)
            if node not in before:
                before.add(node)
                stack.append(node)
    check("...after the release has stored that velocity",
          f"Set {THROW_VELOCITY_VAR}" in {_title(n) for n in before},
          str(sorted(_title(n) for n in before)))


def run():
    check_melee_throw()
