#!/usr/bin/env python3
"""import_gas.py -- copy the Game Animation Sample's motion-matching set into
Content/GAS.  Host side; no ``unreal``.

    python3 Scripts/asset_pipeline/import_gas.py            # copy
    python3 Scripts/asset_pipeline/import_gas.py --check    # what is missing
    python3 Scripts/asset_pipeline/import_gas.py --manifest # rewrite the list

Epic's Game Animation Sample (the Epic launcher, "Game Animation Sample" for
UE 5.8; see SAMPLE_ROOT) ships 5.4 GB.  What comes across is the UEFN
mannequin (its meshes, rigs and every clip, with the PoseSearch databases and
the choosers that pick between them) and SandboxCharacter_CMC_ABP with what
that anim blueprint reaches: gas_manifest.txt, which --manifest recomputes
from the sample's asset registry (a cold editor on the sample, about a
minute).  The Mover variant, the smart objects, the isolated examples and the
other characters (EXCLUDED) stay behind; gas_manifest_cut.txt lists each
reference into them that was cut, so a load warning has a name.

The sample mounts its content at /Game/Characters, /Game/Blueprints, ...; here
it lies one folder down, under /Game/GAS, apart from the game's own
/Game/Audio and /Game/Input.  The copy is byte for byte, so each package
still names its neighbours by the sample's paths: gas_paths.REDIRECTED, written
into Config/DefaultEngine.ini as [CoreRedirects], is what points those at
/Game/GAS (this script checks they are there).  A package saved in this
project afterwards is written with the new paths and no longer needs them.

Two packages are changed here after the copy (gas_paths.PATCHED: the notifies
only the Mover character answers, patch_gas_notifies.py), and the copy leaves
one of those alone once it is here.

Nothing under Content/GAS is committed (.gitignore): asset_sources.py names
this script as the way to get it back.  A file already identical in size and
mtime is skipped, so a sample updated by the launcher is picked up by running
this again.

Licensing: Epic's sample content may be used only in Unreal Engine projects.
"""

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))

from asset_pipeline.gas_paths import (  # noqa: E402
    DEST, EXCLUDED, PATCHED, ROOT_FOLDERS, ROOT_PACKAGES, redirect_lines, redirected)

MANIFEST = os.path.join(HERE, "gas_manifest.txt")
CUT = os.path.join(HERE, "gas_manifest_cut.txt")
ENGINE_INI = os.path.join(PROJECT_ROOT, "Config", "DefaultEngine.ini")

# The sample project, as the launcher installs it.  $GAS_SAMPLE overrides.
SAMPLE_ROOT = os.environ.get(
    "GAS_SAMPLE",
    os.path.expanduser("~/Documents/Unreal Projects/GameAnimationSample"))
SAMPLE_UPROJECT = os.path.join(SAMPLE_ROOT, "GameAnimationSample.uproject")

# The editor script --manifest runs on the sample: the dependency closure,
# soft and hard, of the root packages and of everything in the root folders,
# under /Game only and never into an excluded folder.  Everything else the
# closure reaches is engine or plugin content and is already there.  It writes
# files, not print(): a cold run's print() does not reach the log.
_MANIFEST_SCRIPT = r'''
import unreal
reg = unreal.AssetRegistryHelpers.get_asset_registry()
reg.search_all_assets(True)
EXCLUDED = %(excluded)r
def opts(hard):
    return unreal.AssetRegistryDependencyOptions(
        include_soft_package_references=not hard,
        include_hard_package_references=hard)
def cut(p):
    return any(p == e or p.startswith(e.rstrip("/") + "/") or
               (not e.endswith("/") and p.startswith(e)) for e in EXCLUDED)
todo = list(%(packages)r)
for folder in %(folders)r:
    for a in reg.get_assets_by_path(folder, recursive=True) or []:
        if not cut(str(a.package_name)):
            todo.append(str(a.package_name))
seen, cuts = set(), set()
while todo:
    p = todo.pop()
    if p in seen:
        continue
    seen.add(p)
    for hard in (True, False):
        for d in reg.get_dependencies(p, opts(hard)) or []:
            d = str(d)
            if not d.startswith("/Game/"):
                continue
            if cut(d):
                cuts.add("%%s %%s -> %%s" %% ("hard" if hard else "soft", p, d))
            elif d not in seen:
                todo.append(d)
with open(r"%(out)s", "w") as f:
    for p in sorted(seen):
        if unreal.EditorAssetLibrary.does_asset_exist(p):
            f.write(p + "\n")
with open(r"%(cut)s", "w") as f:
    for line in sorted(cuts):
        f.write(line + "\n")
'''


def packages():
    with open(MANIFEST) as f:
        return [line.strip() for line in f if line.strip()]


def _file_of(content, pkg):
    """The .uasset (or .umap) a sample /Game package is, under ``content``."""
    rel = pkg[len("/Game/"):]
    for ext in (".uasset", ".umap"):
        path = os.path.join(content, rel + ext)
        if os.path.exists(path):
            return path
    return os.path.join(content, rel + ".uasset")


def _src(pkg):
    return _file_of(os.path.join(SAMPLE_ROOT, "Content"), pkg)


def _dst(pkg):
    return _file_of(os.path.join(PROJECT_ROOT, DEST), pkg)


def missing():
    """The manifest's packages that are not in this project."""
    return [p for p in packages() if not os.path.exists(_dst(p))]


def missing_redirects():
    """The [CoreRedirects] lines DefaultEngine.ini lacks."""
    with open(ENGINE_INI) as f:
        have = {line.strip() for line in f}
    return [line for line in redirect_lines() if line not in have]


def unredirected():
    """Manifest packages no redirect covers: they would load from nowhere."""
    return [p for p in packages() if not redirected(p)]


def strays():
    """Files under Content/GAS the manifest does not list."""
    listed = {_dst(p) for p in packages()}
    return sorted(os.path.join(d, f)
                  for d, _, files in os.walk(os.path.join(PROJECT_ROOT, DEST))
                  for f in files
                  if f.endswith((".uasset", ".umap"))
                  and os.path.join(d, f) not in listed)


def _same(a, b):
    try:
        sa, sb = os.stat(a), os.stat(b)
    except OSError:
        return False
    return sa.st_size == sb.st_size and int(sa.st_mtime) == int(sb.st_mtime)


def size():
    """Bytes of the manifest's packages as they lie in this project."""
    return sum(os.path.getsize(_dst(p)) for p in packages()
               if os.path.exists(_dst(p)))


def copy():
    if not os.path.isfile(SAMPLE_UPROJECT):
        sys.exit(f"the Game Animation Sample is not at {SAMPLE_ROOT}: install "
                 "it from the Epic launcher (Samples > Game Animation Sample, "
                 "UE 5.8) or set $GAS_SAMPLE")
    _refuse_bad_redirects()
    copied = skipped = kept = 0
    total = 0
    for pkg in packages():
        src = _src(pkg)
        if not os.path.exists(src):
            sys.exit(f"the sample has no {pkg} ({src}); run --manifest again")
        dst = _dst(pkg)
        if pkg in PATCHED and os.path.exists(dst):
            kept += 1
            continue
        if _same(src, dst):
            skipped += 1
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
        total += os.path.getsize(src)
    print(f"GAS: copied {copied} packages ({total / 2**20:.0f} MB), "
          f"{skipped} already there, {kept} patched here and kept, into "
          f"{DEST} ({size() / 2**30:.2f} GB)")
    for path in strays():
        print(f"GAS: not in the manifest, left alone: {path}")
    print("GAS: then, in the editor: "
          "python3 Scripts/dev/uepy.py Scripts/asset_pipeline/patch_gas_notifies.py")


def _refuse_bad_redirects():
    gone = missing_redirects()
    if gone:
        sys.exit("Config/DefaultEngine.ini lacks the redirect(s) the copied "
                 "packages find each other by; add under [CoreRedirects]:\n  "
                 + "\n  ".join(gone))
    loose = unredirected()
    if loose:
        sys.exit(f"{len(loose)} manifest packages are under no folder of "
                 f"gas_paths.REDIRECTED, first {loose[0]}: add its top folder")


def write_manifest():
    saved = os.path.join(PROJECT_ROOT, "Saved")
    out = os.path.join(saved, "gas_manifest.txt")
    cut = os.path.join(saved, "gas_manifest_cut.txt")
    os.makedirs(saved, exist_ok=True)
    for stale in (out, cut):
        if os.path.exists(stale):
            os.remove(stale)
    script = os.path.join(saved, "gas_manifest_script.py")
    with open(script, "w") as f:
        f.write(_MANIFEST_SCRIPT % dict(
            packages=list(ROOT_PACKAGES), folders=list(ROOT_FOLDERS),
            excluded=list(EXCLUDED), out=out, cut=cut))
    uepy = os.path.join(PROJECT_ROOT, "Scripts", "dev", "uepy.py")
    env = dict(os.environ)
    env.pop("UEPY_SERVE", None)     # a warm editor is this project's, not the sample's
    subprocess.run([sys.executable, uepy, "--cold", "--project", SAMPLE_UPROJECT,
                    script], check=True, env=env)
    with open(out) as f:
        lines = [l for l in f if l.strip()]
    if len(lines) < 100:
        sys.exit(f"the closure came back with {len(lines)} packages; see {out}")
    shutil.copy(out, MANIFEST)
    shutil.copy(cut, CUT)
    with open(cut) as f:
        cuts = [l for l in f if l.strip()]
    print(f"{MANIFEST}: {len(lines)} packages; {len(cuts)} references into "
          f"the excluded folders cut ({CUT})")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="list what is missing")
    ap.add_argument("--manifest", action="store_true",
                    help="recompute gas_manifest.txt from the sample")
    args = ap.parse_args()
    if args.manifest:
        write_manifest()
        return 0
    if args.check:
        gone = missing()
        n = len(packages())
        print(f"GAS: {n - len(gone)} of {n} packages present "
              f"({size() / 2**30:.2f} GB)"
              + (f"; first missing {gone[0]}" if gone else ""))
        bad = missing_redirects()
        if bad:
            print(f"GAS: DefaultEngine.ini lacks {len(bad)} redirect(s), "
                  f"first {bad[0]}")
        for path in strays():
            print(f"GAS: not in the manifest: {path}")
        return 1 if gone or bad else 0
    copy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
