"""verify.ragdoll -- Ragdoll joint limits planned from each physics asset.
"""

import unreal

from combat.hit_zones import hit_zones
from combat.paths import CHARACTER_BP_PATH, NPC_BP_PATH
from combat.ragdoll import (
    RAGDOLL_JOINTS, RAGDOLL_MESH_ROOT, _v_rotate, _v_signed_angle,
    ragdoll_plan,
)
from combat.verify.common import (
    cdo, check, component_template, components, load,
)


# ─── A ragdoll needs bodies to be a ragdoll ──────────────────────────────────

def check_ragdoll_bodies():
    # Not a formality: it is the one precondition the collapse cannot check for
    # itself, and a mesh that arrives without a physics asset would simply stand
    # there dead. install_hit_zones already depends on the same bodies, so a rig
    # that cannot ragdoll cannot be shot in the head either.
    for bp_path in (CHARACTER_BP_PATH, NPC_BP_PATH):
        bp = load(bp_path)
        if not bp:
            continue
        mesh = None
        for name in components(bp):
            obj = component_template(bp, name)
            if isinstance(obj, unreal.SkeletalMeshComponent):
                mesh = obj
                break
        if mesh is None:
            mesh = cdo(bp).get_editor_property("mesh")
        asset = mesh.get_editor_property("skeletal_mesh_asset") if mesh else None
        pa = asset.get_editor_property("physics_asset") if asset else None
        check(f"{bp_path.rsplit('/', 1)[1]} has a physics asset to ragdoll with",
              pa is not None, pa.get_name() if pa else "None")
        if pa:
            head, limbs, body = hit_zones(asset)
            check(f"...with enough bodies to fall apart ({bp_path.rsplit('/', 1)[1]})",
                  len(head) + len(limbs) + len(body) >= 8,
                  f"{len(head) + len(limbs) + len(body)} bodies")

    # The ragdoll's JOINTS, not just its bodies. The importer's physics asset gives
    # every joint one soft 45/45/45 cone centred on the bind pose -- knees folding
    # sideways and backwards, an elbow bent in the bind pose free to hyperextend --
    # and a corpse on those limits lands in shapes no body makes. tune_ragdolls()
    # rewrites limits, springs and frames; this reads them back off the saved
    # assets and then bends every joint to just inside and just past each end of
    # its RAGDOLL_JOINTS range, to prove the saved frames put the range on the
    # side of the joint a body really folds to.
    def _saved_vec(di, name):
        v = di.get_editor_property(name)
        return (v.x, v.y, v.z)


    def _world(rot, v):
        w = rot.rotate_vector(unreal.Vector(*v))
        return (w.x, w.y, w.z)


    def _limit_allows(j, di, flex):
        """Would the saved constraint let this joint sit at `flex` (absolute deg)?"""
        axis = j["axis"]
        x1, y1 = (_world(j["rot1"], _saved_vec(di, "pri_axis1")),
                  _world(j["rot1"], _saved_vec(di, "sec_axis1")))
        x2, y2 = (_world(j["rot2"], _saved_vec(di, "pri_axis2")),
                  _world(j["rot2"], _saved_vec(di, "sec_axis2")))
        # The flex axis is the hinge's X (twist) or the ball joint's Y (swing2);
        # measure the frames' disagreement with the vector that is not it.
        probe1, probe2 = (y1, y2) if j["hinge"] else (x1, x2)
        moved = _v_rotate(probe1, axis, flex - j["rest"])
        prof = di.get_editor_property("profile_instance")
        limit = (prof.get_editor_property("twist_limit")
                 .get_editor_property("twist_limit_degrees") if j["hinge"] else
                 prof.get_editor_property("cone_limit")
                 .get_editor_property("swing2_limit_degrees"))
        return abs(_v_signed_angle(probe2, moved, axis)) <= limit + 1e-3


    for _path in sorted(unreal.EditorAssetLibrary.list_assets(RAGDOLL_MESH_ROOT,
                                                              recursive=True)):
        _mesh = load(_path.split(".")[0])
        if not isinstance(_mesh, unreal.SkeletalMesh):
            continue
        _pa = _mesh.get_editor_property("physics_asset")
        if not _pa:
            continue
        _plan = ragdoll_plan(_mesh)
        _name = _pa.get_name()
        check(f"{_name}: every joint has a role in RAGDOLL_JOINTS",
              len(_plan) == len(_pa.get_constraints(False)),
              f"{len(_plan)} of {len(_pa.get_constraints(False))}")
        _dis = {j["child"]: j["template"].get_editor_property("DefaultInstance")
                for j in _plan}
        _bad = {}
        for j in _plan:
            prof = _dis[j["child"]].get_editor_property("profile_instance")
            cone = prof.get_editor_property("cone_limit")
            tw = prof.get_editor_property("twist_limit")
            got = (round(cone.get_editor_property("swing1_limit_degrees"), 3),
                   round(cone.get_editor_property("swing2_limit_degrees"), 3),
                   round(tw.get_editor_property("twist_limit_degrees"), 3))
            if got != j["limits"]:
                _bad[j["child"]] = got
        check(f"...and the saved limits are the planned ones", not _bad, str(_bad))
        _bad = [j["child"] for j in _plan
                if any(max(abs(a - b) for a, b in zip(
                    _saved_vec(_dis[j["child"]], k[:3] + "_axis" + k[3]), j[k])) > 1e-3
                    for k in ("pri1", "sec1", "pri2", "sec2"))]
        check(f"...and the saved constraint frames are the planned ones",
              not _bad, str(_bad))
        _soft = {}
        for j in _plan:
            prof = _dis[j["child"]].get_editor_property("profile_instance")
            for lim in (prof.get_editor_property("cone_limit"),
                        prof.get_editor_property("twist_limit")):
                if lim.get_editor_property("stiffness") < 500.0:
                    _soft[j["child"]] = lim.get_editor_property("stiffness")
        check(f"...and no joint keeps the importer's soft limit a body falls "
              f"through (stiffness >= 500, as PA_Mannequin)", not _soft, str(_soft))
        _wrong = []
        for j in _plan:
            lo, hi = RAGDOLL_JOINTS[j["role"]]["flex"]
            di = _dis[j["child"]]
            for flex, want in ((lo + 2, True), (hi - 2, True),
                               (lo - 5, False), (hi + 5, False)):
                if _limit_allows(j, di, flex) != want:
                    _wrong.append(f"{j['child']}@{flex:.0f}")
        check(f"...and every joint bends only its own way, as far as "
              f"RAGDOLL_JOINTS says", not _wrong, str(_wrong))
        _hinges = [j for j in _plan if j["role"] in ("leg", "forearm")]
        _wrong = [f"{j['child']}" for j in _hinges
                  if _limit_allows(j, _dis[j["child"]], -10.0)
                  or not _limit_allows(j, _dis[j["child"]], 110.0)]
        check(f"...and no knee or elbow hyperextends 10 deg, and all of them fold "
              f"110 deg ({len(_hinges)} hinges)", _hinges and not _wrong, str(_wrong))
        _knees = [j for j in _plan if j["role"] == "leg"]
        check(f"...and both knees are among them", len(_knees) == 2,
              str([j["child"] for j in _knees]))


def run():
    check_ragdoll_bodies()
