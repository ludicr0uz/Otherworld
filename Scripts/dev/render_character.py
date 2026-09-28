"""render_character.py -- put a skeletal mesh on disk as a PNG.

    python3 Scripts/dev/uepy.py Scripts/dev/render_character.py

Tooling, not content: nothing in the game reads what this writes.  It exists
because the only other way to look at a generated character is to open the
editor and orbit it, and a generation run that produced something wrong is
worth seeing in the same minute it finished rather than the next time somebody
happens to launch the game.

Renders through a SceneCapture2D into a render target rather than through
take_high_res_screenshot, which needs a viewport and therefore cannot run in
the harness this project drives everything else with.  The subject, the lights
and the camera are all spawned and destroyed inside one call, so the open level
ends the run exactly as it started it and is never saved.
"""

import os

import unreal

CHARACTERS = "/Game/Sourced/Characters"
OUT_DIR = os.path.join(unreal.Paths.project_dir(), "Saved", "Renders")
SIZE = (900, 1400)

# Far enough from anything the open level might contain that no tree, terrain
# or wanderer wanders into frame.  Z is on the ground plane of nothing at all,
# which is the point: the subject is lit by the two lights below and by
# nothing else.
STAGE = unreal.Vector(0.0, 0.0, 500000.0)

# Three-quarter front view from just above the sternum, framing a 1.8 m figure
# head to foot at a 35 degree field of view.  +X because that is the direction
# a Meshy character faces out of the box, and the interesting side of a
# character is the one with the face on it.
CAMERA_OFFSET = unreal.Vector(340.0, 210.0, 110.0)
CAMERA_FOV = 35.0

_log = unreal.log_warning


def _spawn(cls, location, rotation=None):
    return unreal.EditorLevelLibrary.spawn_actor_from_class(
        cls, location, rotation or unreal.Rotator())


def render(mesh_pkg, out_path, size=SIZE):
    mesh = unreal.EditorAssetLibrary.load_asset(mesh_pkg)
    if not mesh:
        raise RuntimeError(f"no skeletal mesh at {mesh_pkg}")

    # The world context is not optional on either of these two calls: pass
    # None and create_render_target2d still hands back a target, capture_scene
    # still fills it, and export_render_target writes nothing at all and says
    # nothing about it.
    world = unreal.EditorLevelLibrary.get_editor_world()
    target = unreal.RenderingLibrary.create_render_target2d(
        world, size[0], size[1], unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
    spawned = []
    try:
        subject = _spawn(unreal.SkeletalMeshActor, STAGE)
        spawned.append(subject)
        subject.skeletal_mesh_component.set_skeletal_mesh_asset(mesh)

        # A key light across the face and a sky light to open the shadow side.
        # Without the second one a night-lit character reads as a silhouette,
        # which is a fine thing in the game and a useless thing in a reference
        # render.
        # Over the camera's left shoulder: a Rotator is (roll, pitch, yaw) in
        # Python, and the yaw has to put the light on the same side of the
        # subject as CAMERA_OFFSET or the render is a silhouette.
        key = _spawn(unreal.DirectionalLight, STAGE,
                     unreal.Rotator(0.0, -38.0, 205.0))
        spawned.append(key)
        key.get_component_by_class(unreal.DirectionalLightComponent).set_intensity(7.0)
        sky = _spawn(unreal.SkyLight, STAGE)
        spawned.append(sky)
        sky_comp = sky.get_component_by_class(unreal.SkyLightComponent)
        sky_comp.set_editor_property("intensity", 2.2)
        # A SkyLight with nothing to capture is black. The source has to be set
        # BEFORE recapture, and recapture has to be asked for explicitly --
        # nothing triggers it in a script-driven world with no level rebuild.
        sky_comp.set_editor_property(
            "source_type", unreal.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
        sky_comp.set_editor_property(
            "cubemap", unreal.EditorAssetLibrary.load_asset(
                "/Engine/EngineSky/Cubemap/DaylightAmbientCubemap"))
        sky_comp.recapture_sky()

        centre = unreal.Vector(STAGE.x, STAGE.y,
                               STAGE.z + mesh.get_bounds().box_extent.z)
        eye = unreal.Vector(centre.x + CAMERA_OFFSET.x,
                            centre.y + CAMERA_OFFSET.y,
                            centre.z + CAMERA_OFFSET.z)
        cam = _spawn(unreal.SceneCapture2D, eye,
                     unreal.MathLibrary.find_look_at_rotation(eye, centre))
        spawned.append(cam)
        cap = cam.get_component_by_class(unreal.SceneCaptureComponent2D)
        cap.set_editor_property("texture_target", target)
        cap.set_editor_property("fov_angle", CAMERA_FOV)
        cap.set_editor_property(
            "capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        # Nothing but the subject: the open level is whatever the last session
        # left open, and a tree 500 km below is still a tree the capture would
        # draw if the frustum happened to clip one. The sky and the fog are not
        # primitives and stay, which is what gives the render a backdrop.
        cap.set_editor_property(
            "primitive_render_mode",
            unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST)
        # show_only_actors refuses set_editor_property ("cannot be edited on
        # templates"); the BlueprintCallable adder is the only way in.
        cap.show_only_actor_components(subject, True)
        # Every frame, not once: a single capture lands before the skeletal
        # mesh has finished streaming and renders an empty stage.
        cap.set_editor_property("capture_every_frame", True)
        for _ in range(8):
            cap.capture_scene()

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        unreal.RenderingLibrary.export_render_target(
            world, target, os.path.dirname(out_path), os.path.basename(out_path))
        _log(f"[RENDER] {mesh.get_name()} -> {out_path}")
        return out_path
    finally:
        for actor in spawned:
            unreal.EditorLevelLibrary.destroy_actor(actor)


def main():
    meshes = []
    for path in sorted(unreal.EditorAssetLibrary.list_assets(CHARACTERS, recursive=True)):
        asset = unreal.EditorAssetLibrary.load_asset(path.split(".")[0])
        if isinstance(asset, unreal.SkeletalMesh):
            meshes.append(asset.get_path_name().split(".")[0])
    if not meshes:
        _log(f"[RENDER] nothing under {CHARACTERS} -- run the asset pipeline first")
        return
    for pkg in meshes:
        render(pkg, os.path.join(OUT_DIR, f"{pkg.rsplit('/', 1)[1]}.png"))


main()
