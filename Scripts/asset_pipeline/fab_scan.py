#!/usr/bin/env python3
"""fab_scan.py -- scan a downloaded Fab pack, then copy it into Content/.

    python3 Scripts/asset_pipeline/fab_scan.py <source>              scan only
    python3 Scripts/asset_pipeline/fab_scan.py <source> --promote    scan, then copy
    python3 Scripts/asset_pipeline/fab_scan.py --verify              Content/ vs the records

<source> is a folder holding Content/: a vault pack's data folder
(/Users/Shared/UnrealEngine/Launcher/VaultCache/<pack>/data), or a throwaway
project the pack was added to (then name its folders: --only <Pack> ...).
Download through the launcher into such a project, never straight into this
one, so the scan runs before this project's editor sees the files.

Exit 0 clean, 1 blocked (or --verify found a difference), 2 needs review.
A pack needing review is promoted only with --accept-review. After a promote,
record the listing (fab_library.py --add) and rebuild the index (fab_index.py).

Host-side, standard library only. The checks are fab_intake/ (its __init__.py
is the map). Code plugins are out of scope: they are native code, installed
into the engine, and nothing here can vouch for one.
"""

import argparse
import os
import sys

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from asset_pipeline.fab_intake import manifest, promote, rules  # noqa: E402
from asset_pipeline.fab_intake.scan import scan                 # noqa: E402

EXIT = {"clean": 0, "blocked": 1, "review": 2}


def _print_report(report, notes):
    size = sum(f["size"] for f in report.files.values())
    print(f"{report.source}\n  {len(report.files)} files, {size / 1e6:.1f} MB "
          f"-> {', '.join('/Game/' + t for t in report.tops()) or '(nothing)'}")
    for level in (rules.BLOCK, rules.REVIEW):
        for f in report.at(level):
            print(f"  {level:<6} {f.path}: {f.what}")
    found = report.at(rules.NOTE)
    if found and notes:
        for f in found:
            print(f"  {rules.NOTE:<6} {f.path}: {f.what}")
    elif found:
        print(f"  {len(found)} assets carry Blueprint logic (--notes lists them)")
    print(f"  verdict: {report.verdict}")


def _verify():
    diffs = promote.verify()
    for record, rel, state in diffs:
        print(f"  {state:<8} {rel}  ({record})")
    print(f"{len(diffs)} promoted files differ from their intake record"
          if diffs else "every promoted file matches its intake record")
    return 1 if diffs else 0


def _main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", help="folder holding the pack's Content/")
    ap.add_argument("--only", nargs="+", default=(), metavar="PACK",
                    help="top-level Content folders that are the pack")
    ap.add_argument("--manifest", help="the launcher's manifest (found beside a vault pack)")
    ap.add_argument("--notes", action="store_true", help="list each asset with Blueprint logic")
    ap.add_argument("--promote", action="store_true", help="copy into Content/ when clean")
    ap.add_argument("--accept-review", action="store_true",
                    help="with --promote: you have looked at every REVIEW line")
    ap.add_argument("--verify", action="store_true",
                    help="compare Content/ with every intake record")
    args = ap.parse_args()

    if args.verify:
        return _verify()
    if not args.source or not os.path.isdir(args.source):
        sys.exit("fab_scan: give the folder that holds the pack's Content/")
    report = scan(args.source, args.only)
    listed = args.manifest or manifest.find_for(args.source)
    if listed:
        report.findings += manifest.check(report.source, listed)
        print(f"manifest: {listed}")
    else:
        print("manifest: none found, so the files are not checked against Epic's hashes")
    _print_report(report, args.notes)
    if not args.promote:
        return EXIT[report.verdict]
    if report.verdict == "blocked" or (report.verdict == "review" and not args.accept_review):
        print("not promoted" + (": look at each REVIEW line, then pass --accept-review"
                                if report.verdict == "review" else ""))
        return EXIT[report.verdict]
    clashes = promote.conflicts(report)
    if clashes:
        for rel in clashes:
            print(f"  CONFLICT Content/{rel} exists with different bytes")
        print("not promoted: a pack never overwrites what the project has")
        return 1
    copied, same, record = promote.promote(report)
    print(f"promoted: {copied} copied, {same} already there\n  record: {record}\n"
          "next: fab_library.py --add <name> --url <listing> --at /Game/<folder> "
          "--license <licence>, then uepy.py Scripts/asset_pipeline/fab_index.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
