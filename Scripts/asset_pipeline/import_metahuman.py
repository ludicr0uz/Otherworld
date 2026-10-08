#!/usr/bin/env python3
"""import_metahuman.py -- copy the sample MetaHuman the player wears into
Content/MetaHumans.  Host side; no ``unreal``.

    python3 Scripts/asset_pipeline/import_metahuman.py            # copy
    python3 Scripts/asset_pipeline/import_metahuman.py --check    # what is missing
    python3 Scripts/asset_pipeline/import_metahuman.py --manifest # rewrite the list

Epic's MetaHumans sample (the Epic launcher, "MetaHumans" for UE 5.8; see
SAMPLE_ROOT) ships Ada, Taro and 1 GB of Common.  The player is Taro.  Both
projects mount the sample under /Game/MetaHumans/..., so copying the files
is the editor's Migrate without the editor, and only the packages BP_Taro
reaches are copied: 441 of them (1.1 GB, most of it the 8K face textures),
listed in metahuman_manifest.txt, which --manifest recomputes from the
sample's asset registry (a cold editor on the sample, about a minute).
Nothing under Content/MetaHumans is committed: asset_sources.py names this
script as the way to get it back.

The copy is byte for byte, so a MetaHuman updated in the sample is picked up
by running this again; a file already identical in size and mtime is skipped.

Licensing: Epic's MetaHuman assets may be used only in Unreal Engine projects.
"""

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(HERE))
MANIFEST = os.path.join(HERE, "metahuman_manifest.txt")

# The sample project, as the launcher installs it.  $METAHUMAN_SAMPLE overrides.
SAMPLE_ROOT = os.environ.get(
    "METAHUMAN_SAMPLE",
    os.path.expanduser("~/Documents/Unreal Projects/MetaHumans 5.8"))
SAMPLE_UPROJECT = os.path.join(SAMPLE_ROOT, "MetaHumans.uproject")

# The one character, and the root everything is copied under.
CHARACTER = "Taro"
CHARACTER_BP = f"/Game/MetaHumans/{CHARACTER}/BP_{CHARACTER}"
DEST = "Content/MetaHumans"

# The editor script --manifest runs on the sample: the dependency closure of
# the character's blueprint, soft and hard, under /Game only.  Everything else
# the closure reaches is engine or plugin content and is already there.
_MANIFEST_SCRIPT = r'''
import unreal
reg = unreal.AssetRegistryHelpers.get_asset_registry()
opts = unreal.AssetRegistryDependencyOptions(
    include_soft_package_references=True, include_hard_package_references=True)
seen, todo = set(), ["%(root)s"]
while todo:
    p = todo.pop()
    if p in seen:
        continue
    seen.add(p)
    for d in reg.get_dependencies(p, opts) or []:
        d = str(d)
        if d.startswith("/Game/") and d not in seen:
            todo.append(d)
with open(r"%(out)s", "w") as f:
    for p in sorted(seen):
        if unreal.EditorAssetLibrary.does_asset_exist(p):
            f.write(p + "\n")
'''


def packages():
    with open(MANIFEST) as f:
        return [line.strip() for line in f if line.strip()]


def _file_of(root, pkg):
    """The .uasset (or .umap) a /Game package is, under ``root``/Content."""
    rel = pkg[len("/Game/"):]
    for ext in (".uasset", ".umap"):
        path = os.path.join(root, "Content", rel + ext)
        if os.path.exists(path):
            return path
    return os.path.join(root, "Content", rel + ".uasset")


def missing():
    """The manifest's packages that are not in this project."""
    return [p for p in packages() if not os.path.exists(_file_of(PROJECT_ROOT, p))]


def _same(a, b):
    try:
        sa, sb = os.stat(a), os.stat(b)
    except OSError:
        return False
    return sa.st_size == sb.st_size and int(sa.st_mtime) == int(sb.st_mtime)


def copy():
    if not os.path.isfile(SAMPLE_UPROJECT):
        sys.exit(f"the MetaHumans sample is not at {SAMPLE_ROOT}: install it "
                 "from the Epic launcher (Samples > MetaHumans, UE 5.8) or set "
                 "$METAHUMAN_SAMPLE")
    copied = skipped = 0
    total = 0
    for pkg in packages():
        src = _file_of(SAMPLE_ROOT, pkg)
        if not os.path.exists(src):
            sys.exit(f"the sample has no {pkg} ({src}); run --manifest again")
        dst = _file_of(PROJECT_ROOT, pkg)
        if _same(src, dst):
            skipped += 1
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
        total += os.path.getsize(src)
    print(f"{CHARACTER}: copied {copied} packages ({total / 2**20:.0f} MB), "
          f"{skipped} already there, into {DEST}")


def write_manifest():
    out = os.path.join(PROJECT_ROOT, "Saved", "metahuman_manifest.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    script = os.path.join(PROJECT_ROOT, "Saved", "metahuman_manifest_script.py")
    with open(script, "w") as f:
        f.write(_MANIFEST_SCRIPT % dict(root=CHARACTER_BP, out=out))
    uepy = os.path.join(PROJECT_ROOT, "Scripts", "dev", "uepy.py")
    subprocess.run([sys.executable, uepy, "--cold", "--project", SAMPLE_UPROJECT,
                    script], check=True)
    with open(out) as f:
        lines = [l for l in f if l.strip()]
    if len(lines) < 100:
        sys.exit(f"the closure came back with {len(lines)} packages; see {out}")
    shutil.copy(out, MANIFEST)
    print(f"{MANIFEST}: {len(lines)} packages")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="list what is missing")
    ap.add_argument("--manifest", action="store_true",
                    help="recompute metahuman_manifest.txt from the sample")
    args = ap.parse_args()
    if args.manifest:
        write_manifest()
        return 0
    if args.check:
        gone = missing()
        print(f"{CHARACTER}: {len(packages()) - len(gone)} of {len(packages())} "
              f"packages present" + (f"; first missing {gone[0]}" if gone else ""))
        return 1 if gone else 0
    copy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
