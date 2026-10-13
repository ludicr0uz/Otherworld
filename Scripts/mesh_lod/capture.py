"""In the editor: the built mesh photographed for its impostor, once per
plane, as base colour and world normals.

The mesh stands alone on an actor far above the level, unrotated, at its
LOD0, in the show-only list of an orthographic SceneCapture2D -- the way
map_assets/thumbs.py takes its pictures, and for its reason: neither pass
depends on the level's light, so two runs give one atlas. Neither is a
texture yet (linear, no alpha): atlas.py makes them one outside the editor,
where numpy is.

A pass is read back as floats and written raw (three float32 a pixel, rows
from the top). An 8-bit target will not do: the normal pass is the world
normal as it is, and every component under zero would be clamped away.
"""

import array
import os

import unreal

from mesh_lod import paths, planes

FAR_ABOVE = unreal.Vector(0.0, 0.0, 80000.0)
SOURCES = {"base": unreal.SceneCaptureSource.SCS_BASE_COLOR,
           "normal": unreal.SceneCaptureSource.SCS_NORMAL}


def new_target(world, size):
    return unreal.RenderingLibrary.create_render_target2d(
        world, size[0], size[1], unreal.TextureRenderTargetFormat.RTF_RGBA16F)


def save(world, target, file):
    pixels = unreal.RenderingLibrary.read_render_target_raw(world, target, False)
    flat = array.array("f")
    for p in pixels:
        flat.append(p.r)
        flat.append(p.g)
        flat.append(p.b)
    with open(file, "wb") as fh:
        flat.tofile(fh)
    return len(pixels)


def shoot(mesh, name, spec, frame):
    """Write every plane's two passes under the job's working folder."""
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    out_dir = paths.job_dir(name)
    os.makedirs(out_dir, exist_ok=True)
    size = planes.capture_size(frame, spec.capture_px)
    spawned = []
    try:
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.StaticMeshActor, FAR_ABOVE)
        spawned.append(actor)
        component = actor.static_mesh_component
        component.set_static_mesh(mesh)
        component.set_forced_lod_model(1)                  # 1 is LOD0
        middle = FAR_ABOVE + unreal.Vector(
            frame.centre_x, frame.centre_y, frame.bottom + frame.height / 2.0)
        back = max(frame.width, frame.height) * 2.0
        for kind in ("StaticMesh", "Texture"):
            unreal.SystemLibrary.execute_console_command(
                world, f"Editor.Async{kind}CompilationFinishAll")
        for plane in range(spec.impostor_planes):
            rotation = unreal.Rotator(
                roll=0.0, pitch=0.0, yaw=planes.camera_yaw(plane, spec.impostor_planes))
            forward = unreal.MathLibrary.get_forward_vector(rotation)
            camera = unreal.EditorLevelLibrary.spawn_actor_from_class(
                unreal.SceneCapture2D, middle - forward * back, rotation)
            spawned.append(camera)
            cc = camera.get_component_by_class(unreal.SceneCaptureComponent2D)
            cc.set_editor_property("projection_type", unreal.CameraProjectionMode.ORTHOGRAPHIC)
            cc.set_editor_property("ortho_width", frame.width)
            cc.set_editor_property("capture_every_frame", False)
            cc.set_editor_property("capture_on_movement", False)
            cc.set_editor_property(
                "primitive_render_mode",
                unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST)
            cc.show_only_actor_components(actor)
            if plane == 0:
                # The first capture asks for the shaders and textures; the
                # wait covers only what has been asked for (thumbs.py).
                cc.set_editor_property("capture_source", SOURCES["base"])
                cc.set_editor_property("texture_target", new_target(world, size))
                unreal.AutomationLibrary.finish_loading_before_screenshot()
                cc.capture_scene()
                unreal.AutomationLibrary.finish_loading_before_screenshot()
            for kind in paths.PASSES:
                target = new_target(world, size)
                cc.set_editor_property("texture_target", target)
                cc.set_editor_property("capture_source", SOURCES[kind])
                cc.capture_scene()
                if save(world, target, paths.pass_file(name, plane, kind)) != size[0] * size[1]:
                    raise RuntimeError(f"{name}: plane {plane}'s {kind} pass came back short")
    finally:
        for a in spawned:
            a.destroy_actor()
    return size
