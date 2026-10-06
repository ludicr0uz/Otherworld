"""The glimmer over an item lying on the ground: MPC_ItemGlimmer, M_ItemGlimmer,
the sprite component an item carries, and the Tick fragment that shows it.

    MPC_ItemGlimmer.Highlight   1 = every glimmer shines, 0 = none: the one
                                switch, written by the day/night cycle from
                                the WORLD SETTINGS tab's row
                                (world/item_highlight.py)
    M_ItemGlimmer               unlit, additive: a four-rayed star that
                                appears and is gone every GLIMMER_PERIOD_S,
                                each item out of step with the next (the phase
                                is its position), only near the camera
                                (GLIMMER_NEAR_CM..GLIMMER_FAR_CM), times
                                Highlight
    Glimmer                     a MaterialBillboardComponent on BP_WeaponItem's
                                Body, hidden as built
    author_glimmer              Tick: Glimmer.SetVisibility(Dropped)

Dropped is written in half a dozen places (the drop, the throw's landing, a
kill's gun, the pick-up, wearing), and on some items by default. So nothing
there is told about the glimmer: the item shows it by its own flag, every
Tick. SetVisibility does nothing when nothing changed.

A child with a Tick of its own (heat.py's blades, stick.py) overrides the
base's, so each of those calls author_glimmer at the tail of its own chain;
verify/glimmer.py finds a child that forgot.

The sprite is a component of its own, not an overlay material on the model:
the overlay slot is the hot blade's (heat.py), and a sprite pulled towards
the camera still shows over an item lying in grass.
"""

import unreal

from combat import item_vars as IV
from combat.item_world import author_world_view
from combat.glimmer_tuning import (
    GLIMMER, GLIMMER_COLOUR, GLIMMER_EMISSIVE, GLIMMER_FAR_CM, GLIMMER_HALF_SIZE_CM,
    GLIMMER_LIFT_CM, GLIMMER_NEAR_CM, GLIMMER_PERIOD_S, GLIMMER_PULL_CM,
    GLIMMER_RAY_THIN, GLIMMER_REST,
    GLIMMER_SHARPNESS, HIGHLIGHT_DEFAULT, MAT_ITEM_GLIMMER, MPC_ITEM_GLIMMER,
    MPC_NAME, PARAM_HIGHLIGHT,
)
from combat.log import _log
from uebp.graph import (
    _add_component, _assets, _component_object, _connect, _drop_components, _must_load,
    _node, _pin, then)
from uebp.nodes.actor import FN_SET_VISIBILITY

MEL = unreal.MaterialEditingLibrary

# UV 0..1 across the sprite, T seconds, P the sprite's place in the world,
# On the collection's Highlight, C the camera's place in the world.
GLIMMER_INPUTS = ("UV", "T", "P", "On", "C")
GLIMMER_HLSL = f"""
float2 c = abs(UV - 0.5) * 2.0;
float core = pow(saturate(1.0 - length(c)), 2.0);
float rayX = pow(saturate(1.0 - c.x), 2.0) * pow(saturate(1.0 - c.y * {GLIMMER_RAY_THIN:.4f}), 2.0);
float rayY = pow(saturate(1.0 - c.y), 2.0) * pow(saturate(1.0 - c.x * {GLIMMER_RAY_THIN:.4f}), 2.0);
float star = saturate(core + rayX + rayY);
float phase = dot(P, float3(0.0131, 0.0173, 0.0091));
float beat = sin(T * {6.283185 / GLIMMER_PERIOD_S:.5f} + phase) * 0.5 + 0.5;
float flash = lerp({GLIMMER_REST:.4f}, 1.0, pow(beat, {GLIMMER_SHARPNESS:.4f}));
float near = 1.0 - smoothstep({GLIMMER_NEAR_CM:.1f}, {GLIMMER_FAR_CM:.1f}, length(C - P));
return float3({GLIMMER_COLOUR[0]:.4f}, {GLIMMER_COLOUR[1]:.4f}, {GLIMMER_COLOUR[2]:.4f})
    * (star * flash * near * saturate(On) * {GLIMMER_EMISSIVE:.4f});
"""
# The Custom node and its inputs (the camera's place is the offset's), the exposure's inverse, and the three
# of the offset (the way to the camera, the pull, the lift) with their sums.
EXPRESSION_COUNT = 14


def ensure_collection():
    """MPC_ItemGlimmer with its one scalar at its default. Returns it."""
    eas = _assets()
    if eas.does_asset_exist(MPC_ITEM_GLIMMER):
        mpc = _must_load(MPC_ITEM_GLIMMER)
    else:
        package_path = MPC_ITEM_GLIMMER.rsplit("/", 1)[0]
        mpc = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            MPC_NAME, package_path, unreal.MaterialParameterCollection,
            unreal.MaterialParameterCollectionFactoryNew())
    have = {str(p.get_editor_property("parameter_name")): p
            for p in mpc.get_editor_property("scalar_parameters")}
    # Keep an existing parameter's Id: the material refers to it by that.
    p = have.get(PARAM_HIGHLIGHT) or unreal.CollectionScalarParameter()
    p.set_editor_property("parameter_name", PARAM_HIGHLIGHT)
    p.set_editor_property("default_value", HIGHLIGHT_DEFAULT)
    mpc.set_editor_property("scalar_parameters", [p])
    eas.save_loaded_asset(mpc, only_if_is_dirty=False)
    return mpc


def _material():
    """M_ItemGlimmer emptied of expressions, or created."""
    eas = _assets()
    if eas.does_asset_exist(MAT_ITEM_GLIMMER):
        mat = _must_load(MAT_ITEM_GLIMMER)
        # One call deletes about half of them (world/sky_material.py).
        while MEL.get_num_material_expressions(mat):
            MEL.delete_all_material_expressions(mat)
        return mat
    package_path, name = MAT_ITEM_GLIMMER.rsplit("/", 1)
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, package_path, unreal.Material, unreal.MaterialFactoryNew())
    if not mat:
        raise RuntimeError(f"could not create {MAT_ITEM_GLIMMER}")
    return mat


def build_glimmer_material():
    """MPC_ItemGlimmer and M_ItemGlimmer, re-authored in place. Returns the
    material."""
    mpc = ensure_collection()
    mat = _material()
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("two_sided", True)

    def make(cls, x, y):
        e = MEL.create_material_expression(mat, cls, x, y)
        if not e:
            raise RuntimeError(f"{MAT_ITEM_GLIMMER}: could not create {cls.__name__}")
        return e

    def join(a, b, pin):
        if not MEL.connect_material_expressions(a, "", b, pin):
            raise RuntimeError(f"{MAT_ITEM_GLIMMER}: could not wire {pin!r} of "
                               f"{b.get_class().get_name()}")

    custom = make(unreal.MaterialExpressionCustom, -500, 0)
    custom.set_editor_property("code", GLIMMER_HLSL)
    custom.set_editor_property("description", "ItemGlimmer")
    custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    inputs = []
    for name in GLIMMER_INPUTS:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        inputs.append(ci)
    custom.set_editor_property("inputs", inputs)

    on = make(unreal.MaterialExpressionCollectionParameter, -900, 360)
    on.set_editor_property("collection", mpc)
    on.set_editor_property("parameter_name", PARAM_HIGHLIGHT)
    for name, source in (
            ("UV", make(unreal.MaterialExpressionTextureCoordinate, -900, 0)),
            ("T", make(unreal.MaterialExpressionTime, -900, 120)),
            ("P", make(unreal.MaterialExpressionObjectPositionWS, -900, 240)),
            ("On", on)):
        join(source, custom, name)

    # The exposure divided out: the same glint at noon and at midnight.
    steady = make(unreal.MaterialExpressionEyeAdaptationInverse, -200, 0)
    join(custom, steady, "LightValueInput")
    if not MEL.connect_material_property(
            steady, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR):
        raise RuntimeError(f"{MAT_ITEM_GLIMMER}: could not wire the emissive colour")

    # Up off the ground and towards the eye, in the world's frame: the item
    # may lie any way up.
    # (CameraVectorWS does not exist in a vertex shader.)
    camera = make(unreal.MaterialExpressionCameraPositionWS, -1400, 460)
    here = make(unreal.MaterialExpressionWorldPosition, -1400, 580)
    away = make(unreal.MaterialExpressionSubtract, -1150, 520)
    join(camera, away, "A")
    join(here, away, "B")
    # ...and how far off the item is: the glimmer shows only from near.
    join(camera, custom, "C")
    eye = make(unreal.MaterialExpressionNormalize, -900, 520)
    join(away, eye, "VectorInput")
    pull = make(unreal.MaterialExpressionConstant, -900, 640)
    pull.set_editor_property("r", GLIMMER_PULL_CM)
    toward = make(unreal.MaterialExpressionMultiply, -650, 520)
    join(eye, toward, "A")
    join(pull, toward, "B")
    lift = make(unreal.MaterialExpressionConstant3Vector, -650, 700)
    lift.set_editor_property("constant", unreal.LinearColor(0.0, 0.0, GLIMMER_LIFT_CM, 0.0))
    offset = make(unreal.MaterialExpressionAdd, -400, 520)
    join(toward, offset, "A")
    join(lift, offset, "B")
    if not MEL.connect_material_property(
            offset, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET):
        raise RuntimeError(f"{MAT_ITEM_GLIMMER}: could not wire the offset")

    MEL.recompile_material(mat)
    _assets().save_loaded_asset(mat)
    _log(f"built {MAT_ITEM_GLIMMER} (on {MPC_ITEM_GLIMMER}.{PARAM_HIGHLIGHT})")
    return mat


def add_glimmer(bp, parent_handle, visible=False):
    """The Glimmer sprite under ``parent_handle``, hidden unless ``visible``
    (an item's Tick shows it; BP_AmmoPickup, always on the ground, is built
    with it showing)."""
    _drop_components(bp, {GLIMMER})
    sprite = _component_object(_add_component(
        bp, parent_handle, unreal.MaterialBillboardComponent, GLIMMER))
    element = unreal.MaterialSpriteElement()
    element.set_editor_property("material", _must_load(MAT_ITEM_GLIMMER))
    element.set_editor_property("base_size_x", GLIMMER_HALF_SIZE_CM)
    element.set_editor_property("base_size_y", GLIMMER_HALF_SIZE_CM)
    sprite.set_editor_property("elements", [element])
    sprite.set_editor_property("visible", bool(visible))
    sprite.set_editor_property("cast_shadow", False)
    # As an item's model: it blocks nothing and no trace finds it.
    sprite.set_collision_profile_name("NoCollision")
    return sprite


def author_glimmer(ed, exec_ins):
    """Tick: the Glimmer sprite shows while the item is Dropped. ``exec_ins``
    are the exec pins it runs off (the Tick's, or every tail of a child's own
    chain). Returns the exec pin a chain goes on from."""
    def get(name):
        return _pin(ed.add_get_member_variable_node(name), name, is_input=False)

    # First what a client's copy of a replicated item shows at all
    # (item_world.py): here because every child's Tick calls this.
    exec_ins = author_world_view(ed, exec_ins)
    show = _node(ed, FN_SET_VISIBILITY)
    _connect(get(GLIMMER), _pin(show, "self"))
    _connect(get(IV.Dropped), _pin(show, "bNewVisibility"))
    for e in exec_ins:
        _connect(e, _pin(show, "execute"))
    ed.add_comment_to_nodes(
        f"An item lying on the ground glimmers: the {GLIMMER} sprite shows "
        f"while it is {IV.Dropped}. Whether any glimmer shines at all is "
        f"{MPC_NAME}.{PARAM_HIGHLIGHT}, the WORLD SETTINGS tab's row.", [show])
    return then(show)
