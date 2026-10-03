"""Recoil: turning the view, the kick applied on each shot, and the
recovery back toward the aim the player was holding.
"""

from uebp.graph import _connect, _node, _pin, _set, else_, out, then
from combat.nodes import (
    FN_ABS, FN_ADD_FF, FN_BREAK_ROT, FN_GET_CONTROL_ROT, FN_GREATER_FF,
    FN_INTERP_FF, FN_MAKE_ROT, FN_MUL_FF, FN_RANDOM_FLOAT,
    FN_SET_CONTROL_ROT, FN_SUB_FF,
)
from combat.tuning import COMBAT
from combat.weapon_component.accuracy import RECOIL_SCALE_VAR
from combat.weapon_component.common import _prop


def _author_turn_view(ed, pc_out, pitch_delta, yaw_delta, exec_in):
    """Add a pitch and a yaw to the player's own control rotation.

    SetControlRotation, never AddPitchInput / AddControllerPitchInput. Those
    accumulate into RotationInput, which APlayerController then multiplies by
    its deprecated InputPitchScale -- and that is precisely the handle the
    mouse-sensitivity setting drives every frame (see _author_ads). Recoil fed
    through it would be a fifth of its size for a player on 0.2 and three times
    its size for a player on 3.0, which is a weapon whose kick depends on a
    menu slider.

    Nothing clamps the result here and nothing needs to: the controller's own
    UpdateRotation runs LimitViewPitch against ViewPitchMin/Max on the very
    next frame, so a kick taken while already looking near-vertical is pulled
    back under the limit rather than tipping the camera over the top.

    Roll is carried through from the rotation that was read rather than written
    as zero. Nothing rolls the view in this project today, and a literal 0 here
    would be this function deciding that for whatever does later.

    Returns (the exec pin to carry on from, the nodes it made).
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    now = keep(_node(ed, FN_GET_CONTROL_ROT))
    _connect(pc_out, _pin(now, "self"))
    brk = keep(_node(ed, FN_BREAK_ROT))
    _connect(out(now), _pin(brk, "InRot"))

    lifted = keep(_node(ed, FN_ADD_FF))
    _connect(out(brk, "Pitch"), _pin(lifted, "A"))
    _connect(pitch_delta, _pin(lifted, "B"))
    swung = keep(_node(ed, FN_ADD_FF))
    _connect(out(brk, "Yaw"), _pin(swung, "A"))
    _connect(yaw_delta, _pin(swung, "B"))

    aimed = keep(_node(ed, FN_MAKE_ROT))
    _connect(out(brk, "Roll"), _pin(aimed, "Roll"))
    _connect(out(lifted), _pin(aimed, "Pitch"))
    _connect(out(swung), _pin(aimed, "Yaw"))

    turn = keep(_node(ed, FN_SET_CONTROL_ROT))
    _connect(pc_out, _pin(turn, "self"))
    _connect(out(aimed), _pin(turn, "NewRotation"))
    _connect(exec_in, _pin(turn, "execute"))
    return then(turn), made


def _author_recoil_kick(ed, held, pc_out, exec_in):
    """One shot's jolt: up by the weapon's own RecoilPitch, and a little sideways.

        kick     = Held.RecoilPitch * RecoilScale
        sideways = random in +/- Held.RecoilYaw * RecoilScale
        RecoilDebt    += kick
        RecoilYawDebt += sideways
        control rotation += (kick, sideways)

    Both halves are charged to the accumulators *and* applied to the view. The
    debts are what _author_recoil_recovery then pays back down; without them a
    kick would be permanent, and with them and no view write it would be
    invisible.

    RandomFloatInRange is a PURE node, so every pin that reads it draws its own
    number. The draw is therefore made once, into RecoilYawKick, and read from
    there twice -- inline it in both places and the view would swing one way
    while the accumulator was charged another, so the recovery would never
    cancel the kick it was paying for. That is the same "a pure node is pulled
    by whoever reads it" trap ReloadTake exists for.

    Reading RecoilPitch off Held is safe here and only here: this runs behind
    both fire gates, where Held has already been checked valid.

    Returns the exec pin to carry on from.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    per_shot, per_shot_n = _prop(ed, "RecoilPitch", held)
    keep(per_shot_n)
    # How much of it this frame's stance and aim let through: RecoilScale,
    # written by accuracy.py from the gun's own factors.
    scale = keep(ed.add_get_member_variable_node(RECOIL_SCALE_VAR))
    scale_out = out(scale, RECOIL_SCALE_VAR)
    up = keep(_node(ed, FN_MUL_FF))
    _connect(per_shot, _pin(up, "A"))
    _connect(scale_out, _pin(up, "B"))
    up_out = out(up)

    swing, swing_n = _prop(ed, "RecoilYaw", held)
    keep(swing_n)
    span = keep(_node(ed, FN_MUL_FF))
    _connect(swing, _pin(span, "A"))
    _connect(scale_out, _pin(span, "B"))
    span_out = out(span)
    mirrored = keep(_node(ed, FN_MUL_FF))
    _connect(span_out, _pin(mirrored, "A"))
    _set(mirrored, "B", -1.0)
    draw = keep(_node(ed, FN_RANDOM_FLOAT))
    _connect(out(mirrored), _pin(draw, "Min"))
    _connect(span_out, _pin(draw, "Max"))
    hold = keep(ed.add_set_member_variable_node("RecoilYawKick"))
    _connect(out(draw), _pin(hold, "RecoilYawKick"))
    _connect(exec_in, _pin(hold, "execute"))

    owed = keep(ed.add_get_member_variable_node("RecoilDebt"))
    charge = keep(_node(ed, FN_ADD_FF))
    _connect(out(owed, "RecoilDebt"), _pin(charge, "A"))
    _connect(up_out, _pin(charge, "B"))
    bill = keep(ed.add_set_member_variable_node("RecoilDebt"))
    _connect(out(charge), _pin(bill, "RecoilDebt"))
    _connect(then(hold), _pin(bill, "execute"))

    drawn = keep(ed.add_get_member_variable_node("RecoilYawKick"))
    drawn_out = out(drawn, "RecoilYawKick")
    owed_yaw = keep(ed.add_get_member_variable_node("RecoilYawDebt"))
    charge_yaw = keep(_node(ed, FN_ADD_FF))
    _connect(out(owed_yaw, "RecoilYawDebt"), _pin(charge_yaw, "A"))
    _connect(drawn_out, _pin(charge_yaw, "B"))
    bill_yaw = keep(ed.add_set_member_variable_node("RecoilYawDebt"))
    _connect(out(charge_yaw), _pin(bill_yaw, "RecoilYawDebt"))
    _connect(then(bill), _pin(bill_yaw, "execute"))

    turned, turn_nodes = _author_turn_view(ed, pc_out, up_out, drawn_out, then(bill_yaw))
    made.extend(turn_nodes)

    ed.add_comment_to_nodes(
        "Recoil, on the shot the gate just allowed: this weapon's own "
        "RecoilPitch up and a random +/- RecoilYaw sideways, both times "
        "RecoilScale (its stance and aim factors, accuracy.py), "
        "charged to RecoilDebt and applied to the control rotation. The "
        "pellets below fly down the AimPoint resolved at the top of this "
        "frame, so a shot never bends itself -- it is the next one that pays.",
        made)
    return turned


def _author_recoil_recovery(ed, tick, pc_out, exec_in):
    """Give most of the kick back, every frame, until the debt is settled.

        RecoilDebt    -> FInterpTo(debt, 0, dt, recoil_recovery_speed)
        the view moves by (that step - the debt) * recoil_recovery_fraction

    Two things about that shape are the whole feel of it.

    The debt always reaches zero, so nothing accumulates across a magazine --
    but only recoil_recovery_fraction of each step is handed back to the view,
    so a fraction of every kick stays in the player's aim. A burst therefore
    walks up its target and has to be pulled back down by hand, which is what
    separates a gun from a screen shake.

    And the view is turned BEFORE the debts are written, not after. Every
    number here is pure and is pulled by whoever reads it, so a give-back
    computed from Get RecoilDebt after the Set would read the value it had just
    been reduced to and come out as zero -- the graph would look right and the
    view would never move.

    Skipped entirely while both debts are settled, so this does not write the
    player's control rotation sixty times a second to no effect.

    Returns the exec pins to carry on from.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    owed = keep(ed.add_get_member_variable_node("RecoilDebt"))
    owed_out = out(owed, "RecoilDebt")
    owed_yaw = keep(ed.add_get_member_variable_node("RecoilYawDebt"))
    owed_yaw_out = out(owed_yaw, "RecoilYawDebt")

    size = keep(_node(ed, FN_ABS))
    _connect(owed_out, _pin(size, "A"))
    size_yaw = keep(_node(ed, FN_ABS))
    _connect(owed_yaw_out, _pin(size_yaw, "A"))
    total = keep(_node(ed, FN_ADD_FF))
    _connect(out(size), _pin(total, "A"))
    _connect(out(size_yaw), _pin(total, "B"))
    # FInterpTo snaps to its target once the remaining distance is negligible,
    # so the debt reaches exactly zero and this gate really does close.
    owing = keep(_node(ed, FN_GREATER_FF))
    _connect(out(total), _pin(owing, "A"))
    _set(owing, "B", 0.001)
    gate = keep(ed.add_branch_node())
    _connect(out(owing), _pin(gate, "Condition"))
    _connect(exec_in, _pin(gate, "execute"))

    deltas = []
    for var, current in (("RecoilDebt", owed_out), ("RecoilYawDebt", owed_yaw_out)):
        step = keep(_node(ed, FN_INTERP_FF))
        _connect(current, _pin(step, "Current"))
        _set(step, "Target", 0.0)
        _connect(out(tick, "DeltaSeconds"), _pin(step, "DeltaTime"))
        _set(step, "InterpSpeed", COMBAT.recoil_recovery_speed)
        paid = keep(_node(ed, FN_SUB_FF))
        _connect(out(step), _pin(paid, "A"))
        _connect(current, _pin(paid, "B"))
        given = keep(_node(ed, FN_MUL_FF))
        _connect(out(paid), _pin(given, "A"))
        _set(given, "B", COMBAT.recoil_recovery_fraction)
        deltas.append((step, out(given)))

    turned, turn_nodes = _author_turn_view(ed, pc_out, deltas[0][1], deltas[1][1], then(gate))
    made.extend(turn_nodes)

    flow = turned
    for (step, _delta), var in zip(deltas, ("RecoilDebt", "RecoilYawDebt")):
        settle = keep(ed.add_set_member_variable_node(var))
        _connect(out(step), _pin(settle, var))
        _connect(flow, _pin(settle, "execute"))
        flow = then(settle)

    ed.add_comment_to_nodes(
        f"Recoil recovery: both debts FInterpTo zero at "
        f"{COMBAT.recoil_recovery_speed:g}, and "
        f"{COMBAT.recoil_recovery_fraction * 100:.0f}% of each frame's step is "
        f"handed back to the view -- so the accumulator always settles but "
        f"{(1.0 - COMBAT.recoil_recovery_fraction) * 100:.0f}% of every kick "
        f"stays in the player's aim, which is what makes a burst climb. The "
        f"view is turned before the debts are written, because both give-backs "
        f"are pure and would read the already-reduced value otherwise.",
        made)
    return (flow, else_(gate))
