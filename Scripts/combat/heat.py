"""The item's side of a heated blade: the glow, and the Tick that cools it.

An item that Heats (the knife, the axe: heat_tuning.py) is made Hot by the
interact key at a campfire (weapon_component/heat.py), which writes Hot and
CoolTime on it. Everything that follows from those two is here, on the item's
own Tick, so a hot blade cools and glows the same in the hand, in the bag
(hidden: inventory.py) and on the ground, as a lit stick burns (stick.py):

    [Tick] --> Hot AND now >= CoolTime --> Hot = false
           --> Hot: the model wears HeatMaterial as its overlay; else none
           --> HeatGlow shows while Hot

The overlay and the light are written every frame from the one flag: each
is a no-op when nothing changed, and there is no edge to miss.

THE GLOW
--------
M_HotMetal is an unlit additive overlay, so it only adds light to what the
model already draws and adds nothing where its mask is zero. The mask is the
model's own space: how far a point lies past `Start` along `Axis`, over
`Fade`. So the blade glows and the handle does not, with no second mesh and
no edit to the model's materials. Each item has an instance (MI_Hot<Item>)
carrying where its metal starts, measured off its mesh like the rest of its
numbers (knife.py, axe.py).
"""

import unreal

from combat.log import _log
from uebp.graph import (
    BEL, BGE, _add_component, _assets, _component_object, _connect, _drop_components,
    _events, _find_handle, _must_load, _node, _pin, _set, else_, then)
from uebp.layout import arrange
from combat.heat_tuning import (
    COOL_VAR, HEAT_GLOW, HEAT_GLOW_COLOUR, HEAT_GLOW_INTENSITY,
    HEAT_GLOW_RADIUS_CM, HEAT_MATERIAL_VAR, HEAT_S, HOT_AXIS_PARAM, HOT_COLOUR,
    HOT_EMISSIVE, HOT_FADE_PARAM, HOT_START_PARAM, HOT_VAR, MODEL,
)
from combat.nodes import FN_AND, FN_GE_FF, FN_TIME_SECONDS
from combat.paths import MAT_HOT_METAL
from combat.weapon_items import build_model

FN_SET_OVERLAY = "/Script/Engine.MeshComponent.SetOverlayMaterial"
FN_SET_VISIBILITY = "/Script/Engine.SceneComponent.SetVisibility"


def build_hot_material():
    """M_HotMetal, created or re-authored in place (materials.py says why)."""
    eas = _assets()
    mel = unreal.MaterialEditingLibrary
    package_path, name = MAT_HOT_METAL.rsplit("/", 1)
    if eas.does_asset_exist(MAT_HOT_METAL):
        mat = _must_load(MAT_HOT_METAL)
        mel.delete_all_material_expressions(mat)
    else:
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, package_path, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    # The knife is a skeletal mesh. The editor sets this flag itself the first
    # time a material is put on one; a game cannot, and draws the default
    # material instead.
    mat.set_editor_property("used_with_skeletal_mesh", True)

    def make(cls, x, y):
        return mel.create_material_expression(mat, cls, x, y)

    def join(a, b, pin):
        if not mel.connect_material_expressions(a, "", b, pin):
            raise RuntimeError(f"{MAT_HOT_METAL}: could not wire {pin} of "
                               f"{b.get_class().get_name()}")

    world = make(unreal.MaterialExpressionWorldPosition, -1700, 0)
    local = make(unreal.MaterialExpressionTransformPosition, -1450, 0)
    local.set_editor_property(
        "transform_source_type",
        unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD)
    local.set_editor_property(
        "transform_type",
        unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL)
    join(world, local, "")
    axis = make(unreal.MaterialExpressionVectorParameter, -1450, 200)
    axis.set_editor_property("parameter_name", HOT_AXIS_PARAM)
    axis.set_editor_property("default_value", unreal.LinearColor(0.0, 0.0, 1.0, 0.0))
    along = make(unreal.MaterialExpressionDotProduct, -1150, 0)
    join(local, along, "A")
    join(axis, along, "B")
    start = make(unreal.MaterialExpressionScalarParameter, -1150, 200)
    start.set_editor_property("parameter_name", HOT_START_PARAM)
    start.set_editor_property("default_value", 0.0)
    past = make(unreal.MaterialExpressionSubtract, -900, 0)
    join(along, past, "A")
    join(start, past, "B")
    fade = make(unreal.MaterialExpressionScalarParameter, -900, 200)
    fade.set_editor_property("parameter_name", HOT_FADE_PARAM)
    fade.set_editor_property("default_value", 1.0)
    share = make(unreal.MaterialExpressionDivide, -650, 0)
    join(past, share, "A")
    join(fade, share, "B")
    mask = make(unreal.MaterialExpressionSaturate, -400, 0)
    join(share, mask, "")
    colour = make(unreal.MaterialExpressionConstant3Vector, -400, 200)
    colour.set_editor_property("constant", unreal.LinearColor(
        *(c * HOT_EMISSIVE for c in HOT_COLOUR), 1.0))
    glow = make(unreal.MaterialExpressionMultiply, -150, 0)
    join(mask, glow, "A")
    join(colour, glow, "B")
    if not mel.connect_material_property(
            glow, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR):
        raise RuntimeError(f"{MAT_HOT_METAL}: could not wire the emissive colour")
    mel.delete_unused_expressions(mat)
    mel.recompile_material(mat)
    eas.save_loaded_asset(mat)
    _log(f"built {MAT_HOT_METAL}")
    return mat


def build_hot_instance(path, axis, start, fade):
    """An item's instance of M_HotMetal: its metal lies past ``start`` along
    ``axis`` in its model's own space, the glow fading in over ``fade``."""
    eas = _assets()
    mel = unreal.MaterialEditingLibrary
    package_path, name = path.rsplit("/", 1)
    if eas.does_asset_exist(path):
        mi = _must_load(path)
    else:
        mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, package_path, unreal.MaterialInstanceConstant,
            unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, _must_load(MAT_HOT_METAL))
    mel.set_material_instance_vector_parameter_value(
        mi, HOT_AXIS_PARAM, unreal.LinearColor(*axis, 0.0))
    mel.set_material_instance_scalar_parameter_value(mi, HOT_START_PARAM, start)
    mel.set_material_instance_scalar_parameter_value(mi, HOT_FADE_PARAM, fade)
    mel.update_material_instance(mi)
    eas.save_loaded_asset(mi)
    _log(f"built {path} (hot past {start:g} along {axis}, over {fade:g})")
    return mi


def _author_cooling(ed, tick):
    """Tick: a blade whose time is up is cold, then show it as Hot says."""
    def get(name):
        return _pin(ed.add_get_member_variable_node(name), name, is_input=False)

    def out(n):
        return _pin(n, "ReturnValue", is_input=False)

    now = _node(ed, FN_TIME_SECONDS)
    spent = _node(ed, FN_GE_FF)
    _connect(out(now), _pin(spent, "A"))
    _connect(get(COOL_VAR), _pin(spent, "B"))
    over = _node(ed, FN_AND)
    _connect(get(HOT_VAR), _pin(over, "A"))
    _connect(out(spent), _pin(over, "B"))
    cooled = ed.add_branch_node()
    _connect(out(over), _pin(cooled, "Condition"))
    _connect(then(tick), _pin(cooled, "execute"))
    cold = ed.add_set_member_variable_node(HOT_VAR)
    _set(cold, HOT_VAR, "false")
    _connect(then(cooled), _pin(cold, "execute"))

    # Read after the write above: a pure Get is pulled when its reader runs.
    hot = get(HOT_VAR)
    which = ed.add_branch_node()
    _connect(hot, _pin(which, "Condition"))
    for e in (then(cold), else_(cooled)):
        _connect(e, _pin(which, "execute"))
    wear = _node(ed, FN_SET_OVERLAY)
    _connect(get(MODEL), _pin(wear, "self"))
    _connect(get(HEAT_MATERIAL_VAR), _pin(wear, "NewOverlayMaterial"))
    _connect(then(which), _pin(wear, "execute"))
    # Its material pin is left unconnected: no overlay.
    bare = _node(ed, FN_SET_OVERLAY)
    _connect(get(MODEL), _pin(bare, "self"))
    _connect(else_(which), _pin(bare, "execute"))
    show = _node(ed, FN_SET_VISIBILITY)
    _connect(get(HEAT_GLOW), _pin(show, "self"))
    _connect(hot, _pin(show, "bNewVisibility"))
    for e in (then(wear), then(bare)):
        _connect(e, _pin(show, "execute"))
    ed.add_comment_to_nodes(
        f"A hot blade is cold again at {COOL_VAR} (the interact key at a "
        f"campfire wrote it, {HEAT_S:g} s on: weapon_component/heat.py). "
        f"While it is {HOT_VAR} the model wears {HEAT_MATERIAL_VAR} as its "
        f"overlay and {HEAT_GLOW} is lit.",
        [cooled, cold, which, wear, bare, show])


def build_heated_model(bp, model, glow_at):
    """An item that Heats: its model on Body, the light of its hot metal at
    ``glow_at`` (the item's frame, cm), and the cooling on its Tick. Compiles
    the Blueprint; the caller writes the defaults (Heats, HeatMaterial)."""
    path = bp.get_path_name()
    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    # The graph is wiped before the model is rebuilt, for stick.py's reason:
    # its nodes name the components, which a rebuild drops and re-adds.
    tick, _begin = _events(ed, True)
    _drop_components(bp, {HEAT_GLOW})
    build_model(bp, model)
    body = _find_handle(bp, "Body")
    glow = _component_object(_add_component(bp, body, unreal.PointLightComponent,
                                            HEAT_GLOW))
    glow.set_editor_property("relative_location", unreal.Vector(*glow_at))
    glow.set_editor_property("intensity", HEAT_GLOW_INTENSITY)
    glow.set_editor_property("light_color", unreal.Color(
        r=HEAT_GLOW_COLOUR[0], g=HEAT_GLOW_COLOUR[1], b=HEAT_GLOW_COLOUR[2], a=255))
    glow.set_editor_property("attenuation_radius", HEAT_GLOW_RADIUS_CM)
    glow.set_editor_property("cast_shadows", False)
    glow.set_editor_property("visible", False)
    # The components are variables of the class only once it has compiled.
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{path} failed to compile")
    _author_cooling(ed, tick)
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{path} failed to compile")
