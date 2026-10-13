"""stage.py -- copy a collected item into the cache and write its plan.

The staged copy is the import's only source: assets/cache/fab/raw/<Item>/files/
holds what was taken, at the paths it had in the download (a USD layer names
its neighbours by path), and plan.json beside it says what the editor is to
make of each file. Every copy is hashed again against the scan, so what the
editor reads is what was checked; the editor checks once more before it
imports. Names are decided here, host-side, so the tests cover them.
"""

import datetime
import hashlib
import json
import os
import shutil

from asset_pipeline import fab_library
from asset_pipeline.fab_raw import rules

RAW_DIR = os.path.join(fab_library.INDEX_DIR, "raw")
PLAN = "plan.json"
IMPORTED = "imported.json"
FILES = "files"


def dest_of(slug):
    return f"{fab_library.DEFAULT_ROOT}/{slug}"


def asset_name(prefix, stem, taken):
    """A project asset name for a file stem: prefixed once, plain, unique in ``taken``."""
    plain = rules.NOT_A_NAME.sub("_", stem).strip("_") or "Asset"
    if plain.lower().startswith(prefix.lower()):
        plain = plain[len(prefix):]
    base = name = prefix + plain
    n = 2
    while name.lower() in taken:
        name = f"{base}_{n}"
        n += 1
    taken.add(name.lower())
    return name


def _unprefixed(key):
    """A set named after its textures (T_1911) gives M_1911, not M_T_1911."""
    cut = len(rules.TEXTURE_PREFIX)
    return key[cut:] if key.lower().startswith(rules.TEXTURE_PREFIX.lower()) and key[cut:] else key


def _stem(rel):
    return os.path.splitext(os.path.basename(rel))[0]


def plan_of(item, replace=False, parts=False):
    """What the editor is to make of the item: a dict, written as plan.json."""
    taken = set()
    meshes = [{"file": rel, "asset": asset_name(rules.MESH_PREFIX, _stem(rel), taken),
               "usd": os.path.splitext(rel)[1].lower() in rules.USD_EXT}
              for rel in item.meshes]
    names = {rel: asset_name(rules.TEXTURE_PREFIX, _stem(rel), taken)
             for rel in item.texture_files()}
    sets = {key: {"material": asset_name(rules.MATERIAL_PREFIX, _unprefixed(key), taken),
                  "roles": {role: names[rel] for role, rel in sorted(roles.items())}}
            for key, roles in sorted(item.sets.items())}
    role_of = {rel: role for roles in item.sets.values() for role, rel in roles.items()}
    return {
        "slug": item.slug, "title": item.title, "url": item.url, "seller": item.seller,
        "source": item.source, "dest": dest_of(item.slug), "replace": bool(replace),
        # A kit is many meshes in one file: kept apart when asked, else one mesh.
        "parts": bool(parts),
        "staged": datetime.datetime.now().isoformat(timespec="seconds"),
        "verdict": item.verdict,
        "findings": [[f.level, f.path, f.what] for f in item.findings],
        "left": [list(pair) for pair in item.left],
        "files": item.files,
        "meshes": meshes,
        "textures": [{"file": rel, "asset": names[rel], "role": role_of.get(rel)}
                     for rel in sorted(names)],
        "sets": sets,
    }


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_imported(slug, project=fab_library.PROJECT_DIR):
    """Whether /Game/Fab/<slug> already holds assets."""
    path = fab_library.content_dir(dest_of(slug), project)
    return os.path.isdir(path) and any(files for _d, _s, files in os.walk(path))


def name_apart(item, raw_dir=RAW_DIR):
    """Two listings can share a title ("Puffer Jacket"). When the item's name is
    already staged for another listing, add the listing's id to its title, so
    each keeps its own folder and its own fab_library entry."""
    path = os.path.join(raw_dir, item.slug, PLAN)
    if not (item.url and os.path.isfile(path)):
        return False
    with open(path) as fh:
        other = json.load(fh).get("url", "")
    if not other or other == item.url:
        return False
    item.title = f"{item.title} ({item.url.rstrip('/').rsplit('/', 1)[1][:8]})"
    item.slug = rules.NOT_A_NAME.sub("_", item.title).strip("_")
    return True


def stage(item, raw_dir=RAW_DIR, replace=False, parts=False):
    """Copy the item's taken files under ``raw_dir`` and write the plan. Returns its path."""
    home = os.path.join(raw_dir, item.slug)
    if os.path.lexists(home):
        if not replace:
            raise RuntimeError(f"{home} exists: staged before (--replace stages it again)")
        shutil.rmtree(home)
    for rel, info in sorted(item.files.items()):
        dest = os.path.join(home, FILES, *rel.split("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(os.path.join(item.source, *rel.split("/")), dest)
        if sha256(dest) != info["sha256"]:
            shutil.rmtree(home)
            raise RuntimeError(f"{rel} changed between the scan and the copy: nothing staged")
    path = os.path.join(home, PLAN)
    with open(path, "w") as fh:
        json.dump(plan_of(item, replace, parts), fh, indent=1, sort_keys=True)
        fh.write("\n")
    return path


def staged(raw_dir=RAW_DIR):
    """[(slug, plan dict, imported or not)] for every staged item."""
    out = []
    if not os.path.isdir(raw_dir):
        return out
    for slug in sorted(os.listdir(raw_dir)):
        path = os.path.join(raw_dir, slug, PLAN)
        if os.path.isfile(path):
            with open(path) as fh:
                out.append((slug, json.load(fh),
                            os.path.isfile(os.path.join(raw_dir, slug, IMPORTED))))
    return out
