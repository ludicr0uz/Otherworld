"""Down the sights the aim sways: the view drifts slowly round the point the
mouse left it on, and the gun, its sights and the shot drift with it.

    SwayTime += dt x SwayRate                       (the held gun's: breath.py)
    k         = SightBlend x (prone ? SWAY_PRONE_SCALE : crouched ? SWAY_CROUCH_SCALE : 1)
                x BreathScale                       (holding the breath: breath.py)
    yaw       = SWAY_YAW_DEG   x k x Sin(SwayTime x 2pi / SWAY_YAW_PERIOD_S)
    pitch     = SWAY_PITCH_DEG x k x Sin(SwayTime x 2pi / SWAY_PITCH_PERIOD_S)
    if |yaw - SwayYaw| > SWAY_MIN_STEP_DEG or |pitch - SwayPitch| > SWAY_MIN_STEP_DEG:
        turn the view by (pitch - SwayPitch, yaw - SwayYaw)
        SwayYaw, SwayPitch = yaw, pitch

Why the VIEW sways and not the gun inside it: the camera looks down the gun's
own sight line (sights.py) and the shot goes to the middle of the view, so a
view that drifts takes the sights and the point of impact with it and the two
cannot come apart. A gun swaying under a still camera would point its sights
somewhere the shot does not go.

Why the change is applied and not the offset: the control rotation is also the
mouse's and the recoil's. Turning it by this frame's change leaves both
working on top, and SwayYaw/SwayPitch remember what has been added, so easing
SightBlend back to 0 gives exactly that much back.

Scaled by SightBlend, so it eases in and out with the camera's travel and is
nothing at the hip or on the shoulder. The view is turned BEFORE the two
offsets are stored: the steps read the old ones. No read off Held.

Why the threshold: SetControlRotation ignores a change under 0.001 degrees,
and a frame's step is smaller than that at a high frame rate (and always near
a sine's peak). SwayYaw/SwayPitch are what has really been applied, so a step
too small to take is left to grow until it is taken whole; stored regardless,
the view drifted off by the dropped steps (0.13 degrees in one probe run).
"""

from combat.graph import BEL, _connect, _node, _pin, _set
from combat.nodes import (
    FN_ABS, FN_ADD_FF, FN_EQ_II, FN_GREATER_FF, FN_MUL_FF, FN_OR, FN_SIN,
    FN_SUB_FF,
)
from combat.breath_tuning import BREATH_SCALE_VAR
from combat.sway_tuning import (
    SWAY_CROUCH_SCALE, SWAY_MIN_STEP_DEG, SWAY_PITCH_DEG, SWAY_PITCH_PERIOD_S, SWAY_PITCH_VAR,
    SWAY_PRONE_SCALE, SWAY_RATE_VAR, SWAY_TIME_VAR, SWAY_YAW_DEG, SWAY_YAW_PERIOD_S,
    SWAY_YAW_VAR, sway_rate,
)
from combat.weapon_component.accuracy import _mul, _select
from combat.weapon_component.recoil import _author_turn_view
from combat.weapon_component.stance import CROUCH, PRONE, STANCE_VAR


def _author_sight_sway(ed, tick, pc_out, exec_ins):
    """Turn the view by the change in the sway since it was last turned.
    Returns the exec pins to carry on from."""
    made = []

    def keep(n):
        made.append(n)
        return n

    def out(n, name="ReturnValue"):
        return _pin(n, name, is_input=False)

    # The clock, at the held gun's rate.
    was = keep(ed.add_get_member_variable_node(SWAY_TIME_VAR))
    rate = keep(ed.add_get_member_variable_node(SWAY_RATE_VAR))
    paced = _mul(ed, keep, out(tick, "DeltaSeconds"), out(rate, SWAY_RATE_VAR))
    later = keep(_node(ed, FN_ADD_FF))
    _connect(out(was, SWAY_TIME_VAR), _pin(later, "A"))
    _connect(paced, _pin(later, "B"))
    clock = keep(ed.add_set_member_variable_node(SWAY_TIME_VAR))
    _connect(out(later), _pin(clock, SWAY_TIME_VAR))
    for e in exec_ins:
        _connect(e, _pin(clock, "execute"))

    # How much of it: the camera's travel times the stance.
    stance = keep(ed.add_get_member_variable_node(STANCE_VAR))
    is_low = {}
    for value in (CROUCH, PRONE):
        eq = keep(_node(ed, FN_EQ_II))
        _connect(out(stance, STANCE_VAR), _pin(eq, "A"))
        _set(eq, "B", value)
        is_low[value] = out(eq)
    crouched = _select(ed, keep, SWAY_CROUCH_SCALE, 1.0, is_low[CROUCH])
    steadied = _select(ed, keep, SWAY_PRONE_SCALE, crouched, is_low[PRONE])
    blend = keep(ed.add_get_member_variable_node("SightBlend"))
    sighted = _mul(ed, keep, out(blend, "SightBlend"), steadied)
    breath = keep(ed.add_get_member_variable_node(BREATH_SCALE_VAR))
    amount = _mul(ed, keep, sighted, out(breath, BREATH_SCALE_VAR))

    def wave(var, degrees, period):
        """(the sway now, its change since last frame, the node storing it)."""
        t = keep(ed.add_get_member_variable_node(SWAY_TIME_VAR))
        phase = keep(_node(ed, FN_MUL_FF))
        _connect(out(t, SWAY_TIME_VAR), _pin(phase, "A"))
        _set(phase, "B", sway_rate(period))
        sine = keep(_node(ed, FN_SIN))
        _connect(out(phase), _pin(sine, "A"))
        sized = keep(_node(ed, FN_MUL_FF))
        _connect(out(sine), _pin(sized, "A"))
        _set(sized, "B", degrees)
        now = _mul(ed, keep, out(sized), amount)
        had = keep(ed.add_get_member_variable_node(var))
        step = keep(_node(ed, FN_SUB_FF))
        _connect(now, _pin(step, "A"))
        _connect(out(had, var), _pin(step, "B"))
        store = keep(ed.add_set_member_variable_node(var))
        _connect(now, _pin(store, var))
        return out(step), store

    yaw_step, put_yaw = wave(SWAY_YAW_VAR, SWAY_YAW_DEG, SWAY_YAW_PERIOD_S)
    pitch_step, put_pitch = wave(SWAY_PITCH_VAR, SWAY_PITCH_DEG, SWAY_PITCH_PERIOD_S)

    # Worth taking? (Either axis: the controller compares the whole rotation.)
    def far(step):
        size = keep(_node(ed, FN_ABS))
        _connect(step, _pin(size, "A"))
        over = keep(_node(ed, FN_GREATER_FF))
        _connect(out(size), _pin(over, "A"))
        _set(over, "B", SWAY_MIN_STEP_DEG)
        return out(over)

    either = keep(_node(ed, FN_OR))
    _connect(far(yaw_step), _pin(either, "A"))
    _connect(far(pitch_step), _pin(either, "B"))
    gate = keep(ed.add_branch_node())
    _connect(out(either), _pin(gate, "Condition"))
    _connect(BEL.find_then_pin(clock), _pin(gate, "execute"))

    turned, turn_nodes = _author_turn_view(
        ed, pc_out, pitch_step, yaw_step, BEL.find_then_pin(gate))
    made.extend(turn_nodes)
    put_yaw
    _connect(turned, _pin(put_yaw, "execute"))
    put_pitch
    _connect(BEL.find_then_pin(put_yaw), _pin(put_pitch, "execute"))

    ed.add_comment_to_nodes(
        "Sight sway: down the sights the view drifts on two slow sines "
        f"({SWAY_YAW_DEG:g} deg every {SWAY_YAW_PERIOD_S:g} s sideways, "
        f"{SWAY_PITCH_DEG:g} deg every {SWAY_PITCH_PERIOD_S:g} s up and down, "
        "the clock run at the gun's SwayRate), "
        f"times SightBlend, the stance (crouched {SWAY_CROUCH_SCALE:g}, "
        f"prone {SWAY_PRONE_SCALE:g}) and BreathScale (breath.py). The control rotation is turned by the "
        "change since it was last turned, BEFORE the offsets are stored, so "
        "the mouse and the recoil work on top and letting go gives it back; "
        f"a change under {SWAY_MIN_STEP_DEG:g} deg waits (the controller "
        "would drop it). The gun, "
        "its sights and the shot all follow the view, so they stay together.",
        made)
    return (BEL.find_then_pin(put_pitch), BEL.find_else_pin(gate))
