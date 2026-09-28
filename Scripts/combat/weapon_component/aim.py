"""Aim: resolving the aim point every frame (camera trace, then muzzle trace)
and aiming down the sights (zoom, FOV, sensitivity, ready pose).
"""

from combat.camera import AIM_TRACE_RANGE, BLOCKED_SLACK
from combat.graph import (
    BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set, _vec,
)
from combat.nodes import (
    CAMERA_CLASS_PATH, FN_ADD_VV, FN_AND, FN_CAM_LOC, FN_CAM_ROT, FN_CLAMP,
    FN_DISTANCE, FN_DIV_FF, FN_FORWARD, FN_GET_CAM, FN_GET_COMP,
    FN_GREATER_FF, FN_INTERP_FF, FN_IS_KEY_DOWN, FN_IS_VALID, FN_LERP,
    FN_MUL_FF, FN_MUL_VF, FN_NOT_B, FN_SET_FOV, FN_SET_PITCH_SCALE,
    FN_SET_YAW_SCALE, FN_SUB_FF, FN_TRACE, MOVEMENT_CLASS_PATH,
    NODE_BREAK_HIT,
)
from combat.tuning import AIM_KEY, COMBAT
from combat.weapon_component.common import (
    _muzzle_location, _prop, _trace_defaults,
)


def _author_resolve_aim(ed, held, exec_ins, x0, y0):
    """Work out where this frame's shot lands. The hybrid of the two obvious wrongs.

    Aiming purely from the muzzle is honest and unplayable: the barrel sits below
    and to the side of the camera, so the shot lands a little off wherever the
    crosshair is, and a player standing beside a wall shoots the wall while their
    crosshair is on an enemy in the open. Aiming purely from the camera is
    playable and looks broken: the camera is on a boom behind the shoulder, so
    the pellets visibly fan out from behind the player -- which is exactly what
    was reported here.

    So: the camera decides *what* is being aimed at, and the muzzle decides
    whether the gun can actually reach it.

      1. Trace from the camera along its forward vector. Whatever it hits is the
         aim point; if it hits nothing, the aim point is a point a kilometre out,
         which is the standard stand-in for "the sky".
      2. Trace from the muzzle to that aim point. If something stops that second
         line well short, *that* is where the shot lands -- the wall in front of
         the barrel -- and AimBlocked says so, which is what turns the reticle
         red.

    Step 2 is not a separate safety check bolted on: it is the same line the
    pellets themselves fly down, so the reticle cannot promise a hit the shot
    will not make. The pellet loop then only has to spread a cone around
    (AimPoint - muzzle).

    Runs before the fire gate and unconditionally, because the reticle has to be
    right on frames where the trigger is not pulled -- which is most of them.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    cam = keep(_at(_node(ed, FN_GET_CAM), x0, y0 + 260))
    _set(cam, "PlayerIndex", 0)
    cam_out = _pin(cam, "ReturnValue", is_input=False)
    cam_loc = keep(_at(_node(ed, FN_CAM_LOC), x0 + 240, y0 + 260))
    _connect(cam_out, _pin(cam_loc, "self"))
    cam_loc_out = _pin(cam_loc, "ReturnValue", is_input=False)
    cam_rot = keep(_at(_node(ed, FN_CAM_ROT), x0 + 240, y0 + 400))
    _connect(cam_out, _pin(cam_rot, "self"))
    fwd = keep(_at(_node(ed, FN_FORWARD), x0 + 480, y0 + 400))
    _connect(_pin(cam_rot, "ReturnValue", is_input=False), _pin(fwd, "InRot"))
    reach = keep(_at(_node(ed, FN_MUL_VF), x0 + 720, y0 + 400))
    _connect(_pin(fwd, "ReturnValue", is_input=False), _pin(reach, "A"))
    # The length goes in as a *vector* literal, not a float one. UE 5 promotes
    # Multiply_VectorFloat to a wildcard operator, and with nothing connected
    # its B pin is a vector -- which is a struct pin, which rejects every
    # literal format there is. Multiplying component-wise by (R, R, R) is the
    # same arithmetic and actually survives the save.
    _connect(_vec(ed, AIM_TRACE_RANGE, AIM_TRACE_RANGE, AIM_TRACE_RANGE,
                  x0 + 480, y0 + 560),
             _pin(reach, "B"))
    sky = keep(_at(_node(ed, FN_ADD_VV), x0 + 960, y0 + 320))
    _connect(cam_loc_out, _pin(sky, "A"))
    _connect(_pin(reach, "ReturnValue", is_input=False), _pin(sky, "B"))
    sky_out = _pin(sky, "ReturnValue", is_input=False)

    look = keep(_at(_node(ed, FN_TRACE), x0 + 1200, y0))
    _connect(cam_loc_out, _pin(look, "Start"))
    _connect(sky_out, _pin(look, "End"))
    # Never drawn: this line runs from the camera through the player's own head
    # every frame, so drawing it would fill the screen. Only the pellets are
    # drawn, and only when they are actually fired.
    _trace_defaults(look)
    for e in exec_ins:
        _connect(e, _pin(look, "execute"))

    look_brk = keep(_at(_palette(ed, NODE_BREAK_HIT), x0 + 1200, y0 + 560))
    _connect(_pin(look, "OutHit", is_input=False), _loose_pin(look_brk, "Hit"))
    saw = keep(_at(ed.add_branch_node(), x0 + 1480, y0))
    _connect(_pin(look, "ReturnValue", is_input=False), _pin(saw, "Condition"))
    _connect(BEL.find_then_pin(look), _pin(saw, "execute"))

    on_surface = keep(_at(ed.add_set_member_variable_node("AimPoint"), x0 + 1740, y0 - 160))
    _connect(_loose_pin(look_brk, "Location", is_input=False), _pin(on_surface, "AimPoint"))
    _connect(BEL.find_then_pin(saw), _pin(on_surface, "execute"))
    at_sky = keep(_at(ed.add_set_member_variable_node("AimPoint"), x0 + 1740, y0 + 220))
    _connect(sky_out, _pin(at_sky, "AimPoint"))
    _connect(BEL.find_else_pin(saw), _pin(at_sky, "execute"))

    armed = keep(_at(_node(ed, FN_IS_VALID), x0 + 2000, y0 + 320))
    _connect(held, _pin(armed, "Object"))
    holding = keep(_at(ed.add_branch_node(), x0 + 2240, y0))
    _connect(_pin(armed, "ReturnValue", is_input=False), _pin(holding, "Condition"))
    _connect(BEL.find_then_pin(on_surface), _pin(holding, "execute"))
    _connect(BEL.find_then_pin(at_sky), _pin(holding, "execute"))

    # Empty-handed: there is nothing to draw a reticle for, and no muzzle to
    # trace from -- reading one off a null weapon is how Accessed None happens.
    unarmed = keep(_at(ed.add_set_member_variable_node("AimValid"), x0 + 2500, y0 + 700))
    _set(unarmed, "AimValid", "false")
    _connect(BEL.find_else_pin(holding), _pin(unarmed, "execute"))

    aim_get = keep(_at(ed.add_get_member_variable_node("AimPoint"), x0 + 2500, y0 + 460))
    aim_out = _pin(aim_get, "AimPoint", is_input=False)

    muzzle = _muzzle_location(ed, held, x0 + 2500, y0 + 1000)

    clear = keep(_at(_node(ed, FN_TRACE), x0 + 3260, y0))
    _connect(muzzle, _pin(clear, "Start"))
    _connect(aim_out, _pin(clear, "End"))
    _trace_defaults(clear)
    _connect(BEL.find_then_pin(holding), _pin(clear, "execute"))

    clear_brk = keep(_at(_palette(ed, NODE_BREAK_HIT), x0 + 2760, y0 + 560))
    _connect(_pin(clear, "OutHit", is_input=False), _loose_pin(clear_brk, "Hit"))
    stopped = keep(_at(ed.add_branch_node(), x0 + 3040, y0))
    _connect(_pin(clear, "ReturnValue", is_input=False), _pin(stopped, "Condition"))
    _connect(BEL.find_then_pin(clear), _pin(stopped, "execute"))

    short_by = keep(_at(_node(ed, FN_DISTANCE), x0 + 3040, y0 + 700))
    _connect(_loose_pin(clear_brk, "Location", is_input=False), _pin(short_by, "V1"))
    _connect(aim_out, _pin(short_by, "V2"))
    far_short = keep(_at(_node(ed, FN_GREATER_FF), x0 + 3280, y0 + 700))
    _connect(_pin(short_by, "ReturnValue", is_input=False), _pin(far_short, "A"))
    _set(far_short, "B", BLOCKED_SLACK)

    mark = keep(_at(ed.add_set_member_variable_node("AimBlocked"), x0 + 3300, y0 - 160))
    _connect(_pin(far_short, "ReturnValue", is_input=False), _pin(mark, "AimBlocked"))
    _connect(BEL.find_then_pin(stopped), _pin(mark, "execute"))
    # The aim point moves to where the barrel's own line actually ends, so the
    # reticle sits on the near wall rather than on the enemy behind it.
    reality = keep(_at(ed.add_set_member_variable_node("AimPoint"), x0 + 3560, y0 - 160))
    _connect(_loose_pin(clear_brk, "Location", is_input=False), _pin(reality, "AimPoint"))
    _connect(BEL.find_then_pin(mark), _pin(reality, "execute"))

    open_shot = keep(_at(ed.add_set_member_variable_node("AimBlocked"), x0 + 3300, y0 + 260))
    _set(open_shot, "AimBlocked", "false")
    _connect(BEL.find_else_pin(stopped), _pin(open_shot, "execute"))

    ready = keep(_at(ed.add_set_member_variable_node("AimValid"), x0 + 3840, y0))
    _set(ready, "AimValid", "true")
    _connect(BEL.find_then_pin(reality), _pin(ready, "execute"))
    _connect(BEL.find_then_pin(open_shot), _pin(ready, "execute"))

    ed.add_comment_to_nodes(
        "Resolve aim: the camera picks the target, the muzzle decides whether "
        "the gun can reach it. AimPoint ends up at the first surface on the "
        "line the pellets will actually fly down, which is what makes the "
        "reticle honest -- including when the barrel is against a tree and the "
        "camera can see straight past it.",
        made)
    return [BEL.find_then_pin(ready), BEL.find_then_pin(unarmed)], muzzle


def _author_ads(ed, tick, pc_out, owner_out, held, armed_out, key_pin,
                exec_ins, x0, y0):
    """Right mouse held: narrow the camera to this weapon's AdsZoom.

        Aiming   = RightMouseButton down AND something is equipped
                                          AND not sprinting
        TargetFOV = Aiming ? BaseFOV / Held.AdsZoom : BaseFOV
        CurrentFOV = FInterpTo(CurrentFOV, TargetFOV, dt, COMBAT.ads_interp_speed)
        Camera.SetFieldOfView(CurrentFOV)

    ...and then slow the mouse and the legs by how far that zoom has actually
    travelled, rather than by the key state. The legs are the second write of
    MaxWalkSpeed in this Tick; see the block itself for why that is the cheap
    way round.

    Three things are load-bearing here.

    Not while sprinting, because the fire gate already refuses to shoot while
    sprinting: a zoom that stayed on through a sprint would be aiming a weapon
    that cannot fire, and the view would be narrow exactly when the player is
    running away and needs it wide.

    Not with empty hands, because AdsZoom is read off Held and a pure Get off a
    null self is an Accessed None every frame. The read therefore sits inside
    the true arm of the branch, where Held is known valid -- pure nodes are
    pulled by whoever reads them, so the getter simply never runs on the frames
    nothing is equipped. That is the same trap ``Automatic`` is commented for
    above, and it has bitten this file before.

    Interpolated rather than snapped, and CurrentFOV is a stored variable
    because FInterpTo's input is its own previous output. Recomputing the
    target every frame and lerping toward it also means letting go of the
    button unzooms by the same curve with no second code path.

    Returns the exec pins to carry on from.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    down = keep(_at(_node(ed, FN_IS_KEY_DOWN), x0, y0 + 300))
    _connect(pc_out, _pin(down, "self"))
    _connect(key_pin, _pin(down, "Key"))

    # Sprinting has already been written this frame -- _author_sprint runs
    # before this block -- so this reads the flag rather than the key.
    running = keep(_at(ed.add_get_member_variable_node("Sprinting"), x0, y0 + 420))
    still = keep(_at(_node(ed, FN_NOT_B), x0 + 240, y0 + 420))
    _connect(_pin(running, "Sprinting", is_input=False), _pin(still, "A"))

    can = keep(_at(_node(ed, FN_AND), x0 + 480, y0 + 360))
    _connect(_pin(down, "ReturnValue", is_input=False), _pin(can, "A"))
    _connect(_pin(still, "ReturnValue", is_input=False), _pin(can, "B"))
    wants = keep(_at(_node(ed, FN_AND), x0 + 720, y0 + 300))
    _connect(_pin(can, "ReturnValue", is_input=False), _pin(wants, "A"))
    _connect(armed_out, _pin(wants, "B"))

    mark = keep(_at(ed.add_set_member_variable_node("Aiming"), x0 + 980, y0))
    _connect(_pin(wants, "ReturnValue", is_input=False), _pin(mark, "Aiming"))
    for e in exec_ins:
        _connect(e, _pin(mark, "execute"))

    base = keep(_at(ed.add_get_member_variable_node("BaseFOV"), x0 + 980, y0 + 420))
    base_out = _pin(base, "BaseFOV", is_input=False)

    aiming = keep(_at(ed.add_get_member_variable_node("Aiming"), x0 + 980, y0 + 300))
    zoomed = keep(_at(ed.add_branch_node(), x0 + 1240, y0))
    _connect(_pin(aiming, "Aiming", is_input=False), _pin(zoomed, "Condition"))
    _connect(BEL.find_then_pin(mark), _pin(zoomed, "execute"))

    # True arm: BaseFOV / this weapon's zoom. The AdsZoom getter lives here so
    # it is never pulled on a frame with nothing equipped.
    zoom_pin, zoom_n = _prop(ed, "AdsZoom", held, x0 + 1240, y0 + 420)
    keep(zoom_n)
    narrow = keep(_at(_node(ed, FN_DIV_FF), x0 + 1500, y0 + 420))
    _connect(base_out, _pin(narrow, "A"))
    _connect(zoom_pin, _pin(narrow, "B"))
    want_in = keep(_at(ed.add_set_member_variable_node("TargetFOV"), x0 + 1760, y0))
    _connect(_pin(narrow, "ReturnValue", is_input=False), _pin(want_in, "TargetFOV"))
    _connect(BEL.find_then_pin(zoomed), _pin(want_in, "execute"))

    want_out = keep(_at(ed.add_set_member_variable_node("TargetFOV"), x0 + 1760, y0 + 220))
    _connect(base_out, _pin(want_out, "TargetFOV"))
    _connect(BEL.find_else_pin(zoomed), _pin(want_out, "execute"))

    # --- move the camera toward it ------------------------------------------
    have = keep(_at(ed.add_get_member_variable_node("CurrentFOV"), x0 + 2020, y0 + 420))
    want = keep(_at(ed.add_get_member_variable_node("TargetFOV"), x0 + 2020, y0 + 540))
    step = keep(_at(_node(ed, FN_INTERP_FF), x0 + 2280, y0 + 420))
    _connect(_pin(have, "CurrentFOV", is_input=False), _pin(step, "Current"))
    _connect(_pin(want, "TargetFOV", is_input=False), _pin(step, "Target"))
    _connect(_pin(tick, "DeltaSeconds", is_input=False), _pin(step, "DeltaTime"))
    _set(step, "InterpSpeed", COMBAT.ads_interp_speed)
    moved = keep(_at(ed.add_set_member_variable_node("CurrentFOV"), x0 + 2540, y0))
    _connect(_pin(step, "ReturnValue", is_input=False), _pin(moved, "CurrentFOV"))
    for tail in (BEL.find_then_pin(want_in), BEL.find_then_pin(want_out)):
        _connect(tail, _pin(moved, "execute"))

    cam = keep(_at(_node(ed, FN_GET_COMP), x0 + 2540, y0 + 420))
    _connect(owner_out, _pin(cam, "self"))
    _pin(cam, "ComponentClass").set_pin_value(CAMERA_CLASS_PATH)
    apply_fov = keep(_at(_node(ed, FN_SET_FOV), x0 + 2800, y0))
    _connect(_pin(cam, "ReturnValue", is_input=False), _pin(apply_fov, "self"))
    # Driven from the SET node's own pass-through output, not from a fresh
    # getter: the setter passes the value it wrote straight out, so this cannot
    # read a stale CurrentFOV the way a second Get would if anything were ever
    # spliced in between. That pin is called "Output_Get", NOT the variable's
    # own name -- a Set node's data output is named for what it does, not for
    # what it writes.
    _connect(_loose_pin(moved, "Output_Get", is_input=False),
             _pin(apply_fov, "InFieldOfView"))
    _connect(BEL.find_then_pin(moved), _pin(apply_fov, "execute"))

    # --- and slow the mouse by the same curve --------------------------------
    # Not "if aiming, use the slow number": the factor is read straight off how
    # far the zoom has actually travelled this frame, so it eases in and out
    # along the FInterpTo above, is automatically stronger on the 4x scope than
    # on 1.5x irons, and has no second code path for letting the button go.
    #
    #     eased = Lerp(1, CurrentFOV / BaseFOV, COMBAT.ads_sens_compensation)
    #     yaw   scale = BaseYawScale   * MouseSensitivity * eased
    #     pitch scale = BasePitchScale * MouseSensitivity * eased
    #
    # Both base scales are signed as the engine shipped them, so multiplying
    # by a positive sensitivity cannot flip the pitch axis.
    base_again = keep(_at(ed.add_get_member_variable_node("BaseFOV"),
                          x0 + 2800, y0 + 560))
    ratio = keep(_at(_node(ed, FN_DIV_FF), x0 + 3060, y0 + 480))
    _connect(_loose_pin(moved, "Output_Get", is_input=False), _pin(ratio, "A"))
    _connect(_pin(base_again, "BaseFOV", is_input=False), _pin(ratio, "B"))
    eased = keep(_at(_node(ed, FN_LERP), x0 + 3320, y0 + 480))
    _set(eased, "A", 1.0)
    _connect(_pin(ratio, "ReturnValue", is_input=False), _pin(eased, "B"))
    _set(eased, "Alpha", COMBAT.ads_sens_compensation)

    sens = keep(_at(ed.add_get_member_variable_node("MouseSensitivity"),
                    x0 + 3320, y0 + 620))
    factor = keep(_at(_node(ed, FN_MUL_FF), x0 + 3580, y0 + 480))
    _connect(_pin(eased, "ReturnValue", is_input=False), _pin(factor, "A"))
    _connect(_pin(sens, "MouseSensitivity", is_input=False), _pin(factor, "B"))
    factor_out = _pin(factor, "ReturnValue", is_input=False)

    flow = BEL.find_then_pin(apply_fov)
    for i, (var, setter, arg) in enumerate(
            (("BaseYawScale", FN_SET_YAW_SCALE, "NewValue"),
             ("BasePitchScale", FN_SET_PITCH_SCALE, "NewValue"))):
        base_scale = keep(_at(ed.add_get_member_variable_node(var),
                              x0 + 3840, y0 + 480 + i * 140))
        scaled = keep(_at(_node(ed, FN_MUL_FF), x0 + 4100, y0 + 480 + i * 140))
        _connect(_pin(base_scale, var, is_input=False), _pin(scaled, "A"))
        _connect(factor_out, _pin(scaled, "B"))
        put = keep(_at(_node(ed, setter), x0 + 4360, y0 + i * 220))
        _connect(pc_out, _pin(put, "self"))
        _connect(_pin(scaled, "ReturnValue", is_input=False),
                 _loose_pin(put, arg))
        _connect(flow, _pin(put, "execute"))
        flow = BEL.find_then_pin(put)

    # --- and slow the legs by the same curve ---------------------------------
    # A SECOND write of MaxWalkSpeed, after the one _author_sprint made earlier
    # in this same Tick, and that ordering is the whole design. Sprint writes
    # the speed unconditionally every frame -- Sprinting ? sprint_speed :
    # BaseSpeed -- so this write does not need an "undo" path at all: the frame
    # this branch stops running, sprint's write has already put the player back
    # at BaseSpeed. Moving the decision into _author_sprint instead was the
    # alternative, and it is worse: the aim state is resolved after the sprint
    # block (it reads Sprinting), and sprint's CastFailed pin is a live
    # continuation that would then need the same arithmetic on it.
    #
    # Gated on "not sprinting", the same pin the zoom is gated on, so the two
    # MaxWalkSpeed writes can never disagree about a frame: while Sprinting is
    # set this block does nothing and sprint's 900 stands, and letting go of
    # Shift hands the frame straight back here. Gated on armed as well,
    # because the AdsZoom read below needs a valid Held.
    #
    #     progress = FClamp((BaseFOV / CurrentFOV - 1) / (AdsZoom - 1), 0, 1)
    #     MaxWalkSpeed = BaseSpeed * Lerp(1, COMBAT.ads_move_speed_scale, progress)
    #
    # progress is the scope overlay's fade alpha, node for node -- how far the
    # camera has actually travelled toward this weapon's zoom, 0 at rest and 1
    # at full ADS. So the slowdown eases in and out on the FInterpTo above
    # instead of snapping on a key, it has no second code path for release, and
    # because it is NORMALISED by the weapon's own AdsZoom it lands on exactly
    # ads_move_speed_scale at full ADS for every weapon. The un-normalised
    # CurrentFOV/BaseFOV the sensitivity uses would have made the sniper slower
    # on its legs than the pistol, which is a zoom factor leaking into a
    # mechanic that has nothing to do with zoom.
    steady = keep(_at(_node(ed, FN_AND), x0 + 4620, y0 + 900))
    _connect(_pin(still, "ReturnValue", is_input=False), _pin(steady, "A"))
    _connect(armed_out, _pin(steady, "B"))
    slow_gate = keep(_at(ed.add_branch_node(), x0 + 4880, y0 + 760))
    _connect(_pin(steady, "ReturnValue", is_input=False), _pin(slow_gate, "Condition"))
    _connect(flow, _pin(slow_gate, "execute"))

    base_third = keep(_at(ed.add_get_member_variable_node("BaseFOV"),
                          x0 + 4880, y0 + 1040))
    zoom_ratio = keep(_at(_node(ed, FN_DIV_FF), x0 + 5140, y0 + 1040))
    _connect(_pin(base_third, "BaseFOV", is_input=False), _pin(zoom_ratio, "A"))
    _connect(_loose_pin(moved, "Output_Get", is_input=False), _pin(zoom_ratio, "B"))
    so_far = keep(_at(_node(ed, FN_SUB_FF), x0 + 5400, y0 + 1040))
    _connect(_pin(zoom_ratio, "ReturnValue", is_input=False), _pin(so_far, "A"))
    _set(so_far, "B", 1.0)

    # The denominator is this weapon's own zoom, not the config's, for the same
    # reason the scope's fade uses it: 4x has four times as far to travel.
    zoom_again, zoom_again_n = _prop(ed, "AdsZoom", held, x0 + 5140, y0 + 1180)
    keep(zoom_again_n)
    span = keep(_at(_node(ed, FN_SUB_FF), x0 + 5400, y0 + 1180))
    _connect(zoom_again, _pin(span, "A"))
    _set(span, "B", 1.0)

    frac = keep(_at(_node(ed, FN_DIV_FF), x0 + 5660, y0 + 1040))
    _connect(_pin(so_far, "ReturnValue", is_input=False), _pin(frac, "A"))
    _connect(_pin(span, "ReturnValue", is_input=False), _pin(frac, "B"))
    # Clamped because the FInterpTo can overshoot its target by a fraction on a
    # long frame, and an unclamped progress of 1.02 is a walk speed below the
    # configured floor -- small, but it would be a number nobody chose.
    progress = keep(_at(_node(ed, FN_CLAMP), x0 + 5920, y0 + 1040))
    _connect(_pin(frac, "ReturnValue", is_input=False), _pin(progress, "Value"))
    _set(progress, "Min", 0.0)
    _set(progress, "Max", 1.0)

    slowed = keep(_at(_node(ed, FN_LERP), x0 + 6180, y0 + 1040))
    _set(slowed, "A", 1.0)
    _set(slowed, "B", COMBAT.ads_move_speed_scale)
    _connect(_pin(progress, "ReturnValue", is_input=False), _pin(slowed, "Alpha"))
    # Off BaseSpeed, not off the speed that is currently set: this runs every
    # frame, so a factor applied to the live value would compound.
    walked = keep(_at(ed.add_get_member_variable_node("BaseSpeed"),
                      x0 + 6180, y0 + 1180))
    speed = keep(_at(_node(ed, FN_MUL_FF), x0 + 6440, y0 + 1040))
    _connect(_pin(walked, "BaseSpeed", is_input=False), _pin(speed, "A"))
    _connect(_pin(slowed, "ReturnValue", is_input=False), _pin(speed, "B"))

    # No cast: GetComponentByClass reshapes its return pin to the class chosen
    # on ComponentClass, so this wires straight into the movement component's
    # own setter. _author_sprint casts to Character instead only because it
    # needs the CastFailed pin as a continuation; here the branch above is
    # already the guard.
    legs = keep(_at(_node(ed, FN_GET_COMP), x0 + 5140, y0 + 900))
    _connect(owner_out, _pin(legs, "self"))
    _pin(legs, "ComponentClass").set_pin_value(MOVEMENT_CLASS_PATH)
    apply_speed = keep(_at(ed.add_set_member_variable_node(
        "MaxWalkSpeed", MOVEMENT_CLASS_PATH), x0 + 6700, y0 + 760))
    _connect(_pin(legs, "ReturnValue", is_input=False), _pin(apply_speed, "self"))
    _connect(_pin(speed, "ReturnValue", is_input=False),
             _pin(apply_speed, "MaxWalkSpeed"))
    _connect(BEL.find_then_pin(slow_gate), _pin(apply_speed, "execute"))

    ed.add_comment_to_nodes(
        f"{AIM_KEY}: zoom to BaseFOV / the weapon's own AdsZoom "
        f"({COMBAT.ads_zoom_irons:g}x irons, {COMBAT.ads_zoom_scope:g}x on the sniper's "
        f"scope), interpolated at {COMBAT.ads_interp_speed:g} so it arrives in about "
        f"a fifth of a second. Refused while sprinting -- the fire gate already "
        f"is -- and with empty hands, which is also what keeps the AdsZoom "
        f"getter off a null Held. The cone shrinks to "
        f"{COMBAT.ads_spread_scale:g}x while Aiming; see _author_fire. The mouse "
        f"slows with the zoom rather than with the button: "
        f"Lerp(1, CurrentFOV/BaseFOV, {COMBAT.ads_sens_compensation:g}) scaling both "
        f"of the controller's cached look scales, so a 4x scope is slower than "
        f"1.5x irons for free and the slowdown eases in on the same curve. "
        f"The legs slow too, to {COMBAT.ads_move_speed_scale:g}x BaseSpeed at full "
        f"ADS, on the scope overlay's own fade curve -- a second MaxWalkSpeed "
        f"write after the sprint block's, which is what makes releasing the "
        f"button need no code: sprint restores BaseSpeed unconditionally on "
        f"the next frame.",
        made)
    return (BEL.find_then_pin(apply_speed), BEL.find_else_pin(slow_gate))
