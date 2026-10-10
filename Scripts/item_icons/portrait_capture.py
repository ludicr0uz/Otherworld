"""The editor's half of the character's portrait: the player's MetaHuman,
posed, photographed from the front through capture.py's passes.

What stands before the camera is combat/metahuman_body.py's tree rebuilt out
of plain actors (nothing here spawns the player): the whole body in its
underwear material, the face following the body's neck and head, the grooms
bound to the face. The hidden mesh and the retargeting anim blueprint are not
there: nothing ticks an animation in the capture, so the idle is retargeted
onto the body's skeleton as a clip, once, and its first frame is the pose.
"""

import os

import unreal

from asset_pipeline.ual_retarget import _asset_data, _fresh
from item_icons.capture import FAR_ABOVE, _log, _shoot, _world
from item_icons.paths import PART_HAIR, PART_SEAM, PASSES_DIR
from item_icons.portrait import (
    PORTRAIT, PORTRAIT_FACE, PORTRAIT_GROOMS, PORTRAIT_MATERIAL, PORTRAIT_MESH, PORTRAIT_POSE,
    PORTRAIT_POSE_MESH, PORTRAIT_RETARGETER, PORTRAIT_SCRATCH, PORTRAIT_YAW,
)

EAL = unreal.EditorAssetLibrary
KEEP = unreal.AttachmentRule.KEEP_RELATIVE


def _full_textures(comp):
    """Have a mesh's textures in at full size before it is photographed.

    A freshly loaded texture starts on its low mips, and a picture taken a
    moment after the editor started shows them: a generated body's atlas
    (hundreds of small islands, skin beside cloth) came out blotched, every
    island's edge its neighbour's colour. In the game the textures have
    streamed in and none of it shows.
    """
    mel = unreal.MaterialEditingLibrary
    comp.set_editor_property("force_mip_streaming", True)
    for mi in comp.get_materials():
        if not isinstance(mi, unreal.MaterialInstanceConstant):
            continue
        for name in mel.get_texture_parameter_names(mi):
            tex = mel.get_material_instance_texture_parameter_value(mi, name)
            if tex:
                tex.set_force_mip_levels_to_be_resident(60.0)
    comp.prestream_textures(60.0, True)


def _idle_on_body(body_mesh):
    """The idle clip on the body's skeleton, in PORTRAIT_SCRATCH."""
    _fresh(PORTRAIT_SCRATCH)
    inputs = unreal.IKRetargetBatchOperationInputs()
    inputs.set_editor_property("assets_to_retarget",
                               [_asset_data(unreal.load_asset(PORTRAIT_POSE))])
    inputs.set_editor_property("source_mesh", unreal.load_asset(PORTRAIT_POSE_MESH))
    inputs.set_editor_property("target_mesh", body_mesh)
    inputs.set_editor_property("ik_retarget_asset", unreal.load_asset(PORTRAIT_RETARGETER))
    inputs.set_editor_property("include_referenced_assets", False)
    inputs.set_editor_property("target_path", PORTRAIT_SCRATCH)
    inputs.set_editor_property("use_source_path", False)
    inputs.set_editor_property("overwrite_existing_files", True)
    made = [a.get_asset() for a in unreal.IKRetargetBatchOperation.run_batch_retarget(inputs)]
    clips = [a for a in made if isinstance(a, unreal.AnimSequence)]
    if len(clips) != 1:
        raise RuntimeError(f"{PORTRAIT_POSE} retargeted into {len(clips)} clips")
    return clips[0]


def _spawn(cls, spawned, parent=None):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(cls, FAR_ABOVE)
    spawned.append(actor)
    if parent:
        actor.attach_to_component(parent, "", KEEP, KEEP, KEEP, False)
        actor.set_actor_relative_location(unreal.Vector(0.0, 0.0, 0.0), False, False)
    return actor


def _body(mesh, pose, spawned):
    body = _spawn(unreal.SkeletalMeshActor, spawned).skeletal_mesh_component
    # The clip's first frame. The clip is in place before the mesh: setting
    # the mesh initialises the animation, and that poses the body once.
    play = unreal.SingleAnimationPlayData()
    play.set_editor_property("anim_to_play", pose)
    play.set_editor_property("saved_position", 0.0)
    play.set_editor_property("saved_playing", False)
    body.set_editor_property("animation_mode", unreal.AnimationMode.ANIMATION_SINGLE_NODE)
    body.set_editor_property("animation_data", play)
    body.set_skinned_asset_and_update(mesh)
    # The whole body has no material of its own (combat/metahuman_body.py).
    body.set_material(0, unreal.load_asset(PORTRAIT_MATERIAL))
    return body


HEAD = "head"                    # the bone a groom rides, on both skeletons


def _face(body, spawned):
    """The face, led by the body, and its head bone as the mesh was made
    (in the component's space): where the grooms were modelled round."""
    face = _spawn(unreal.SkeletalMeshActor, spawned, body).skeletal_mesh_component
    face.set_skinned_asset_and_update(unreal.load_asset(PORTRAIT_FACE))
    head_made = face.get_socket_transform(HEAD, unreal.RelativeTransformSpace.RTS_COMPONENT)
    # In the game Face_AnimBP copies the body's neck and head each frame. The
    # two skeletons name those bones alike, so here the face is led by the body.
    face.set_leader_pose_component(body, True)
    face.set_forced_lod(1)
    return face, head_made


def _grooms(body, head_made, spawned):
    """The grooms, each moved as the head moved. Not bound to the face: a
    binding follows the skin through the skin cache, which nothing has filled
    for a face that was spawned this frame, and the hair lay at its feet."""
    moved = head_made.inverse() * body.get_socket_transform(HEAD)
    made = []
    for groom, _binding in PORTRAIT_GROOMS.values():
        actor = _spawn(unreal.GroomActor, spawned)
        actor.get_component_by_class(unreal.GroomComponent).set_groom_asset(
            unreal.load_asset(groom))
        actor.set_actor_transform(moved, False, False)
        made.append(actor)
    return made


def capture_portrait():
    """Write the character's passes: the player's body, posed, from the front."""
    mesh = unreal.load_asset(PORTRAIT_MESH) if EAL.does_asset_exist(PORTRAIT_MESH) else None
    if not mesh:
        _log(f"SKIPPED {PORTRAIT}: {PORTRAIT_MESH} is not imported")
        return False
    spawned = []
    try:
        body = _body(mesh, _idle_on_body(mesh), spawned)
        face, head_made = _face(body, spawned)
        grooms = _grooms(body, head_made, spawned)
        for comp in (body, face):
            _full_textures(comp)
        _shoot(_world(), [body.get_owner(), face.get_owner()],
               unreal.Rotator(roll=0.0, pitch=0.0, yaw=PORTRAIT_YAW + 180.0),
               os.path.join(PASSES_DIR, PORTRAIT), PORTRAIT, spawned, also=grooms,
               parts={PART_SEAM: [face.get_owner()], PART_HAIR: grooms})
        return True
    finally:
        for a in spawned:
            a.destroy_actor()
        EAL.delete_directory(PORTRAIT_SCRATCH)
