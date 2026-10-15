"""BP_BloodSprite: the splatter flipbook at a wound, and what it is drawn with
(T_BloodSprite, M_BloodSprite). Spawned beside BP_BloodSplash where a pellet
or a thrown blade draws blood, sized by the zone it struck (impact.py,
throw_strike.py; the sizes are blood_sprite_consts.py).

**A flat card, not Niagara or Paper2D,** for the reason burst.py gives for
the droplets: nothing here may be an asset a script cannot rebuild. The
frames are drawn in plain Python (blood_sprite_image.py) and imported; the
material picks the frame; the actor does three things at BeginPlay and then
nothing:

  * writes the world's time into the card's custom primitive data, slot
    SPLAT_SPAWN_SLOT. The material's SpawnTime reads it there, and its Time
    node is the same clock, so (Time - SpawnTime) / SPLAT_LIFETIME is how far
    through the flipbook this one card is: one material for every splat, no
    material instance, no Tick;
  * turns to face the local camera (the camera manager of the
    PlayerController that IsLocalController, never one asked for by index
    (net/CLAUDE.md); with a random roll, so no two splats
    look alike), the card lifted toward it by SPLAT_LIFT so a splat seen
    from the side is not half inside the body. Without a camera it keeps the
    spawn's facing, the hit normal;
  * SetLifeSpan(SPLAT_LIFETIME).
"""

import os

import unreal

from combat.blood_sprite_consts import (
    SPLAT_COLOUR_GAIN, SPLAT_COMPONENT, SPLAT_FRAMES, SPLAT_GRID, SPLAT_LIFETIME, SPLAT_LIFT,
    SPLAT_ROOT, SPLAT_ROUGHNESS, SPLAT_SPAWN_PARAM, SPLAT_SPAWN_SLOT,
)
from combat.blood_sprite_image import splat_png
from combat.log import _log
from combat.materials import BLOOD_BASE_COLOUR
from combat.paths import BLOOD_SPRITE_BP_PATH, MAT_BLOOD_SPRITE, PLANE, TEX_BLOOD_SPRITE
from uebp.g import _G
from uebp.graph import (
    BEL, BGE, _add_component, _assets, _component_object, _create_blueprint, _drop_components,
    _connect, _events, _loose_pin, _must_load, _pin, _root_handle, _rot, _set, out, then)
from uebp.layout import arrange
from uebp.nodes.actor import (
    FN_ACTOR_LOC, FN_CAM_LOC, FN_IS_LOCAL_CONTROLLER, FN_LIFESPAN, FN_SET_ACTOR_ROT,
    FN_SET_CPD_FLOAT)
from uebp.nodes.math import FN_BREAK_ROT, FN_LOOK_AT, FN_MAKE_ROT, FN_RANDOM_FLOAT
from uebp.nodes.palette import MACRO_FOR_EACH
from uebp.nodes.system import FN_ALL_ACTORS, FN_IS_VALID, FN_TIME_SECONDS


PC_CLASS_PATH = "/Script/Engine.PlayerController"
CAM_MANAGER_VAR = "PlayerCameraManager"


# --- T_BloodSprite -------------------------------------------------------------

def build_splat_texture():
    """Draw the flipbook, import it and save T_BloodSprite (every run)."""
    png = os.path.join(unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_saved_dir()), "Weapons", "T_BloodSprite.png")
    os.makedirs(os.path.dirname(png), exist_ok=True)
    with open(png, "wb") as f:
        f.write(splat_png())
    dest_dir, name = TEX_BLOOD_SPRITE.rsplit("/", 1)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", png)
    task.set_editor_property("destination_path", dest_dir)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    tex = unreal.EditorAssetLibrary.load_asset(TEX_BLOOD_SPRITE)
    if not tex:
        raise RuntimeError(f"could not import {png} as {TEX_BLOOD_SPRITE}")
    # A shade, not a colour: linear, and clamped so no frame bleeds into the next.
    tex.set_editor_property("srgb", False)
    tex.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
    tex.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
    unreal.EditorAssetLibrary.save_asset(TEX_BLOOD_SPRITE)
    _log(f"built {TEX_BLOOD_SPRITE} ({SPLAT_FRAMES} frames, {SPLAT_GRID}x{SPLAT_GRID})")
    return tex


# --- M_BloodSprite -------------------------------------------------------------

def _expr(mat, cls, **props):
    e = unreal.MaterialEditingLibrary.create_material_expression(mat, cls, 0, 0)
    for k, v in props.items():
        e.set_editor_property(k, v)
    return e


def _link(a, b, pin, out_pin=""):
    if not unreal.MaterialEditingLibrary.connect_material_expressions(a, out_pin, b, pin):
        raise RuntimeError(f"could not link {a.get_name()}.{out_pin} -> {b.get_name()}.{pin}")


def build_splat_material(tex):
    """Masked, lit, two-sided: the frame (Time - SpawnTime) / life picks,
    its shade times M_Blood's colour, its alpha the mask."""
    mel = unreal.MaterialEditingLibrary
    eas = _assets()
    package_path, name = MAT_BLOOD_SPRITE.rsplit("/", 1)
    if eas.does_asset_exist(MAT_BLOOD_SPRITE):
        mat = _must_load(MAT_BLOOD_SPRITE)
        mel.delete_all_material_expressions(mat)
    else:
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, package_path, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    mat.set_editor_property("two_sided", True)
    mat.set_editor_property("opacity_mask_clip_value", 0.5)

    E = unreal
    now = _expr(mat, E.MaterialExpressionTime)
    born = _expr(mat, E.MaterialExpressionScalarParameter,
                 parameter_name=SPLAT_SPAWN_PARAM, use_custom_primitive_data=True,
                 primitive_data_index=SPLAT_SPAWN_SLOT)
    age = _expr(mat, E.MaterialExpressionSubtract)
    _link(now, age, "A")
    _link(born, age, "B")
    phase = _expr(mat, E.MaterialExpressionMultiply, const_b=1.0 / SPLAT_LIFETIME)
    _link(age, phase, "A")
    played = _expr(mat, E.MaterialExpressionSaturate)
    _link(phase, played, "")
    # frame = min(floor(played * FRAMES), FRAMES - 1)
    scaled = _expr(mat, E.MaterialExpressionMultiply, const_b=float(SPLAT_FRAMES))
    _link(played, scaled, "A")
    whole = _expr(mat, E.MaterialExpressionFloor)
    _link(scaled, whole, "")
    frame = _expr(mat, E.MaterialExpressionMin, const_b=float(SPLAT_FRAMES - 1))
    _link(whole, frame, "A")
    # row = floor(frame / GRID), column = frame - row * GRID
    per_row = _expr(mat, E.MaterialExpressionMultiply, const_b=1.0 / SPLAT_GRID)
    _link(frame, per_row, "A")
    row = _expr(mat, E.MaterialExpressionFloor)
    _link(per_row, row, "")
    row_start = _expr(mat, E.MaterialExpressionMultiply, const_b=float(SPLAT_GRID))
    _link(row, row_start, "A")
    column = _expr(mat, E.MaterialExpressionSubtract)
    _link(frame, column, "A")
    _link(row_start, column, "B")
    cell = _expr(mat, E.MaterialExpressionAppendVector)
    _link(column, cell, "A")
    _link(row, cell, "B")
    uv = _expr(mat, E.MaterialExpressionTextureCoordinate)
    shifted = _expr(mat, E.MaterialExpressionAdd)
    _link(uv, shifted, "A")
    _link(cell, shifted, "B")
    atlas_uv = _expr(mat, E.MaterialExpressionMultiply, const_b=1.0 / SPLAT_GRID)
    _link(shifted, atlas_uv, "A")
    sample = _expr(mat, E.MaterialExpressionTextureSample, texture=tex,
                   sampler_type=E.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    _link(atlas_uv, sample, "UVs")

    tint = _expr(mat, E.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(
        *[c * SPLAT_COLOUR_GAIN for c in BLOOD_BASE_COLOUR], 1.0))
    base = _expr(mat, E.MaterialExpressionMultiply)
    _link(sample, base, "A", "R")
    _link(tint, base, "B")
    rough = _expr(mat, E.MaterialExpressionConstant, r=SPLAT_ROUGHNESS)
    mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(sample, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
    mel.delete_unused_expressions(mat)
    mel.layout_material_expressions(mat)
    mel.recompile_material(mat)
    eas.save_loaded_asset(mat)
    _log(f"built {MAT_BLOOD_SPRITE}")
    return mat


# --- BP_BloodSprite --------------------------------------------------------------

def _author_begin_play(ed, begin):
    g = _G(ed)
    card = g.get(SPLAT_COMPONENT)
    stamp = g.call(FN_SET_CPD_FLOAT, [then(begin)], self=card, DataIndex=SPLAT_SPAWN_SLOT,
                   Value=out(g.call(FN_TIME_SECONDS)))

    # The local camera, never asked for by player index (net/CLAUDE.md): the
    # PlayerController that is local, out of those this machine has (a client
    # has its own alone), and that controller's own camera manager.
    every = g.call(FN_ALL_ACTORS, [then(stamp)], ActorClass=PC_CLASS_PATH)
    loop = g.keep(ed.add_macro_node(MACRO_FOR_EACH))
    _connect(out(every, "OutActors"), _loose_pin(loop, "Array"))
    _connect(then(every), _loose_pin(loop, "Exec"))
    pc = _loose_pin(loop, "ArrayElement", is_input=False)
    local, _remote = g.branch(out(g.call(FN_IS_LOCAL_CONTROLLER, self=pc)),
                              [_loose_pin(loop, "LoopBody", is_input=False)])
    cam = g.keep(ed.add_get_member_variable_node(CAM_MANAGER_VAR, PC_CLASS_PATH))
    _connect(pc, _pin(cam, "self"))
    cam = out(cam, CAM_MANAGER_VAR)
    seen, _unseen = g.branch(out(g.call(FN_IS_VALID, Object=cam)), [local])
    toward = g.call(FN_LOOK_AT, Start=out(g.call(FN_ACTOR_LOC)),
                    Target=out(g.call(FN_CAM_LOC, self=cam)))
    parts = g.call(FN_BREAK_ROT, InRot=out(toward))
    roll = g.call(FN_RANDOM_FLOAT)
    _set(roll, "Min", 0.0)
    _set(roll, "Max", 360.0)
    facing = g.call(FN_MAKE_ROT, Roll=out(roll), Pitch=out(parts, "Pitch"),
                    Yaw=out(parts, "Yaw"))
    g.call(FN_SET_ACTOR_ROT, [seen], NewRotation=out(facing))
    life = g.call(FN_LIFESPAN, [_loose_pin(loop, "Completed", is_input=False)])
    _set(life, "InLifespan", SPLAT_LIFETIME)
    ed.add_comment_to_nodes(
        f"BP_BloodSprite (blood_sprite.py): the spawn time into the card's custom data "
        f"slot {SPLAT_SPAWN_SLOT}, which M_BloodSprite's {SPLAT_SPAWN_PARAM} reads: the "
        f"material plays the {SPLAT_FRAMES}-frame flipbook from it over "
        f"{SPLAT_LIFETIME}s. Then the card turns to the local camera, rolled at random "
        f"(no camera: it keeps the hit normal), and lives {SPLAT_LIFETIME}s.", g.made)


def build_blood_sprite(rebuild=True):
    """T_BloodSprite, M_BloodSprite and BP_BloodSprite, every run."""
    mat = build_splat_material(build_splat_texture())
    bp = _create_blueprint(BLOOD_SPRITE_BP_PATH, unreal.Actor)
    _drop_components(bp, {SPLAT_ROOT, SPLAT_COMPONENT})
    root = _add_component(bp, _root_handle(bp), unreal.SceneComponent, SPLAT_ROOT)
    card = _component_object(_add_component(bp, root, unreal.StaticMeshComponent,
                                            SPLAT_COMPONENT))
    card.set_editor_property("static_mesh", _must_load(PLANE))
    card.set_editor_property("override_materials", [mat])
    # The plane faces +Z; a quarter turn in pitch faces it down the actor's X,
    # which the spawn points along the hit normal and BeginPlay at the camera.
    card.set_editor_property("relative_rotation", _rot(90.0, 0.0, 0.0))
    card.set_editor_property("relative_location", unreal.Vector(SPLAT_LIFT, 0.0, 0.0))
    card.set_editor_property("cast_shadow", False)
    card.set_collision_profile_name("NoCollision")
    # Compiled once with the card, so the graph can read it as a variable.
    BEL.compile_blueprint(bp)

    ed = BGE.get_graph_editor_by_name(bp, "EventGraph")
    tick, begin = _events(ed, rebuild)
    ed.remove_nodes([tick])
    _author_begin_play(ed, begin)
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError("BP_BloodSprite failed to compile")
    _assets().save_loaded_asset(bp)
    _log(f"built {BLOOD_SPRITE_BP_PATH} ({SPLAT_LIFETIME}s, faces the camera)")
    return bp
