#!/usr/bin/env python3
"""fetch_monsters.py -- run the Meshy chain for every spec in the catalog.

Host-side.  Imports no ``unreal``: this downloads into assets/cache/meshy/ and
stops.  Getting those files into Content/ is import_characters.py's job, run
inside the editor through Scripts/dev/uepy.py.

    python3 Scripts/asset_pipeline/fetch_monsters.py            # all specs
    python3 Scripts/asset_pipeline/fetch_monsters.py zombie_01  # just one
    python3 Scripts/asset_pipeline/fetch_monsters.py --status   # spend nothing

Safe to re-run.  Every completed stage is recorded in the spec's task.json and
skipped on the next pass, so an interrupted run resumes instead of re-paying.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asset_pipeline import catalog                      # noqa: E402
from asset_pipeline.providers import meshy              # noqa: E402

GEN_PATH = "/openapi/v2/text-to-3d"
RIG_PATH = "/openapi/v1/rigging"


def _stage(state, name):
    return state["stages"].get(name)


def _finish(spec, state, name, task):
    state["stages"][name] = {
        "task_id": task["id"],
        "status": task["status"],
        "consumed_credits": task.get("consumed_credits"),
    }
    meshy.save_state(spec, state)
    return task


def _pull(spec, task, label):
    """Save a finished stage's outputs immediately.

    Downloads used to happen once, after the whole chain.  The zombie's first
    run paid 20 + 10 credits for a preview and a refine, then failed at the
    rigger and wrote nothing to disk -- the bytes existed, we had paid for
    them, and we had no copy.  Each stage now lands before the next one is
    allowed to fail.
    """
    out = meshy.cache_dir(spec)
    for fmt, url in (task.get("model_urls") or {}).items():
        if url:
            meshy.download(url, os.path.join(out, f"{spec.id}_{label}.{fmt}"))
    for tex in (task.get("texture_urls") or []):
        if not isinstance(tex, dict):
            continue
        for kind, url in tex.items():
            if isinstance(url, str) and url.startswith("http"):
                ext = url.split("?")[0].rsplit(".", 1)[-1][:4] or "png"
                meshy.download(url, os.path.join(out, "textures", f"{spec.id}_{kind}.{ext}"))
    if task.get("result"):
        _download_tree(task["result"], os.path.join(out, "rigged"), spec.id)


def run_spec(spec) -> dict:
    print(f"\n=== {spec.id} ===", flush=True)
    print(f"  height {spec.height_meters} m | {spec.target_polycount} tris | "
          f"{spec.texture_resolution} textures | {spec.pose_mode}", flush=True)
    state = meshy.load_state(spec)
    state["prompt"] = spec.prompt
    state["license"] = spec.license
    state["dest"] = spec.dest
    # The importer checks arrival scale against this. Without it that check
    # silently falls back to a default and validates nothing.
    state["height_meters"] = spec.height_meters
    state["target_polycount"] = spec.target_polycount

    def stage(name, submit, poll_path, label):
        """Run one stage, or reuse it if a previous run already paid for it."""
        done = _stage(state, name)
        if done:
            print(f"  [skip] {name} {done['task_id']}", flush=True)
            task = meshy._request("GET", f"{poll_path}/{done['task_id']}")
        else:
            print(f"  [{label}] {name} ...", flush=True)
            task_id = submit()
            task = meshy.poll(poll_path, task_id, name)
            _finish(spec, state, name, task)
        _pull(spec, task, name)
        return task

    preview_task = stage("preview", lambda: meshy.preview(spec), GEN_PATH, "1/4")

    # Rigging rejects untextured meshes, so PBR has to land before the rig.
    refine_task = stage("refine", lambda: meshy.refine(spec, preview_task["id"]),
                        GEN_PATH, "2/4")

    # And the rigger caps at 320k faces, which a 4k refine blows straight past.
    remesh_path = {"v": None}

    def _submit_remesh():
        task_id, used = meshy.remesh(spec, refine_task["id"])
        remesh_path["v"] = used
        return task_id

    done = _stage(state, "remesh")
    if done:
        print(f"  [skip] remesh {done['task_id']}", flush=True)
        rp = state.get("remesh_path", "/openapi/v1/remesh")
        remesh_task = meshy._request("GET", f"{rp}/{done['task_id']}")
        _pull(spec, remesh_task, "remesh")
    else:
        print("  [3/4] remesh ...", flush=True)
        task_id = _submit_remesh()
        state["remesh_path"] = remesh_path["v"]
        remesh_task = meshy.poll(remesh_path["v"], task_id, "remesh")
        _finish(spec, state, "remesh", remesh_task)
        _pull(spec, remesh_task, "remesh")

    rig_task = stage("rig", lambda: meshy.rig(spec, remesh_task["id"]), RIG_PATH, "4/4")

    state["cache_dir"] = meshy.cache_dir(spec)
    meshy.save_state(spec, state)
    spent = sum((s.get("consumed_credits") or 0) for s in state["stages"].values())
    print(f"  done -- {spent} credits, cached in "
          f"{os.path.relpath(state['cache_dir'], meshy.PROJECT_DIR)}", flush=True)
    return state


def _download_tree(node, dest, prefix, trail=""):
    """Rig results nest URLs a few levels deep; pull every one we find."""
    if isinstance(node, str) and node.startswith("http"):
        ext = node.split("?")[0].rsplit(".", 1)[-1][:5] or "bin"
        name = f"{prefix}{trail}.{ext}" if trail else f"{prefix}.{ext}"
        meshy.download(node, os.path.join(dest, name))
    elif isinstance(node, dict):
        for k, v in node.items():
            _download_tree(v, dest, prefix, f"{trail}_{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _download_tree(v, dest, prefix, f"{trail}_{i}")


def cmd_status():
    for spec in catalog.MONSTERS:
        state = meshy.load_state(spec)
        stages = state.get("stages", {})
        marks = " ".join(
            f"{n}:{'ok' if n in stages else '--'}"
            for n in ("preview", "refine", "remesh", "rig")
        )
        spent = sum((s.get("consumed_credits") or 0) for s in stages.values())
        print(f"{spec.id:14s} {marks}   {spent} credits")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ids", nargs="*", help="spec ids; default is all of them")
    ap.add_argument("--status", action="store_true", help="report progress, spend nothing")
    args = ap.parse_args()

    if args.status:
        cmd_status()
        return 0

    specs = [catalog.by_id(i) for i in args.ids] if args.ids else list(catalog.MONSTERS)
    failures = []
    for spec in specs:
        try:
            run_spec(spec)
        except meshy.MeshyError as exc:
            print(f"  FAILED {spec.id}: {exc}", flush=True)
            failures.append((spec.id, str(exc)))

    print("\n=== summary ===")
    cmd_status()
    for sid, err in failures:
        print(f"FAILED {sid}: {err}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
