"""verify.steady -- down the sights a hit plays no flinch: the health
component's Steady gate in front of the reaction (hit_reaction.py), and the
weapon component's write of it (weapon_component/steady.py).

That the view stays put in the game, and that the flinch still plays at the
hip, is probes/probe_ads_hit.py.
"""

from combat.anim_blueprint import HIT_SLOT
from combat.hit_reaction import PREV_HEALTH_VAR, STEADY_VAR
from combat.verify.common import BEL, PIN, check, has_in_pin, in_pins, num_pin, pin_value
from combat.verify.fixtures import h, hg, wg
from combat.verify.sights import _feeds, _title
from combat.weapon_component.steady import STEADY_BLEND


def _after(pin):
    return [PIN.get_owning_node(q) for q in PIN.list_connected_pins(pin)]


def _before(node):
    return _after(BEL.find_input_pin(node, "execute"))


def _reads(nodes):
    """The Branches whose Condition a `Get Steady` in `nodes` feeds."""
    return [b for b in nodes if "Condition" in in_pins(b)
            and f"Get {STEADY_VAR}" in
            {_title(n) for n in _feeds(BEL.find_input_pin(b, "Condition"))}]


def check_steady_gate():
    check(f"{STEADY_VAR} is a bool on the health component, False until a "
          f"weapon component says otherwise (a wanderer's never is)",
          h.get_editor_property(STEADY_VAR) is False,
          repr(h.get_editor_property(STEADY_VAR)))
    gates = _reads(hg)
    check(f"the health Tick asks {STEADY_VAR} once, on a Branch of its own",
          len(gates) == 1 and len(_feeds(BEL.find_input_pin(gates[0], "Condition"))) == 1,
          f"{len(gates)} branches")
    if len(gates) != 1:
        return
    kept = _after(BEL.find_then_pin(gates[0]))
    check(f"...steady: the hit is only remembered ({PREV_HEALTH_VAR} = Health), "
          f"so it is not read as a new one when the sights come down",
          len(kept) == 1 and has_in_pin(kept[0], PREV_HEALTH_VAR),
          str([_title(n) for n in kept]))
    hurt = _after(BEL.find_else_pin(gates[0]))
    cond = ({_title(n) for n in _feeds(BEL.find_input_pin(hurt[0], "Condition"))}
            if len(hurt) == 1 and "Condition" in in_pins(hurt[0]) else set())
    check("...not steady: on to the flinch's own test, Health < "
          f"{PREV_HEALTH_VAR}",
          {"Get Health", f"Get {PREV_HEALTH_VAR}"} <= cond, str(sorted(cond)))


def check_steady_write():
    writes = [n for n in wg if _title(n) == f"Set {STEADY_VAR}"]
    fed = _feeds(BEL.find_input_pin(writes[0], STEADY_VAR)) if writes else set()
    names = {_title(n) for n in fed}
    check(f"the weapon component writes the owner's {STEADY_VAR} once a frame: "
          f"SightBlend > {STEADY_BLEND:g}, the whole time the camera is on the gun",
          len(writes) == 1 and names >= {"Get SightBlend"}
          and "Get SightAiming" not in names
          and any(abs((num_pin(n, "B") or 0.0) - STEADY_BLEND) < 1e-9
                  for n in fed if "B" in in_pins(n)),
          f"{len(writes)} writes, fed by {sorted(names)}")
    if len(writes) != 1:
        return
    caught = [b for b in _reads(wg) if writes[0] in _after(BEL.find_else_pin(b))]
    cond = (_feeds(BEL.find_input_pin(caught[0], "Condition"))
            if len(caught) == 1 else set())
    check(f"...and a flinch playing on the frame it turns true ({HIT_SLOT} "
          f"active, last frame's {STEADY_VAR} false) is caught first",
          len(caught) == 1 and "Get SightBlend" in {_title(n) for n in cond}
          and any(pin_value(n, "SlotNodeName") == HIT_SLOT
                  for n in cond if "SlotNodeName" in in_pins(n)),
          str(sorted(_title(n) for n in cond)))
    if len(caught) != 1:
        return
    asked = _after(BEL.find_then_pin(caught[0]))
    check("...by a re-equip (NeedsRefresh), which plays the ready pose "
          "straight over it, then the write",
          len(asked) == 1 and _title(asked[0]) == "Set NeedsRefresh"
          and pin_value(asked[0], "NeedsRefresh") == "true"
          and _after(BEL.find_then_pin(asked[0])) == writes,
          str([_title(n) for n in asked]))


def run():
    check_steady_gate()
    check_steady_write()
