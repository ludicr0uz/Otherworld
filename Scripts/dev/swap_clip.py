#!/usr/bin/env python3
"""swap_clip.py -- put one of the player's Mixamo clips on another download.

    python3 Scripts/dev/swap_clip.py --list
    python3 Scripts/dev/swap_clip.py axe_swing "assets/cache/mixamo/Pro Melee Axe Pack/standing melee attack horizontal.fbx"
    python3 Scripts/dev/swap_clip.py axe_swing ~/Downloads/Great\\ Sword\\ Slash.fbx --dry-run
    python3 Scripts/dev/swap_clip.py axe_swing <fbx> --hit-s 0.85     # the strike, given
    python3 Scripts/dev/swap_clip.py --prune                         # delete the clips no role names

A role is a row of Scripts/asset_pipeline/player_clips.csv (the knife's and
the axe's ready pose and swing, the prone crawl, the punch).  The command registers the
FBX (one outside the cache is copied to assets/cache/mixamo/Player), and the
editor then imports and retargets that clip alone, reads a swing's strike off
its hand, rewrites the row and rebuilds only what is baked from it
(asset_pipeline/player_clip_swap.py).  It runs in the open editor, or boots
one (Scripts/dev/uepy.py).  Swapping back is the same command with the old
FBX, which it prints; a clip that was imported before is not imported again
(``--reimport``: the FBX itself changed).

Then look at it: ``uepy.py --verify-for`` holds the bake to the melee
verifier, and probe_metahuman_look.py (windowed) pictures the axe's swing.
"""

import argparse
import collections
import filecmp
import json
import os
import shutil
import subprocess
import sys

DEV = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(DEV)
sys.path.insert(0, SCRIPTS)

from asset_pipeline import player_clips                          # noqa: E402
from asset_pipeline.mixamo_paths import (                         # noqa: E402
    MIXAMO_CACHE, PLAYER_PACKS, REPO_ROOT, clip_stem,
)

LOOSE = "Player"            # the PLAYER_PACKS folder a new FBX is copied to
RESULT = os.path.join(REPO_ROOT, "Saved", "uepy", "clip_swap.json")

# What a swap will do: the row it writes, and the copy that registers the FBX
# (``copy_to`` None: it is in the cache already).
Plan = collections.namedtuple("Plan", "role old pack clip fbx copy_to steps")


def plan(role, fbx, rows, cache=MIXAMO_CACHE, packs=PLAYER_PACKS):
    """Check ``role`` and ``fbx`` and say what swapping them in means.  Raises
    ValueError with the message to print."""
    player_clips.check_role(role, [r.role for r in rows])
    fbx = os.path.abspath(os.path.expanduser(fbx))
    if not os.path.isfile(fbx) or not fbx.lower().endswith(".fbx"):
        raise ValueError(f"{fbx} is not an FBX file")
    stem = clip_stem(os.path.basename(fbx))
    folder = os.path.dirname(fbx)
    here = [short for name, short in packs
            if os.path.realpath(folder) == os.path.realpath(os.path.join(cache, name))]
    copy_to = None
    if not here:
        loose = next(name for name, short in packs if short == LOOSE)
        copy_to = os.path.join(cache, loose, os.path.basename(fbx))
        if os.path.exists(copy_to):
            if not filecmp.cmp(fbx, copy_to, shallow=False):
                raise ValueError(f"{copy_to} is another file by that name: rename the new one")
            copy_to = None
    pack = here[0] if here else LOOSE
    twins = [f for f in os.listdir(folder)
             if here and f.lower().endswith(".fbx") and clip_stem(f) == stem]
    if len(twins) > 1:
        raise ValueError(f"{', '.join(sorted(twins))} are one clip name ({stem}): rename one")
    old = next(r for r in rows if r.role == role)
    return Plan(role, old, pack, stem, fbx, copy_to, player_clips.ROLES[role][1])


def fbx_of(row, cache=MIXAMO_CACHE, packs=PLAYER_PACKS):
    """The cached FBX a row names, or None (a zip not yet extracted)."""
    folder = os.path.join(cache, next((n for n, s in packs if s == row.pack), row.pack))
    if not os.path.isdir(folder):
        return None
    found = [f for f in sorted(os.listdir(folder))
             if f.lower().endswith(".fbx") and clip_stem(f) == row.clip]
    return os.path.join(folder, found[0]) if found else None


def undo_line(old):
    """The command that puts ``old`` back."""
    fbx = fbx_of(old) or f"<the FBX of {old.pack}/{old.clip}>"
    return (f'python3 Scripts/dev/swap_clip.py {old.role} "{os.path.relpath(fbx, REPO_ROOT)}"'
            + (f" --hit-s {old.hit_s:.2f}" if old.hit_s is not None else ""))


def describe(p, hit_s, reimport):
    swing = p.role in player_clips.SWINGS
    lines = [f"{p.role}: {player_clips.ROLES[p.role][0]}",
             f"  row now   {player_clips.line_of(p.old)}",
             f"  row then  {p.role},{p.pack},{p.clip},"
             + ((f"{hit_s:.2f}" if hit_s is not None else "<the strike read off the hand>")
                if swing else ""),
             f"  fbx       {p.fbx}"
             + (f"\n            copied to {p.copy_to}" if p.copy_to else " (in the cache)"),
             "  import    that clip alone onto SK_XBot, retargeted onto the player's skeleton"
             + (" (again: --reimport)" if reimport else " (kept if it is there already)"),
             "  rebuild   " + ", ".join(
                 ([f"the bake of {p.role}"] if p.role != "prone_crawl" else [])
                 + [f"the weapons build's step {s}" for s in p.steps]),
             f"  back      {undo_line(p.old)}"]
    return "\n".join(lines)


def _editor(code):
    """Run ``code`` in the editor; returns (exit code, output tail, result)."""
    if os.path.exists(RESULT):
        os.remove(RESULT)
    os.makedirs(os.path.dirname(RESULT), exist_ok=True)
    head = f"import sys; sys.path.insert(0, {SCRIPTS!r}) if {SCRIPTS!r} not in sys.path else None; "
    run = subprocess.run([sys.executable, os.path.join(DEV, "uepy.py"), "--summary", "-c",
                          head + code], capture_output=True, text=True)
    result = None
    if os.path.exists(RESULT):
        with open(RESULT, encoding="utf-8") as f:
            result = json.load(f)
    return run.returncode, (run.stdout + run.stderr).strip().splitlines()[-12:], result


def report(result):
    """The lines to print for a swap's result."""
    lines = [f"  row       {result['old']}  ->  {result.get('new', '(unchanged)')}"]
    if "made" in result:
        lines.append(f"  clip      {', '.join(result['made']) or 'already imported, kept'}, "
                     f"{result['length_s']:.2f} s long")
    if "detected_s" in result:
        used = result.get("new", ",").rsplit(",", 1)[1]
        found = result["detected_s"]
        lines.append(
            f"  strike    read at {'no moment' if found is None else f'{found:.2f} s'}"
            f" (the hand goes from {result['reach_cm'][0]:.0f} to {result['reach_cm'][1]:.0f} cm "
            f"ahead of the body)"
            + (f"; the row has {used}, as given" if used and found is not None
               and abs(float(used) - found) > 0.005 else "")
            + (f"\n            the bake starts {float(used) - result['impact_s']:.2f} s in: "
               f"the blow lands {result['impact_s']:.2f} s after the key" if used else ""))
    for label, ok in result.get("checks", []):
        lines.append(f"  {'pass' if ok else 'FAIL'}      {label}")
    if "error" in result:
        lines.append(f"  error     {result['error']}")
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("role", nargs="?", help="the role to replace (--list)")
    ap.add_argument("fbx", nargs="?", help="the Mixamo download that takes it")
    ap.add_argument("--list", action="store_true", help="print the roles and their clips")
    ap.add_argument("--dry-run", action="store_true", help="say what would happen, change nothing")
    ap.add_argument("--hit-s", type=float, help="a swing's strike (s into Mixamo's clip), "
                                                "instead of the one read off the hand")
    ap.add_argument("--reimport", action="store_true",
                    help="import and retarget the clip even if it is in the project")
    ap.add_argument("--prune", action="store_true",
                    help="delete the player's clips no role names (left by earlier swaps)")
    args = ap.parse_args(argv)
    rows = player_clips.read_rows()
    if args.list:
        for r in rows:
            print(f"{r.role:12} {r.pack}/{r.clip}"
                  + (f"  strike {r.hit_s:.2f} s" if r.hit_s is not None else "")
                  + f"   {player_clips.ROLES[r.role][0]}")
        return 0
    if args.prune:
        code, tail, result = _editor(
            f"from asset_pipeline.player_clip_swap import prune; prune({RESULT!r})")
        if not result:
            print("\n".join(tail))
            return code or 1
        print("\n".join(result["pruned"]) or "nothing to prune")
        return 0
    if not args.role or not args.fbx:
        ap.error("a role and an FBX (or --list, --prune)")
    try:
        p = plan(args.role, args.fbx, rows)
    except ValueError as exc:
        print(f"swap_clip: {exc}", file=sys.stderr)
        return 2
    print(describe(p, args.hit_s, args.reimport))
    if args.dry_run:
        print("dry run: nothing changed")
        return 0
    if p.copy_to:
        os.makedirs(os.path.dirname(p.copy_to), exist_ok=True)
        shutil.copy2(p.fbx, p.copy_to)
    code, tail, result = _editor(
        "from asset_pipeline.player_clip_swap import swap; "
        f"swap({p.role!r}, {p.pack!r}, {p.clip!r}, hit_s={args.hit_s!r}, "
        f"reimport={args.reimport!r}, result={RESULT!r})")
    if result:
        print("\n".join(report(result)))
    if code or not result or "error" in result:
        print("\n".join(tail))
        print("swap_clip: FAILED, the row is as it was", file=sys.stderr)
        return code or 1
    print(f"swapped in {result['seconds']:.0f} s"
          + ("" if result["ok"] else ", but the bake FAILS its checks: swap back, or give --hit-s"))
    print("next: python3 Scripts/dev/uepy.py --verify-for   (the verifiers the change maps to)")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
