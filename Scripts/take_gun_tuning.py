#!/usr/bin/env python3
"""Take a packaged build's GUN SETTINGS save back as the new gun defaults.

    python3 Scripts/take_gun_tuning.py            # the newest build save found
    python3 Scripts/take_gun_tuning.py <csv>      # that file
    python3 Scripts/take_gun_tuning.py --dry-run  # say what would move, copy nothing

Copies it over Scripts/combat/gun_tuning.csv (combat/gun_tuning_take.py); then
build_weapons_and_combat.py and build_graphics_menu.py bake it in. Run outside
the editor.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from combat.gun_tuning import CSV_PATH  # noqa: E402
from combat.gun_tuning_take import (  # noqa: E402
    changes, header_problem, newest, saved_copies, take)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv", nargs="?", help="the build's gun_tuning.csv (default: the newest found)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    source = args.csv or newest(saved_copies())
    if not source:
        sys.exit("[take] no packaged build's save found in:\n  "
                 + "\n  ".join(saved_copies()))
    problem = header_problem(source)
    if problem:
        sys.exit(f"[take] {problem}")
    moved = changes(CSV_PATH, source) if args.dry_run else take(source)
    for weapon, col, old, new in moved:
        print(f"[take] {weapon} {col}: {old} -> {new}")
    verb = "would take" if args.dry_run else "took"
    print(f"[take] {verb} {len(moved)} changed cells from {source}")
    if moved and not args.dry_run:
        print("[take] now: uepy.py Scripts/build_weapons_and_combat.py, then "
              "Scripts/build_graphics_menu.py")


if __name__ == "__main__":
    main()
