"""export_poses.py -- sample every animation sequence the project holds into
bone positions, for the animation library viewer (README.md).

    python3 Scripts/dev/uepy.py --cold --summary Scripts/dev/anim_library/export_poses.py

Per clip it writes Saved/AnimLibrary/poses/<id>.json (the body's joints per
frame, in cm, as integers, in the clip's own frame: x right, y forward, z up,
facing taken from frame 0, the pelvis's x and y taken out so a clip that
travels stays on the spot) and one line of Saved/AnimLibrary/rows.jsonl.
Each skeleton's bone list and parents land in skeletons.json.
build_library.py turns those into the catalogue the page reads.

Why joints and not video: a cold editor never ticks, so no mesh can be posed
and photographed in it, and a headless game renders nothing; the pose of a
clip at a time is exact through AnimPoseExtensions, in any rig, with no GPU.

Tooling, not content: nothing in the game reads any of this.
Optional Saved/AnimLibrary/job.json: {"only": [clip names], "offset": n,
"count": n, "force": bool}.
"""
import json
import math
import os
import re
import time

import sys

import unreal

_SCRIPTS = os.path.join(unreal.Paths.project_dir(), "Scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
from asset_pipeline.rig_util import mesh_ref_pose  # noqa: E402

LIB = os.path.join(unreal.Paths.project_dir(), "Saved", "AnimLibrary")
# Every animation sequence under /Game is listed; a clip's source is the first
# of these its path starts with, else the folder under /Game. A pack added to
# the project needs no line here, only a nicer name if its folder's is poor.
SOURCES = (("/Game/GAS/", "GAS"), ("/Game/Sourced/Lyra/", "Lyra"),
           ("/Game/Sourced/Mixamo/", "Mixamo"), ("/Game/Sourced/Quaternius/", "Quaternius"),
           ("/Game/Sourced/Characters/", "Game (baked)"), ("/Game/Weapons/", "Game (baked)"),
           ("/Game/Characters/Mannequins/", "UE5 Mannequin"),
           ("/Game/MetaHumans/", "MetaHuman"),
           ("/Game/FreeLadderAnimationSet/", "FreeLadder"),
           ("/Game/FP_AKS74U_Animation/", "FP_AKS74U"))
Q = "/Game/Sourced/Quaternius"
MESHES = {
    "SK_UEFN_Mannequin": "/Game/GAS/Characters/UEFN_Mannequin/Meshes/SKM_UEFN_Mannequin",
    "SK_Mannequin": "/Game/Sourced/Lyra/Characters/Heroes/Mannequin/Meshes/SKM_Manny",
    "SK_XBot": "/Game/Sourced/Mixamo/XBot/SKM_XBot",
    "SK_UAL1": f"{Q}/UAL1/SKM_UAL1", "SK_UAL2": f"{Q}/UAL2/SKM_UAL2",
    "SK_Zombie": f"{Q}/Zombie/SKM_Zombie",
}
# The same clips again on other bodies, or creatures that are not the player's
# to browse: the original is on the list.
SKIP = ("SK_Adventurer01", "SK_Adventurer02", "SK_Adventurer03", "SK_Zombie01",
        "SK_Wendigo01")
# A skeleton with fewer of the body's joints than this is not a body (a gun, a
# face, a garment): its clips are counted in the summary and left out.
MIN_JOINTS = 15
# The joints of the body worth drawing: the spine, head, arms to the hand and
# legs to the toe, on the mannequin's names and Mixamo's. Helper bones (twist,
# corrective, fingers) are left out: this is for choosing a motion.
KEEP = re.compile(
    r"^(pelvis|spine_0\d|neck_0\d|head|(clavicle|upperarm|lowerarm|hand|thigh|calf|foot|ball)_[lr]"
    r"|Hips|Spine\d?|Neck|Head|HeadTop_End|(Left|Right)(Shoulder|Arm|ForeArm|Hand|UpLeg|Leg|Foot|ToeBase))$")
PELVIS = ("pelvis", "Pelvis", "Hips", "hips", "pelvis_01")
LEGS = (("thigh_l", "thigh_r"), ("LeftUpLeg", "RightUpLeg"), ("upperleg_l", "upperleg_r"),
        ("LeftUpperLeg", "RightUpperLeg"), ("Left_UpLeg", "Right_UpLeg"), ("thigh_L", "thigh_R"))
FPS = 15
MIN_FRAMES, MAX_FRAMES = 4, 60
LOOP_TOL_CM = 6.0
_log = unreal.log_warning


def clip_id(path):
    return path.replace("/Game/", "").replace("/", "__")


def skeleton_of(mesh_path):
    ref = mesh_ref_pose(unreal.load_asset(mesh_path))
    names = list(ref)
    kept = [n for n in names if KEEP.match(n)]
    keep = set(kept)

    def parent(n):
        p = ref[n][1]
        while p is not None and p not in keep:
            p = ref[p][1]
        return p
    parents = [(kept.index(parent(n)) if parent(n) is not None else -1) for n in kept]
    pelvis = next((b for b in PELVIS if b in keep), None)
    legs = next((pr for pr in LEGS if pr[0] in keep and pr[1] in keep), None)
    return {"bones": kept, "parents": parents, "pelvis": pelvis, "legs": legs,
            "skipped": len(names) - len(kept)}


def source_of(path):
    return next((name for root, name in SOURCES if path.startswith(root)),
                path.split("/")[2])


def skeleton_from_clip(seq, sk):
    """The same facts as skeleton_of, for a skeleton with no mesh on the
    MESHES table: the bones from its reference pose, the parents from the
    clip. None when it is not a body."""
    ref = unreal.AnimPoseExtensions.get_reference_pose(sk)
    names = [str(n) for n in unreal.AnimPoseExtensions.get_bone_names(ref)]
    kept = [n for n in names if KEEP.match(n)]
    keep = set(kept)
    pelvis = next((b for b in PELVIS if b in keep), None)
    legs = next((pr for pr in LEGS if pr[0] in keep and pr[1] in keep), None)
    if len(kept) < MIN_JOINTS or not pelvis or not legs:
        return None

    def parent(n):
        up = [str(b) for b in unreal.AnimationLibrary.find_bone_path_to_root(seq, n)]
        return next((kept.index(b) for b in up[1:] if b in keep), -1)
    return {"bones": kept, "parents": [parent(n) for n in kept], "pelvis": pelvis,
            "legs": legs, "skipped": len(names) - len(kept)}


class Skeletons:
    """The viewer's skeletons by key. The MESHES table's keep their names (the
    poses already written index their bone lists); another skeleton is keyed
    by its own name, with its pack's folder when the name is taken (four
    packs ship an SK_Mannequin)."""

    def __init__(self, known):
        self.by_key = dict(known)
        # skeleton path -> key, or None: not a body. An earlier run's keys
        # come back by the path each was found at, so a key never changes.
        self.key_of = {f["path"]: k for k, f in known.items() if f.get("path")}
        for key, mesh in MESHES.items():
            sk = unreal.load_asset(mesh).get_editor_property("skeleton")
            self.key_of[sk.get_path_name()] = key

    def key(self, seq):
        sk = seq.get_editor_property("skeleton")
        if not sk:
            return None
        path = sk.get_path_name()
        if path not in self.key_of:
            facts = skeleton_from_clip(seq, sk)
            key = None
            if facts:
                key = sk.get_name()
                if key in self.by_key or key in SKIP:
                    key = f"{key} ({source_of(path)})"
                self.by_key[key] = dict(facts, path=path)
                _log(f"[ANIMLIB] {key}: {len(facts['bones'])} joints, from {path}")
            self.key_of[path] = key
        return self.key_of[path]


def sample(seq, skel):
    """Frames x bones x (x, y, z) in cm and the clip's facts, or None."""
    length = max(seq.get_play_length(), 0.0)
    frames = int(min(MAX_FRAMES, max(MIN_FRAMES, round(length * FPS))))
    opts = unreal.AnimPoseEvaluationOptions()
    world = unreal.AnimPoseSpaces.WORLD
    bones = skel["bones"]
    raw = []
    for i in range(frames):
        t = length * i / max(frames - 1, 1) if frames > 1 else 0.0
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(seq, t, opts)
        row = []
        for b in bones:
            v = unreal.AnimPoseExtensions.get_bone_pose(pose, b, world).translation
            row.append((v.x, v.y, v.z))
        raw.append(row)
    bi = {b: i for i, b in enumerate(bones)}
    pel = bi.get(skel["pelvis"], 0)
    # Facing, from frame 0: forward = up x left, in the plane.
    fx, fy = 0.0, 1.0
    if skel["legs"]:
        l, r = raw[0][bi[skel["legs"][0]]], raw[0][bi[skel["legs"][1]]]
        lx, ly = l[0] - r[0], l[1] - r[1]
        n = math.hypot(lx, ly)
        if n > 1e-6:
            lx, ly = lx / n, ly / n
            fx, fy = -ly, lx           # (0,0,1) x (lx,ly,0)
    rx, ry = fy, -fx                   # right = forward x up
    out, travel = [], 0.0
    p0 = raw[0][pel]
    for row in raw:
        c = row[pel]
        for (x, y, z) in row:
            dx, dy = x - c[0], y - c[1]
            out.extend((round(dx * rx + dy * ry), round(dx * fx + dy * fy), round(z)))
    pl, pf = raw[-1][pel][0] - p0[0], raw[-1][pel][1] - p0[1]
    travel = math.hypot(pl, pf)
    fwd_cm = pl * fx + pf * fy
    first, last = raw[0], raw[-1]
    gap = max(math.dist((a[0] - first[pel][0], a[1] - first[pel][1], a[2]),
                        (b[0] - last[pel][0], b[1] - last[pel][1], b[2]))
              for a, b in zip(first, last))
    top = max(r[pel][2] for r in raw) - min(r[pel][2] for r in raw)
    return out, frames, {"travel_cm": round(travel), "forward_cm": round(fwd_cm),
                         "loops": gap < LOOP_TOL_CM, "pelvis_rise_cm": round(top)}


def main():
    os.makedirs(os.path.join(LIB, "poses"), exist_ok=True)
    job = {}
    jp = os.path.join(LIB, "job.json")
    if os.path.exists(jp):
        job = json.load(open(jp))
    reg = unreal.AssetRegistryHelpers.get_asset_registry()
    skels = {}
    for sk, mesh in MESHES.items():
        skels[sk] = skeleton_of(mesh)
        _log(f"[ANIMLIB] {sk}: {len(skels[sk]['bones'])} joints "
             f"({skels[sk]['skipped']} dropped), pelvis {skels[sk]['pelvis']}, legs {skels[sk]['legs']}")
    sp = os.path.join(LIB, "skeletons.json")
    if os.path.exists(sp) and not job.get("force"):
        # An earlier run's, for the rows it wrote and this run will not redo.
        skels = {**json.load(open(sp)), **skels}
    book = Skeletons(skels)
    skels = book.by_key
    todo = []
    for a in reg.get_assets_by_class(
            unreal.TopLevelAssetPath("/Script/Engine", "AnimSequence"), True):
        path = str(a.package_name)
        if path.startswith("/Game/"):
            todo.append((source_of(path + "/"), path, str(a.asset_name)))
    todo.sort(key=lambda r: r[1])
    if job.get("only"):
        todo = [r for r in todo if r[2] in job["only"]]
    todo = todo[job.get("offset", 0):][:job.get("count") or None]
    rows_path = os.path.join(LIB, "rows.jsonl")
    seen = set()
    if os.path.exists(rows_path) and not job.get("force"):
        seen = {json.loads(l)["path"] for l in open(rows_path) if l.strip()}
    out = open(rows_path, "a")
    t0, done, failed, no_body = time.time(), 0, [], {}
    for n, (source, path, name) in enumerate(todo):
        if path in seen:
            continue
        try:
            seq = unreal.load_asset(path)
            sk = seq.get_editor_property("skeleton")
            if not sk or sk.get_name() in SKIP:
                continue
            skn = book.key(seq)
            if skn is None:
                no_body[sk.get_name()] = no_body.get(sk.get_name(), 0) + 1
                continue
            if source == "Quaternius" and sk.get_name() == "SK_Mannequin":
                continue
            additive = ("NONE" if "NONE" in str(seq.get_editor_property("additive_anim_type"))
                        else "ADDITIVE")
            row = {"id": clip_id(path), "path": path, "name": name, "source": source,
                   "skeleton": skn, "length": round(seq.get_play_length(), 3),
                   "root_motion": bool(seq.get_editor_property("enable_root_motion")),
                   "additive": additive, "frames": 0}
            if "NONE" in additive and seq.get_play_length() > 0.0:
                data, frames, facts = sample(seq, skels[skn])
                with open(os.path.join(LIB, "poses", row["id"] + ".json"), "w") as f:
                    json.dump({"f": frames, "p": data}, f, separators=(",", ":"))
                row.update(facts, frames=frames)
            out.write(json.dumps(row) + "\n")
            done += 1
        except Exception as e:  # one bad clip must not end a run of thousands
            failed.append(f"{name}: {e}")
        if n % 100 == 0:
            _log(f"[ANIMLIB] {n}/{len(todo)} {name} ({time.time() - t0:.0f}s)")
    out.close()
    with open(sp, "w") as f:
        json.dump(skels, f)
    _log(f"[ANIMLIB] {done} clips in {time.time() - t0:.0f}s; failed {len(failed)}: {failed[:8]}")
    with open(os.path.join(LIB, "export_summary.txt"), "w") as f:
        f.write(f"{done} clips in {time.time() - t0:.0f}s\nfailed {len(failed)}\n" + "\n".join(failed)
                + f"\nnot a body, left out: {json.dumps(no_body)}\n")


main()
