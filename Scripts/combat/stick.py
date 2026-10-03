"""BP_Stick: a stick that takes fire from a campfire and is a torch until it
burns out, the sixth thing the player starts with.

A stick IS a BP_WeaponItem, for the reason the axe and the matches are: the
bag, Q, G, E, the throw, the profile and the HUD strip are keyed on that
class. It is flagged `Burns`, which the use key's stage asks about
(weapon_component/torch.py): used within reach of a campfire it is `Lit`
until `BurnOutTime`, and a lit one in hand is raised in its `UsePose` while
the key is held. It is neither Melee nor Consumable, so the fire key runs the
guns' path over nothing, as it does for wood.

    [Tick] --> Lit AND now >= BurnOutTime --> Lit = false
           --> the bare stick shows while not Lit; the burning one and its
               glow while Lit

The stick burns on its own Tick, not the weapon component's, so it burns down
in the bag and on the ground as it does in the hand, and one thrown or
dropped lights the ground where it lies. Burnt out it is a stick again. The
three visibilities are written every frame from the one flag: each is a
no-op when nothing changed, and there is no edge to miss. In the bag the
actor is hidden (inventory.py), which hides the fire and its light with it.

THE MODEL
---------
SM_WoodenTorch and SM_WoodenTorch_Fire (CC0, Quaternius's Survival Pack,
imported by asset_pipeline/import_quaternius.py): a club with a wrapped head,
standing on its end, and the same club with flames standing on it. Both are
hung on Body in the one place and one is shown. The pack is at no one size
(weapon_models.py): at STICK_SCALE the stick is 48 cm, 64 with its flames.
Every number below is measured off the mesh's vertices, on the scaled mesh,
in cm. It is held upright in the fist by the stretch of handle round the
mesh's origin, in A_HoldTorch (hold_pose.py).
"""

import unreal

from combat.chop_tuning import CHOPS_VAR
from combat.log import _log
from uebp.graph import (
    BEL, BGE, _add_component, _apply_defaults, _component_object, _connect,
    _create_blueprint, _drop_components, _events, _find_handle, _must_load, _node, _pin,
    _rot, _set, else_, then)
from uebp.layout import arrange
from combat.grip import _grip_location, _grip_rotation
from combat.light_tuning import LIGHTS_VAR
from combat.nodes import FN_AND, FN_GE_FF, FN_NOT, FN_TIME_SECONDS
from combat.paths import (
    CUBE, HOLD_TORCH_ANIM_PATH, MAT_METAL, STICK_BP_PATH, WARD_TORCH_ANIM_PATH,
)
from combat.seat_tuning import HAS_SIGHTS_VAR
from combat.torch_tuning import (
    BURN_OUT_VAR, BURNS_VAR, LIT_VAR, STICK_BURN_S, USE_POSE_VAR,
)
from combat.tuning import COMBAT
from combat.weapon_items import build_model
from combat.weapon_specs import _weapon_icon
from item_icons.items import ICON_TINT

FN_SET_VISIBILITY = "/Script/Engine.SceneComponent.SetVisibility"

STICK_MESH = "/Game/Sourced/Quaternius/Survival/SM_WoodenTorch"
STICK_LIT_MESH = "/Game/Sourced/Quaternius/Survival/SM_WoodenTorch_Fire"
STICK_DISPLAY = "Stick"
STICK_SCALE = 0.18

# On the scaled mesh, in its own frame (cm): the stretch of handle the fist
# closes on, and where the flames stand (the glow's place).
HANDLE_CENTRE = (0.2, 0.0, 0.9)
HANDLE_SIZE = (3.8, 3.2, 12.0)
FLAME_CENTRE = (0.0, 0.0, 44.0)

# The component names: the bare stick, the burning one, its light.
MODEL, FLAME, GLOW = "Model", "Flame", "Glow"
GLOW_COLOUR = (255, 140, 50)        # sRGB bytes: firelight, the campfire's
GLOW_INTENSITY = 1500.0
GLOW_RADIUS_CM = 700.0


def _placed(point):
    return tuple(p - c for p, c in zip(point, HANDLE_CENTRE))


def stick_model():
    """The two models, upright, placed so the gripped handle's centre is the
    item's origin."""
    return tuple((name, mesh, _placed((0.0, 0.0, 0.0)), _rot(), (STICK_SCALE,) * 3)
                 for name, mesh in ((MODEL, STICK_MESH), (FLAME, STICK_LIT_MESH)))


def stick_outline():
    """Grip: the handle in the fist, in the item's frame, the form the grip
    solve reads (weapon_models.py says why an outline). Never built."""
    return (("Grip", CUBE, (0.0, 0.0, 0.0), _rot(),
             tuple(s / 100.0 for s in HANDLE_SIZE), MAT_METAL),)


def _build_model(bp):
    """Both models on Body and the glow at the flames; the burning one and
    the glow start hidden."""
    _drop_components(bp, {GLOW})
    build_model(bp, stick_model())
    body = _find_handle(bp, "Body")
    glow = _component_object(_add_component(bp, body, unreal.PointLightComponent, GLOW))
    glow.set_editor_property("relative_location", unreal.Vector(*_placed(FLAME_CENTRE)))
    glow.set_editor_property("intensity", GLOW_INTENSITY)
    glow.set_editor_property("light_color", unreal.Color(
        r=GLOW_COLOUR[0], g=GLOW_COLOUR[1], b=GLOW_COLOUR[2], a=255))
    glow.set_editor_property("attenuation_radius", GLOW_RADIUS_CM)
    glow.set_editor_property("cast_shadows", False)
    glow.set_editor_property("visible", False)
    flame = _component_object(_find_handle(bp, FLAME))
    flame.set_editor_property("visible", False)


def _author_burn(ed, tick):
    """Tick: put a spent fire out, then show the stick as Lit says."""
    def get(name):
        return _pin(ed.add_get_member_variable_node(name), name, is_input=False)

    def out(n):
        return _pin(n, "ReturnValue", is_input=False)

    now = _node(ed, FN_TIME_SECONDS)
    spent = _node(ed, FN_GE_FF)
    _connect(out(now), _pin(spent, "A"))
    _connect(get(BURN_OUT_VAR), _pin(spent, "B"))
    over = _node(ed, FN_AND)
    _connect(get(LIT_VAR), _pin(over, "A"))
    _connect(out(spent), _pin(over, "B"))
    burnt = ed.add_branch_node()
    _connect(out(over), _pin(burnt, "Condition"))
    _connect(then(tick), _pin(burnt, "execute"))
    dark = ed.add_set_member_variable_node(LIT_VAR)
    _set(dark, LIT_VAR, "false")
    _connect(then(burnt), _pin(dark, "execute"))

    # Read after the write above: a pure Get is pulled when its reader runs.
    lit = get(LIT_VAR)
    unlit = _node(ed, FN_NOT)
    _connect(lit, _pin(unlit, "A"))
    made = [burnt, dark]
    prev = (then(dark), else_(burnt))
    for name, shown in ((MODEL, out(unlit)), (FLAME, lit), (GLOW, lit)):
        show = _node(ed, FN_SET_VISIBILITY)
        _connect(get(name), _pin(show, "self"))
        _connect(shown, _pin(show, "bNewVisibility"))
        for e in prev:
            _connect(e, _pin(show, "execute"))
        prev = (then(show),)
        made.append(show)
    ed.add_comment_to_nodes(
        f"A lit stick burns out at {BURN_OUT_VAR} (the use key's stage wrote "
        f"it, {STICK_BURN_S:g} s on from the campfire that lit it) and is a "
        "stick again. The bare model shows while it is not Lit; the burning "
        "one and the glow while it is.", made)


def build_stick(item_bp, rebuild=True):
    """BP_Stick: the two models and the glow on Body, the burn on its Tick,
    and the base class's defaults for it."""
    bp = _create_blueprint(STICK_BP_PATH, BEL.generated_class(item_bp))
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    # The graph is wiped before the model is rebuilt: its nodes name the
    # components, and a rebuild drops and re-adds those (the compile below
    # failed on a second build with last build's graph still reading them).
    tick, _begin = _events(ed, rebuild)
    _build_model(bp)
    # The components are variables of the class only once it has compiled.
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{STICK_BP_PATH} failed to compile")
    _author_burn(ed, tick)
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{STICK_BP_PATH} failed to compile")
    aim = HOLD_TORCH_ANIM_PATH
    grip_rot = _grip_rotation(aim)
    _apply_defaults(bp, {
        "DisplayName": STICK_DISPLAY,
        BURNS_VAR: True,
        LIT_VAR: False,
        BURN_OUT_VAR: 0.0,
        LIGHTS_VAR: False,
        "Melee": False,
        "Consumable": False,
        CHOPS_VAR: False,
        HAS_SIGHTS_VAR: False,
        "Dropped": False,
        # Nothing to fire: the guns' path runs over no pellets and no sound.
        "UsesAmmo": False,
        "Automatic": False,
        "Damage": 0.0,
        "PelletCount": 0,
        "MagazineSize": 0,
        "Loaded": 0,
        "Reserve": 0,
        "InfiniteReserve": False,
        "NextFireTime": 0.0,
        "MuzzleOffset": unreal.Vector(0.0, 0.0, 0.0),
        "GripLocation": unreal.Vector(*_grip_location(aim, grip_rot, stick_outline())),
        "GripRotation": grip_rot,
        "SlotColor": unreal.LinearColor(*ICON_TINT, 1.0),
        # Not 1.0, for the knife's reason: right-click still aims.
        "AdsZoom": float(COMBAT.ads_zoom_irons),
        "Scoped": False,
        "RecoilPitch": 0.0,
        "ShotVolume": 0.0,
        "TwoHanded": False,
        "Icon": _weapon_icon(STICK_DISPLAY),
        "AimPose": _must_load(aim),
        USE_POSE_VAR: _must_load(WARD_TORCH_ANIM_PATH),
    })
    _log(f"built {STICK_BP_PATH} ({STICK_MESH.rsplit('/', 1)[-1]} at {STICK_SCALE}, "
         f"burning {STICK_BURN_S:g} s once lit)")
    return bp
