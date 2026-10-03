"""The editor's half: photograph each item's model into three passes.

An item is spawned far above the level, alone in a SceneCapture2D's show-only
list, and captured through an orthographic camera three times:

    base.png    its base colour (linear), straight out of the G-buffer
    normal.png  its world-space normals, n * 0.5 + 0.5
    mask.png    scene colour, kept for its alpha: 0 on the item, 255 off it

plus view.json, the camera's axes, which turn those normals into the camera's
space. compose.py lights the picture from them.

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
from item_icons.paths import PASSES_DIR
from item_icons.portrait import PORTRAIT, PORTRAIT_MESH, PORTRAIT_POSE, PORTRAIT_YAW

SIZE = 1024                      # square, so any view of any model fits
MARGIN = 1.08                    # of the model's bounding sphere
FAR_ABOVE = unreal.Vector(0.0, 0.0, 50000.0)   # clear of the level and its fog
PASSES = (
    ("base", "SCS_BASE_COLOR"),
    ("normal", "SCS_NORMAL"),
    ("mask", "SCS_SCENE_COLOR_HDR"),
)


def _log(msg):
    unreal.log_warning(f"[GEN] item icons: {msg}")


def _world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def _model_sphere(actor):
    """Centre and radius of the sphere round every mesh the item shows."""
    lo, hi = None, None
    for c in actor.get_components_by_class(unreal.MeshComponent):
        if not c.is_visible():
            continue
        origin, extent, _radius = unreal.SystemLibrary.get_component_bounds(c)
        a, b = origin - extent, origin + extent
        lo = a if lo is None else unreal.Vector(min(lo.x, a.x), min(lo.y, a.y), min(lo.z, a.z))
        hi = b if hi is None else unreal.Vector(max(hi.x, b.x), max(hi.y, b.y), max(hi.z, b.z))
    if lo is None:
        raise RuntimeError(f"{actor.get_class().get_name()} shows no mesh")
    return (lo + hi) * 0.5, ((hi - lo) * 0.5).length()


def _camera_rotation(item):
    """Standing on the item's yaw side, looking back at it."""
    return unreal.Rotator(roll=item.roll, pitch=-item.pitch, yaw=item.yaw + 180.0)


def _shoot(world, actor, rotation, out_dir, label, spawned):
    """The three passes and view.json of ``actor``, alone, seen along
    ``rotation``. The camera it spawns is added to ``spawned``."""
    centre, radius = _model_sphere(actor)
    forward = unreal.MathLibrary.get_forward_vector(rotation)
    camera = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SceneCapture2D, centre - forward * (radius * 4.0 + 50.0), rotation)
    spawned.append(camera)
    cc = camera.get_component_by_class(unreal.SceneCaptureComponent2D)
    cc.set_editor_property("projection_type", unreal.CameraProjectionMode.ORTHOGRAPHIC)
    cc.set_editor_property("ortho_width", 2.0 * radius * MARGIN)
    cc.set_editor_property("capture_every_frame", False)
    cc.set_editor_property("capture_on_movement", False)
    cc.set_editor_property(
        "primitive_render_mode",
        unreal.SceneCapturePrimitiveRenderMode.PRM_USE_SHOW_ONLY_LIST)
    cc.show_only_actor_components(actor)
    # Without this the first capture of a model is the default checker
    # material: its shaders are still compiling and its textures are at
    # their lowest mip.
    unreal.AutomationLibrary.finish_loading_before_screenshot()

    os.makedirs(out_dir, exist_ok=True)
    for name, source in PASSES:
        target = unreal.RenderingLibrary.create_render_target2d(
            world, SIZE, SIZE, unreal.TextureRenderTargetFormat.RTF_RGBA8)
        cc.set_editor_property("texture_target", target)
        cc.set_editor_property("capture_source", getattr(unreal.SceneCaptureSource, source))
        cc.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, target, out_dir, f"{name}.png")
        if not os.path.isfile(os.path.join(out_dir, f"{name}.png")):
            raise RuntimeError(f"{label}: the {name} pass was not written")
    axes = {k: v.to_tuple() for k, v in (
        ("right", unreal.MathLibrary.get_right_vector(rotation)),
        ("up", unreal.MathLibrary.get_up_vector(rotation)),
        ("forward", forward))}
    with open(os.path.join(out_dir, "view.json"), "w") as fh:
        json.dump(axes, fh)
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
        _shoot(world, actor, _camera_rotation(item), out_dir, item.display, spawned)
        return True
    finally:
        for a in spawned:
            a.destroy_actor()


def capture_portrait():
    """Write the character's passes: the player's body, posed, from the front."""
    mesh, pose = unreal.load_asset(PORTRAIT_MESH), unreal.load_asset(PORTRAIT_POSE)
    if not mesh:
        _log(f"SKIPPED {PORTRAIT}: {PORTRAIT_MESH} is not imported")
        return False
    spawned = []
    try:
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            unreal.SkeletalMeshActor, FAR_ABOVE)
        spawned.append(actor)
        body = actor.skeletal_mesh_component
        if pose:
            # The clip's first frame. Nothing ticks an animation here, so the
            # clip is in place before the mesh: setting the mesh initialises
            # the animation, and that poses the body once.
            play = unreal.SingleAnimationPlayData()
            play.set_editor_property("anim_to_play", pose)
            play.set_editor_property("saved_position", 0.0)
            play.set_editor_property("saved_playing", False)
            body.set_editor_property("animation_mode",
                                     unreal.AnimationMode.ANIMATION_SINGLE_NODE)
            body.set_editor_property("animation_data", play)
        else:
            _log(f"note: {PORTRAIT_POSE} is missing: the portrait is the bind pose")
        body.set_skinned_asset_and_update(mesh)
        _shoot(_world(), actor, unreal.Rotator(roll=0.0, pitch=0.0, yaw=PORTRAIT_YAW + 180.0),
               os.path.join(PASSES_DIR, PORTRAIT), PORTRAIT, spawned)
        return True
    finally:
        for a in spawned:
            a.destroy_actor()


def capture_all(only=()):
    """Write every item's passes, and the character's portrait's. Returns the
    names captured."""
    world = _world()
    done = []
    for item in ITEMS:
        if only and item.display not in only:
            continue
        if _capture(world, item, os.path.join(PASSES_DIR, item.display)):
            done.append(item.display)
    _log(f"{len(done)} of {len(ITEMS)} items captured")
    if (not only or PORTRAIT in only) and capture_portrait():
        done.append(PORTRAIT)
    return done
