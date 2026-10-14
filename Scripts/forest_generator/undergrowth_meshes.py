"""The meshes the grass and the bushes are planted from. Pure Python (no ``unreal``).

Two come out of Fab packs the user added, and are planted where the pack put
them, with the pack's own materials (the grass on a level grass_look.py names
draws an instance of its own, a child of the pack's); the third is ours, made
of the first:

    grass    grass_02_09_mesh   "temperate Vegetation: optimized Grass Library"
    grass    SM_Grass_Patch     seven of that clump merged (GRASS_PATCH, below)
    grass    lowGrass_*_SM      six more of the same pack, the other grass
                                types (LOW_GRASS_MESHES, F2)
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

# Ours, not a pack's: seven copies of the clump merged into one patch 1.2 m
# across, built by Scripts/build_grass_patch.py (forest_generator/
# grass_patch.py has its numbers and reasons). The 200 m map plants it
# (grass_look.PATCH_GRASS_LEVELS). It draws the dark grass with pivot textures
# of its own, so it needs those, the dark instance and what the clump's
# material needs; not the clump. Its LOD0 is seven of the clump's LOD2, which
# has lost the tallest blades: so it is lower than the clump.
_PATCH = "/Game/Forest/Undergrowth"

GRASS_PATCH = LibraryMesh(
    name="Grass_Patch",
    pack=GRASS_02_09.pack,
    mesh=f"{_PATCH}/SM_Grass_Patch",
    height_cm=49.2, width_cm=120.4, lods=4, lod0_triangles=3766,
    packages=(
        "/Game/Forest/Materials/MI_Grass_02_09_Dark",
        f"{_PATCH}/MI_Grass_Patch_Dark",
        f"{_PATCH}/SM_Grass_Patch",
        f"{_PATCH}/T_Grass_Patch_PIV",
        f"{_PATCH}/T_Grass_Patch_VEC",
    ) + tuple(p for p in GRASS_02_09.packages if p != GRASS_02_09.mesh))

# The six other grass types (grass_look.GRASS_TYPES), F2: the pack's
# "lowGrass" clumps, wide and cheap (456-1,416 triangles against the patch's
# 3,766). Each needs only itself, its material instance and its pivot
# textures: the master material, its functions and the atlas are the clump's.
_GRASS_SHARED = tuple(p for p in GRASS_02_09.packages
                      if "/grass_02_09" not in p)
_LOW_VEC = f"{_GRASS}/Textures/grassTextures/PivPainterTextures/lowGrass_VEC"


def _low_grass(tag, height_cm, width_cm, lod0_triangles):
    name = f"lowGrass_{tag}"
    return LibraryMesh(
        name=f"LowGrass_{tag}",
        pack=GRASS_02_09.pack,
        mesh=f"{_GRASS}/Meshes/grassMesh/{name}_SM",
        height_cm=height_cm, width_cm=width_cm, lods=4,
        lod0_triangles=lod0_triangles,
        packages=_GRASS_SHARED + (
            f"{_GRASS}/Materials/grassMaterials/grassMaterials/{name}_Mat",
            f"{_GRASS}/Meshes/grassMesh/{name}_SM",
            f"{_GRASS}/Textures/grassTextures/PivPainterTextures/{name}_PIV",
            _LOW_VEC))


LOW_GRASS_01_02 = _low_grass("01_02", 22.4, 61.6, 537)
LOW_GRASS_02_02 = _low_grass("02_02", 42.0, 82.5, 728)
LOW_GRASS_03_03 = _low_grass("03_03", 66.3, 85.7, 904)
LOW_GRASS_04_06 = _low_grass("04_06", 92.2, 89.5, 756)
LOW_GRASS_06_02 = _low_grass("06_02", 92.7, 111.9, 1416)
LOW_GRASS_07_03 = _low_grass("07_03", 84.3, 103.1, 456)
LOW_GRASS_MESHES = (LOW_GRASS_01_02, LOW_GRASS_02_02, LOW_GRASS_03_03,
                    LOW_GRASS_04_06, LOW_GRASS_06_02, LOW_GRASS_07_03)

GRASS_MESHES = (GRASS_02_09, GRASS_PATCH) + LOW_GRASS_MESHES
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


# The packs' folders: git ignores them but for what gitignore_lines() names.
PACK_ROOTS = (_GRASS, _BUSH)


def in_a_pack(package):
    return package.startswith(tuple(f"{root}/" for root in PACK_ROOTS))


def gitignore_lines():
    """The lines .gitignore needs to let the shipped packs' packages through
    (ours, under /Game/Forest, are not ignored)."""
    return [f"!/{content_file(p)}" for p in shipped_packages() if in_a_pack(p)]
