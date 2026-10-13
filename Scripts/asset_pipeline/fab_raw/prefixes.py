"""prefixes.py -- give what an importer named the project's asset prefixes.

A mesh this import names itself is SM_ from the start. What a file names is
not: the parts of a kit, the materials and textures an FBX carries, a USD
stage's prims. Those are renamed here, once everything is in, by class (hard
rule 3 of the root CLAUDE.md). A rename fixes every reference and can leave a
redirector at the old name, which is deleted: nothing outside the item's
folder knew the old name.
"""

import unreal

EAL = unreal.EditorAssetLibrary

# Subclasses first: an instance is a MaterialInterface too.
PREFIX_OF = (
    (unreal.StaticMesh, "SM_"), (unreal.SkeletalMesh, "SK_"), (unreal.Skeleton, "SKEL_"),
    (unreal.Texture, "T_"), (unreal.MaterialInstance, "MI_"), (unreal.Material, "M_"),
    (unreal.PhysicsAsset, "PHYS_"), (unreal.AnimSequence, "A_"),
)


def apply(folder):
    """Prefix every asset under ``folder`` that lacks its class's. Returns how many."""
    renamed = 0
    for path in sorted(str(p) for p in EAL.list_assets(folder, True)):
        package = path.split(".")[0]
        asset = EAL.load_asset(package)
        prefix = next((p for cls, p in PREFIX_OF if isinstance(asset, cls)), None)
        name = package.rsplit("/", 1)[1]
        if prefix is None or name.lower().startswith(prefix.lower()):
            continue
        target = f"{package.rsplit('/', 1)[0]}/{prefix}{name}"
        if not EAL.does_asset_exist(target) and EAL.rename_asset(package, target):
            renamed += 1
    if renamed:
        EAL.save_directory(folder, only_if_is_dirty=False, recursive=True)
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
        for data in registry.get_assets_by_path(folder, True):
            # Python has no ObjectRedirector class to test against: go by name.
            if str(data.asset_class_path.asset_name) == "ObjectRedirector":
                EAL.delete_asset(str(data.package_name))
    return renamed
