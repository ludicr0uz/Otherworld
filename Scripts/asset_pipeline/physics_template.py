"""physics_template.py -- a body that must replace another takes that body's
physics bodies: the same bones carry one, whatever its own mesh looks like.

Editor-side. import_characters.py calls adopt() for every character whose
catalog spec names ``compatible_with``; by hand:

    python3 Scripts/dev/uepy.py Scripts/asset_pipeline/physics_template.py

``SkeletalMeshEditorSubsystem.create_physics_asset`` takes no settings, and
which bones get a body depends on each mesh's geometry. On the adventurer in
boxers it made 15 bodies with none on Head or Spine01: the head rode on the
neck's body, so combat/hit_zones.py found no head to zone and the weapons
build stopped. Every Meshy rig has the same bone names, so the reference's
body set is copied whole. Three things in the copy are the reference's and
not this body's, and each is put right:

  * where each joint is. A constraint keeps its position in both bodies'
    bone spaces, and this rig's bones are other lengths: reseat_joints()
    puts every joint back on its child bone, from this mesh's reference pose.
  * which way each joint bends: combat/ragdoll.py rewrites every frame from
    the reference pose, in the weapons build.
  * how big each body is and which way it lies: combat/hit_bodies.py refits
    every capsule to this mesh's vertices, on their own axes, in the same build.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unreal                                                     # noqa: E402

from asset_pipeline import player_body                            # noqa: E402

ROOT = "/Game/Sourced/Characters"


def _log(msg):
    unreal.log_warning(f"[PHYS] {msg}")


def _mesh_path(name):
    return f"{ROOT}/SKM_{name}/SKM_{name}"


def _pa_path(name):
    return f"{ROOT}/SKM_{name}/SKM_{name}_PhysicsAsset"


def _templates(pa):
    """Every constraint template of ``pa`` (the array is protected; its
    entries are subobjects under a predictable name)."""
    want = len(pa.get_constraints(False))
    out, i = [], 0
    while len(out) < want and i < 4 * want + 16:
        t = unreal.find_object(pa, f"PhysicsConstraintTemplate_{i}")
        i += 1
        if t is not None:
            out.append(t)
    return out


def joint_seats(mesh, pa):
    """[(template, child bone, parent bone, the child's place in the parent's
    space)] for every joint, from ``mesh``'s reference pose."""
    skeleton = mesh.get_editor_property("skeleton")
    pose = unreal.AnimPoseExtensions.get_reference_pose(skeleton)
    names = {str(n) for n in unreal.AnimPoseExtensions.get_bone_names(pose)}
    out = []
    for t in _templates(pa):
        di = t.get_editor_property("DefaultInstance")
        child = str(di.get_editor_property("constraint_bone1"))
        parent = str(di.get_editor_property("constraint_bone2"))
        if child not in names or parent not in names:
            raise RuntimeError(f"{pa.get_name()}: a joint between {child} and "
                               f"{parent}, which {skeleton.get_name()} lacks")
        at = unreal.AnimPoseExtensions.get_bone_pose(
            pose, child, unreal.AnimPoseSpaces.WORLD).translation
        seat = unreal.AnimPoseExtensions.get_bone_pose(
            pose, parent, unreal.AnimPoseSpaces.WORLD).inverse_transform_location(at)
        out.append((t, child, parent, seat))
    return out


def reseat_joints(mesh, pa):
    """Put every joint of ``pa`` on its child bone as ``mesh`` has it; returns
    the furthest any joint was moved, in cm."""
    worst = 0.0
    pa.modify()
    for t, child, _parent, seat in joint_seats(mesh, pa):
        t.modify()
        di = t.get_editor_property("DefaultInstance")
        was = di.get_editor_property("pos2")
        worst = max(worst, (was - seat).length())
        di.set_editor_property("pos1", unreal.Vector(0.0, 0.0, 0.0))
        di.set_editor_property("pos2", seat)
        t.set_editor_property("DefaultInstance", di)
        got = t.get_editor_property("DefaultInstance").get_editor_property("pos2")
        if (got - seat).length() > 0.01:
            raise RuntimeError(f"{pa.get_name()}: {child}'s joint did not move")
    return worst


def adopt(name, reference):
    """Replace ``name``'s physics asset with a copy of ``reference``'s, its
    joints reseated on ``name``'s bones. False where there is nothing to copy."""
    eal = unreal.EditorAssetLibrary
    mesh = eal.load_asset(_mesh_path(name))
    if not mesh or not eal.does_asset_exist(_pa_path(reference)):
        _log(f"{name}: no mesh, or no {reference} physics asset to copy -- skipped")
        return False
    mesh.set_editor_property("physics_asset", None)
    if eal.does_asset_exist(_pa_path(name)) and not eal.delete_asset(_pa_path(name)):
        raise RuntimeError(f"could not delete {_pa_path(name)} to replace it")
    pa = eal.duplicate_asset(_pa_path(reference), _pa_path(name))
    if not pa:
        raise RuntimeError(f"could not copy {_pa_path(reference)}")
    moved = reseat_joints(mesh, pa)
    mesh.set_editor_property("physics_asset", pa)
    eal.save_loaded_asset(pa)
    eal.save_loaded_asset(mesh)
    _log(f"{name}: physics bodies are {reference}'s ({len(pa.get_constraints(False))} "
         f"joints, reseated by up to {moved:.1f} cm)")
    return True


def main(only=None):
    """Every imported character whose spec names a body to replace, or just
    the short names in ``only``."""
    for spec in player_body.catalog.CHARACTERS:
        name = player_body.name_of(spec.id)
        reference = player_body.reference_of(name)
        if reference and (not only or name in only):
            adopt(name, reference)


if __name__ == "__main__":
    main()
