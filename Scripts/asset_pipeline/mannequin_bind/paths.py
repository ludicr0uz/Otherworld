"""paths -- where the bind reads from and writes to.  Constants and two
lookups; no unreal.

Everything it reads is git-ignored data (assets/cache, Content/), which a
git worktree does not have.  So what it READS comes from the data root: the
checkout that owns the .git directory, which in the main checkout is the
project itself and in a worktree is the main checkout the worktree hangs off
(``OW_DATA_ROOT`` overrides both).  What it WRITES goes under the checkout
it is run from, so a bind run in a worktree leaves the main checkout alone.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

# The mesh, not SK_Mannequin: a skeleton asset holds every bone any mannequin
# mesh uses (161), and a mesh's own reference skeleton holds the ones it is
# bound to (89). The second is what a body skinned like it must carry.
MANNEQUIN_MESH = "Content/Characters/Mannequins/Meshes/SKM_Manny_Simple.uasset"
MANNEQUIN_SKELETON_ASSET = "/Game/Characters/Mannequins/Meshes/SK_Mannequin"

# Where the bound bodies land in Content/, beside the per-body-skeleton ones
# (/Game/Sourced/Characters), so both flows can stand while one replaces the
# other.
BOUND_ROOT = "/Game/Sourced/Bound"


def data_root():
    """The checkout whose assets/ and Content/ are real."""
    override = os.environ.get("OW_DATA_ROOT")
    if override:
        return override
    dot_git = os.path.join(PROJECT_DIR, ".git")
    if os.path.isfile(dot_git):          # a worktree: "gitdir: <main>/.git/worktrees/<n>"
        with open(dot_git) as fh:
            gitdir = fh.read().split(":", 1)[1].strip()
        common = os.path.normpath(os.path.join(gitdir, "..", ".."))
        if os.path.basename(common) == ".git":
            return os.path.dirname(common)
    return PROJECT_DIR


def meshy_cache(spec_id=None):
    root = os.path.join(data_root(), "assets", "cache", "meshy")
    return os.path.join(root, spec_id) if spec_id else root


def mannequin_mesh_file():
    return os.path.join(data_root(), MANNEQUIN_MESH)


def bound_dir(spec_id):
    """Where one body's bound GLB and its report are written: git-ignored,
    and in the main checkout beside the rig they are made from."""
    return os.path.join(PROJECT_DIR, "assets", "cache", "meshy", spec_id, "bound")


def short_name(spec_id):
    """adventurer_03 -> Adventurer03, off the catalog's dest (as
    player_body.name_of; repeated here because player_body imports this
    package's neighbours and the bind must not import the player's setting)."""
    from asset_pipeline import catalog
    return os.path.basename(catalog.by_id(spec_id).dest).replace("SKM_", "")


def bound_glb(spec_id):
    """Named as the asset it becomes: Unreal's glTF importer names a mesh
    after its file and takes no other name (first run, 2026-10-03: a file
    called adventurer_03_mannequin.glb arrived as that, not as the
    destination name the import task asked for)."""
    return os.path.join(bound_dir(spec_id), f"{bound_asset_name(short_name(spec_id))}.glb")


def bound_report(spec_id):
    return os.path.join(bound_dir(spec_id), "bind_report.json")


def bound_asset_name(short):
    """adventurer_03's short name Adventurer03 -> SKM_Adventurer03, the same
    name its per-body-skeleton mesh has, in the other folder."""
    return f"SKM_{short}"


def bound_asset_dir(short):
    return f"{BOUND_ROOT}/{bound_asset_name(short)}"
