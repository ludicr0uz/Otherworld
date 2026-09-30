"""fab_inventory -- describe every asset under a content folder, for the Fab index.

Editor-side. Reads the asset registry's tags rather than loading assets: a pack
like the Game Animation Sample holds thousands of clips, and the registry
already carries what an agent needs to choose one (skeleton, length, frames,
root motion; a mesh's bone and triangle counts). Only skeletons are loaded --
there are few -- to check them for the mannequin's bone names.
"""

import unreal

from asset_pipeline.fab_library import MANNEQUIN_BONES, MANNEQUIN_SKELETON
from asset_pipeline.rig_util import _skeleton_bone_names

# Registry tag -> index key, per class. Values are kept as the registry's
# strings except where a number or a bool is plainly meant.
TAGS = {
    "SkeletalMesh": {"Skeleton": "skeleton", "Bones": "bones", "Triangles": "triangles"},
    "StaticMesh": {"Triangles": "triangles", "Vertices": "vertices"},
    "AnimSequence": {"Skeleton": "skeleton", "SequenceLength": "seconds",
                     "Number of Frames": "frames", "bEnableRootMotion": "root_motion"},
    "AnimMontage": {"Skeleton": "skeleton", "SequenceLength": "seconds"},
    "BlendSpace": {"Skeleton": "skeleton"},
    "AimOffsetBlendSpace": {"Skeleton": "skeleton"},
    "MaterialInstanceConstant": {"Parent": "parent"},
}
NUMBERS = {"bones", "triangles", "vertices", "frames"}


def _object_path(value):
    """"/Script/Engine.Skeleton'/Game/X/SK.SK'" -> "/Game/X/SK"."""
    if "'" in value:
        value = value.split("'")[1]
    return value.split(".")[0]


def _tag_values(ad, cls):
    out = {}
    for tag, key in TAGS.get(cls, {}).items():
        value = ad.get_tag_value(tag)
        if not value:
            continue
        if key in ("skeleton", "parent"):
            value = _object_path(value)
        elif key == "seconds":
            value = round(float(value), 3)
        elif key in NUMBERS:
            value = int(value)
        elif key == "root_motion":
            value = value.lower() == "true"
        out[key] = value
    return out


def _skeleton_facts(path):
    skeleton = unreal.EditorAssetLibrary.load_asset(path)
    if skeleton is None:
        return {}
    bones = set(_skeleton_bone_names(skeleton))
    return {"bone_count": len(bones),
            "mannequin_bones": all(b in bones for b in MANNEQUIN_BONES)}


def describe(root):
    """One dict per asset under root: path, class, and the class's tag values."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    assets = []
    for ad in registry.get_assets_by_path(root, recursive=True):
        cls = str(ad.asset_class_path.asset_name)
        entry = {"path": str(ad.package_name), "class": cls}
        entry.update(_tag_values(ad, cls))
        if cls == "Skeleton":
            entry.update(_skeleton_facts(entry["path"]))
        if entry.get("skeleton") == MANNEQUIN_SKELETON:
            entry["mannequin_skeleton"] = True
        assets.append(entry)
    return sorted(assets, key=lambda a: a["path"])
