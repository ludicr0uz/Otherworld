#!/usr/bin/env python3
"""fab_raw_scan.py -- check a raw Fab download (FBX, OBJ, GLB, USD) and stage it.

    python3 Scripts/asset_pipeline/fab_raw_scan.py --list              what the launcher holds
    python3 Scripts/asset_pipeline/fab_raw_scan.py <item>              scan only
    python3 Scripts/asset_pipeline/fab_raw_scan.py <item> --stage      scan, then copy to the cache
    python3 Scripts/dev/uepy.py Scripts/asset_pipeline/fab_raw_import.py   then: import what is staged

<item> is a folder, or part of a name in the launcher's Fab library
(/Users/Shared/UnrealEngine/Launcher/VaultCache/FabLibrary): "axe", "1911".
Any folder of meshes and textures will do; one the launcher wrote also gives
the listing's title and URL. A staged item lands in /Game/Fab/<Name>, where
<Name> is the title (--name overrides it).

Exit 0 clean, 1 blocked, 2 needs review (staged only with --accept-review).
Host-side, standard library only. The work is fab_raw/ (its __init__.py is
the map). A pack that has a Content/ folder is fab_scan.py's.
"""

import argparse
import os
import sys

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from asset_pipeline.fab_raw import listing, stage    # noqa: E402
from asset_pipeline.fab_raw.collect import collect   # noqa: E402

EXIT = {"clean": 0, "blocked": 1, "review": 2}


def _list():
    plans = stage.staged()
    for folder in listing.raw_items():
        meta = listing.read(folder)
        # By listing, not by title: two listings can share one.
        slug = next((s for s, plan, _done in plans if meta["url"] and plan["url"] == meta["url"]),
                    listing.slug(meta["title"]))
        state = ("imported" if stage.is_imported(slug)
                 else "staged" if any(s == slug for s, _p, _d in plans) else "-")
        print(f"  {state:<9} {os.path.basename(folder):<60} {meta['title']}")
    return 0


def _resolve(name):
    if os.path.isdir(name):
        return name
    found = listing.find(name)
    starts = [f for f in found if os.path.basename(f).lower().startswith(name.lower())]
    found = starts if len(starts) == 1 else found
    if len(found) == 1:
        return found[0]
    sys.exit(f"fab_raw_scan: {name!r} is not a folder and names "
             + (f"{len(found)} library items:\n  " + "\n  ".join(found) if found
                else "nothing in the Fab library (--list shows it)"))


def _print(item):
    size = sum(f["size"] for f in item.files.values())
    print(f"{item.title}  ({item.url or 'no listing'})\n  {item.source}\n"
          f"  {len(item.files)} files, {size / 1e6:.1f} MB -> {stage.dest_of(item.slug)}")
    for rel in item.meshes:
        print(f"  mesh   {rel}")
    for key, roles in sorted(item.sets.items()):
        print(f"  set    {key}: " + ", ".join(sorted(roles)))
    for rel in item.loose:
        print(f"  loose  {rel}: its name gives no role, so no material wears it")
    for rel, why in item.left:
        print(f"  left   {rel}: {why}")
    for f in item.findings:
        print(f"  {f.level:<6} {f.path}: {f.what}")
    print(f"  verdict: {item.verdict}")


def _main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("item", nargs="?", help="a folder, or part of a library item's name")
    ap.add_argument("--list", action="store_true", help="the launcher's raw downloads")
    ap.add_argument("--name", default="", help="the title to import under")
    ap.add_argument("--stage", action="store_true", help="copy to the cache when clean")
    ap.add_argument("--accept-review", action="store_true",
                    help="with --stage: you have looked at every REVIEW line")
    ap.add_argument("--replace", action="store_true",
                    help="with --stage: stage again, and let the import replace "
                         "what /Game/Fab/<Name> holds")
    ap.add_argument("--parts", action="store_true",
                    help="with --stage: a kit, so each object in a mesh file "
                         "becomes its own static mesh instead of one combined")
    args = ap.parse_args()

    if args.list:
        return _list()
    if not args.item:
        sys.exit("fab_raw_scan: name an item (--list shows the launcher's)")
    item = collect(_resolve(args.item), args.name)
    if stage.name_apart(item):
        print(f"another listing is staged under this title: this one is {item.title!r}")
    _print(item)
    if not args.stage:
        return EXIT[item.verdict]
    if item.verdict == "blocked" or (item.verdict == "review" and not args.accept_review):
        print("not staged" + (": look at each REVIEW line, then pass --accept-review"
                              if item.verdict == "review" else ""))
        return EXIT[item.verdict]
    if stage.is_imported(item.slug) and not args.replace:
        print(f"not staged: {stage.dest_of(item.slug)} already holds assets "
              "(--replace; or --name, if this is another listing with the same title)")
        return 1
    path = stage.stage(item, replace=args.replace, parts=args.parts)
    print(f"staged: {path}\nnext: python3 Scripts/dev/uepy.py "
          "Scripts/asset_pipeline/fab_raw_import.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
