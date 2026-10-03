# Combat: the player's body

Part of `Scripts/combat/CLAUDE.md`, which indexes it.

## The player's body (`skin.py`)

- **Which body the player wears is one setting:** `asset_pipeline/player_body.py`
  `PLAYER_BODY`, a catalog id (`adventurer_01` today: `SKM_Adventurer01`, animated by
  `A_Adventurer01_ABP_Unarmed`, which is `ABP_Unarmed` retargeted by
  `asset_pipeline/build_retarget.py`). Every path in `SKIN_ADVENTURER` follows it, and
  `verify/body_setting.py` checks that. To change it:
  `python3 Scripts/asset_pipeline/swap_player_body.py <id>` (`Scripts/asset_pipeline/CLAUDE.md`).
- **Nothing here may be measured on one body.** A generated body swaps in because the poses,
  grips and hit bodies are solved against whatever is worn; a constant read off the dressed
  adventurer is what broke the first swap.
- **`PlayerSkin` is one record:** mesh, anim BP, grip, poses and offsets.
  - `player_skin()` picks the adventurer only if **all** its assets exist (mesh, anim BP, both
    ready poses and the punch clip), and otherwise falls
    back to `SKIN_QUINN`.
  - A partial skin compiles, then stands in its bind pose.
- **The animation moved to the mesh, not the mesh to `SK_Mannequin`:**
  - Meshy returns its own 24-bone Mixamo-named rig, with no fingers and no twist bones.
    `asset_pipeline/finger_rig.py` adds 15 finger bones per hand and skins them (mannequin
    layout and weights carried into the measured hand frame), so the retargeted clips curl the
    fingers.
  - FBX import merges bone trees.
  - 5.8 exposes no skin transfer to Python.
- **Everything else is rig-agnostic:**
  - hit zones and the ragdoll read whatever mesh is worn;
  - `fix_retargeted_abp()` re-points `spine_01` to `Spine02`.
- **The grip is a bone (`RightHand`), not a socket**, because Python can't create a socket.
  `_BoneGrip` stands in for one.
  - The weapon is attached at the wrist, then moved into the fist by `GripLocation`.
  - The fingers close the way the mannequin's do in the retargeted ready pose.
    `finger_verify.py` checks each finger's curl against the mannequin's.
- **The two ready poses and the six hit reactions are retargeted onto every creature**
  (`AIM_SOURCES`, `HIT_SOURCES`), because they are played by path and no dependency walk
  finds them.
- **Build order from nothing:** `import_quaternius` (the gun models) → weapons (mannequin
  fallback) → `fetch_monsters` → `import_characters` → `build_creature_materials` →
  `build_retarget` → `import_quaternius` again (the crouch and crawl clips need the adventurer's
  IK rig) → `build_npc_blueprints` → weapons again.
  - Rerunning `import_quaternius` regenerates the clips the anim BP plays, so the weapons build
    must follow it. The build strips the old stance blends first (`unpatch_stance_clips`):
    with their clips regenerated they play nothing, and the anim BP would not compile.
  - `build_retarget` deletes and rebuilds `Anims/<Creature>/` every run, so
    `build_npc_blueprints` must follow it. Otherwise four checks fail in the *level* verifier.
- **Looking at a character:** `Scripts/dev/render_character.py` renders every character mesh to
  `Saved/Renders/`.
  - **To see a pose on it,** call `override_animation_data(anim, True, True, 0, 1)` on a
    `SkeletalMeshActor` already set to single-node with `play_animation`, set
    `visibility_based_anim_tick_option` to `ALWAYS_TICK_POSE_AND_REFRESH_BONES`, and capture in
    a **later** `uepy` job. Nothing poses in the job that spawns the actor. A scene capture is
    not "rendered", so the default option never evaluates the pose.
  - The world context is **not** optional on `create_render_target2d`/`export_render_target`.
  - Use `show_only_actor_components()`.
