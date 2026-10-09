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
    fab_scan.py                 entry point: scan a downloaded Fab pack, then copy it
                                into Content/ (the checks: fab_intake/, which has
                                its own map; tests: dev/tests/test_fab_intake.py)
    import_gas.py               entry point: copy the Game Animation Sample's
                                motion-matching set into Content/GAS (the list:
                                gas_manifest.txt; what was cut: gas_manifest_cut.txt;
                                tests: dev/tests/test_gas_import.py)
    gas_paths.py                constants: where that copy lies, what comes
                                across, what stays, and the redirects it loads by
    import_lyra.py              entry point: Lyra's clips the game plays (the
                                punch) retargeted onto the player's UEFN skeleton
                                (tests: dev/tests/test_lyra_import.py)
    lyra_paths.py               constants: where the user's copy of Lyra lies, the
                                redirect it loads by, which of its clips are played
    bind_to_mannequin.py        entry point: bind cached bodies to the mannequin's
                                skeleton -> assets/cache/meshy/<id>/bound/
    mannequin_bind/             the bind itself (its __init__.py is its module
                                map; tests: dev/tests/test_mannequin_bind.py)

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
    mixamo_player.py            the player's melee set (PLAYER_CLIPS) onto SK_XBot and
                                from there onto the player's skeleton, in place
    import_mixamo_player.py     entry point: that step of import_mixamo.py alone
    import_quaternius.py        entry point: Quaternius zips -> UAL clips on the
                                adventurer, gun/survival props, the zombie
    quaternius_paths.py         constants: packs, asset paths, which clips/models play
    quaternius_import.py        unzip; import each GLB/FBX and rename it into its pack
    retarget_player_clips.py    entry point: the UAL clips onto the player's body
                                alone, from the packs as imported (the swap's step)
    ual_retarget.py             IK_UAL1/2, RTG_<Character>_from_UAL1/2, batch retarget
    patch_gas_notifies.py       entry point: empty the two GAS notifies only the
                                sample's Mover character answers, so they compile
    check_gas_load.py           entry point: load everything under /Game/GAS and
                                read the editor's log back for what was missing
    build_gas_bridge.py         entry point: the skeleton bridge from the GAS clips
                                to the MetaHuman, as far as one idle: a source IK
                                rig on SK_UEFN_Mannequin, its retargeter and anim
                                blueprint, and ABP_GasIdle
    gas_bridge_paths.py         constants: what the hidden mesh becomes, the idle,
                                and what that build writes
    gas_player_mesh.py          SKM_UEFN_Player: the hidden mesh the player wears on
                                the bridge, the sample's with the game's sockets
    gas_idle_abp.py             ABP_GasIdle: one sequence player on the UEFN skeleton
    metahuman_retarget.py       a retargeter between two rigs and the retargeting
                                anim blueprint pointed at it (the mannequin's
                                bridge, build_metahuman_retarget.py, and the UEFN's)
    measure_gas_bridge.py       entry point: what the UEFN mannequin lacks that the
                                game names on SK_Mannequin (Saved/gas_bridge.txt)
    import_bound.py             entry point: bound GLBs -> /Game/Sourced/Bound on
                                SK_Mannequin, and the checks only an editor can make
    retarget_ual_to_mannequin.py  entry point: the Quaternius clips onto SK_Mannequin,
                                once, for every bound body
    retarget_to_uefn.py         entry point: the game's own clips (the mannequin's
                                ready poses, punch and flinches, Quaternius's stances
                                and throw) onto SK_UEFN_Mannequin, for the weapon
                                layers over the motion matching
    plain_retarget.py           the retargeter between two rigs named the
                                mannequin's way: in place, aligned chain to chain
    bound_look.py               entry point (tooling): photograph the bound body,
                                the per-body one and Quinn in the same clip poses
    import_ui_art.py            entry point: HUD art PNGs -> textures
    fab_index.py                entry point: index Fab content -> assets/cache/fab/
    fab_inventory.py            describe a folder's assets from registry tags
"""
