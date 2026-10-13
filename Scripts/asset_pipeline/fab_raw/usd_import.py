"""usd_import.py -- the USD half of the import: which layers, and that they stay inside.

A USD layer can name other files: a layer per variant referencing one of
shared branches, and equally a path anywhere on this machine or a URL. Before
anything is imported every file a staged layer names must be another staged
file of the same item. Then only the layers nothing else names are imported;
the ones they reference come in with them.

The importer names assets after the stage's prims and lays its own folders
under the destination (prefixes.py renames what needs it afterwards).
"""

import os

import unreal

# What comes out is assets to place, not a level: no actors, no sequences.
OPTIONS = {
    "import_actors": False,
    "import_geometry": True,
    "import_skeletal_animations": False,
    "import_level_sequences": False,
    "import_materials": True,
    "prim_path_folder_structure": False,
}


def names_of(path):
    """Every file the layer at ``path`` names: sublayers, references, payloads, asset paths."""
    from pxr import UsdUtils
    subs, refs, payloads = UsdUtils.ExtractExternalReferences(path)
    return sorted(set(subs) | set(refs) | set(payloads))


def roots(files_dir, usd_rels):
    """(the layers to import, problems). A problem is a name that leaves the item."""
    staged = {os.path.normpath(os.path.join(files_dir, *rel.split("/"))): rel
              for rel in usd_rels}
    named, problems = set(), []
    for path, rel in sorted(staged.items()):
        for name in names_of(path):
            if "://" in name or os.path.isabs(name):
                problems.append(f"{rel} names {name}: not a file of this item")
                continue
            target = os.path.normpath(os.path.join(os.path.dirname(path), name))
            if target in staged:
                named.add(staged[target])
            else:
                problems.append(f"{rel} names {name}: not among the staged files")
    return sorted(set(usd_rels) - named), problems


def options():
    opts = unreal.UsdStageImportOptions()
    for name, value in OPTIONS.items():
        try:
            opts.set_editor_property(name, value)
        except Exception:                           # an option this engine has renamed
            unreal.log_warning(f"[FAB-RAW] UsdStageImportOptions has no {name}")
    return opts

