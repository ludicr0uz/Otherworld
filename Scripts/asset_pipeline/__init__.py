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
    rig_chains.py               constants: IK chain tables, finger bone names
    rig_util.py                 log, asset loading, bone lists, bone pose in a clip
    import_ui_art.py            entry point: HUD art PNGs -> textures
    fab_index.py                entry point: index Fab content -> assets/cache/fab/
    fab_inventory.py            describe a folder's assets from registry tags
"""
