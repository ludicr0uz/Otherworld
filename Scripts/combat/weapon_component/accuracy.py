"""Accuracy, once a frame: how wide the held gun's cloud is and how hard it
will kick, given the stance and the aim (the numbers are GUN_ACCURACY in
weapon_specs.py, copied onto each weapon as variables).

    AimSpread     = Held.SpreadDegrees x aim(Spread) x stance(Spread)
    RecoilScale   = aim(Recoil) x stance(Recoil)
    ReticleSpread = DegTan(AimSpread) / DegTan(CurrentFOV / 2)

    aim(X)    = SightAiming ? (Spread: 0 | Recoil: Held.RecoilSightsScale)
              : Aiming      ? Held.<X>ShoulderScale : 1
    stance(X) = Stance == PRONE ? Held.<X>ProneScale
              : Stance == CROUCH ? Held.<X>CrouchScale : 1

Stored rather than read inline where they are used, for two readers: the fire
block draws the shot's direction inside AimSpread and scales the kick by
RecoilScale, and the HUD draws the reticle's gap from ReticleSpread -- a
fraction of half the viewport's width, since UE's field of view is horizontal.
The reticle is therefore the cloud: what it encloses is where the shot can go.

Every read off Held is behind an IsValid Branch (the root CLAUDE.md's nested
Branch rule); with nothing held all three are zero. After ads.py (Aiming,
SightAiming, CurrentFOV) and stance.py (Stance) in the Tick, and before the
trigger.
"""

from combat.graph import BEL, _at, _connect, _node, _pin, _set
from combat.nodes import (
    FN_DEG_TAN, FN_DIV_FF, FN_EQ_II, FN_MUL_FF, FN_SELECT_FF,
)
from combat.weapon_component.common import _prop
from combat.weapon_component.stance import CROUCH, PRONE, STANCE_VAR

AIM_SPREAD_VAR = "AimSpread"
RECOIL_SCALE_VAR = "RecoilScale"
RETICLE_SPREAD_VAR = "ReticleSpread"
ACCURACY_OUT_VARS = (AIM_SPREAD_VAR, RECOIL_SCALE_VAR, RETICLE_SPREAD_VAR)


def _select(ed, keep, a, b, pick, x, y):
    """SelectFloat(pick ? a : b). A and B are pins or literals."""
    n = keep(_at(_node(ed, FN_SELECT_FF), x, y))
    for name, v in (("A", a), ("B", b)):
        if isinstance(v, float):
            _set(n, name, v)
        else:
            _connect(v, _pin(n, name))
    _connect(pick, _pin(n, "bPickA"))
    return _pin(n, "ReturnValue", is_input=False)


def _mul(ed, keep, a, b, x, y):
    n = keep(_at(_node(ed, FN_MUL_FF), x, y))
    _connect(a, _pin(n, "A"))
    _connect(b, _pin(n, "B"))
    return _pin(n, "ReturnValue", is_input=False)


def _factors(ed, keep, held, kind, sights, x, y):
    """aim(kind) x stance(kind), where kind is "Spread" or "Recoil" and
    `sights` is what down the sights gives (0.0, or a Held pin)."""
    stance = keep(_at(ed.add_get_member_variable_node(STANCE_VAR), x, y))
    stance_out = _pin(stance, STANCE_VAR, is_input=False)
    is_low = {}
    for value, dy in ((CROUCH, 0), (PRONE, 120)):
        eq = keep(_at(_node(ed, FN_EQ_II), x + 240, y + dy))
        _connect(stance_out, _pin(eq, "A"))
        _set(eq, "B", value)
        is_low[value] = _pin(eq, "ReturnValue", is_input=False)

    def held_scale(suffix, dy):
        pin, n = _prop(ed, f"{kind}{suffix}Scale", held, x + 240, y + dy)
        keep(n)
        return pin

    crouched = _select(ed, keep, held_scale("Crouch", 240), 1.0,
                       is_low[CROUCH], x + 500, y)
    stance_f = _select(ed, keep, held_scale("Prone", 360), crouched,
                       is_low[PRONE], x + 760, y)

    aiming = keep(_at(ed.add_get_member_variable_node("Aiming"), x, y + 480))
    sighting = keep(_at(ed.add_get_member_variable_node("SightAiming"), x, y + 600))
    shoulder = _select(ed, keep, held_scale("Shoulder", 480), 1.0,
                       _pin(aiming, "Aiming", is_input=False), x + 500, y + 480)
    aim_f = _select(ed, keep, sights, shoulder,
                    _pin(sighting, "SightAiming", is_input=False), x + 760, y + 480)
    return _mul(ed, keep, stance_f, aim_f, x + 1020, y + 240)


def _author_accuracy(ed, held, armed_out, exec_ins, x0, y0):
    """Write AimSpread, RecoilScale and ReticleSpread. Returns the exec pins
    to carry on from."""
    made = []

    def keep(n):
        made.append(n)
        return n

    gate = keep(_at(ed.add_branch_node(), x0, y0))
    _connect(armed_out, _pin(gate, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(gate, "execute"))

    hip, hip_n = _prop(ed, "SpreadDegrees", held, x0 + 1300, y0 + 300)
    keep(hip_n)
    spread = _mul(ed, keep, hip,
                  _factors(ed, keep, held, "Spread", 0.0, x0, y0 + 300),
                  x0 + 1560, y0 + 300)
    sights_kick, sights_n = _prop(ed, "RecoilSightsScale", held, x0 + 1300, y0 + 1100)
    keep(sights_n)
    kick = _factors(ed, keep, held, "Recoil", sights_kick, x0, y0 + 1100)

    put_spread = keep(_at(ed.add_set_member_variable_node(AIM_SPREAD_VAR),
                          x0 + 1820, y0))
    _connect(spread, _pin(put_spread, AIM_SPREAD_VAR))
    _connect(BEL.find_then_pin(gate), _pin(put_spread, "execute"))
    put_kick = keep(_at(ed.add_set_member_variable_node(RECOIL_SCALE_VAR),
                        x0 + 2080, y0))
    _connect(kick, _pin(put_kick, RECOIL_SCALE_VAR))
    _connect(BEL.find_then_pin(put_spread), _pin(put_kick, "execute"))

    # The reticle: the cloud's half-angle over the half field of view, both as
    # tangents, which is where a ray at that angle crosses the screen.
    cloud = keep(_at(ed.add_get_member_variable_node(AIM_SPREAD_VAR),
                     x0 + 1820, y0 + 1800))
    cloud_tan = keep(_at(_node(ed, FN_DEG_TAN), x0 + 2080, y0 + 1800))
    _connect(_pin(cloud, AIM_SPREAD_VAR, is_input=False), _pin(cloud_tan, "A"))
    fov = keep(_at(ed.add_get_member_variable_node("CurrentFOV"), x0 + 1820, y0 + 1940))
    half_fov = keep(_at(_node(ed, FN_MUL_FF), x0 + 2080, y0 + 1940))
    _connect(_pin(fov, "CurrentFOV", is_input=False), _pin(half_fov, "A"))
    _set(half_fov, "B", 0.5)
    fov_tan = keep(_at(_node(ed, FN_DEG_TAN), x0 + 2340, y0 + 1940))
    _connect(_pin(half_fov, "ReturnValue", is_input=False), _pin(fov_tan, "A"))
    ratio = keep(_at(_node(ed, FN_DIV_FF), x0 + 2600, y0 + 1800))
    _connect(_pin(cloud_tan, "ReturnValue", is_input=False), _pin(ratio, "A"))
    _connect(_pin(fov_tan, "ReturnValue", is_input=False), _pin(ratio, "B"))
    put_reticle = keep(_at(ed.add_set_member_variable_node(RETICLE_SPREAD_VAR),
                           x0 + 2340, y0))
    _connect(_pin(ratio, "ReturnValue", is_input=False),
             _pin(put_reticle, RETICLE_SPREAD_VAR))
    _connect(BEL.find_then_pin(put_kick), _pin(put_reticle, "execute"))

    # Empty hands: nothing to draw, nothing to kick.
    flow = BEL.find_else_pin(gate)
    for i, var in enumerate(ACCURACY_OUT_VARS):
        clear = keep(_at(ed.add_set_member_variable_node(var),
                         x0 + 1820 + i * 260, y0 - 300))
        _set(clear, var, 0.0)
        _connect(flow, _pin(clear, "execute"))
        flow = BEL.find_then_pin(clear)

    ed.add_comment_to_nodes(
        "Accuracy: AimSpread (the cloud the next shot is drawn in; zero down "
        "the sights), RecoilScale (what the kick is multiplied by) and "
        "ReticleSpread (the cloud as a fraction of the half screen, which the "
        "HUD draws). Each is the held gun's own number times its aim and "
        "stance factors (GUN_ACCURACY in weapon_specs.py).",
        made)
    return (BEL.find_then_pin(put_reticle), flow)
