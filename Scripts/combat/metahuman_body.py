"""The MetaHuman body hung under the player's mannequin.

    Mesh (SK_Mannequin, hidden, runs ABP_Unarmed as it always did)
    └── Body      m_med_nrw_body, ABP_MetaHuman_Retarget: retargets the
        │         parent's pose every frame (build_metahuman_retarget.py)
        ├── Face  Taro_FaceMesh, Face_AnimBP (copies the body's neck and head)
        │   └── Hair, Eyebrows, Eyelashes, Mustache, Beard, Fuzz  (grooms)
        ├── Torso, Legs, Feet   clothing; MetaHuman gives them their
        │                       post-process anim BP, which follows Body
        MetaHuman   MetaHumanComponentUE: the correctives and the clothing
        LODSync     one LOD for all of it, led by Body and Face

This is BP_Taro's component tree, read off it once (metahuman_paths.py),
grafted under the game's mannequin instead of under a root of its own. The
mannequin keeps everything that was ever built against it -- the anim
blueprint, the slots, the ready poses, the grip socket, the hit bodies and
the ragdoll -- and the MetaHuman is what is drawn. Nothing in the weapons
build changes for it; skin.wear_skin() calls install() or remove() with the
rest of the skin.

Names matter: MetaHumanComponentUE finds the body and the face by component
name ("Body", "Face"), and LODSync lists its components by name too.
"""

import unreal

from asset_pipeline.metahuman_paths import (
    ABP_RETARGET, BODY_MESH, CLOTHING, CLOTHING_POST_PROCESS, FACE_ANIM_BP, FACE_MESH,
    GROOMS,
)
from combat.log import _log
from uebp.graph import _add_component, _component_object, _drop_components, _find_handle

BODY, FACE, META, LOD_SYNC = "Body", "Face", "MetaHuman", "LODSync"
COMPONENTS = (BODY, FACE, META, LOD_SYNC) + tuple(CLOTHING) + tuple(GROOMS)

# BP_Taro's LOD sync: eight LODs, the body and the face drive, the rest
# follow, and the body and clothing (four LODs each) take every face LOD
# in pairs.
NUM_LODS = 8
LOD_PAIRS = (0, 0, 1, 1, 2, 2, 3, 3)


def _anim_class(bp_path):
    cls = unreal.load_class(None, f"{bp_path}.{bp_path.rsplit('/', 1)[1]}_C")
    if not cls:
        raise RuntimeError(f"{bp_path} has no generated class -- it did not compile")
    return cls


def _must(path):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if not asset:
        raise RuntimeError(f"{path} is missing -- run import_metahuman.py and "
                           "build_metahuman_retarget.py")
    return asset


def _skeletal(bp, parent, name, mesh, anim_bp=None):
    handle = _add_component(bp, parent, unreal.SkeletalMeshComponent, name)
    comp = _component_object(handle)
    comp.set_editor_property("skeletal_mesh_asset", _must(mesh))
    if anim_bp:
        comp.set_editor_property("animation_mode", unreal.AnimationMode.ANIMATION_BLUEPRINT)
        comp.set_editor_property("anim_class", _anim_class(anim_bp))
    # Posed whether or not it is drawn, like the mannequin (skin.wear_skin):
    # behind the sniper's scope the body is hidden from its own camera.
    comp.set_editor_property(
        "visibility_based_anim_tick_option",
        unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    return handle, comp


def _sync_entry(name, option):
    entry = unreal.ComponentSync()
    entry.set_editor_property("name", name)
    entry.set_editor_property("sync_option", option)
    return entry


def install(bp, mannequin_handle, retarget=None):
    """Graft the MetaHuman under the mannequin's handle. Rebuilt from
    nothing each time, so a run after an edit here leaves no stale part.
    ``retarget`` is the anim Blueprint the body follows its parent through:
    the mannequin's unless the parent is another mesh (PlayerSkin.retarget)."""
    retarget = retarget or ABP_RETARGET
    _drop_components(bp, COMPONENTS)
    body, body_comp = _skeletal(bp, mannequin_handle, BODY, BODY_MESH, retarget)
    face, _face_comp = _skeletal(bp, body, FACE, FACE_MESH, FACE_ANIM_BP)
    for name, mesh in CLOTHING.items():
        _skeletal(bp, body, name, mesh)
    for name, (groom, binding) in GROOMS.items():
        comp = _component_object(_add_component(bp, face, unreal.GroomComponent, name))
        comp.set_editor_property("groom_asset", _must(groom))
        comp.set_editor_property("binding_asset", _must(binding))
        comp.set_editor_property("use_attach_parent_bound", True)

    meta = _component_object(_add_component(bp, mannequin_handle,
                                            unreal.MetaHumanComponentUE, META))
    meta.set_editor_property("body_component_name", BODY)
    meta.set_editor_property("face_component_name", FACE)
    meta.set_editor_property("post_process_anim_bp", _anim_class(CLOTHING_POST_PROCESS))

    sync = _component_object(_add_component(bp, mannequin_handle,
                                            unreal.LODSyncComponent, LOD_SYNC))
    sync.set_editor_property("num_lods", NUM_LODS)
    drive, passive = unreal.SyncOption.DRIVE, unreal.SyncOption.PASSIVE
    sync.set_editor_property("components_to_sync", [
        _sync_entry(BODY, drive), _sync_entry(FACE, drive),
        *[_sync_entry(n, passive) for n in list(CLOTHING) + list(GROOMS)]])
    mapping = unreal.LODMappingData()
    mapping.set_editor_property("mapping", list(LOD_PAIRS))
    sync.set_editor_property("custom_lod_mapping",
                             {n: mapping for n in (BODY, *CLOTHING)})
    got = body_comp.get_editor_property("anim_class")
    if got != _anim_class(retarget):
        raise RuntimeError(f"the body's anim class did not stick: {got}")
    _log(f"player: MetaHuman body, face, {len(CLOTHING)} garments and "
         f"{len(GROOMS)} grooms under the mannequin")


def remove(bp):
    """Take the MetaHuman off, for a skin that is not it."""
    if any(_find_handle(bp, n) for n in COMPONENTS):
        _drop_components(bp, COMPONENTS)
        _log("player: MetaHuman body removed")


def installed(bp):
    return _find_handle(bp, BODY) is not None
