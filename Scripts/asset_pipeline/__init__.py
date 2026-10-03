"""asset_pipeline -- fetch and generate third-party assets for Otherworld.

Fetching runs host-side against external APIs; importing and rigging run
inside the editor.  The two halves meet at assets/cache/, which is git-ignored.

Host-side (no ``unreal``):
    catalog.py                  what to generate: one spec per character
    fetch_monsters.py           entry point: drive Meshy for every spec, cache the results
    providers/meshy.py          Meshy client: preview -> refine -> remesh -> rig
    skeleton_probe.py           fingerprint a cached GLB's bone hierarchy
    rig_compat.py               can one cached rig replace another: compatible,
                                normalise or fail (tests: dev/tests/test_rig_compat.py)
    player_body.py              constants: THE setting naming the player's body,
                                and the clothing base body
    swap_player_body.py         entry point: write that setting, import, rebuild, verify
    fab_library.py              Fab manifest (fab_library.json) + CLI; acquisition is manual

Editor-side, in pipeline order:
    import_body.py              entry point: bring in every cached character not
                                imported yet (the three steps below, for it alone)
    import_characters.py        entry point: cached FBX -> SKM_/SK_ per character
    physics_template.py         a body that replaces another takes its physics
                                bodies; joints reseated on its own bones
    build_creature_materials.py entry point: the creature material and instances
    build_retarget.py           entry point: fingers, IK rigs, retargeters, clips
    finger_rig.py               add and skin 15 finger bones per Meshy hand
    clavicle_align.py           turn a clavicle far off the source's onto its line
    two_hands.py                the two-handed ready poses keep the source's hand spacing
    quat_math.py                quaternion/vector tuples for the passes above
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
    import_quaternius.py        entry point: Quaternius zips -> UAL clips on the
                                adventurer, gun/survival props, the zombie
    quaternius_paths.py         constants: packs, asset paths, which clips/models play
    quaternius_import.py        unzip; import each GLB/FBX and rename it into its pack
    retarget_player_clips.py    entry point: the UAL clips onto the player's body
                                alone, from the packs as imported (the swap's step)
    ual_retarget.py             IK_UAL1/2, RTG_<Character>_from_UAL1/2, batch retarget
    import_ui_art.py            entry point: HUD art PNGs -> textures
    fab_index.py                entry point: index Fab content -> assets/cache/fab/
    fab_inventory.py            describe a folder's assets from registry tags
"""
