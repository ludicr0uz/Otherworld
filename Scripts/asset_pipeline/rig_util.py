"""rig_util -- small editor helpers shared by the retarget modules: the log,
asset loading, bone lists, and a bone's component-space pose in a clip.
"""

import unreal


# print() goes nowhere in a cold -ExecutePythonScript run; the log does.
def _log(msg):
    unreal.log_warning(f"[RETARGET] {msg}")


def _reuse_or_create(pkg, cls, factory):
    """Load the asset at pkg, or create it there. Never deletes."""
    existing = unreal.EditorAssetLibrary.load_asset(pkg)
    if isinstance(existing, cls):
        return existing
    folder, name = pkg.rsplit("/", 1)
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, folder, cls, factory)
    if asset is None:
        raise RuntimeError(f"could not create {pkg}")
    return asset


def _load(pkg):
    a = unreal.EditorAssetLibrary.load_asset(pkg)
    if a is None:
        raise RuntimeError(f"missing asset {pkg}")
    return a


def _bone_names(mesh):
    """Bone list for a skeletal mesh, via a throwaway component far off-level."""
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SkeletalMeshActor, unreal.Vector(0, 0, -1000000))
    try:
        comp = actor.skeletal_mesh_component
        comp.set_skeletal_mesh_asset(mesh)
        return [str(comp.get_bone_name(i)) for i in range(comp.get_num_bones())]
    finally:
        unreal.EditorLevelLibrary.destroy_actor(actor)


def _bone_world(anim, bone, time):
    """Component-space position of a bone at a time, composed up the hierarchy.

    get_bone_pose_for_time returns a LOCAL transform, so a bone's actual
    position is its own transform multiplied by every parent's up to the root.
    """
    xf = unreal.Transform()
    for b in unreal.AnimationLibrary.find_bone_path_to_root(anim, bone):
        xf = xf.multiply(unreal.AnimationLibrary.get_bone_pose_for_time(
            anim, b, time, False))
    return xf.translation


def _bone_xf(anim, bone, time):
    """Component-space TRANSFORM of a bone at a time (not just its position)."""
    xf = unreal.Transform()
    for b in unreal.AnimationLibrary.find_bone_path_to_root(anim, bone):
        xf = xf.multiply(unreal.AnimationLibrary.get_bone_pose_for_time(
            anim, b, time, False))
    return xf


def _skeleton_bone_names(skeleton):
    pose = unreal.AnimPoseExtensions.get_reference_pose(skeleton)
    return [str(b) for b in unreal.AnimPoseExtensions.get_bone_names(pose)]


def mesh_ref_pose(mesh):
    """{bone: (component-space Transform, parent name or None)} in the MESH's
    own reference pose.

    Not the skeleton's.  SKM_Quinn_Simple shares SK_Mannequin, whose reference
    pose is Manny's: the two disagree by ~10 degrees at the hand and ~4 cm at
    the fingers, and what a clip shows on a mesh is built on the mesh's pose
    (see visible_bone_xf).  A skeleton can also lag its mesh: moving a bone
    that already exists never rewrites the skeleton's copy of it.
    """
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.SkeletalMeshActor, unreal.Vector(0, 0, -1000000))
    try:
        comp = actor.skeletal_mesh_component
        comp.set_skeletal_mesh_asset(mesh)
        out = {}
        for i in range(comp.get_num_bones()):
            name = str(comp.get_bone_name(i))
            parent = str(comp.get_parent_bone(name))
            out[name] = (comp.get_socket_transform(
                name, unreal.RelativeTransformSpace.RTS_COMPONENT),
                None if parent in ("", "None") else parent)
        return out
    finally:
        unreal.EditorLevelLibrary.destroy_actor(actor)


def visible_bone_xf(anim, mesh, ref=None):
    """A function bone -> component-space Transform of ``anim`` at time 0 as it
    is SHOWN on ``mesh``, which is not what _bone_xf samples.

    A track that only repeats the skeleton's reference pose is dropped by
    compression, and a dropped track is filled from the reference pose of the
    MESH being animated.  MM_Idle's metacarpals are such tracks: sampled raw
    they hold Manny's rest, on SKM_Quinn_Simple they show Quinn's, 10-15
    degrees apart.  The retargeter reads the pose as shown -- predicted this
    way its finger output matches to 0.0 degrees, sampled raw it is 15 off.
    """
    ref = ref or mesh_ref_pose(mesh)
    skel = unreal.AnimPoseExtensions.get_reference_pose(
        mesh.get_editor_property("skeleton"))
    cache = {}

    def local(bone):
        raw = unreal.AnimationLibrary.get_bone_pose_for_time(anim, bone, 0.0, False)
        rest = unreal.AnimPoseExtensions.get_bone_pose(
            skel, bone, unreal.AnimPoseSpaces.LOCAL)
        same = (raw.rotation.angular_distance(rest.rotation) < 1e-3
                and (raw.translation - rest.translation).length() < 0.01)
        if not same:
            return raw
        xf, parent = ref[bone]
        return xf.make_relative(ref[parent][0]) if parent else xf

    def world(bone):
        if bone not in cache:
            _xf, parent = ref[bone]
            mine = local(bone)
            cache[bone] = mine.multiply(world(parent)) if parent else mine
        return cache[bone]

    return world
