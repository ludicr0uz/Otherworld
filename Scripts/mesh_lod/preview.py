"""A picture of what was built: every LOD of a mesh from one camera, side by
side, so a person can see what each distance will show.

Two halves, like the impostor's atlas. In the editor shoot() photographs the
mesh once per LOD, forced, as base colour and world normals. Outside it
sheet() lights each pair under one light and lays them in a row (Pillow +
numpy, imported there so the editor can import this module).
"""

import math
import os

from mesh_lod import paths

SIZE = (512, 768)                # (width, height) of one LOD's picture
FOV = 30.0
YAW, PITCH = 250.0, -6.0         # off every plane's axis: the cards show as cards
MARGIN = 1.05
AMBIENT, KEY, BACK_SHARE, GAIN = 0.42, 0.85, 0.45, 1.25


def shoot(mesh, name):
    """Write both passes of every LOD. Editor only."""
    import unreal
    from mesh_lod import capture

    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    rotation = unreal.Rotator(roll=0.0, pitch=PITCH, yaw=YAW)
    forward = unreal.MathLibrary.get_forward_vector(rotation)
    spawned = []
    try:
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.StaticMeshActor, capture.FAR_ABOVE)
        spawned.append(actor)
        component = actor.static_mesh_component
        component.set_static_mesh(mesh)
        # Nothing streams textures in for a camera the level does not know
        # of: left alone, the impostor is drawn from a 32-pixel mip.
        for slot in mesh.static_materials:
            material = slot.material_interface
            if isinstance(material, unreal.MaterialInstanceConstant):
                for value in material.get_editor_property("texture_parameter_values"):
                    if value.parameter_value:
                        value.parameter_value.set_force_mip_levels_to_be_resident(30.0)
        centre, _extent, radius = unreal.SystemLibrary.get_component_bounds(component)
        distance = radius * MARGIN / math.sin(math.radians(FOV / 2.0))
        camera = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.SceneCapture2D, centre - forward * distance, rotation)
        spawned.append(camera)
        cc = camera.get_component_by_class(unreal.SceneCaptureComponent2D)
        cc.set_editor_property("fov_angle", FOV)
        cc.set_editor_property("capture_every_frame", False)
        cc.set_editor_property("capture_on_movement", False)
        cc.set_editor_property(
            "primitive_render_mode",
            unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST)
        cc.show_only_actor_components(actor)
        for lod in range(mesh.get_num_lods()):
            component.set_forced_lod_model(lod + 1)
            for kind in ("StaticMesh", "Texture"):
                unreal.SystemLibrary.execute_console_command(
                    world, f"Editor.Async{kind}CompilationFinishAll")
            # Thrown away: it asks for this LOD's shaders and textures.
            cc.set_editor_property("capture_source", capture.SOURCES["base"])
            cc.set_editor_property("texture_target", capture.new_target(world, SIZE))
            unreal.AutomationLibrary.finish_loading_before_screenshot()
            cc.capture_scene()
            unreal.AutomationLibrary.finish_loading_before_screenshot()
            for kind in paths.PASSES:
                target = capture.new_target(world, SIZE)
                cc.set_editor_property("texture_target", target)
                cc.set_editor_property("capture_source", capture.SOURCES[kind])
                cc.capture_scene()
                capture.save(world, target, paths.preview_file(name, lod, kind))
    finally:
        for a in spawned:
            a.destroy_actor()
    return mesh.get_num_lods()


def _light():
    yaw, pitch = math.radians(YAW), math.radians(PITCH)
    forward = (math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch))
    right = (-math.sin(yaw), math.cos(yaw), 0.0)
    light = [-forward[i] * 0.6 - right[i] * 0.5 + (0.0, 0.0, 0.7)[i] for i in range(3)]
    length = math.sqrt(sum(v * v for v in light))
    return [v / length for v in light]


def sheet(name, triangles):
    """Write the row of lit LODs, each captioned with its triangle count.
    Returns the file, or None when a pass is missing. Host only."""
    import numpy as np
    from PIL import Image, ImageDraw

    from mesh_lod import atlas

    row = Image.new("RGB", (SIZE[0] * len(triangles), SIZE[1]), (58, 62, 70))
    draw = ImageDraw.Draw(row)
    for lod, count in enumerate(triangles):
        files = [paths.preview_file(name, lod, kind) for kind in paths.PASSES]
        if not all(os.path.isfile(f) for f in files):
            return None
        colour, world = (atlas.read_pass(f, SIZE) for f in files)
        mask = atlas.mesh_mask(colour, world)[..., None]
        facing = world @ np.array(_light(), dtype=np.float32)
        lit = AMBIENT + KEY * np.where(facing > 0.0, facing, -facing * BACK_SHARE)
        rgb = atlas._srgb(colour * lit[..., None] * GAIN)
        back = np.array([58, 62, 70], dtype=np.float32) / 255.0
        picture = rgb * mask + back * (1.0 - mask)
        row.paste(Image.fromarray((picture * 255.0 + 0.5).astype(np.uint8), "RGB"),
                  (lod * SIZE[0], 0))
        draw.text((lod * SIZE[0] + 10, 8), f"LOD{lod}: {count:,} triangles",
                  fill=(255, 255, 255))
    out = paths.preview_png(name)
    row.save(out)
    return out
