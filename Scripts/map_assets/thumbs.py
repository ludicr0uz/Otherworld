"""The editor's half of the pictures: each mesh photographed into a PNG.

A browser cannot draw a .uasset and nothing outside the editor can read one,
so the editor draws it: the mesh alone on an actor of its kind far above the
level, in a SceneCapture2D's show-only list, as item_icons/capture.py does.
The passes are base colour and world normals, for that module's reason: they
depend on the mesh and its materials and not on the level's sun, so two runs
give one picture. Neither is a picture yet (linear, unlit, alpha 0
everywhere): shade.py lights them outside the editor.

A raw scan still wears the material its glTF import gave it, a child of one
of the Interchange plugin's glTF parents (Substrate/M_GLTF, M_Default), and
Substrate is off in this project: it draws black, and a leaf card is not
drawn at all.
The game never shows one (the meshes it plants were given instances of
M_Master_Foliage), so the picture does the same for the shot alone: such a
slot is shot through STAND_IN carrying the slot's own textures. Nothing is
saved.

A translucent mesh (a glow, a rig control) is in neither pass, and has no
picture: the page shows an empty tile.

Each mesh is shot from its picture's view and then from SPIN_FRAMES more, the
camera walking once round it: the page's large view turns the mesh by
flipping through them. shade.py makes one strip of a mesh's turn and deletes
those passes.

A mesh's passes (or the strip made of them) are kept until its package is
newer than them, so a run after the first draws only what was added or
changed, and a run that dies is taken up where it stopped. This is the one step that loads meshes: one at a time,
with a garbage collection every GC_EVERY.
"""

import math
import os

import unreal

from map_assets.paths import (PASSES_DIR, SPIN_DIR, SPIN_PASSES_DIR, pass_file, spin_file,
                              spin_pass_file)
from map_assets.view import FOV, MARGIN, PASS_SIZE, PITCH, SPIN_FRAMES, YAW, spin_yaw

PASSES = (("base", "SCS_BASE_COLOR"), ("normal", "SCS_NORMAL"))
FAR_ABOVE = unreal.Vector(0.0, 0.0, 50000.0)   # clear of the level and its fog
GC_EVERY = 25
BROKEN_PARENTS = ("/InterchangeAssets/gltf/",)
STAND_IN = "/Game/Forest/Materials/M_Master_Foliage"
STAND_IN_TEXTURES = ("BaseColorTexture", "NormalTexture")


def _log(msg):
    unreal.log_warning(f"[GEN] map assets: {msg}")


def _views(path):
    """[(yaw, {pass name: file})]: the picture's view, then the turn's."""
    views = [(YAW, {name: os.path.join(PASSES_DIR, pass_file(path, name))
                    for name, _source in PASSES})]
    for frame in range(SPIN_FRAMES):
        views.append((spin_yaw(frame), {
            name: os.path.join(SPIN_PASSES_DIR, spin_pass_file(path, frame, name))
            for name, _source in PASSES}))
    return views


def _fresh(files, source):
    return all(os.path.isfile(f) for f in files) and not (
        os.path.isfile(source) and os.path.getmtime(source) > min(map(os.path.getmtime, files)))


def _stale(path):
    source = os.path.join(unreal.Paths.project_content_dir(), path[len("/Game/"):] + ".uasset")
    views = _views(path)
    if not _fresh(list(views[0][1].values()), source):
        return True
    turn = [f for _yaw, files in views[1:] for f in files.values()]
    return not (_fresh([os.path.join(SPIN_DIR, spin_file(path))], source)
                or _fresh(turn, source))


def _stand_in(world, component, mesh):
    """Shoot each slot whose material cannot draw here through STAND_IN."""
    parent = unreal.load_asset(STAND_IN)
    if parent is None:
        return
    for index, slot in enumerate(mesh.static_materials):
        material = slot.material_interface
        base = material.get_base_material() if material else None
        if base is None or not base.get_path_name().startswith(BROKEN_PARENTS):
            continue
        if not isinstance(material, unreal.MaterialInstanceConstant):
            continue
        own = {str(v.parameter_info.name): v.parameter_value
               for v in material.get_editor_property("texture_parameter_values")}
        dynamic = unreal.MaterialLibrary.create_dynamic_material_instance(world, parent)
        for name in STAND_IN_TEXTURES:
            if own.get(name):
                dynamic.set_texture_parameter_value(name, own[name])
        component.set_material(index, dynamic)


def _stage(world, mesh, spawned):
    """The mesh on an actor of its kind, far above the level. A skeletal mesh
    stands in its reference pose: nothing animates it."""
    if isinstance(mesh, unreal.SkeletalMesh):
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.SkeletalMeshActor, FAR_ABOVE)
        spawned.append(actor)
        component = actor.skeletal_mesh_component
        component.set_skeletal_mesh_asset(mesh)
    else:
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.StaticMeshActor, FAR_ABOVE)
        spawned.append(actor)
        component = actor.static_mesh_component
        component.set_static_mesh(mesh)
        _stand_in(world, component, mesh)
    return actor, component


def _shoot(world, mesh, path):
    """Write every view of the mesh. Returns whether each file was written."""
    views = _views(path)
    for _yaw, files in views:
        for out in files.values():
            if os.path.isfile(out):
                os.remove(out)
    spawned = []
    try:
        actor, component = _stage(world, mesh, spawned)
        centre, _extent, radius = unreal.SystemLibrary.get_component_bounds(component)
        distance = max(radius, 1.0) * MARGIN / math.sin(math.radians(FOV / 2.0))
        rotation = unreal.Rotator(roll=0.0, pitch=PITCH, yaw=YAW)
        camera = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.SceneCapture2D,
            centre - unreal.MathLibrary.get_forward_vector(rotation) * distance, rotation)
        spawned.append(camera)
        cc = camera.get_component_by_class(unreal.SceneCaptureComponent2D)
        cc.set_editor_property("fov_angle", FOV)
        cc.set_editor_property("capture_every_frame", False)
        cc.set_editor_property("capture_on_movement", False)
        cc.set_editor_property(
            "primitive_render_mode",
            unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST)
        cc.show_only_actor_components(actor)
        # A texture loaded a moment ago is a 32-pixel black placeholder while
        # it compiles in the background: a scan came out black, and a masked
        # one, cut out by black, came out empty. Nothing here ticks, so wait.
        for kind in ("StaticMesh", "SkinnedAsset", "Texture"):
            unreal.SystemLibrary.execute_console_command(
                world, f"Editor.Async{kind}CompilationFinishAll")
        # The first capture of a mesh asks for its shaders and textures; the
        # wait covers only what something has asked for (item_icons/capture.py),
        # so a capture that is thrown away asks first.
        cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_BASE_COLOR)
        cc.set_editor_property("texture_target", unreal.RenderingLibrary.create_render_target2d(
            world, PASS_SIZE, PASS_SIZE, unreal.TextureRenderTargetFormat.RTF_RGBA8))
        unreal.AutomationLibrary.finish_loading_before_screenshot()
        cc.capture_scene()
        unreal.AutomationLibrary.finish_loading_before_screenshot()
        target = unreal.RenderingLibrary.create_render_target2d(
            world, PASS_SIZE, PASS_SIZE, unreal.TextureRenderTargetFormat.RTF_RGBA8)
        cc.set_editor_property("texture_target", target)
        for yaw, files in views:
            # The bounds are a sphere about the centre, so the mesh fills
            # every frame of the turn alike.
            rotation = unreal.Rotator(roll=0.0, pitch=PITCH, yaw=yaw)
            forward = unreal.MathLibrary.get_forward_vector(rotation)
            camera.set_actor_location_and_rotation(
                centre - forward * distance, rotation, False, True)
            for name, source in PASSES:
                cc.set_editor_property(
                    "capture_source", getattr(unreal.SceneCaptureSource, source))
                cc.capture_scene()
                folder, file = os.path.split(files[name])
                unreal.RenderingLibrary.export_render_target(world, target, folder, file)
    finally:
        for a in spawned:
            a.destroy_actor()
    return all(os.path.isfile(f) for _yaw, files in views for f in files.values())


def render(paths):
    """Write the passes of every mesh of ``paths`` whose passes are missing or
    older than its package. Returns how many were drawn."""
    os.makedirs(PASSES_DIR, exist_ok=True)
    os.makedirs(SPIN_PASSES_DIR, exist_ok=True)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    todo = [p for p in paths if _stale(p)]
    _log(f"pictures: {len(todo)} to draw, {len(paths) - len(todo)} kept")
    drawn = 0
    for index, path in enumerate(todo, 1):
        mesh = unreal.EditorAssetLibrary.load_asset(path)
        if not isinstance(mesh, (unreal.StaticMesh, unreal.SkeletalMesh)):
            _log(f"SKIPPED {path}: did not load as a mesh")
            continue
        if _shoot(world, mesh, path):
            drawn += 1
        else:
            _log(f"SKIPPED {path}: a pass was not written")
        if index % GC_EVERY == 0:
            unreal.SystemLibrary.collect_garbage()
            _log(f"pictures: {index} of {len(todo)}")
    _log(f"pictures: {drawn} drawn -> {PASSES_DIR}")
    return drawn
