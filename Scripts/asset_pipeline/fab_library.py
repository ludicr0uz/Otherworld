#!/usr/bin/env python3
"""fab_library.py -- what has been acquired from Fab, and where it landed.

    python3 Scripts/asset_pipeline/fab_library.py --list
    python3 Scripts/asset_pipeline/fab_library.py --check
    python3 Scripts/asset_pipeline/fab_library.py --add "Game Animation Sample" \\
        --url https://www.fab.com/listings/<id> --at /Game/GameAnimationSample

Host-side, standard library only, no ``unreal``: dev-team, sync_assets.py and
the editor-side index (fab_index.py) all read the same manifest.

── Acquisition is manual, always ───────────────────────────────────────────

Fab has no public download API. Getting an asset means being signed in to the
user's Epic account, accepting its licence and adding it to the library, in
the Fab plugin's browser inside the editor (it imports under /Game/Fab) or the
launcher's "Add to project" (a pack lands in its own /Game/<Pack> folder).
None of that is scriptable, and no agent may try. A session that needs an
asset asks for it (dev-team: a FAB-REQUIRED report, see devteam/fab.py), the
user acquires it, and the entry is recorded here.

── Why the manifest is tracked and the assets are not ─────────────────────

The repository is code only (see forest_generator/asset_sources.py), so the
imported .uassets are never committed. fab_library.json is the restore recipe
instead: a fresh clone runs --check, and the user re-adds whatever it lists
as missing. The index built from it lives in git-ignored assets/cache/fab/.
"""

import argparse
import datetime
import json
import os
import sys
from dataclasses import asdict, dataclass

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(HERE))
LIBRARY = os.path.join(HERE, "fab_library.json")
INDEX_DIR = os.path.join(PROJECT_DIR, "assets", "cache", "fab")
INDEX_JSON = os.path.join(INDEX_DIR, "index.json")
INDEX_MD = os.path.join(INDEX_DIR, "index.md")

# Where the Fab plugin imports (FabSettings / the plugin's own "/Game/Fab").
DEFAULT_ROOT = "/Game/Fab"
# The retargeter's source skeleton. A skeleton with these bones is the UE5
# mannequin's naming, which rig_chains.py's chain tables are keyed on.
MANNEQUIN_SKELETON = "/Game/Characters/Mannequins/Meshes/SK_Mannequin"
MANNEQUIN_BONES = ("pelvis", "spine_01", "neck_01", "head", "hand_l", "hand_r",
                   "foot_l", "foot_r")


@dataclass
class FabItem:
    name: str                   # the listing's title
    content: str                # /Game/... folder it imported into
    url: str = ""               # https://www.fab.com/listings/<id>
    license: str = ""           # e.g. "Standard", "Personal", "CC-BY"
    added: str = ""             # ISO date it was recorded
    note: str = ""


def load(path=LIBRARY):
    if not os.path.isfile(path):
        return []
    with open(path) as fh:
        return [FabItem(**entry) for entry in json.load(fh).get("items", [])]


def save(items, path=LIBRARY):
    items = sorted(items, key=lambda i: i.name.lower())
    with open(path, "w") as fh:
        json.dump({"items": [asdict(i) for i in items]}, fh, indent=2)
        fh.write("\n")


def find(items, name="", url=""):
    """The entry for a listing: by URL when one is given, else by name."""
    for item in items:
        if url and item.url and item.url.rstrip("/") == url.rstrip("/"):
            return item
    for item in items:
        if name and item.name.strip().lower() == name.strip().lower():
            return item
    return None


def record(item, path=LIBRARY):
    """Add an entry, or replace the one for the same listing."""
    items = load(path)
    old = find(items, item.name, item.url)
    if old:
        items.remove(old)
    item.added = item.added or datetime.date.today().isoformat()
    items.append(item)
    save(items, path)
    return item


def content_dir(content, project=PROJECT_DIR):
    """/Game/X -> <project>/Content/X, or None for a path outside /Game."""
    content = content.rstrip("/")
    if content != "/Game" and not content.startswith("/Game/"):
        return None
    return os.path.join(project, "Content", *content.split("/")[2:])


def is_present(item, project=PROJECT_DIR):
    path = content_dir(item.content, project)
    return bool(path) and os.path.isdir(path) and any(
        f.endswith((".uasset", ".umap")) for _d, _s, files in os.walk(path) for f in files)


def index_roots(items):
    """Content folders the index walks: the plugin's default and every entry's."""
    roots = {DEFAULT_ROOT} | {i.content.rstrip("/") for i in items}
    # A root nested in another is walked by its parent already.
    return sorted(r for r in roots
                  if not any(r != o and r.startswith(o + "/") for o in roots))


def render_index_md(assets, items):
    """The short, human- and agent-readable summary beside index.json."""
    lines = ["# Fab index", "",
             f"{len(assets)} assets. Full list, one per line: `assets/cache/fab/index.json` "
             "(grep it). Rebuild: `python3 Scripts/dev/uepy.py "
             "Scripts/asset_pipeline/fab_index.py`.", "", "## Library", ""]
    if not items:
        lines.append("(nothing acquired yet -- see fab_library.py)")
    for i in items:
        lines.append(f"- **{i.name}** -> `{i.content}`"
                     + (f" ({i.license})" if i.license else "") + (f" {i.url}" if i.url else ""))
    by_class = {}
    for a in assets:
        by_class[a["class"]] = by_class.get(a["class"], 0) + 1
    lines += ["", "## By class", ""]
    lines += [f"- {cls}: {n}" for cls, n in sorted(by_class.items(), key=lambda kv: -kv[1])]
    skeletons = {}
    for a in assets:
        if a["class"] in ("SkeletalMesh", "AnimSequence", "AnimMontage", "BlendSpace",
                          "AimOffsetBlendSpace"):
            s = skeletons.setdefault(a.get("skeleton") or "?", {"meshes": 0, "anims": 0,
                                                                "mannequin": None})
            s["meshes" if a["class"] == "SkeletalMesh" else "anims"] += 1
        if a["class"] == "Skeleton":
            skeletons.setdefault(a["path"], {"meshes": 0, "anims": 0, "mannequin": None})[
                "mannequin"] = a.get("mannequin_bones")
    if skeletons:
        lines += ["", "## Skeletons", "",
                  "`mannequin` = has the UE5 mannequin's bone names, so the existing IK "
                  "rig chains (asset_pipeline/rig_chains.py) apply.", "",
                  "| skeleton | meshes | anims | mannequin |", "|---|---|---|---|"]
        for path, s in sorted(skeletons.items()):
            flag = {True: "yes", False: "no", None: "?"}[s["mannequin"]]
            lines.append(f"| `{path}` | {s['meshes']} | {s['anims']} | {flag} |")
    return "\n".join(lines) + "\n"


def _main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="print the library")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any entry's content folder is missing on disk")
    ap.add_argument("--add", metavar="NAME", help="record a listing you acquired")
    ap.add_argument("--url", default="")
    ap.add_argument("--at", metavar="/Game/...", help="with --add: where it imported")
    ap.add_argument("--license", default="")
    ap.add_argument("--note", default="")
    args = ap.parse_args()

    if args.add:
        if not args.at or content_dir(args.at) is None:
            sys.exit("fab_library: --add needs --at /Game/<folder>")
        item = record(FabItem(args.add, args.at, args.url, args.license, note=args.note))
        print(f"recorded {item.name} -> {item.content}"
              + ("" if is_present(item) else "  (WARNING: nothing on disk there yet)"))
        return 0
    items = load()
    missing = [i for i in items if not is_present(i)]
    for i in items:
        state = "present" if i not in missing else "MISSING"
        print(f"  {state:<8} {i.name:<40} {i.content}  {i.url}")
    if not items:
        print("  (library is empty)")
    if args.check and missing:
        print(f"\n{len(missing)} missing: re-add each through the Fab plugin "
              "(or the launcher's Add to project), then rebuild the index.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
