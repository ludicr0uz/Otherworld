"""verify.skins -- every generated character (the player's body, the zombie,
the wendigo) renders its own textures, not the engine's grey default.

asset_pipeline/build_creature_materials.py recreates the shared master
M_MeshyCreature on each run; an instance it does not re-parent keeps a null
parent and the mesh draws grey with nothing in the log.
"""

import unreal

from combat.ragdoll import RAGDOLL_MESH_ROOT
from combat.verify.common import check

MASTER = "/Game/Sourced/Characters/Materials/M_MeshyCreature"
ROLES = ("BaseColor", "Normal", "ORM")


def check_character_materials():
    eas = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    mel = unreal.MaterialEditingLibrary
    for path in sorted(eas.list_assets(RAGDOLL_MESH_ROOT, recursive=True)):
        mesh = eas.load_asset(path.split(".")[0])
        if not isinstance(mesh, unreal.SkeletalMesh):
            continue
        name = mesh.get_name()
        for slot in mesh.get_editor_property("materials"):
            mi = slot.get_editor_property("material_interface")
            parent = (mi.get_editor_property("parent")
                      if isinstance(mi, unreal.MaterialInstanceConstant) else None)
            check(f"{name}: its material is an instance of {MASTER.rsplit('/', 1)[1]}",
                  parent is not None and parent.get_path_name().split(".")[0] == MASTER,
                  f"{mi.get_name() if mi else None} parent {parent}")
            if parent is None:
                continue
            own = mesh.get_name().replace("SKM_", "")
            texs = {r: mel.get_material_instance_texture_parameter_value(mi, r)
                    for r in ROLES}
            check(f"...wearing its own {', '.join(ROLES)} maps",
                  all(t is not None and own in t.get_name() for t in texs.values()),
                  str({r: t.get_name() if t else None for r, t in texs.items()}))


def run():
    check_character_materials()
