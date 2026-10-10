"""The editor's half: photograph each item's model into four passes.

An item is spawned far above the level, alone in a SceneCapture2D's show-only
list, and captured through an orthographic camera four times:

    base.png    its base colour (linear), straight out of the G-buffer
    normal.png  its world-space normals, n * 0.5 + 0.5
    mask.png    scene colour, kept for its alpha: 0 on the item, 255 off it
    depth.exr   scene colour again, into a float target, kept for its alpha:
                each pixel's distance from the camera, in cm

plus view.json: the camera's axes, which turn those normals into the camera's
space, and the picture's width in cm, which turns the depth into a shape.
light.py lights the picture from them: the depth is what lets one part of a
model shade another.

Why the G-buffer and not a lit capture: the lit one depends on the level's
sun (the forest boots at a random hour, and the first try came out black),
its sky light and the capture's auto-exposure. Base colour and normals depend
on the model and nothing else, so two runs give the same icon.

The item is the Blueprint, not a mesh path: whatever the builder hung on it
(the sniper's scope, the canteen's primitives, a model's scale) is in the
picture, and nothing here knows what any of them is made of.
"""

import json
import os

import unreal

from item_icons.items import ITEMS
from item_icons.paths import PASSES_DIR, part_file

SIZE = 1024                      # square, so any view of any model fits
MARGIN = 1.08                    # of the model's bounding sphere
FAR_ABOVE = unreal.Vector(0.0, 0.0, 50000.0)   # clear of the level and its fog
# The camera stands this far off the model's centre, in radii. As close as
# clears the model: the scene's depth is a half float, whose step grows with
# the distance (0.125 cm from 128 cm on, a pixel and more of a rifle).
CAMERA_RADII = 1.5
CAMERA_CLEAR = 10.0              # cm, on top of that
RGBA8 = "RTF_RGBA8"
PASSES = (
    ("base.png", "SCS_BASE_COLOR", RGBA8),
    ("normal.png", "SCS_NORMAL", RGBA8),
    ("mask.png", "SCS_SCENE_COLOR_HDR", RGBA8),
    # A float target is exported as an EXR whatever its file is called.
    ("depth.exr", "SCS_SCENE_COLOR_SCENE_DEPTH", "RTF_RGBA32F"),
)


def _log(msg):
    unreal.log_warning(f"[GEN] item icons: {msg}")


def _world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def _model_sphere(actors):
    """Centre and radius of the sphere round every mesh the actors show."""
    lo, hi = None, None
    for c in [c for a in actors for c in a.get_components_by_class(unreal.MeshComponent)]:
        if not c.is_visible():
            continue
        origin, extent, _radius = unreal.SystemLibrary.get_component_bounds(c)
        a, b = origin - extent, origin + extent
        lo = a if lo is None else unreal.Vector(min(lo.x, a.x), min(lo.y, a.y), min(lo.z, a.z))
        hi = b if hi is None else unreal.Vector(max(hi.x, b.x), max(hi.y, b.y), max(hi.z, b.z))
    if lo is None:
        raise RuntimeError(f"{actors[0].get_class().get_name()} shows no mesh")
    return (lo + hi) * 0.5, ((hi - lo) * 0.5).length()


def _camera_rotation(item):
    """Standing on the item's yaw side, looking back at it."""
    return unreal.Rotator(roll=item.roll, pitch=-item.pitch, yaw=item.yaw + 180.0)


def _shoot(world, actors, rotation, out_dir, label, spawned, also=(), parts=None):
    """The four passes and view.json of ``actors``, alone, seen along
    ``rotation``. ``also`` are in the picture without being framed (a groom's
    bounds are not its hair's). ``parts`` ({name: actors}) are each written a
    mask of their own, alone (parts.py). The camera it spawns is added to
    ``spawned``."""
    centre, radius = _model_sphere(actors)
    forward = unreal.MathLibrary.get_forward_vector(rotation)
    camera = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SceneCapture2D, centre - forward * (radius * CAMERA_RADII + CAMERA_CLEAR), rotation)
    spawned.append(camera)
    cc = camera.get_component_by_class(unreal.SceneCaptureComponent2D)
    cc.set_editor_property("projection_type", unreal.CameraProjectionMode.ORTHOGRAPHIC)
    cc.set_editor_property("ortho_width", 2.0 * radius * MARGIN)
    cc.set_editor_property("capture_every_frame", False)
    cc.set_editor_property("capture_on_movement", False)
    cc.set_editor_property(
        "primitive_render_mode",
        unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST)
    for actor in (*actors, *also):
        cc.show_only_actor_components(actor)
    # Without this the first capture of a model is the default material:
    # its shaders are still compiling and its textures are at their lowest
    # mip. The wait only covers what something has asked for, and the first
    # model of a run has been drawn by nothing yet (the pistol came out one
    # flat grey), so a capture that is thrown away asks first.
    unreal.AutomationLibrary.finish_loading_before_screenshot()
    cc.set_editor_property("texture_target", unreal.RenderingLibrary.create_render_target2d(
        world, SIZE, SIZE, getattr(unreal.TextureRenderTargetFormat, RGBA8)))
    cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_BASE_COLOR)
    cc.capture_scene()
    unreal.AutomationLibrary.finish_loading_before_screenshot()

    os.makedirs(out_dir, exist_ok=True)
    for name, source, fmt in PASSES:
        target = unreal.RenderingLibrary.create_render_target2d(
            world, SIZE, SIZE, getattr(unreal.TextureRenderTargetFormat, fmt))
        cc.set_editor_property("texture_target", target)
        cc.set_editor_property("capture_source", getattr(unreal.SceneCaptureSource, source))
        cc.capture_scene()
        if os.path.isfile(os.path.join(out_dir, name)):
            os.remove(os.path.join(out_dir, name))
        unreal.RenderingLibrary.export_render_target(world, target, out_dir, name)
        if not os.path.isfile(os.path.join(out_dir, name)):
            raise RuntimeError(f"{label}: the {name} pass was not written")
    for part, shown in (parts or {}).items():
        cc.clear_show_only_components()
        for actor in shown:
            cc.show_only_actor_components(actor)
        target = unreal.RenderingLibrary.create_render_target2d(
            world, SIZE, SIZE, getattr(unreal.TextureRenderTargetFormat, RGBA8))
        cc.set_editor_property("texture_target", target)
        cc.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_SCENE_COLOR_HDR)
        cc.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, target, out_dir, part_file(part))
    view = {k: v.to_tuple() for k, v in (
        ("right", unreal.MathLibrary.get_right_vector(rotation)),
        ("up", unreal.MathLibrary.get_up_vector(rotation)),
        ("forward", forward))}
    view["width_cm"] = 2.0 * radius * MARGIN
    with open(os.path.join(out_dir, "view.json"), "w") as fh:
        json.dump(view, fh)
    _log(f"{label:<9} radius {radius:6.1f} cm -> {out_dir}")


def _capture(world, item, out_dir):
    cls = unreal.load_object(None, f"{item.blueprint}.{item.blueprint.rsplit('/', 1)[1]}_C")
    if not cls:
        _log(f"SKIPPED {item.display}: {item.blueprint} is not built")
        return False
    spawned = []
    try:
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(cls, FAR_ABOVE)
        spawned.append(actor)
        if not actor.get_editor_property("Icon"):
            _log(f"note: {item.display} was built before its icon existed: run its "
                 "build again after this (weapons, or survival for the consumables)")
        _shoot(world, [actor], _camera_rotation(item), out_dir, item.display, spawned)
        return True
    finally:
        for a in spawned:
            a.destroy_actor()


def capture_all(only=()):
    """Write every item's passes. Returns the names captured. (The character's
    portrait is portrait_capture.py's.)"""
    world = _world()
    done = []
    for item in ITEMS:
        if only and item.display not in only:
            continue
        if _capture(world, item, os.path.join(PASSES_DIR, item.display)):
            done.append(item.display)
    _log(f"{len(done)} of {len(ITEMS)} items captured")
    return done
