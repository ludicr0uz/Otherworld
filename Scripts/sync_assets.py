#!/usr/bin/env python3
"""
sync_assets.py -- put the non-code bytes back, and check they are the right ones.

    python3 Scripts/sync_assets.py --status         what is present, what is missing
    python3 Scripts/sync_assets.py --restore-stock  copy the stock assets from the engine
    python3 Scripts/sync_assets.py --verify         checksum the stock assets
    python3 Scripts/sync_assets.py --record         re-record the checksums (engine upgrade)
    python3 Scripts/sync_assets.py --plan           print the full from-scratch order

The repository is code only: a fresh clone has no Content/ except Content/Python.
``--restore-stock`` copies the four template directories out of the installed
engine, which is the whole of the non-regenerable problem -- everything else in
Content/ is written by a builder in Scripts/ and is reproduced by running it.

Run with plain ``python3`` on the host, not inside the editor, and with the
editor CLOSED: this replaces .uasset files on disk, and an editor holding them
open will write its stale copies back over the top.

Checksums cover stock files only, and deliberately not the three the builders
patch (see PATCHED_STOCK in forest_generator/asset_sources.py). A Blueprint
recompile is not byte-deterministic, so a patched asset cannot be hashed
against a stored value -- the verifier suite is what says those are correct.
"""

import argparse
import glob
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from forest_generator.asset_sources import (          # noqa: E402
    ALL_SOURCES,
    CACHE,
    ENGINE_ROOT_GLOB,
    FAB,
    ENGINE_VERSION,
    GENERATED,
    PATCHED_STOCK,
    RESTORE_ORDER,
    STOCK,
    STOCK_CHECKSUM_FILE,
)


def engine_root(override=None) -> str:
    """The UE_x.y directory. Mirrors Scripts/dev/uepy.py's resolution order."""
    for candidate in (override, os.environ.get("UE_ENGINE_DIR")):
        if candidate:
            # uepy.py's variable points at .../UE_x.y/Engine; accept either.
            root = candidate[:-len("/Engine")] if candidate.rstrip("/").endswith("Engine") else candidate
            if os.path.isdir(os.path.join(root, "Templates")):
                return root
    roots = sorted(glob.glob(ENGINE_ROOT_GLOB))
    roots = [r for r in roots if os.path.isdir(os.path.join(r, "Templates"))]
    if not roots:
        sys.exit(f"[assets] no UE {ENGINE_VERSION} install found -- "
                 f"pass --engine or set UE_ENGINE_DIR")
    return roots[-1]


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _walk(root: str):
    """Every file under root, as paths relative to it, sorted."""
    out = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name == ".DS_Store":
                continue
            full = os.path.join(dirpath, name)
            out.append(os.path.relpath(full, root))
    return sorted(out)


# ── status ───────────────────────────────────────────────────────────────────

def cmd_status() -> int:
    print(f"project: {PROJECT_ROOT}\n")
    width = max(len(s.dest) for s in ALL_SOURCES)
    for group, label in ((STOCK, "stock"), (GENERATED, "generated"), (CACHE, "cache"),
                         (FAB, "fab (manual)")):
        print(f"── {label} ──")
        for src in group:
            path = os.path.join(PROJECT_ROOT, src.dest)
            if os.path.isdir(path):
                n = len(_walk(path))
                mb = sum(os.path.getsize(os.path.join(path, f)) for f in _walk(path)) / (1 << 20)
                state = f"present  {n:>4} files  {mb:>7.1f} MB"
            else:
                state = "MISSING"
            print(f"  {src.dest:<{width}}  {state}")
            if not os.path.isdir(path):
                how = (f"--restore-stock" if src.is_stock
                       else "  &&  ".join(src.builders))
                print(f"  {'':<{width}}  -> {how}")
        print()
    from asset_pipeline import fab_library
    items = fab_library.load()
    print(f"── fab library ({len(items)} recorded in asset_pipeline/fab_library.json) ──")
    for item in items:
        state = "present" if fab_library.is_present(item) else "MISSING  -> re-add in Fab"
        print(f"  {item.content:<{width}}  {state}  ({item.name})")
    print()
    return 0


# ── restore ──────────────────────────────────────────────────────────────────

def cmd_restore_stock(engine: str, force: bool) -> int:
    print(f"[assets] engine: {engine}")
    copied = 0
    for src in STOCK:
        source = os.path.join(engine, src.engine_subpath)
        dest = os.path.join(PROJECT_ROOT, src.dest)
        if not os.path.isdir(source):
            print(f"[assets] FAIL  no such engine directory: {source}")
            return 1
        if os.path.isdir(dest):
            if not force:
                print(f"[assets] skip  {src.dest} already present "
                      f"(--force to replace)")
                continue
            shutil.rmtree(dest)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copytree(source, dest)
        n = len(_walk(dest))
        copied += n
        print(f"[assets] copied {src.dest}  ({n} files)")
    if copied:
        print(f"[assets] {copied} files restored. The three patched assets are "
              f"stock until the builders run:")
        for path in PATCHED_STOCK:
            print(f"           {path}")
        print(f"[assets] next: {RESTORE_ORDER[1]}")
    return 0


# ── verify / record ──────────────────────────────────────────────────────────

def _stock_manifest(engine: str) -> dict:
    """{project-relative path: sha256} for every stock file, patched excluded."""
    out = {}
    for src in STOCK:
        source = os.path.join(engine, src.engine_subpath)
        for rel in _walk(source):
            dest_rel = f"{src.dest}/{rel}"
            if dest_rel in PATCHED_STOCK:
                continue
            out[dest_rel] = _sha256(os.path.join(source, rel))
    return out


def cmd_record(engine: str) -> int:
    manifest = _stock_manifest(engine)
    path = os.path.join(PROJECT_ROOT, STOCK_CHECKSUM_FILE)
    payload = {
        "engine_version": ENGINE_VERSION,
        "engine_root": engine,
        "note": "sha256 of every stock asset, as shipped by the engine. "
                "The three assets in PATCHED_STOCK are excluded: builders "
                "rewrite them and a Blueprint recompile is not byte-stable.",
        "files": manifest,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"[assets] recorded {len(manifest)} checksums -> {STOCK_CHECKSUM_FILE}")
    return 0


def cmd_verify() -> int:
    path = os.path.join(PROJECT_ROOT, STOCK_CHECKSUM_FILE)
    if not os.path.isfile(path):
        sys.exit(f"[assets] no {STOCK_CHECKSUM_FILE} -- run --record first")
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    expected = payload["files"]
    missing, changed, ok = [], [], 0
    for rel, want in sorted(expected.items()):
        full = os.path.join(PROJECT_ROOT, rel)
        if not os.path.isfile(full):
            missing.append(rel)
        elif _sha256(full) != want:
            changed.append(rel)
        else:
            ok += 1
    print(f"[assets] recorded against UE {payload['engine_version']}")
    print(f"[assets] {ok} stock assets match")
    for rel in missing:
        print(f"[assets] MISSING  {rel}")
    for rel in changed:
        print(f"[assets] CHANGED  {rel}")
    print(f"[assets] {len(PATCHED_STOCK)} patched assets not checksummed "
          f"(the verifier suite covers those)")
    if missing or changed:
        print("[assets] a CHANGED stock asset means either a local edit that "
              "no script reproduces, or an engine upgrade. Both need a "
              "decision -- do not just re-record.")
        return 1
    return 0


def cmd_plan() -> int:
    print("From an empty Content/ (bar Content/Python), with the editor closed:\n")
    for i, step in enumerate(RESTORE_ORDER, 1):
        print(f"  {i}. python3 {step}")
    print("\nThen the verifiers, every check of which must pass:\n")
    for v in ("Scripts/verify_weapons_and_combat.py",
              "Scripts/verify_npc_blueprints.py",
              "Scripts/verify_graphics_menu.py",
              "Scripts/generated_levels/Lvl_Forest_200m/verify_Lvl_Forest_200m.py"):
        print(f"     python3 Scripts/dev/uepy.py --cold {v}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--restore-stock", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="with --restore-stock: replace directories that exist")
    ap.add_argument("--engine", help="path to the UE_x.y directory")
    args = ap.parse_args()

    if args.restore_stock:
        return cmd_restore_stock(engine_root(args.engine), args.force)
    if args.record:
        return cmd_record(engine_root(args.engine))
    if args.verify:
        return cmd_verify()
    if args.plan:
        return cmd_plan()
    return cmd_status()


if __name__ == "__main__":
    raise SystemExit(main())
