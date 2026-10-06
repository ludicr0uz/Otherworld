"""Aiming: the shoulder aim and aiming down the sights as two keys, and what
both do -- the zoom, the look slowdown and the walk slowdown.

The aim state written here (Aiming, SightAiming, AimZoom) is what firing.py and
recoil.py read for the tighter cone and the steadier kick (either way of
aiming earns them), and what sights.py reads to move the camera onto the gun.
"""

from uebp.graph import _connect, _loose_pin, _node, _pin, _set, else_, out, then
from combat.nodes import CAMERA_CLASS_PATH
from combat.seat_tuning import HAS_SIGHTS_VAR
from combat.tuning import AIM_KEY, COMBAT, SIGHTS_KEY
from combat.use_tuning import USING_VAR
from combat.weapon_component.common import _prop
from uebp.nodes.actor import (
    FN_GET_COMP, FN_IS_KEY_DOWN, FN_SET_FOV, FN_SET_PITCH_SCALE, FN_SET_YAW_SCALE)
from uebp.nodes.math import (
    FN_AND, FN_CLAMP, FN_DIV_FF, FN_INTERP_FF, FN_LERP, FN_MUL_FF, FN_NOT, FN_OR,
    FN_SELECT_FF, FN_SUB_FF)
from uebp.nodes.move import FN_SET_AIM_WALK
from combat import item_vars as IV
from combat.weapon_component import vars as WV

# A probe's hand on the shoulder-aim key (ORed with it): no key can be pressed
# in a headless game.
AIM_FORCED_VAR = "AimForced"


def _author_aim_state(ed, pc_out, held, armed_out, key_pins, sights_key,
                      exec_ins, keep):
    """Read the two aim keys into the aim state and the FOV to zoom to.

        shoulder  = IsInputKeyDown(KeyAim)
        sights    = (IsInputKeyDown(KeySights) OR SightsForced) AND NOT Using
        Aiming    = (shoulder OR sights) AND NOT Sprinting AND IsValid(Held)
        if Aiming:
            SightAiming = sights AND Held.HasSights
            AimZoom     = SightAiming ? Held.AdsZoom : COMBAT.shoulder_zoom
            TargetFOV   = BaseFOV / AimZoom
        else:
            SightAiming = false
            TargetFOV   = BaseFOV

    Holding both keys is aiming down the sights: the sights are the stronger
    of the two, and letting go of them drops back to the shoulder.

    SightsForced is a probe's stand-in for the sights key (no key can be
    injected into a headless game); it is false in every real game. The key
    and its stand-in are polled once, by use.py, which hands the pin in
    (``sights_key``).

    The weapon's own zoom starts on the sights key, as the camera's travel
    onto the gun does (seat.py's SightSeat, eased at the same speed), so the
    two are one motion: the scope's 4x, and the glass that fades in on it,
    arrive with the camera. The sights key never stops at the shoulder's zoom
    on the way.

    Not while sprinting, because the fire gate already refuses to shoot while
    sprinting: a zoom that stayed on through a sprint would be aiming a weapon
    that cannot fire, and the view would be narrow exactly when the player is
    running away and needs it wide.

    Not with empty hands, because AdsZoom and HasSights are read off Held and
    a pure Get off a null self is an Accessed None every frame. Those reads sit
    inside the true arm of the branch, where Held is known valid -- pure nodes
    are pulled by whoever reads them, so the getters simply never run on the
    frames nothing is equipped. Only a gun has sights (HasSights, set by the
    guns' rows alone). With anything else in hand the sights key is the use
    key (use.py, which ran earlier this frame and wrote Using), so it does
    not aim at all: the knife, the axe, the matches, wood, food and the stick
    aim over the shoulder on the shoulder key alone.

    AimZoom is not written on the false arm on purpose: it is left at the zoom
    being let go of, which is what the walk slowdown's ease-out normalises by.

    Returns (exits, the NOT Sprinting pin).
    """
    def held_down(var):
        n = keep(_node(ed, FN_IS_KEY_DOWN))
        _connect(pc_out, _pin(n, "self"))
        _connect(key_pins[var], _pin(n, "Key"))
        return out(n)

    forced = keep(ed.add_get_member_variable_node(AIM_FORCED_VAR))
    shoulder_or = keep(_node(ed, FN_OR))
    _connect(held_down("KeyAim"), _pin(shoulder_or, "A"))
    _connect(out(forced, AIM_FORCED_VAR), _pin(shoulder_or, "B"))
    shoulder = out(shoulder_or)
    # The same key uses an item that has no sights (use.py): then it is not
    # an aim key this frame.
    using = keep(ed.add_get_member_variable_node(USING_VAR))
    not_using = keep(_node(ed, FN_NOT))
    _connect(out(using, USING_VAR), _pin(not_using, "A"))
    sights_and = keep(_node(ed, FN_AND))
    _connect(sights_key, _pin(sights_and, "A"))
    _connect(out(not_using), _pin(sights_and, "B"))
    sights = out(sights_and)
    either = keep(_node(ed, FN_OR))
    _connect(shoulder, _pin(either, "A"))
    _connect(sights, _pin(either, "B"))

    # Sprinting has already been written this frame -- _author_sprint runs
    # before this block -- so this reads the flag rather than the key.
    running = keep(ed.add_get_member_variable_node(WV.Sprinting))
    still = keep(_node(ed, FN_NOT))
    _connect(out(running, WV.Sprinting), _pin(still, "A"))

    can = keep(_node(ed, FN_AND))
    _connect(out(either), _pin(can, "A"))
    _connect(out(still), _pin(can, "B"))
    wants = keep(_node(ed, FN_AND))
    _connect(out(can), _pin(wants, "A"))
    _connect(armed_out, _pin(wants, "B"))

    mark = keep(ed.add_set_member_variable_node(WV.Aiming))
    _connect(out(wants), _pin(mark, WV.Aiming))
    for e in exec_ins:
        _connect(e, _pin(mark, "execute"))

    base = keep(ed.add_get_member_variable_node(WV.BaseFOV))
    base_out = out(base, WV.BaseFOV)

    aiming = keep(ed.add_get_member_variable_node(WV.Aiming))
    zoomed = keep(ed.add_branch_node())
    _connect(out(aiming, WV.Aiming), _pin(zoomed, "Condition"))
    _connect(then(mark), _pin(zoomed, "execute"))

    # True arm. Held is valid here, so it can be asked about.
    sighted, sighted_n = _prop(ed, HAS_SIGHTS_VAR, held)
    keep(sighted_n)
    down_sights = keep(_node(ed, FN_AND))
    _connect(sights, _pin(down_sights, "A"))
    _connect(sighted, _pin(down_sights, "B"))
    sight_on = keep(ed.add_set_member_variable_node(WV.SightAiming))
    _connect(out(down_sights), _pin(sight_on, WV.SightAiming))
    _connect(then(zoomed), _pin(sight_on, "execute"))

    # The weapon's zoom down its sights, the shoulder's for everything else.
    # The literal is on B, which is the pin a Kismet node lets hold one.
    zoom_pin, zoom_n = _prop(ed, IV.AdsZoom, held)
    keep(zoom_n)
    pick = keep(_node(ed, FN_SELECT_FF))
    _connect(zoom_pin, _pin(pick, "A"))
    _set(pick, "B", COMBAT.shoulder_zoom)
    _connect(_loose_pin(sight_on, "Output_Get", is_input=False),
             _pin(pick, "bPickA"))
    chosen = keep(ed.add_set_member_variable_node(WV.AimZoom))
    _connect(out(pick), _pin(chosen, WV.AimZoom))
    _connect(then(sight_on), _pin(chosen, "execute"))

    narrow = keep(_node(ed, FN_DIV_FF))
    _connect(base_out, _pin(narrow, "A"))
    _connect(_loose_pin(chosen, "Output_Get", is_input=False), _pin(narrow, "B"))
    want_in = keep(ed.add_set_member_variable_node(WV.TargetFOV))
    _connect(out(narrow), _pin(want_in, WV.TargetFOV))
    _connect(then(chosen), _pin(want_in, "execute"))

    # False arm: not aiming at all, so not down the sights either.
    sight_off = keep(ed.add_set_member_variable_node(WV.SightAiming))
    _set(sight_off, WV.SightAiming, False)
    _connect(else_(zoomed), _pin(sight_off, "execute"))
    want_out = keep(ed.add_set_member_variable_node(WV.TargetFOV))
    _connect(base_out, _pin(want_out, WV.TargetFOV))
    _connect(then(sight_off), _pin(want_out, "execute"))

    return ((then(want_in), then(want_out)), out(still))


def _author_zoom(ed, tick, pc_out, owner_out, exec_ins, keep):
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
    have = keep(ed.add_get_member_variable_node(WV.CurrentFOV))
    want = keep(ed.add_get_member_variable_node(WV.TargetFOV))
    step = keep(_node(ed, FN_INTERP_FF))
    _connect(out(have, WV.CurrentFOV), _pin(step, "Current"))
    _connect(out(want, WV.TargetFOV), _pin(step, "Target"))
    _connect(out(tick, "DeltaSeconds"), _pin(step, "DeltaTime"))
    _set(step, "InterpSpeed", COMBAT.ads_interp_speed)
    moved = keep(ed.add_set_member_variable_node(WV.CurrentFOV))
    _connect(out(step), _pin(moved, WV.CurrentFOV))
    for tail in exec_ins:
        _connect(tail, _pin(moved, "execute"))

    cam = keep(_node(ed, FN_GET_COMP))
    _connect(owner_out, _pin(cam, "self"))
    _pin(cam, "ComponentClass").set_pin_value(CAMERA_CLASS_PATH)
    apply_fov = keep(_node(ed, FN_SET_FOV))
    _connect(out(cam), _pin(apply_fov, "self"))
    # Driven from the SET node's own pass-through output, not from a fresh
    # getter: the setter passes the value it wrote straight out, so this cannot
    # read a stale CurrentFOV the way a second Get would if anything were ever
    # spliced in between. That pin is called "Output_Get", NOT the variable's
    # own name -- a Set node's data output is named for what it does, not for
    # what it writes.
    _connect(_loose_pin(moved, "Output_Get", is_input=False),
             _pin(apply_fov, "InFieldOfView"))
    _connect(then(moved), _pin(apply_fov, "execute"))

    # --- the mouse: the same at every aim but the scope's ---------------------
    # The shoulder aim and the irons leave the look scales alone. They used to
    # slow the mouse with the zoom (0.75x at 1.5x), and since aiming is also
    # what walks the character, the mouse read as slower walking than standing
    # or running. Only zoom PAST the irons slows it, so only the sniper's scope:
    #
    #     past  = FClamp((BaseFOV / CurrentFOV - irons) / (scope - irons), 0, 1)
    #     glass = Lerp(1, scope_base * ScopeSensitivity, past)
    #     yaw   scale = BaseYawScale   * MouseSensitivity * glass
    #     pitch scale = BasePitchScale * MouseSensitivity * glass
    #
    # scope_base (COMBAT.scope_sens_base()) is the share of the scope's zoom
    # given back in slower mouse movement. Read off how far the zoom has
    # travelled this frame, so it eases in and out along the FInterpTo above
    # and has no second code path for letting the button go.
    #
    # Both base scales are signed as the engine shipped them, so multiplying
    # by a positive sensitivity cannot flip the pitch axis.
    base_again = keep(ed.add_get_member_variable_node(WV.BaseFOV))
    zoom_now = keep(_node(ed, FN_DIV_FF))
    _connect(out(base_again, WV.BaseFOV), _pin(zoom_now, "A"))
    _connect(_loose_pin(moved, "Output_Get", is_input=False), _pin(zoom_now, "B"))
    beyond = keep(_node(ed, FN_SUB_FF))
    _connect(out(zoom_now), _pin(beyond, "A"))
    _set(beyond, "B", COMBAT.ads_zoom_irons)
    beyond_frac = keep(_node(ed, FN_DIV_FF))
    _connect(out(beyond), _pin(beyond_frac, "A"))
    _set(beyond_frac, "B", COMBAT.ads_zoom_scope - COMBAT.ads_zoom_irons)
    past = keep(_node(ed, FN_CLAMP))
    _connect(out(beyond_frac), _pin(past, "Value"))
    _set(past, "Min", 0.0)
    _set(past, "Max", 1.0)
    # ScopeSensitivity is the player's (settings screen, pushed by the HUD),
    # whose CDO default is COMBAT.ads_scope_sens_scale.
    glass_sens = keep(ed.add_get_member_variable_node(WV.ScopeSensitivity))
    through = keep(_node(ed, FN_MUL_FF))
    _connect(out(glass_sens, WV.ScopeSensitivity), _pin(through, "A"))
    _set(through, "B", COMBAT.scope_sens_base())
    scoped = keep(_node(ed, FN_LERP))
    _set(scoped, "A", 1.0)
    _connect(out(through), _pin(scoped, "B"))
    _connect(out(past), _pin(scoped, "Alpha"))

    sens = keep(ed.add_get_member_variable_node(WV.MouseSensitivity))
    factor = keep(_node(ed, FN_MUL_FF))
    _connect(out(scoped), _pin(factor, "A"))
    _connect(out(sens, WV.MouseSensitivity), _pin(factor, "B"))
    factor_out = out(factor)

    flow = then(apply_fov)
    for var, setter, arg in (("BaseYawScale", FN_SET_YAW_SCALE, "NewValue"),
                             ("BasePitchScale", FN_SET_PITCH_SCALE, "NewValue")):
        base_scale = keep(ed.add_get_member_variable_node(var))
        scaled = keep(_node(ed, FN_MUL_FF))
        _connect(out(base_scale, var), _pin(scaled, "A"))
        _connect(factor_out, _pin(scaled, "B"))
        put = keep(_node(ed, setter))
        _connect(pc_out, _pin(put, "self"))
        _connect(out(scaled), _loose_pin(put, arg))
        _connect(flow, _pin(put, "execute"))
        flow = then(put)

    return flow, moved


def _author_aim_slowdown(ed, owner_out, flow, keep):
    """Slow the legs while aiming: tell the movement component.

        SetAimWalk(owner, Aiming)

    The walk at a full aim is COMBAT.ads_move_speed_scale of the jog, for
    every weapon and both ways of aiming, and it eases in and out with the
    zoom: the movement component runs its own FInterpTo towards the flag, at
    the zoom's speed (ads_interp_speed, which player_move.py writes onto
    it). That ease used to be read off the camera's FOV here and written
    into MaxWalkSpeed, which only this machine saw; as a flag on each move
    the owning client predicts the slower walk and the server makes the same
    one. Aiming is already false while sprinting and with empty hands, so
    the flag needs no gate of its own.
    """
    aiming = keep(ed.add_get_member_variable_node(WV.Aiming))
    tell = keep(_node(ed, FN_SET_AIM_WALK))
    _connect(owner_out, _pin(tell, "Character"))
    _connect(out(aiming, WV.Aiming), _pin(tell, "bAiming"))
    _connect(flow, _pin(tell, "execute"))
    return (then(tell),)


def _author_ads(ed, tick, pc_out, owner_out, held, armed_out, key_pins,
                sights_key, exec_ins):
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
                                     sights_key, exec_ins, keep)
    flow, moved = _author_zoom(ed, tick, pc_out, owner_out, aimed, keep)
    exits = _author_aim_slowdown(ed, owner_out, flow, keep)

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
        f"is the same on the shoulder and down the irons as with no aim at "
        f"all; only zoom past the irons slows it, by "
        f"{COMBAT.scope_sens_base():g} x ScopeSensitivity "
        f"(settings screen, default {COMBAT.ads_scope_sens_scale:g}x), eased "
        f"in with the zoom, so only the scope gets it. "
        f"The legs slow too, to {COMBAT.ads_move_speed_scale:g}x BaseSpeed at full "
        f"zoom, normalised by AimZoom -- a second MaxWalkSpeed "
        f"write after the sprint block's, which is what makes releasing the "
        f"button need no code: sprint restores BaseSpeed unconditionally on "
        f"the next frame.",
        made)
    return exits
