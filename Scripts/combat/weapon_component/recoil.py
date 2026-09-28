"""Recoil: turning the view, the kick applied on each shot, and the
recovery back toward the aim the player was holding.
"""

from combat.graph import BEL, _at, _connect, _node, _pin, _set
from combat.nodes import (
    FN_ABS, FN_ADD_FF, FN_BREAK_ROT, FN_GET_CONTROL_ROT, FN_GREATER_FF,
    FN_INTERP_FF, FN_MAKE_ROT, FN_MUL_FF, FN_RANDOM_FLOAT, FN_SELECT_FF,
    FN_SET_CONTROL_ROT, FN_SUB_FF,
)
from combat.tuning import COMBAT
from combat.weapon_component.common import _prop


def _author_turn_view(ed, pc_out, pitch_delta, yaw_delta, exec_in, x0, y0):
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

    now = keep(_at(_node(ed, FN_GET_CONTROL_ROT), x0, y0 + 240))
    _connect(pc_out, _pin(now, "self"))
    brk = keep(_at(_node(ed, FN_BREAK_ROT), x0 + 240, y0 + 240))
    _connect(_pin(now, "ReturnValue", is_input=False), _pin(brk, "InRot"))

    lifted = keep(_at(_node(ed, FN_ADD_FF), x0 + 500, y0 + 240))
    _connect(_pin(brk, "Pitch", is_input=False), _pin(lifted, "A"))
    _connect(pitch_delta, _pin(lifted, "B"))
    swung = keep(_at(_node(ed, FN_ADD_FF), x0 + 500, y0 + 400))
    _connect(_pin(brk, "Yaw", is_input=False), _pin(swung, "A"))
    _connect(yaw_delta, _pin(swung, "B"))

    aimed = keep(_at(_node(ed, FN_MAKE_ROT), x0 + 760, y0 + 240))
    _connect(_pin(brk, "Roll", is_input=False), _pin(aimed, "Roll"))
    _connect(_pin(lifted, "ReturnValue", is_input=False), _pin(aimed, "Pitch"))
    _connect(_pin(swung, "ReturnValue", is_input=False), _pin(aimed, "Yaw"))

    turn = keep(_at(_node(ed, FN_SET_CONTROL_ROT), x0 + 1020, y0))
    _connect(pc_out, _pin(turn, "self"))
    _connect(_pin(aimed, "ReturnValue", is_input=False), _pin(turn, "NewRotation"))
    _connect(exec_in, _pin(turn, "execute"))
    return BEL.find_then_pin(turn), made


def _author_recoil_kick(ed, held, pc_out, exec_in, x0, y0):
    """One shot's jolt: up by the weapon's own RecoilPitch, and a little sideways.

        kick     = Held.RecoilPitch * (Aiming ? recoil_ads_scale : 1)
        sideways = random in +/- kick * recoil_horizontal_ratio
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

    per_shot, per_shot_n = _prop(ed, "RecoilPitch", held, x0, y0 + 320)
    keep(per_shot_n)
    # Down the sights the weapon is shouldered and kicks less. SelectFloat and
    # not a Branch, the same shape _author_fire picks the cone width with, so
    # the aimed and unaimed cases are one expression that cannot drift.
    aiming = keep(_at(ed.add_get_member_variable_node("Aiming"), x0, y0 + 460))
    steadied = keep(_at(_node(ed, FN_SELECT_FF), x0 + 260, y0 + 460))
    _set(steadied, "A", COMBAT.recoil_ads_scale)
    _set(steadied, "B", 1.0)
    _connect(_pin(aiming, "Aiming", is_input=False), _pin(steadied, "bPickA"))
    up = keep(_at(_node(ed, FN_MUL_FF), x0 + 520, y0 + 320))
    _connect(per_shot, _pin(up, "A"))
    _connect(_pin(steadied, "ReturnValue", is_input=False), _pin(up, "B"))
    up_out = _pin(up, "ReturnValue", is_input=False)

    span = keep(_at(_node(ed, FN_MUL_FF), x0 + 780, y0 + 620))
    _connect(up_out, _pin(span, "A"))
    _set(span, "B", COMBAT.recoil_horizontal_ratio)
    span_out = _pin(span, "ReturnValue", is_input=False)
    mirrored = keep(_at(_node(ed, FN_MUL_FF), x0 + 1040, y0 + 760))
    _connect(span_out, _pin(mirrored, "A"))
    _set(mirrored, "B", -1.0)
    draw = keep(_at(_node(ed, FN_RANDOM_FLOAT), x0 + 1300, y0 + 620))
    _connect(_pin(mirrored, "ReturnValue", is_input=False), _pin(draw, "Min"))
    _connect(span_out, _pin(draw, "Max"))
    hold = keep(_at(ed.add_set_member_variable_node("RecoilYawKick"), x0 + 1560, y0))
    _connect(_pin(draw, "ReturnValue", is_input=False), _pin(hold, "RecoilYawKick"))
    _connect(exec_in, _pin(hold, "execute"))

    owed = keep(_at(ed.add_get_member_variable_node("RecoilDebt"), x0 + 1820, y0 + 320))
    charge = keep(_at(_node(ed, FN_ADD_FF), x0 + 2080, y0 + 320))
    _connect(_pin(owed, "RecoilDebt", is_input=False), _pin(charge, "A"))
    _connect(up_out, _pin(charge, "B"))
    bill = keep(_at(ed.add_set_member_variable_node("RecoilDebt"), x0 + 2340, y0))
    _connect(_pin(charge, "ReturnValue", is_input=False), _pin(bill, "RecoilDebt"))
    _connect(BEL.find_then_pin(hold), _pin(bill, "execute"))

    drawn = keep(_at(ed.add_get_member_variable_node("RecoilYawKick"),
                     x0 + 1820, y0 + 620))
    drawn_out = _pin(drawn, "RecoilYawKick", is_input=False)
    owed_yaw = keep(_at(ed.add_get_member_variable_node("RecoilYawDebt"),
                        x0 + 1820, y0 + 480))
    charge_yaw = keep(_at(_node(ed, FN_ADD_FF), x0 + 2080, y0 + 480))
    _connect(_pin(owed_yaw, "RecoilYawDebt", is_input=False), _pin(charge_yaw, "A"))
    _connect(drawn_out, _pin(charge_yaw, "B"))
    bill_yaw = keep(_at(ed.add_set_member_variable_node("RecoilYawDebt"),
                        x0 + 2600, y0))
    _connect(_pin(charge_yaw, "ReturnValue", is_input=False),
             _pin(bill_yaw, "RecoilYawDebt"))
    _connect(BEL.find_then_pin(bill), _pin(bill_yaw, "execute"))

    turned, turn_nodes = _author_turn_view(
        ed, pc_out, up_out, drawn_out, BEL.find_then_pin(bill_yaw),
        x0 + 2860, y0)
    made.extend(turn_nodes)

    ed.add_comment_to_nodes(
        f"Recoil, on the shot the gate just allowed: this weapon's own "
        f"RecoilPitch up ({COMBAT.recoil_ads_scale:g}x of it while aiming) and "
        f"a random +/-{COMBAT.recoil_horizontal_ratio:g} of that sideways, "
        f"charged to RecoilDebt and applied to the control rotation. The "
        f"pellets below fly down the AimPoint resolved at the top of this "
        f"frame, so a shot never bends itself -- it is the next one that pays.",
        made)
    return turned


def _author_recoil_recovery(ed, tick, pc_out, exec_in, x0, y0):
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

    owed = keep(_at(ed.add_get_member_variable_node("RecoilDebt"), x0, y0 + 300))
    owed_out = _pin(owed, "RecoilDebt", is_input=False)
    owed_yaw = keep(_at(ed.add_get_member_variable_node("RecoilYawDebt"),
                        x0, y0 + 440))
    owed_yaw_out = _pin(owed_yaw, "RecoilYawDebt", is_input=False)

    size = keep(_at(_node(ed, FN_ABS), x0 + 260, y0 + 300))
    _connect(owed_out, _pin(size, "A"))
    size_yaw = keep(_at(_node(ed, FN_ABS), x0 + 260, y0 + 440))
    _connect(owed_yaw_out, _pin(size_yaw, "A"))
    total = keep(_at(_node(ed, FN_ADD_FF), x0 + 520, y0 + 360))
    _connect(_pin(size, "ReturnValue", is_input=False), _pin(total, "A"))
    _connect(_pin(size_yaw, "ReturnValue", is_input=False), _pin(total, "B"))
    # FInterpTo snaps to its target once the remaining distance is negligible,
    # so the debt reaches exactly zero and this gate really does close.
    owing = keep(_at(_node(ed, FN_GREATER_FF), x0 + 780, y0 + 360))
    _connect(_pin(total, "ReturnValue", is_input=False), _pin(owing, "A"))
    _set(owing, "B", 0.001)
    gate = keep(_at(ed.add_branch_node(), x0 + 1040, y0))
    _connect(_pin(owing, "ReturnValue", is_input=False), _pin(gate, "Condition"))
    _connect(exec_in, _pin(gate, "execute"))

    deltas = []
    for i, (var, current) in enumerate((("RecoilDebt", owed_out),
                                        ("RecoilYawDebt", owed_yaw_out))):
        step = keep(_at(_node(ed, FN_INTERP_FF), x0 + 1300, y0 + 300 + i * 300))
        _connect(current, _pin(step, "Current"))
        _set(step, "Target", 0.0)
        _connect(_pin(tick, "DeltaSeconds", is_input=False), _pin(step, "DeltaTime"))
        _set(step, "InterpSpeed", COMBAT.recoil_recovery_speed)
        paid = keep(_at(_node(ed, FN_SUB_FF), x0 + 1560, y0 + 300 + i * 300))
        _connect(_pin(step, "ReturnValue", is_input=False), _pin(paid, "A"))
        _connect(current, _pin(paid, "B"))
        given = keep(_at(_node(ed, FN_MUL_FF), x0 + 1820, y0 + 300 + i * 300))
        _connect(_pin(paid, "ReturnValue", is_input=False), _pin(given, "A"))
        _set(given, "B", COMBAT.recoil_recovery_fraction)
        deltas.append((step, _pin(given, "ReturnValue", is_input=False)))

    turned, turn_nodes = _author_turn_view(
        ed, pc_out, deltas[0][1], deltas[1][1], BEL.find_then_pin(gate),
        x0 + 2080, y0)
    made.extend(turn_nodes)

    flow = turned
    for i, ((step, _delta), var) in enumerate(zip(deltas,
                                                  ("RecoilDebt", "RecoilYawDebt"))):
        settle = keep(_at(ed.add_set_member_variable_node(var),
                          x0 + 3400 + i * 260, y0))
        _connect(_pin(step, "ReturnValue", is_input=False), _pin(settle, var))
        _connect(flow, _pin(settle, "execute"))
        flow = BEL.find_then_pin(settle)

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
    return (flow, BEL.find_else_pin(gate))
