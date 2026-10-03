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

from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from combat.nodes import (
    FN_DEG_TAN, FN_DIV_FF, FN_EQ_II, FN_MUL_FF, FN_SELECT_FF,
)
from combat.weapon_component.common import _prop
from combat.weapon_component.stance import CROUCH, PRONE, STANCE_VAR

AIM_SPREAD_VAR = "AimSpread"
RECOIL_SCALE_VAR = "RecoilScale"
RETICLE_SPREAD_VAR = "ReticleSpread"
ACCURACY_OUT_VARS = (AIM_SPREAD_VAR, RECOIL_SCALE_VAR, RETICLE_SPREAD_VAR)


def _select(ed, keep, a, b, pick):
    """SelectFloat(pick ? a : b). A and B are pins or literals."""
    n = keep(_node(ed, FN_SELECT_FF))
    for name, v in (("A", a), ("B", b)):
        if isinstance(v, float):
            _set(n, name, v)
        else:
            _connect(v, _pin(n, name))
    _connect(pick, _pin(n, "bPickA"))
    return out(n)


def _mul(ed, keep, a, b):
    n = keep(_node(ed, FN_MUL_FF))
    _connect(a, _pin(n, "A"))
    _connect(b, _pin(n, "B"))
    return out(n)


def _factors(ed, keep, held, kind, sights):
    """aim(kind) x stance(kind), where kind is "Spread" or "Recoil" and
    `sights` is what down the sights gives (0.0, or a Held pin)."""
    stance = keep(ed.add_get_member_variable_node(STANCE_VAR))
    stance_out = out(stance, STANCE_VAR)
    is_low = {}
    for value in (CROUCH, PRONE):
        eq = keep(_node(ed, FN_EQ_II))
        _connect(stance_out, _pin(eq, "A"))
        _set(eq, "B", value)
        is_low[value] = out(eq)

    def held_scale(suffix):
        pin, n = _prop(ed, f"{kind}{suffix}Scale", held)
        keep(n)
        return pin

    crouched = _select(ed, keep, held_scale("Crouch"), 1.0, is_low[CROUCH])
    stance_f = _select(ed, keep, held_scale("Prone"), crouched, is_low[PRONE])

    aiming = keep(ed.add_get_member_variable_node("Aiming"))
    sighting = keep(ed.add_get_member_variable_node("SightAiming"))
    shoulder = _select(ed, keep, held_scale("Shoulder"), 1.0, out(aiming, "Aiming"))
    aim_f = _select(ed, keep, sights, shoulder, out(sighting, "SightAiming"))
    return _mul(ed, keep, stance_f, aim_f)


def _author_accuracy(ed, held, armed_out, exec_ins):
    """Write AimSpread, RecoilScale and ReticleSpread. Returns the exec pins
    to carry on from."""
    made = []

    def keep(n):
        made.append(n)
        return n

    gate = keep(ed.add_branch_node())
    _connect(armed_out, _pin(gate, "Condition"))
    for e in exec_ins:
        _connect(e, _pin(gate, "execute"))

    hip, hip_n = _prop(ed, "SpreadDegrees", held)
    keep(hip_n)
    spread = _mul(ed, keep, hip, _factors(ed, keep, held, "Spread", 0.0))
    sights_kick, sights_n = _prop(ed, "RecoilSightsScale", held)
    keep(sights_n)
    kick = _factors(ed, keep, held, "Recoil", sights_kick)

    put_spread = keep(ed.add_set_member_variable_node(AIM_SPREAD_VAR))
    _connect(spread, _pin(put_spread, AIM_SPREAD_VAR))
    _connect(then(gate), _pin(put_spread, "execute"))
    put_kick = keep(ed.add_set_member_variable_node(RECOIL_SCALE_VAR))
    _connect(kick, _pin(put_kick, RECOIL_SCALE_VAR))
    _connect(then(put_spread), _pin(put_kick, "execute"))

    # The reticle: the cloud's half-angle over the half field of view, both as
    # tangents, which is where a ray at that angle crosses the screen.
    cloud = keep(ed.add_get_member_variable_node(AIM_SPREAD_VAR))
    cloud_tan = keep(_node(ed, FN_DEG_TAN))
    _connect(out(cloud, AIM_SPREAD_VAR), _pin(cloud_tan, "A"))
    fov = keep(ed.add_get_member_variable_node("CurrentFOV"))
    half_fov = keep(_node(ed, FN_MUL_FF))
    _connect(out(fov, "CurrentFOV"), _pin(half_fov, "A"))
    _set(half_fov, "B", 0.5)
    fov_tan = keep(_node(ed, FN_DEG_TAN))
    _connect(out(half_fov), _pin(fov_tan, "A"))
    ratio = keep(_node(ed, FN_DIV_FF))
    _connect(out(cloud_tan), _pin(ratio, "A"))
    _connect(out(fov_tan), _pin(ratio, "B"))
    put_reticle = keep(ed.add_set_member_variable_node(RETICLE_SPREAD_VAR))
    _connect(out(ratio), _pin(put_reticle, RETICLE_SPREAD_VAR))
    _connect(then(put_kick), _pin(put_reticle, "execute"))

    # Empty hands: nothing to draw, nothing to kick.
    flow = else_(gate)
    for var in ACCURACY_OUT_VARS:
        clear = keep(ed.add_set_member_variable_node(var))
        _set(clear, var, 0.0)
        _connect(flow, _pin(clear, "execute"))
        flow = then(clear)

    ed.add_comment_to_nodes(
        "Accuracy: AimSpread (the cloud the next shot is drawn in; zero down "
        "the sights), RecoilScale (what the kick is multiplied by) and "
        "ReticleSpread (the cloud as a fraction of the half screen, which the "
        "HUD draws). Each is the held gun's own number times its aim and "
        "stance factors (GUN_ACCURACY in weapon_specs.py).",
        made)
    return (then(put_reticle), flow)
