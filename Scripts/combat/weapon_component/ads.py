"""Aiming: the shoulder aim and aiming down the sights as two keys, and what
both do -- the zoom, the look slowdown and the walk slowdown.

The aim state written here (Aiming, SightAiming, AimZoom) is what firing.py and
recoil.py read for the tighter cone and the steadier kick (either way of
aiming earns them), and what sights.py reads to move the camera onto the gun.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _pin, _set
from combat.nodes import (
    CAMERA_CLASS_PATH, FN_AND, FN_CLAMP, FN_DIV_FF, FN_GET_COMP, FN_INTERP_FF,
    FN_IS_KEY_DOWN, FN_LERP, FN_MUL_FF, FN_NOT_B, FN_OR, FN_SELECT_FF,
    FN_SET_FOV, FN_SET_PITCH_SCALE, FN_SET_YAW_SCALE, FN_SUB_FF,
    MOVEMENT_CLASS_PATH,
)
from combat.seat_tuning import HAS_SIGHTS_VAR, SEATED_VAR, SIGHTS_FORCED_VAR
from combat.tuning import AIM_KEY, COMBAT, SIGHTS_KEY
from combat.weapon_component.common import _prop


def _author_aim_state(ed, pc_out, held, armed_out, key_pins, exec_ins, keep,
                      x0, y0):
    """Read the two aim keys into the aim state and the FOV to zoom to.

        shoulder  = IsInputKeyDown(KeyAim)
        sights    = IsInputKeyDown(KeySights) OR SightsForced
        Aiming    = (shoulder OR sights) AND NOT Sprinting AND IsValid(Held)
        if Aiming:
            SightAiming = sights AND Held.HasSights
            AimZoom     = SightAiming AND SightSeated ? Held.AdsZoom
                                                      : COMBAT.shoulder_zoom
            TargetFOV   = BaseFOV / AimZoom
        else:
            SightAiming = false
            TargetFOV   = BaseFOV

    Holding both keys is aiming down the sights: the sights are the stronger
    of the two, and letting go of them drops back to the shoulder.

    SightsForced is a probe's stand-in for the sights key (no key can be
    injected into a headless game); it is false in every real game.

    The weapon's own zoom waits for SightSeated (seat.py, written later in the
    frame, so this reads last frame's): until the gun is up and the camera may
    go onto it, the sights key zooms as the shoulder does. The irons zoom the
    same as the shoulder, so only the scope shows it: its 4x, and the glass
    that fades in on it, arrive with the camera rather than over the shoulder.

    Not while sprinting, because the fire gate already refuses to shoot while
    sprinting: a zoom that stayed on through a sprint would be aiming a weapon
    that cannot fire, and the view would be narrow exactly when the player is
    running away and needs it wide.

    Not with empty hands, because AdsZoom and HasSights are read off Held and
    a pure Get off a null self is an Accessed None every frame. Those reads sit
    inside the true arm of the branch, where Held is known valid -- pure nodes
    are pulled by whoever reads them, so the getters simply never run on the
    frames nothing is equipped. Only a gun has sights (HasSights, set by the
    guns' rows alone), so the knife, the axe, the matches, wood and food aim
    over the shoulder whichever key is held.

    AimZoom is not written on the false arm on purpose: it is left at the zoom
    being let go of, which is what the walk slowdown's ease-out normalises by.

    Returns (exits, the NOT Sprinting pin).
    """
    def held_down(var, y):
        n = keep(_at(_node(ed, FN_IS_KEY_DOWN), x0, y))
        _connect(pc_out, _pin(n, "self"))
        _connect(key_pins[var], _pin(n, "Key"))
        return _pin(n, "ReturnValue", is_input=False)

    shoulder = held_down("KeyAim", y0 + 300)
    forced = keep(_at(ed.add_get_member_variable_node(SIGHTS_FORCED_VAR),
                      x0, y0 + 80))
    sights_or = keep(_at(_node(ed, FN_OR), x0 + 240, y0 + 120))
    _connect(held_down("KeySights", y0 + 180), _pin(sights_or, "A"))
    _connect(_pin(forced, SIGHTS_FORCED_VAR, is_input=False), _pin(sights_or, "B"))
    sights = _pin(sights_or, "ReturnValue", is_input=False)
    either = keep(_at(_node(ed, FN_OR), x0 + 240, y0 + 240))
    _connect(shoulder, _pin(either, "A"))
    _connect(sights, _pin(either, "B"))

    # Sprinting has already been written this frame -- _author_sprint runs
    # before this block -- so this reads the flag rather than the key.
    running = keep(_at(ed.add_get_member_variable_node("Sprinting"), x0, y0 + 420))
    still = keep(_at(_node(ed, FN_NOT_B), x0 + 240, y0 + 420))
    _connect(_pin(running, "Sprinting", is_input=False), _pin(still, "A"))

    can = keep(_at(_node(ed, FN_AND), x0 + 480, y0 + 360))
    _connect(_pin(either, "ReturnValue", is_input=False), _pin(can, "A"))
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

    # True arm. Held is valid here, so it can be asked about.
    sighted, sighted_n = _prop(ed, HAS_SIGHTS_VAR, held, x0 + 1240, y0 + 560)
    keep(sighted_n)
    down_sights = keep(_at(_node(ed, FN_AND), x0 + 1760, y0 + 500))
    _connect(sights, _pin(down_sights, "A"))
    _connect(sighted, _pin(down_sights, "B"))
    sight_on = keep(_at(ed.add_set_member_variable_node("SightAiming"),
                        x0 + 1500, y0))
    _connect(_pin(down_sights, "ReturnValue", is_input=False),
             _pin(sight_on, "SightAiming"))
    _connect(BEL.find_then_pin(zoomed), _pin(sight_on, "execute"))

    # The weapon's zoom down its sights, the shoulder's for everything else.
    # The literal is on B, which is the pin a Kismet node lets hold one.
    zoom_pin, zoom_n = _prop(ed, "AdsZoom", held, x0 + 1760, y0 + 700)
    keep(zoom_n)
    pick = keep(_at(_node(ed, FN_SELECT_FF), x0 + 2020, y0 + 560))
    _connect(zoom_pin, _pin(pick, "A"))
    _set(pick, "B", COMBAT.shoulder_zoom)
    seated = keep(_at(ed.add_get_member_variable_node(SEATED_VAR),
                      x0 + 1760, y0 + 840))
    on_gun = keep(_at(_node(ed, FN_AND), x0 + 2020, y0 + 760))
    _connect(_loose_pin(sight_on, "Output_Get", is_input=False), _pin(on_gun, "A"))
    _connect(_pin(seated, SEATED_VAR, is_input=False), _pin(on_gun, "B"))
    _connect(_pin(on_gun, "ReturnValue", is_input=False), _pin(pick, "bPickA"))
    chosen = keep(_at(ed.add_set_member_variable_node("AimZoom"), x0 + 1760, y0))
    _connect(_pin(pick, "ReturnValue", is_input=False), _pin(chosen, "AimZoom"))
    _connect(BEL.find_then_pin(sight_on), _pin(chosen, "execute"))

    narrow = keep(_at(_node(ed, FN_DIV_FF), x0 + 2280, y0 + 420))
    _connect(base_out, _pin(narrow, "A"))
    _connect(_loose_pin(chosen, "Output_Get", is_input=False), _pin(narrow, "B"))
    want_in = keep(_at(ed.add_set_member_variable_node("TargetFOV"), x0 + 2020, y0))
    _connect(_pin(narrow, "ReturnValue", is_input=False), _pin(want_in, "TargetFOV"))
    _connect(BEL.find_then_pin(chosen), _pin(want_in, "execute"))

    # False arm: not aiming at all, so not down the sights either.
    sight_off = keep(_at(ed.add_set_member_variable_node("SightAiming"),
                         x0 + 1500, y0 + 220))
    _set(sight_off, "SightAiming", "false")
    _connect(BEL.find_else_pin(zoomed), _pin(sight_off, "execute"))
    want_out = keep(_at(ed.add_set_member_variable_node("TargetFOV"),
                        x0 + 2020, y0 + 220))
    _connect(base_out, _pin(want_out, "TargetFOV"))
    _connect(BEL.find_then_pin(sight_off), _pin(want_out, "execute"))

    return ((BEL.find_then_pin(want_in), BEL.find_then_pin(want_out)),
            _pin(still, "ReturnValue", is_input=False))


def _author_zoom(ed, tick, pc_out, owner_out, exec_ins, keep, x0, y0):
    """Move the camera's FOV toward TargetFOV, and slow the mouse with it.

        CurrentFOV = FInterpTo(CurrentFOV, TargetFOV, dt, COMBAT.ads_interp_speed)
        Camera.SetFieldOfView(CurrentFOV)

    Interpolated rather than snapped, and CurrentFOV is a stored variable
    because FInterpTo's input is its own previous output. Recomputing the
    target every frame and lerping toward it also means letting go of the
    button unzooms by the same curve with no second code path.

    Returns (the exec pin to carry on from, the CurrentFOV setter).
    """
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
    for tail in exec_ins:
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
    # on the 1.5x shoulder or irons, and has no second code path for letting the button go.
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

    # The scope's extra slowdown, on zoom past the irons:
    #
    #     past  = FClamp((BaseFOV / CurrentFOV - irons) / (scope - irons), 0, 1)
    #     scoped = eased * Lerp(1, ScopeSensitivity, past)
    #
    # Irons never get past their own zoom, so this is 1 for every weapon but the
    # sniper, and on the sniper it arrives with the zoom.
    zoom_now = keep(_at(_node(ed, FN_DIV_FF), x0 + 3060, y0 + 760))
    _connect(_pin(base_again, "BaseFOV", is_input=False), _pin(zoom_now, "A"))
    _connect(_loose_pin(moved, "Output_Get", is_input=False), _pin(zoom_now, "B"))
    beyond = keep(_at(_node(ed, FN_SUB_FF), x0 + 3320, y0 + 760))
    _connect(_pin(zoom_now, "ReturnValue", is_input=False), _pin(beyond, "A"))
    _set(beyond, "B", COMBAT.ads_zoom_irons)
    beyond_frac = keep(_at(_node(ed, FN_DIV_FF), x0 + 3580, y0 + 760))
    _connect(_pin(beyond, "ReturnValue", is_input=False), _pin(beyond_frac, "A"))
    _set(beyond_frac, "B", COMBAT.ads_zoom_scope - COMBAT.ads_zoom_irons)
    past = keep(_at(_node(ed, FN_CLAMP), x0 + 3840, y0 + 760))
    _connect(_pin(beyond_frac, "ReturnValue", is_input=False), _pin(past, "Value"))
    _set(past, "Min", 0.0)
    _set(past, "Max", 1.0)
    # B is the player's ScopeSensitivity (settings screen, pushed by the HUD),
    # whose CDO default is COMBAT.ads_scope_sens_scale.
    glass = keep(_at(_node(ed, FN_LERP), x0 + 4100, y0 + 760))
    _set(glass, "A", 1.0)
    glass_sens = keep(_at(ed.add_get_member_variable_node("ScopeSensitivity"),
                          x0 + 3840, y0 + 900))
    _connect(_pin(glass_sens, "ScopeSensitivity", is_input=False),
             _pin(glass, "B"))
    _connect(_pin(past, "ReturnValue", is_input=False), _pin(glass, "Alpha"))
    scoped = keep(_at(_node(ed, FN_MUL_FF), x0 + 3580, y0 + 600))
    _connect(_pin(eased, "ReturnValue", is_input=False), _pin(scoped, "A"))
    _connect(_pin(glass, "ReturnValue", is_input=False), _pin(scoped, "B"))

    sens = keep(_at(ed.add_get_member_variable_node("MouseSensitivity"),
                    x0 + 3320, y0 + 620))
    factor = keep(_at(_node(ed, FN_MUL_FF), x0 + 3580, y0 + 480))
    _connect(_pin(scoped, "ReturnValue", is_input=False), _pin(factor, "A"))
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

    return flow, moved


def _author_aim_slowdown(ed, owner_out, armed_out, still, moved, flow, keep,
                         x0, y0):
    """Slow the legs by how far the zoom has travelled; see the block."""
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
    # Shift hands the frame straight back here. Gated on armed as well, the
    # same as Aiming is, so empty hands always walk at sprint's speed.
    #
    #     progress = FClamp((BaseFOV / CurrentFOV - 1) / (AimZoom - 1), 0, 1)
    #     MaxWalkSpeed = BaseSpeed * Lerp(1, COMBAT.ads_move_speed_scale, progress)
    #
    # progress is how far the camera has actually travelled toward the zoom
    # being aimed at, 0 at rest and 1 at full zoom. So the slowdown eases in
    # and out on the FInterpTo above instead of snapping on a key, it has no
    # second code path for release, and because it is NORMALISED by AimZoom --
    # the shoulder's zoom, or the weapon's own AdsZoom down the sights -- it
    # lands on exactly ads_move_speed_scale at full zoom for every weapon and
    # both ways of aiming. The un-normalised
    # CurrentFOV/BaseFOV the sensitivity uses would have made the sniper slower
    # on its legs than the pistol, which is a zoom factor leaking into a
    # mechanic that has nothing to do with zoom.
    steady = keep(_at(_node(ed, FN_AND), x0 + 4620, y0 + 900))
    _connect(still, _pin(steady, "A"))
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

    # The denominator is the zoom being aimed at, not the config's: 4x down
    # the scope has four times as far to travel as 1.5x off the shoulder.
    # AimZoom rather than Held.AdsZoom because the sniper's shoulder aim stops
    # at 1.5x, and rather than a fresh select because on release AimZoom is
    # left at the zoom being let go of, which is what the ease-out travels.
    zoom_again = keep(_at(ed.add_get_member_variable_node("AimZoom"),
                          x0 + 5140, y0 + 1180))
    span = keep(_at(_node(ed, FN_SUB_FF), x0 + 5400, y0 + 1180))
    _connect(_pin(zoom_again, "AimZoom", is_input=False), _pin(span, "A"))
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

    return (BEL.find_then_pin(apply_speed), BEL.find_else_pin(slow_gate))


def _author_ads(ed, tick, pc_out, owner_out, held, armed_out, key_pins,
                exec_ins, x0, y0):
    """Either aim key held: zoom the camera, and slow the mouse and the legs.

    The shoulder aim (KeyAim) keeps the camera on its boom and zooms by
    COMBAT.shoulder_zoom; aiming down the sights (KeySights) zooms by the
    weapon's own AdsZoom, and sights.py moves the camera onto the weapon. Both
    set Aiming, so the tighter cone and the steadier kick are earned either
    way. The mouse and the legs slow by how far that zoom has actually
    travelled, rather than by the key state. The legs are the second write of
    MaxWalkSpeed in this Tick; see _author_aim_slowdown for why that is the
    cheap way round.

    Returns the exec pins to carry on from.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    aimed, still = _author_aim_state(ed, pc_out, held, armed_out, key_pins,
                                     exec_ins, keep, x0, y0)
    flow, moved = _author_zoom(ed, tick, pc_out, owner_out, aimed, keep, x0, y0)
    exits = _author_aim_slowdown(ed, owner_out, armed_out, still, moved, flow,
                                 keep, x0, y0)

    ed.add_comment_to_nodes(
        f"{AIM_KEY} aims over the shoulder at {COMBAT.shoulder_zoom:g}x; "
        f"{SIGHTS_KEY} aims down the sights at the weapon's own AdsZoom "
        f"({COMBAT.ads_zoom_irons:g}x irons, {COMBAT.ads_zoom_scope:g}x on the sniper's "
        f"scope) and sights.py moves the camera onto the gun. Interpolated at "
        f"{COMBAT.ads_interp_speed:g} so it arrives in about "
        f"a fifth of a second. Refused while sprinting -- the fire gate already "
        f"is -- and with empty hands, which is also what keeps the AdsZoom "
        f"getter off a null Held. Aiming is either key; SightAiming only the "
        f"second, and never with food in hand. The shot's cloud narrows with "
        f"either (accuracy.py). The mouse "
        f"slows with the zoom rather than with the button: "
        f"Lerp(1, CurrentFOV/BaseFOV, {COMBAT.ads_sens_compensation:g}) scaling both "
        f"of the controller's cached look scales, so a 4x scope is slower than "
        f"1.5x irons for free and the slowdown eases in on the same curve; "
        f"zoom past the irons scales it by a further ScopeSensitivity "
        f"(settings screen, default {COMBAT.ads_scope_sens_scale:g}x), so only "
        f"the scope gets it. "
        f"The legs slow too, to {COMBAT.ads_move_speed_scale:g}x BaseSpeed at full "
        f"zoom, normalised by AimZoom -- a second MaxWalkSpeed "
        f"write after the sprint block's, which is what makes releasing the "
        f"button need no code: sprint restores BaseSpeed unconditionally on "
        f"the next frame.",
        made)
    return exits
