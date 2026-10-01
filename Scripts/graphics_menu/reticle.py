"""The HUD's reticle: a crosshair nailed to the centre of the viewport, red
when the muzzle is blocked, handing over to the sniper's scope (scope.py)
down the sights, and to a gun's own iron sights there too: with the camera on
the sights it is drawn only in debug mode. Split out of
build_graphics_menu.py, which calls _author_reticle from DrawHUD.
"""

from combat.graph import BEL, _at, _connect, _loose_pin, _node, _palette, _pin, _set
from combat.seat_tuning import RETICLE_HIDE_SEAT, SEAT_VAR
from graphics_menu.scope import _author_scope, _author_scope_gate

WEAPON_COMP_CLASS_PATH = "/Game/Weapons/BP_WeaponComponent.BP_WeaponComponent_C"
ITEM_CLASS_PATH = "/Game/Weapons/BP_WeaponItem.BP_WeaponItem_C"

FN_ADD = "/Script/Engine.KismetMathLibrary.Add_DoubleDouble"
FN_AND = "/Script/Engine.KismetMathLibrary.BooleanAND"
FN_GREATER = "/Script/Engine.KismetMathLibrary.Greater_DoubleDouble"
FN_NOT = "/Script/Engine.KismetMathLibrary.Not_PreBool"
FN_BREAK_V2D = "/Script/Engine.KismetMathLibrary.BreakVector2D"
FN_DRAW_RECT = "/Script/Engine.HUD.DrawRect"
FN_FMIN = "/Script/Engine.KismetMathLibrary.FMin"
FN_GET_COMP = "/Script/Engine.Actor.GetComponentByClass"
FN_GET_PLAYER_PAWN = "/Script/Engine.GameplayStatics.GetPlayerPawn"
FN_MUL = "/Script/Engine.KismetMathLibrary.Multiply_DoubleDouble"
FN_SELECT_COLOR = "/Script/Engine.KismetMathLibrary.SelectColor"
FN_SUB = "/Script/Engine.KismetMathLibrary.Subtract_DoubleDouble"
FN_VIEWPORT = "/Script/UMG.WidgetLayoutLibrary.GetViewportSize"
NODE_CAST_WEAPON = "Utilities|Casting|CastToBP_WeaponComponent"

# --- reticle, nailed to the centre of the viewport ----------------------------
# The aim ray is cast from the camera along its forward vector, which is the
# centre of the screen, so the centre is where the shot goes. Drawing it at the
# projected impact point instead was tried and reverted: that point is a world
# position on whatever surface the ray lands on, so the crosshair slid around
# under its own parallax and could not be aimed with. Only the colour still
# reflects the world -- red when the muzzle's line is blocked.
RETICLE_GAP = 7.0          # pixels of clear space around the centre dot
# ...plus the held gun's accuracy cloud, in pixels: the weapon component's
# ReticleSpread (tan of the cloud over tan of half the field of view) times
# half the viewport's width. So the ticks sit where the cloud's edge crosses
# the screen, and down the sights (no cloud) they close to RETICLE_GAP. Capped
# so a hip-fired sniper on a small window cannot throw them off screen.
RETICLE_SPREAD_MAX = 240.0
RETICLE_ARM = 11.0         # length of each of the four ticks
RETICLE_THICK = 2.0
RETICLE_DOT = 3.0
COL_RETICLE = "(R=0.960000,G=0.960000,B=0.970000,A=0.900000)"
COL_RETICLE_BLOCKED = "(R=0.950000,G=0.250000,B=0.200000,A=0.950000)"


def _author_reticle(ed, x0, y0, in_execs):
    """A crosshair pinned to the centre of the screen.

    It was briefly drawn at the projected impact point instead, on the theory
    that a reticle should sit on the thing about to be hit. In practice that
    reticle will not hold still: the impact point is a world position on
    whatever surface the ray lands on, so it slides as the player walks, jumps
    between a near trunk and the ground behind it, and shifts under its own
    parallax. A crosshair that moves is unusable -- you aim with it by holding
    it still and turning the camera, which only works if it is nailed down.

    Fixed at the centre is also *correct* here, not a compromise: the aim ray is
    cast from the camera along its forward vector, and the camera's forward
    vector is the centre of the screen. AimPoint is still where the shot lands;
    the reticle just no longer tries to follow it around.

    What is kept from the impact point is the one thing worth showing: the
    crosshair turns red when the muzzle's line is blocked short of what the
    camera can see, so a barrel against a tree reads as such without moving.

    The gap is not fixed: the four ticks stand off by the held gun's accuracy
    cloud on screen (ReticleSpread x half the width, see RETICLE_SPREAD_MAX),
    so what the reticle encloses is where the shot can land -- wide from the
    hip, tighter crouched or prone, closed down the sights.

    A scoped weapon draws _author_scope instead of this, never as well as it:
    the scope has a reticle of its own and two crosshairs on one centre is the
    sort of thing that reads as a bug.

    Down the sights the crosshair is not drawn either: the camera looks along
    the gun's own sight line (combat sights.py), so the front sight's tip is
    the middle of the view and the crosshair only covered it. It goes once
    the camera is nearly on the sights (SightSeat past RETICLE_HIDE_SEAT), so
    the sights come up to meet it, and stays in debug mode (DebugOn), where
    it shows that the two agree. The hip and the shoulder aim keep it.
    """
    made = []

    def keep(n):
        made.append(n)
        return n

    pawn = keep(_at(_node(ed, FN_GET_PLAYER_PAWN), x0, y0 + 300))
    _set(pawn, "PlayerIndex", 0)
    comp = keep(_at(_node(ed, FN_GET_COMP), x0 + 240, y0 + 300))
    _connect(_pin(pawn, "ReturnValue", is_input=False), _pin(comp, "self"))
    _pin(comp, "ComponentClass").set_pin_value(WEAPON_COMP_CLASS_PATH)

    cast = keep(_at(_palette(ed, NODE_CAST_WEAPON), x0 + 500, y0))
    _connect(_pin(comp, "ReturnValue", is_input=False), _pin(cast, "Object"))
    for e in in_execs:
        _connect(e, _pin(cast, "execute"))
    as_weapon = _loose_pin(cast, "AsBPWeaponComponent", is_input=False)

    valid = keep(_at(ed.add_get_member_variable_node("AimValid",
                                                     WEAPON_COMP_CLASS_PATH),
                     x0 + 760, y0 + 300))
    _connect(as_weapon, _pin(valid, "self"))
    blocked = keep(_at(ed.add_get_member_variable_node("AimBlocked",
                                                       WEAPON_COMP_CLASS_PATH),
                       x0 + 760, y0 + 420))
    _connect(as_weapon, _pin(blocked, "self"))

    # Empty hands draw nothing: a reticle with no weapon behind it points at a
    # shot that cannot be taken.
    armed = keep(_at(ed.add_branch_node(), x0 + 1020, y0))
    _connect(_pin(valid, "AimValid", is_input=False), _pin(armed, "Condition"))
    _connect(BEL.find_then_pin(cast), _pin(armed, "execute"))

    # Centre from the viewport, not from a constant: DrawRect works in canvas
    # pixels, which change with the window.
    size = keep(_at(_node(ed, FN_VIEWPORT), x0 + 1020, y0 + 560))
    wh = keep(_at(_node(ed, FN_BREAK_V2D), x0 + 1260, y0 + 560))
    _connect(_pin(size, "ReturnValue", is_input=False), _loose_pin(wh, "InVec"))

    def half(axis, py):
        n = keep(_at(_node(ed, FN_MUL), x0 + 1500, py))
        _connect(_loose_pin(wh, axis, is_input=False), _pin(n, "A"))
        _set(n, "B", 0.5)
        return _pin(n, "ReturnValue", is_input=False)

    cx = half("X", y0 + 560)
    cy = half("Y", y0 + 700)

    # Held is read here rather than in _author_scope because both arms of the
    # branch below are downstream of it, and because AimValid is exactly the
    # weapon component's answer to "is Held valid" -- it is set false on the
    # empty-handed path, so under `armed` this Get cannot be an Accessed None.
    held = keep(_at(ed.add_get_member_variable_node("Held",
                                                    WEAPON_COMP_CLASS_PATH),
                    x0 + 760, y0 + 540))
    _connect(as_weapon, _pin(held, "self"))
    held_out = _pin(held, "Held", is_input=False)
    scoped = keep(_at(ed.add_get_member_variable_node("Scoped", ITEM_CLASS_PATH),
                      x0 + 1020, y0 + 540))
    _connect(held_out, _pin(scoped, "self"))
    glass = keep(_at(ed.add_branch_node(), x0 + 1260, y0))
    _connect(_author_scope_gate(ed, as_weapon,
                                _pin(scoped, "Scoped", is_input=False), keep,
                                x0 + 1020, y0 + 1000),
             _pin(glass, "Condition"))
    _connect(BEL.find_then_pin(armed), _pin(glass, "execute"))

    scoped_tail = _author_scope(ed, x0 + 4000, y0, BEL.find_then_pin(glass),
                                as_weapon, held_out, cx, cy,
                                _loose_pin(wh, "Y", is_input=False))

    colour = keep(_at(_node(ed, FN_SELECT_COLOR), x0 + 1500, y0 + 840))
    _set(colour, "A", COL_RETICLE_BLOCKED)
    _set(colour, "B", COL_RETICLE)
    _connect(_pin(blocked, "AimBlocked", is_input=False), _pin(colour, "bPickA"))
    colour_out = _pin(colour, "ReturnValue", is_input=False)

    def offset(src, by, px, py):
        """centre + by, as a node -- DrawRect wants the corner, we have the middle."""
        n = keep(_at(_node(ed, FN_ADD), px, py))
        _connect(src, _pin(n, "A"))
        _set(n, "B", by)
        return _pin(n, "ReturnValue", is_input=False)

    # The cloud's radius on screen, and the centre pushed out by it each way
    # for the four ticks. The dot stays on the true centre.
    reticle_spread = keep(_at(ed.add_get_member_variable_node(
        "ReticleSpread", WEAPON_COMP_CLASS_PATH), x0 + 1260, y0 + 1300))
    _connect(as_weapon, _pin(reticle_spread, "self"))
    spread_px = keep(_at(_node(ed, FN_MUL), x0 + 1500, y0 + 1300))
    _connect(_pin(reticle_spread, "ReticleSpread", is_input=False), _pin(spread_px, "A"))
    _connect(cx, _pin(spread_px, "B"))
    # FMin, not FClamp: ReticleSpread is never negative, and the verifier
    # reads every FClamp on this HUD as a settings slider.
    capped = keep(_at(_node(ed, FN_FMIN), x0 + 1740, y0 + 1300))
    _connect(_pin(spread_px, "ReturnValue", is_input=False), _pin(capped, "A"))
    _set(capped, "B", RETICLE_SPREAD_MAX)
    capped_out = _pin(capped, "ReturnValue", is_input=False)

    def pushed(centre, fn, py):
        n = keep(_at(_node(ed, fn), x0 + 1980, py))
        _connect(centre, _pin(n, "A"))
        _connect(capped_out, _pin(n, "B"))
        return _pin(n, "ReturnValue", is_input=False)

    left_x, right_x = pushed(cx, FN_SUB, y0 + 1200), pushed(cx, FN_ADD, y0 + 1320)
    top_y, bottom_y = pushed(cy, FN_SUB, y0 + 1440), pushed(cy, FN_ADD, y0 + 1560)

    half_t = RETICLE_THICK / 2.0
    half_d = RETICLE_DOT / 2.0
    inner = RETICLE_GAP
    outer = RETICLE_GAP + RETICLE_ARM
    # (name, x from, dx, y from, dy, w, h) of each piece: an offset from the
    # centre, or from the centre pushed out by the cloud.
    pieces = (
        ("left",   left_x,  -outer,   cy,       -half_t,  RETICLE_ARM,   RETICLE_THICK),
        ("right",  right_x,  inner,   cy,       -half_t,  RETICLE_ARM,   RETICLE_THICK),
        ("top",    cx,      -half_t,  top_y,    -outer,   RETICLE_THICK, RETICLE_ARM),
        ("bottom", cx,      -half_t,  bottom_y,  inner,   RETICLE_THICK, RETICLE_ARM),
        ("dot",    cx,      -half_d,  cy,       -half_d,  RETICLE_DOT,   RETICLE_DOT),
    )

    # Down the sights, outside debug mode, the gun's own sights are the
    # reticle. Under `armed`, so the component is valid.
    seat = keep(_at(ed.add_get_member_variable_node(SEAT_VAR, WEAPON_COMP_CLASS_PATH),
                    x0 + 1260, y0 - 420))
    _connect(as_weapon, _pin(seat, "self"))
    on_sights = keep(_at(_node(ed, FN_GREATER), x0 + 1500, y0 - 420))
    _connect(_pin(seat, SEAT_VAR, is_input=False), _pin(on_sights, "A"))
    _set(on_sights, "B", RETICLE_HIDE_SEAT)
    debug = keep(_at(ed.add_get_member_variable_node("DebugOn"), x0 + 1260, y0 - 280))
    plain = keep(_at(_node(ed, FN_NOT), x0 + 1500, y0 - 280))
    _connect(_pin(debug, "DebugOn", is_input=False), _pin(plain, "A"))
    irons = keep(_at(_node(ed, FN_AND), x0 + 1740, y0 - 360))
    _connect(_pin(on_sights, "ReturnValue", is_input=False), _pin(irons, "A"))
    _connect(_pin(plain, "ReturnValue", is_input=False), _pin(irons, "B"))
    hidden = keep(_at(ed.add_branch_node(), x0 + 1520, y0))
    _connect(_pin(irons, "ReturnValue", is_input=False), _pin(hidden, "Condition"))
    _connect(BEL.find_else_pin(glass), _pin(hidden, "execute"))

    flow = BEL.find_else_pin(hidden)
    for i, (name, fx, dx, fy, dy, w, h) in enumerate(pieces):
        px = x0 + 1800 + i * 260
        r = keep(_at(_node(ed, FN_DRAW_RECT), px, y0))
        _set(r, "ScreenW", w)
        _set(r, "ScreenH", h)
        _connect(colour_out, _pin(r, "RectColor"))
        _connect(offset(fx, dx, px, y0 + 300), _pin(r, "ScreenX"))
        _connect(offset(fy, dy, px, y0 + 440), _pin(r, "ScreenY"))
        _connect(flow, _pin(r, "execute"))
        flow = BEL.find_then_pin(r)

    ed.add_comment_to_nodes(
        "Reticle, nailed to the centre of the viewport. The aim ray is cast "
        "along the camera's forward vector, and that *is* the centre of the "
        "screen, so this is where the shot goes -- it turns red when the muzzle "
        "cannot reach what the camera is looking at. The ticks stand off by the "
        "held gun's accuracy cloud (ReticleSpread x half the width), so the "
        "gap is where the shot can land: wide at the hip, closed down the "
        "sights. With the camera on the gun's sights (SightSeat past "
        f"{RETICLE_HIDE_SEAT:g}) it is drawn only in debug mode: the front "
        "sight is the middle of the view there.",
        made)

    return (flow,
            BEL.find_then_pin(hidden),
            scoped_tail,
            BEL.find_else_pin(armed),
            _pin(cast, "CastFailed", is_input=False))
