"""The editor's half: every StaticMesh and SkeletalMesh under /Game, from the
asset registry.

Reads the registry's tags and loads no mesh: the project holds hundreds, some
of them Nanite scans of a hundred thousand triangles and more, and the tags
already carry the counts. Two of them count triangles:

    Triangles        LOD 0 as it is drawn without Nanite. On a Nanite mesh
                     this is the fallback, which can be a small share of it.
    NaniteTriangles  what Nanite was built from, 0 when the mesh has none.

`triangles` is the one the mesh is built from: the Nanite count on a Nanite
mesh, LOD 0's otherwise. Both are kept.

A skeletal mesh (a gun with a moving bolt, a tree that bends in the wind, a
body) is on the list too, as `type` "skeletal". The registry holds less of
it: its LOD 0 triangles and its bones, and no vertices, LOD count or size,
which stay 0 and "".

What kind of thing a mesh is, the page decides (kinds.py), not the scan: the
kinds can be retuned without the editor.

A mesh's levels are the World packages that reach it within HOPS references
(a level names a foliage type or a Blueprint, which names the mesh), and the
levels whose external actors do.
"""

import json
import os
import time

import unreal

from map_assets.paths import OUT_DIR, SCAN_JSON

ROOT = "/Game"
HOPS = 3
EXTERNAL = "/Game/__ExternalActors__/"
INT_TAGS = {"Triangles": "lod0_triangles", "Vertices": "vertices",
            "NaniteTriangles": "nanite_triangles", "NaniteVertices": "nanite_vertices",
            "LODs": "lods", "Materials": "materials", "CollisionPrims": "collision_prims",
            "EstTotalCompressedSize": "bytes", "Bones": "bones"}
CLASSES = (("StaticMesh", "static"), ("SkeletalMesh", "skeletal"))


def _log(msg):
    unreal.log_warning(f"[GEN] map assets: {msg}")


def _of_class(registry, name):
    return registry.get_assets(unreal.ARFilter(
        class_paths=[unreal.TopLevelAssetPath("/Script/Engine", name)],
        package_paths=[ROOT], recursive_paths=True))


def _external_level(package):
    """"/Game/__ExternalActors__/Maps/Lvl_X/A/BC/HASH" -> "Lvl_X"."""
    parts = package[len(EXTERNAL):].split("/")
    named = [p for p in parts[:-1] if len(p) > 2]
    return named[-1] if named else None


def _levels(registry, package, worlds, options):
    """Names of the levels that reach ``package`` within HOPS references."""
    found, seen, front = set(), {package}, [package]
    for _hop in range(HOPS):
        nxt = []
        for name in front:
            for ref in registry.get_referencers(name, options) or ():
                ref = str(ref)
                if ref in seen:
                    continue
                seen.add(ref)
                if ref in worlds:
                    found.add(ref.rsplit("/", 1)[1])
                elif ref.startswith(EXTERNAL):
                    level = _external_level(ref)
                    if level:
                        found.add(level)
                else:
                    nxt.append(ref)
        front = nxt
    return sorted(found)


def _number(value):
    """A tag's value as an int; 0 when the class has no such tag or keeps
    something else under the name (a skeletal mesh's Materials is a list)."""
    try:
        return int(float(value)) if value else 0
    except ValueError:
        return 0


def _describe(ad, kind):
    path = str(ad.package_name)
    entry = {"path": path, "name": str(ad.asset_name), "type": kind}
    for tag, key in INT_TAGS.items():
        entry[key] = _number(ad.get_tag_value(tag))
    entry["nanite"] = (ad.get_tag_value("NaniteEnabled") or "").lower() == "true"
    entry["size_cm"] = ad.get_tag_value("ApproxSize") or ""
    entry["triangles"] = (entry["nanite_triangles"] if entry["nanite"]
                          and entry["nanite_triangles"] else entry["lod0_triangles"])
    return entry


def scan():
    """Write SCAN_JSON and return the meshes."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.wait_for_completion()
    worlds = {str(ad.package_name) for ad in _of_class(registry, "World")}
    options = unreal.AssetRegistryDependencyOptions()
    meshes = []
    for cls, kind in CLASSES:
        for ad in _of_class(registry, cls):
            entry = _describe(ad, kind)
            entry["levels"] = _levels(registry, entry["path"], worlds, options)
            meshes.append(entry)
    meshes.sort(key=lambda m: m["path"])
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(SCAN_JSON, "w") as fh:
        json.dump({"scanned": time.strftime("%Y-%m-%d %H:%M"), "meshes": meshes}, fh, indent=1)
    _log(f"{len(meshes)} meshes ({sum(m['type'] == 'skeletal' for m in meshes)} skeletal), "
         f"{sum(bool(m['levels']) for m in meshes)} used by a level -> {SCAN_JSON}")
    return meshes
