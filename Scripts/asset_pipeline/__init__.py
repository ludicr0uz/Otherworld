"""asset_pipeline -- fetch and generate third-party assets for Otherworld.

Fetching runs host-side against external APIs; importing and rigging run
inside the editor.  The two halves meet at assets/cache/, which is git-ignored.

Host-side (no ``unreal``):
    catalog.py                  what to generate: one spec per character
    fetch_monsters.py           entry point: drive Meshy for every spec, cache the results
    providers/meshy.py          Meshy client: preview -> refine -> remesh -> rig
    skeleton_probe.py           fingerprint a cached GLB's bone hierarchy
    fab_library.py              Fab manifest (fab_library.json) + CLI; acquisition is manual

Editor-side, in pipeline order:
    import_characters.py        entry point: cached FBX -> SKM_/SK_ per character
    build_creature_materials.py entry point: the creature material and instances
    build_retarget.py           entry point: fingers, IK rigs, retargeters, clips
    finger_rig.py               add and skin 15 finger bones per Meshy hand
    palm_twist.py               hand frame from skinned geometry; palm roll calibration
    retarget_abp.py             fix the copied ABP_Unarmed for the Meshy skeleton
    retarget_verify.py          retargeted clips stand, stay in place and step
    finger_verify.py            fingers skinned, mapped, and posed like the mannequin's
    retarget_paths.py           constants: asset paths and the mannequin source clips
    rig_chains.py               constants: IK chain tables (mannequin, Meshy, Mixamo)
    rig_util.py                 log, asset loading, bone lists, bone pose in a clip
    retarget_rig.py             build one IK rig from a chain table; one retargeter
    import_mixamo.py            entry point: Mixamo zips -> X Bot clips -> the zombie
    mixamo_paths.py             constants: packs, asset paths, which clip plays what
    mixamo_import.py            unzip the packs; import X Bot and every clip onto SK_XBot
    mixamo_retarget.py          IK_XBot, RTG_<Creature>_from_XBot, batch retarget
    mixamo_locomotion.py        the creature's blend space plays the Mixamo gait; checks
    import_ui_art.py            entry point: HUD art PNGs -> textures
    fab_index.py                entry point: index Fab content -> assets/cache/fab/
    fab_inventory.py            describe a folder's assets from registry tags
"""
