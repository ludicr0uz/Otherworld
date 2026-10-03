"""The base body in boxers: imported on its own skeleton at the player's
height, with a physics asset, a material, finger bones and its own animation
set, so the player can be moved onto it."""

import unreal

from asset_pipeline.catalog import QUINN_HEIGHT_M
from asset_pipeline.rig_chains import meshy_finger_bones
from combat.verify.common import check, load
from clothing.specs import BASE_BODY_ABP, BASE_BODY_MESH, BASE_BODY_SKELETON


def run():
    mesh = load(BASE_BODY_MESH)
    check("the base body in boxers is a skeletal mesh",
          isinstance(mesh, unreal.SkeletalMesh), BASE_BODY_MESH)
    if not isinstance(mesh, unreal.SkeletalMesh):
        return
    skel = mesh.get_editor_property("skeleton")
    check("the base body is on its own skeleton",
          skel is not None and skel.get_path_name().split(".")[0] == BASE_BODY_SKELETON,
          skel.get_path_name() if skel else "None")
    height = mesh.get_bounds().box_extent.z * 2.0
    check(f"the base body stands about {QUINN_HEIGHT_M:.2f} m tall",
          abs(height - QUINN_HEIGHT_M * 100.0) < 10.0, f"{height:.1f} uu")
    check("the base body has a physics asset (it can be shot)",
          mesh.get_editor_property("physics_asset") is not None)
    mats = mesh.get_editor_property("materials")
    check("the base body wears its PBR material instance",
          len(mats) > 0 and isinstance(mats[0].material_interface,
                                       unreal.MaterialInstanceConstant),
          str([m.material_interface.get_name() if m.material_interface else None
               for m in mats]))
    pose = unreal.AnimPoseExtensions.get_reference_pose(skel) if skel else None
    bones = {str(b) for b in unreal.AnimPoseExtensions.get_bone_names(pose)} if pose else set()
    missing = [b for b in meshy_finger_bones() if b not in bones]
    check("the base body has its finger bones", not missing,
          f"{len(missing)} missing, e.g. {missing[:3]}")
    check("the base body has its own retargeted anim BP",
          isinstance(load(BASE_BODY_ABP), unreal.AnimBlueprint), BASE_BODY_ABP)
