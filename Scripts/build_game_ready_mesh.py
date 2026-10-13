#!/usr/bin/env python3
"""build_game_ready_mesh.py -- one high-triangle mesh in, a game-ready mesh
out: fewer triangles, a LOD chain, and an impostor as the last LOD.

Run outside the editor:

    python3 Scripts/build_game_ready_mesh.py trees                # the forest's five
    python3 Scripts/build_game_ready_mesh.py /Game/Some/SM_Rock   # any static mesh
    python3 Scripts/build_game_ready_mesh.py /Game/A/SM_X /Game/B/SM_Y --dest /Game/Props/LOD
    python3 Scripts/build_game_ready_mesh.py trees --set lod0_triangles=60000 \\
        --set lod_distances_m=40,80,150
    python3 Scripts/build_game_ready_mesh.py --settings           # every setting and its default
    python3 Scripts/build_game_ready_mesh.py trees --force        # rebuild what is already built

The source is read and never written. The built mesh goes to --dest (default
/Game/GameReady; the trees go to /Game/Forest/TreesLOD) under the source's
name, its impostor's textures and material in Impostors/ beside it. A mesh
already built from the same settings is kept.

Three steps, and this script runs them all (uepy.py: the open editor if one is
listening, a cold one otherwise):

    1. mesh      in the editor: the source cut into the mesh LODs, written to
                 a copy with Nanite off, and that copy photographed from each
                 of the impostor's planes
    2. atlas     here (Pillow + numpy): the photographs made into the
                 impostor's colour-and-mask and normal textures
    3. impostor  in the editor: the textures imported, the cards added as the
                 last LOD, screen sizes and collision set, the mesh saved,
                 and every LOD photographed; the photographs are lit here
                 into one picture per mesh, to look at

See Scripts/mesh_lod/__init__.py for the package and mesh_lod/spec.py for
what each setting means.
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import fields

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from mesh_lod import atlas, jobs, paths, preview                     # noqa: E402
from mesh_lod.spec import LodSpec                           # noqa: E402

UEPY = os.path.join(HERE, "dev", "uepy.py")
EDITOR_SCRIPT = os.path.join(HERE, "build_game_ready_mesh_editor.py")


def _overrides(pairs):
    out = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")
        if not sep:
            sys.exit(f"--set wants name=value, got {pair!r}")
        out[name.strip()] = value.strip()
    return out


def _jobs(args):
    extra = _overrides(args.set)
    found = []
    for target in args.targets:
        if target in jobs.SETS:
            batch = jobs.SETS[target]
        elif target.startswith("/Game/"):
            batch = (jobs.Job(target, args.dest or jobs.DEFAULT_DEST),)
        else:
            sys.exit(f"{target!r} is neither a /Game path nor one of: {', '.join(jobs.SETS)}")
        for job in batch:
            job = jobs.Job(job.source, args.dest or job.dest, job.name,
                           {**job.overrides, **extra})
            try:
                problems = job.spec.problems()
            except ValueError as error:
                sys.exit(str(error))
            if problems:
                sys.exit(f"{job.asset_name}: " + "; ".join(problems))
            found.append(job)
    names = [j.path for j in found]
    if len(set(names)) != len(names):
        sys.exit("two jobs would build the same mesh: give them different --dest")
    return found


def _editor(stage, batch, force):
    os.makedirs(paths.WORK_DIR, exist_ok=True)
    for job in batch:
        report = paths.report_json(job.asset_name, stage)
        if os.path.isfile(report):
            os.remove(report)
    with open(paths.REQUEST_JSON, "w") as fh:
        json.dump({"stage": stage, "force": force, "jobs": [j.to_dict() for j in batch]}, fh,
                  indent=1)
    subprocess.run([sys.executable, UEPY, EDITOR_SCRIPT], check=False)
    reports = {}
    for job in batch:
        report = paths.report_json(job.asset_name, stage)
        if not os.path.isfile(report):
            sys.exit(f"the {stage} stage wrote nothing for {job.asset_name}: "
                     "read the editor's output above")
        with open(report) as fh:
            reports[job.asset_name] = json.load(fh)
    return reports


def _line(name, source_triangles, built):
    lods = " / ".join(f"{t:,}" for t in built["triangles"])
    sizes = " / ".join(f"{s:.2f}" for s in built["screen_sizes"])
    return f"{name}: {source_triangles:,} -> {lods} triangles; screen sizes {sizes}"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("targets", nargs="*", help="/Game mesh paths, or a set: "
                        + ", ".join(jobs.SETS))
    parser.add_argument("--dest", help="the /Game folder the built meshes go in")
    parser.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                        help="change a setting for every job of this run")
    parser.add_argument("--force", action="store_true", help="rebuild what is already built")
    parser.add_argument("--settings", action="store_true", help="list the settings and exit")
    args = parser.parse_args()
    if args.settings:
        for f in fields(LodSpec):
            print(f"{f.name} = {getattr(LodSpec(), f.name)!r}")
        return 0
    if not args.targets:
        parser.error("name a /Game mesh path or a set")
    batch = _jobs(args)

    meshes = _editor("mesh", batch, args.force)
    failed = {n: r["error"] for n, r in meshes.items() if "error" in r}
    todo = [j for j in batch if j.asset_name not in failed
            and not meshes[j.asset_name].get("kept")]
    with_impostor = [j for j in todo if j.spec.impostor]
    for job in with_impostor:
        _files, covered = atlas.build(
            job.asset_name, job.spec, tuple(meshes[job.asset_name]["capture_px"]))
        print(f"{job.asset_name}: atlas made, the mesh covers {covered:.0%} of it")
    impostors = _editor("impostor", with_impostor, args.force) if with_impostor else {}
    failed.update({n: r["error"] for n, r in impostors.items() if "error" in r})

    print()
    for job in batch:
        name = job.asset_name
        if name in failed:
            print(f"{name}: FAILED -- {failed[name]}")
        elif meshes[name].get("kept"):
            print(f"{name}: already built from these settings, kept ({job.path})")
        else:
            built = (impostors.get(name) or meshes[name])["built"]
            print(_line(name, meshes[name]["source_triangles"], built))
            print(f"    {job.path}")
            picture = preview.sheet(name, built["triangles"])
            if picture:
                print(f"    every LOD side by side: {picture}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
