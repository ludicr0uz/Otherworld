#!/usr/bin/env python3
"""bind_to_mannequin.py -- bind cached Meshy bodies to the mannequin's
skeleton.  Host-side: no editor, no credits.

    python3 Scripts/asset_pipeline/bind_to_mannequin.py adventurer_03
    python3 Scripts/asset_pipeline/bind_to_mannequin.py --all
    python3 Scripts/asset_pipeline/bind_to_mannequin.py adventurer_03 --check

Each body is written to assets/cache/meshy/<id>/bound/<id>_mannequin.glb with
a bind_report.json beside it, and checked (mannequin_bind/check.py).  --check
checks without writing.  The editor's half is import_bound.py.

What the bind does and why is in mannequin_bind/__init__.py.
"""

import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asset_pipeline.mannequin_bind import (             # noqa: E402
    bind, body as body_mod, check, paths, ref_skeleton,
)


def cached_ids():
    """Every cached spec with a rigged GLB; a folder set aside (``_name``, a
    generation that was replaced) is not one."""
    root = paths.meshy_cache()
    out = []
    for sid in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        if sid.startswith("_"):
            continue
        try:
            body_mod.rigged_glb(sid)
        except FileNotFoundError:
            continue
        out.append(sid)
    return out


def one(spec_id, mann, write=True):
    """Bind, check and report one body; True if it passed."""
    try:
        body = body_mod.load(spec_id)
        bound = bind.bind_body(body, mann)
    except (FileNotFoundError, ValueError) as why:
        # Not the Meshy humanoid rig, or not a body the mannequin's skeleton
        # fits (the wendigo): said, and the others still bind.
        print(f"{spec_id}: NOT BOUND -- {why}")
        return False
    with tempfile.TemporaryDirectory() as scratch:
        path = paths.bound_glb(spec_id) if write else os.path.join(scratch, "check.glb")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        bound.report["bytes"] = bind.write(body, bound, path)
        fails, measures = check.run(body, bound, mann, path)
        bound.report.update({"source": os.path.basename(body.mesh.path),
                             "failures": fails, "measures": measures})
        if write:
            with open(paths.bound_report(spec_id), "w") as fh:
                json.dump(bound.report, fh, indent=2, sort_keys=True)
                fh.write("\n")

    r = bound.report
    print(f"{spec_id}: {r['vertices']} vertices on {r['bones']} bones"
          + (f" -> {path}" if write else " (checked, not written)"))
    print(f"  forearm roll {r['forearm_roll_deg']}  fingers found {r['fingers_found']}")
    print(f"  edge lengths after/before {measures['edge_length_after_over_before']}")
    for s, m in sorted(measures["ribs_when_a_clavicle_lifts"].items()):
        print(f"  ribs under clavicle_{s} when it lifts {check.CLAVICLE_LIFT_DEG:.0f} deg: "
              f"{m['moved_cm_before']} cm before, {m['moved_cm_after']} cm bound "
              f"(clavicle weight there {m['clavicle_weight_before']} -> "
              f"{m['clavicle_weight_after']})")
    for note in r["notes"]:
        print(f"  note: {note}")
    for fail in fails:
        print(f"  FAIL: {fail}")
    return not fails


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("ids", nargs="*", help="catalog ids (see catalog.py)")
    ap.add_argument("--all", action="store_true", help="every cached body")
    ap.add_argument("--check", action="store_true", help="check without writing")
    args = ap.parse_args(argv)
    ids = cached_ids() if args.all else args.ids
    if not ids:
        ap.error("name a body, or --all")
    mann = ref_skeleton.read_uasset(paths.mannequin_mesh_file())
    results = [one(sid, mann, write=not args.check) for sid in ids]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
