#!/usr/bin/env python3
"""skeleton_probe.py -- fingerprint a rigged GLB's bone hierarchy, host-side.

No editor, no import.  Meshy's rigger ships an armature-only GLB alongside each
animation (~100 KB, skeleton and nothing else), and a GLB's first chunk is
plain JSON.  Reading the node graph out of it answers the question the whole
spike exists to answer -- do two separately generated monsters come back on
the same bone hierarchy -- in milliseconds instead of a 30-second cold boot.

    python3 Scripts/asset_pipeline/skeleton_probe.py            # compare all
    python3 Scripts/asset_pipeline/skeleton_probe.py <file.glb> # dump one

The fingerprint is over (bone name, parent name) pairs only.  Deliberately not
over transforms: a wendigo and a zombie SHOULD differ in proportion while
sharing a rig, and hierarchy is what decides whether one skeleton asset, one
IK Rig and one anim BP can serve both.
"""

import glob
import hashlib
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(HERE))
CACHE_ROOT = os.path.join(PROJECT_DIR, "assets", "cache", "meshy")


def glb_json(path):
    """The JSON chunk of a binary glTF."""
    with open(path, "rb") as fh:
        magic, version, _ = struct.unpack("<III", fh.read(12))
        if magic != 0x46546C67:
            raise ValueError(f"{path} is not a GLB (magic {magic:#x})")
        length, ctype = struct.unpack("<II", fh.read(8))
        if ctype != 0x4E4F534A:
            raise ValueError(f"{path}: first chunk is not JSON")
        return json.loads(fh.read(length).decode("utf-8"))


def hierarchy(doc):
    """[(bone, parent)] in node order, for every node in every skin."""
    nodes = doc.get("nodes", [])
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get("children", []):
            parent[c] = i
    joints = set()
    for skin in doc.get("skins", []):
        joints.update(skin.get("joints", []))
    if not joints:
        joints = set(range(len(nodes)))
    out = []
    for i in sorted(joints):
        name = nodes[i].get("name", f"node{i}")
        p = parent.get(i)
        pname = nodes[p].get("name", f"node{p}") if p is not None else "<root>"
        out.append((name, pname))
    return out


def fingerprint(pairs):
    blob = "\n".join(f"{b}<-{p}" for b, p in pairs)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def armature_glb(spec_dir):
    hits = sorted(glob.glob(os.path.join(spec_dir, "rigged", "*armature*.glb")))
    if hits:
        return hits[0]
    hits = sorted(glob.glob(os.path.join(spec_dir, "rigged", "*character*.glb")))
    return hits[0] if hits else None


def main(argv):
    if argv:
        for path in argv:
            pairs = hierarchy(glb_json(path))
            print(f"{path}\n  {len(pairs)} bones  fingerprint {fingerprint(pairs)}")
            for b, p in pairs:
                print(f"    {b:<28s} <- {p}")
        return 0

    results = {}
    for spec_dir in sorted(glob.glob(os.path.join(CACHE_ROOT, "*"))):
        if not os.path.isdir(spec_dir):
            continue
        glb = armature_glb(spec_dir)
        if not glb:
            continue
        pairs = hierarchy(glb_json(glb))
        results[os.path.basename(spec_dir)] = (fingerprint(pairs), pairs)

    if not results:
        print(f"no rigged GLBs under {CACHE_ROOT}")
        return 1

    for sid, (fp, pairs) in results.items():
        print(f"{sid:14s} {len(pairs):3d} bones  {fp}")

    prints = {fp for fp, _ in results.values()}
    print()
    if len(results) < 2:
        print("only one monster rigged so far -- need two to decide")
        return 0
    if len(prints) == 1:
        print("SHARED: identical bone hierarchies.")
        print("  One skeleton, one IK Rig, one retargeter and one anim BP serve every")
        print("  monster. Each new creature is a mesh and nothing else.")
    else:
        print("DIVERGENT: bone hierarchies differ.")
        names = {sid: {b for b, _ in pairs} for sid, (_, pairs) in results.items()}
        ids = list(names)
        a, b = names[ids[0]], names[ids[1]]
        print(f"  only in {ids[0]}: {sorted(a - b)}")
        print(f"  only in {ids[1]}: {sorted(b - a)}")
        print(f"  shared: {len(a & b)} bones")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
