"""measure_gas_bridge.py -- what moving the player's hidden mesh from
SK_Mannequin to the Game Animation Sample's SK_UEFN_Mannequin would break.
Editor-side; reads, writes nothing but its report.

    python3 Scripts/dev/uepy.py Scripts/asset_pipeline/measure_gas_bridge.py

Saved/gas_bridge.txt: the two skeletons' bones (which the other lacks), the
bones and sockets the combat scripts name (combat/grip.py, hit_zones.py,
hit_bodies.py, skin.py, hold_pose.py, support_hand.py), each mesh's sockets,
the two physics assets' bodies, how far apart the two reference poses stand,
and which skeletons each calls compatible.  The choice it was written for is
in Scripts/asset_pipeline/CLAUDE.md ("The skeleton bridge").
"""

import os
import sys

import unreal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _name in [m for m in sys.modules if m.startswith("asset_pipeline")]:
    del sys.modules[_name]          # a warm editor keeps yesterday's modules

from asset_pipeline.gas_bridge_paths import HIDDEN_MESH_GAS           # noqa: E402
from asset_pipeline.rig_chains import CHAINS_MANNEQUIN                # noqa: E402
from asset_pipeline.rig_util import _bone_names, _load, mesh_ref_pose  # noqa: E402

PLAYER_BP = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter"
MANNEQUIN_MESH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(
    unreal.Paths.project_saved_dir()), "gas_bridge.txt")

# Every bone a combat script addresses by name on the player's mesh (grep
# '"hand_r"' and friends under Scripts/combat, 2026-10-08).
NAMED_BONES = (
    "root", "pelvis", "spine_01", "spine_03", "spine_05", "neck_01", "head",
    "clavicle_l", "clavicle_r", "upperarm_l", "upperarm_r", "lowerarm_l",
    "lowerarm_r", "hand_l", "hand_r", "thigh_l", "thigh_r", "calf_l", "calf_r",
    "foot_l", "foot_r", "ball_l", "ball_r",
)
NAMED_SOCKETS = ("HandGrip_R", "HandGrip_L")
# Where two bodies must agree for a socket offset or a hit body to carry over.
POSED = ("pelvis", "spine_05", "head", "hand_l", "hand_r", "foot_l", "foot_r")


def _sockets(mesh):
    """{socket: bone} of a mesh and its skeleton."""
    out = {}
    for i in range(mesh.num_sockets()):
        s = mesh.get_socket_by_index(i)
        out[str(s.get_editor_property("socket_name"))] = str(s.get_editor_property("bone_name"))
    return out


def _bodies(mesh):
    """(the mesh's physics asset, the bones it has a body on).  The asset's
    own array is protected from Python; each setup is a named subobject."""
    pa = mesh.get_editor_property("physics_asset")
    names = []
    for i in range(256):
        setup = unreal.find_object(pa, f"SkeletalBodySetup_{i}") if pa else None
        if setup:
            names.append(str(setup.get_editor_property("bone_name")))
    return pa, sorted(names)


def _compatible(mesh):
    skel = mesh.get_editor_property("skeleton")
    try:
        return [str(s.get_path_name()) for s in skel.get_editor_property("compatible_skeletons")]
    except Exception as e:                                   # noqa: BLE001
        return [f"unreadable: {e}"]


def _player_anim_assets():
    """{class: count} of the animation assets on SK_Mannequin that the
    player's blueprint reaches: what bridge (a) has to bring onto the UEFN
    skeleton before the weapon layers play on it."""
    reg = unreal.AssetRegistryHelpers.get_asset_registry()
    opts = unreal.AssetRegistryDependencyOptions(
        include_soft_package_references=False, include_hard_package_references=True)
    seen, todo, out = set(), [PLAYER_BP], {}
    while todo:
        pkg = todo.pop()
        if pkg in seen or not pkg.startswith("/Game/") or pkg.startswith("/Game/MetaHumans"):
            continue
        seen.add(pkg)
        for data in reg.get_assets_by_package_name(pkg):
            if "SK_Mannequin" in str(data.get_tag_value("Skeleton") or ""):
                cls = str(data.asset_class_path.asset_name)
                out[cls] = out.get(cls, 0) + 1
        todo.extend(str(d) for d in reg.get_dependencies(pkg, opts) or [])
    return out


def main():
    man, uefn = _load(MANNEQUIN_MESH), _load(HIDDEN_MESH_GAS)
    mb, ub = _bone_names(man), _bone_names(uefn)
    lines = [f"mannequin {man.get_path_name()} on "
             f"{man.get_editor_property('skeleton').get_name()}: {len(mb)} bones",
             f"uefn      {uefn.get_path_name()} on "
             f"{uefn.get_editor_property('skeleton').get_name()}: {len(ub)} bones",
             f"only on the mannequin ({len(set(mb) - set(ub))}): {sorted(set(mb) - set(ub))}",
             f"only on the UEFN ({len(set(ub) - set(mb))}): {sorted(set(ub) - set(mb))}",
             "named by combat scripts, missing on the UEFN: "
             f"{[b for b in NAMED_BONES if b not in ub]}",
             "retarget chain ends missing on the UEFN: "
             f"{sorted({b for se in CHAINS_MANNEQUIN.values() for b in se if b not in ub})}"]

    ms, us = _sockets(man), _sockets(uefn)
    lines += [f"mannequin sockets: {ms}", f"uefn sockets: {us}",
              f"named sockets missing on the UEFN: {[s for s in NAMED_SOCKETS if s not in us]}"]

    for label, mesh in (("mannequin", man), ("uefn", uefn)):
        pa, bodies = _bodies(mesh)
        lines.append(f"{label} physics asset {pa.get_path_name() if pa else None}: "
                     f"{len(bodies)} bodies {bodies}")
        lines.append(f"{label} compatible skeletons: {_compatible(mesh)}")

    mp, up = mesh_ref_pose(man), mesh_ref_pose(uefn)
    for bone in POSED:
        a, b = mp[bone][0], up[bone][0]
        gap = (a.translation - b.translation).length()
        turn = a.rotation.angular_distance(b.rotation) * 57.2958
        lines.append(f"reference pose {bone}: {gap:.1f} cm apart, {turn:.1f} deg "
                     f"(mannequin z {a.translation.z:.1f}, uefn z {b.translation.z:.1f})")

    anims = _player_anim_assets()
    lines.append(f"on SK_Mannequin, reached from the player's blueprint: "
                 f"{sum(anims.values())} animation assets {dict(sorted(anims.items()))}")

    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    for line in lines:
        unreal.log_warning(f"[GEN] gas bridge: {line}")
    unreal.log_warning(f"[GEN] gas bridge: report {OUT}")


if __name__ == "__main__":
    main()
