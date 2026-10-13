"""The meshes the grass and the bushes are planted from. Pure Python (no ``unreal``).

Both come out of Fab packs the user added, and are planted where the pack put
them, with the pack's own materials (the grass on a level grass_look.py names
draws an instance of its own, a child of the pack's):

    grass    grass_02_09_mesh   "temperate Vegetation: optimized Grass Library"
    bushes   SM_Bush_02         "Light Foliage"

Neither is Nanite. Each has four mesh LODs and a masked, two-sided foliage
material, and sways by its pack's own wind, not MPC_Wind (forest_generator/
wind.py): the graphics menu's wind strength does not reach them, its
world-position-offset switch does.

Committed, though the packs are not
----------------------------------
A pack folder is the asset library: on disk, git-ignored (.gitignore, "The Fab
asset library"). The game needs these two meshes and what they reference, so
.gitignore re-includes exactly ``packages`` below and Git LFS carries them.
``forest_import/undergrowth_assets.py`` checks in the editor that a mesh
references nothing outside its list, and
``dev/tests/test_undergrowth_meshes.py`` that .gitignore lets every one of
them through and nothing else of the two packs. To plant another library mesh, add
its record here and its ``gitignore_lines()`` to .gitignore.

The sizes are the meshes' bounds as measured in the editor; the level verifier
re-measures them, so a pack update that changes one fails there.

The generated meshes these replaced (forest_generator/foliage_meshes.py,
/Game/Forest/Procedural) are still built by forest_import/foliage_assets.py
run on its own, but no level plants them.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LibraryMesh:
    """One mesh planted straight out of a Fab pack."""
    name: str                # short name, the tail of the cells' label
    pack: str                # the pack's name in asset_pipeline/fab_library.json
    mesh: str                # package path
    height_cm: float         # bounds height
    width_cm: float          # the wider of the two bounds widths
    lods: int
    lod0_triangles: int
    packages: tuple          # every /Game package it needs, itself included


_GRASS = "/Game/PN_GrassLibrary"
_BUSH = "/Game/Light_Foliage"

GRASS_02_09 = LibraryMesh(
    name="Grass_02_09",
    pack="temperate Vegetation: optimized Grass Library",
    mesh=f"{_GRASS}/Meshes/grassMesh/grass_02_09_mesh",
    height_cm=59.7, width_cm=54.1, lods=4, lod0_triangles=2152,
    packages=(
        f"{_GRASS}/Materials/MaterialFunctions/PN_AnimationShader",
        f"{_GRASS}/Materials/MaterialFunctions/PN_Bending",
        f"{_GRASS}/Materials/MaterialFunctions/PN_BendingParameters",
        f"{_GRASS}/Materials/MaterialFunctions/PN_MultiBend",
        f"{_GRASS}/Materials/MaterialFunctions/PN_WindAnimation",
        f"{_GRASS}/Materials/PN_WindParameters",
        f"{_GRASS}/Materials/grassMaterials/MA_Grass",
        f"{_GRASS}/Materials/grassMaterials/grassMaterials/grass_02_09_Mat",
        f"{_GRASS}/Meshes/grassMesh/grass_02_09_mesh",
        # The pack's one atlas, 8k: 109 MB of the 110 MB this mesh brings.
        f"{_GRASS}/Textures/grassTextures/MasterTextures/springGrass_Albedo_8k_I",
        f"{_GRASS}/Textures/grassTextures/MasterTextures/springGrass_Normal_springGrass_8k",
        f"{_GRASS}/Textures/grassTextures/MasterTextures/springGrass_Opacity_8k",
        f"{_GRASS}/Textures/grassTextures/PivPainterTextures/grass_02_09_PIV",
        f"{_GRASS}/Textures/grassTextures/PivPainterTextures/grass_02_09_VEC",
    ))

BUSH_02 = LibraryMesh(
    name="Bush_02",
    pack="Light Foliage",
    mesh=f"{_BUSH}/Meshes/SM_Bush_02",
    height_cm=195.2, width_cm=349.4, lods=4, lod0_triangles=1304,
    packages=(
        f"{_BUSH}/Materials/MI_Branch",
        f"{_BUSH}/Materials/MI_Bush_02",
        f"{_BUSH}/Materials/Master_Materials/M_Master_Foliage",
        f"{_BUSH}/Meshes/SM_Bush_02",
        f"{_BUSH}/Textures/T_Bush_02_Mask",
        f"{_BUSH}/Textures/T_Bush_02_Normal",
        f"{_BUSH}/Textures/T_Bush_04_Normal",
        f"{_BUSH}/Textures/T_Bush_Branch_Mask",
    ))

GRASS_MESHES = (GRASS_02_09,)
BUSH_MESHES = (BUSH_02,)
UNDERGROWTH_MESHES = GRASS_MESHES + BUSH_MESHES


def asset_path(mesh):
    """The object path a spec plants: ``/Game/Dir/Name.Name``."""
    return f"{mesh.mesh}.{mesh.mesh.rsplit('/', 1)[1]}"


def content_file(package):
    """A /Game package's file, relative to the project root."""
    return f"Content/{package[len('/Game/'):]}.uasset"


def shipped_packages():
    """Every library package the levels need, sorted."""
    return sorted({p for m in UNDERGROWTH_MESHES for p in m.packages})


def gitignore_lines():
    """The lines .gitignore needs to let the shipped packages through."""
    return [f"!/{content_file(p)}" for p in shipped_packages()]
