"""What a change can move in the verifier sweep, and the tree snapshot that
says what changed.

A verifier suite reads built assets under Content/ and the Python it imports.
A path can move a suite's result only if it is that content, the builder that
writes it, the suite itself or what every suite shares (uebp, the verify
helpers, the C++, the config). So the gate's sweeps are keyed and scoped by
paths rather than by commit: ``snapshot`` is every tracked and untracked file
with its blob hash; ``changed`` is what differs between two of them; and
``suites_for`` says which suites those paths reach -- an empty set for docs,
Scripts/dev, probes and the like (nothing to sweep), None for a path every
suite may feel or one no rule knows (the whole sweep). Unknown means whole,
never skip.
"""

import os
import subprocess

from uepylib import probe_map

ALL = None                                  # suites_for: the whole sweep

# Paths no suite reads: a change here moves no verifier.
IRRELEVANT = (
    "docs/", "Scripts/dev/", "Scripts/probes/", "Scripts/server/", "Build/", "Saved/",
    "assets/", "Content/Python/", "Content/Splash/", "Content/Collections/",
    "Content/Developers/", "Content/Tmp/",
    ".gitignore", ".gitattributes", "LICENSE.txt", "CompletedTasks.md",
)
# Paths every suite may feel.
WHOLE = (
    "Scripts/uebp/", "Scripts/combat/verify/common.py", "Scripts/combat/verify/fixtures.py",
    "Scripts/asset_pipeline/", "Scripts/forest_import/", "Source/", "Config/",
    "Otherworld.uproject", "Content/Characters/", "Content/MetaHumans/", "Content/GAS/",
    "Content/Sourced/", "Content/ThirdPerson/", "Content/LevelPrototyping/",
)
WEAPONS = "verify_weapons_and_combat.py"
LEVELS = tuple(os.path.basename(p) for p in probe_map.LEVELS)
# Built content by folder: the suite that reads it.
CONTENT = (
    ("Content/Weapons/", (WEAPONS,)),
    ("Content/Audio/", (WEAPONS,)),
    ("Content/FPS_Weapon_Bundle/", (WEAPONS,)),
    ("Content/Input/", (WEAPONS, "verify_graphics_menu.py")),
    ("Content/Tuning/", (WEAPONS,)),
    ("Content/UI/", ("verify_graphics_menu.py",)),
    ("Content/Clothing/", ("verify_clothing.py", WEAPONS)),
    ("Content/Survival/", ("verify_survival.py",)),
    ("Content/World/", ("verify_day_night.py",)),
    ("Content/Forest/", LEVELS + ("verify_npc_blueprints.py",)),
    ("Content/Maps/", LEVELS),
    ("Content/__ExternalActors__/", LEVELS),
    ("Content/__ExternalObjects__/", LEVELS),
)


def suites_for(paths):
    """The suite labels (verifier basenames) the paths can move: a set, or
    ALL (None) when any path reaches every suite or none of the rules knows it."""
    out = set()
    for path in paths:
        path = path.replace(os.sep, "/")
        if path.endswith(".md") or path.startswith(IRRELEVANT):
            continue
        if path.startswith(WHOLE):
            return ALL
        found = None
        for prefix, suites in CONTENT:
            if path.startswith(prefix):
                found = suites
                break
        if found is None:
            found = [os.path.basename(s) for s in probe_map.verifiers_for([path])]
        if not found:
            return ALL                      # a path no rule knows
        out.update(found)
    return out


def snapshot(root):
    """{repo path: content hash} of the working tree: tracked files by their
    index blob (a worktree edit re-hashed), untracked files hashed too."""
    files = {}
    for line in _git(root, "ls-files", "-s").splitlines():
        meta, _tab, path = line.partition("\t")
        files[path] = meta.split()[1]
    dirty = []
    for line in _git(root, "status", "--porcelain", "--untracked-files=all").splitlines():
        path = line[3:].split(" -> ")[-1].strip('"')
        if os.path.exists(os.path.join(root, path)):
            dirty.append(path)
        else:
            files.pop(path, None)
    if dirty:
        hashes = _git(root, "hash-object", "--stdin-paths", stdin="\n".join(dirty) + "\n")
        files.update(zip(dirty, hashes.split()))
    return files


def changed(before, after):
    """The paths whose hash differs between two snapshots, sorted."""
    return sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))


def relevant(files):
    """The snapshot's entries a suite can read: the cache key's material."""
    return {p: h for p, h in files.items() if suites_for([p]) != set()}


def _git(root, *args, stdin=None):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                          input=stdin).stdout
