# Generated bodies: making one, checking it, swapping it in

`__init__.py` is the module map. This note is the part that is easy to get wrong: a new
player body from a description, with no numbers of its own anywhere in the repo.

## A new body, start to finish

```bash
# 1. describe it: one MonsterSpec in catalog.py, compatible_with="adventurer_01"
# 2. generate (Meshy credits: preview 20, refine 10, remesh 5, rig 5 -- ask the user first)
python3 Scripts/asset_pipeline/fetch_monsters.py adventurer_03 --through preview   # look at the thumbnail
python3 Scripts/asset_pipeline/fetch_monsters.py adventurer_03                     # the rest, and the rig check
# 3. wear it: imports it, retargets, rebuilds, verifies (editor closed; about 5 minutes)
python3 Scripts/asset_pipeline/swap_player_body.py adventurer_03
```

`swap_player_body.py --plan <id>` prints the commands instead; `--check` runs the verifiers
alone. The setting it writes is `player_body.PLAYER_BODY`: **the one place that names the
player's body**. `combat/skin.py`, `quaternius_paths.UAL_CHARACTERS` and the checks in
`combat/verify/body_setting.py` all follow it. `CLOTHING_BASE_BODY`, beside it, names the
body the garments are drawn on.

## Why it is checked afterwards, not asked for

Meshy's rigger takes a mesh and a height and nothing else. Every rig comes back with the same
24 bone names and its own rest pose, and no prompt wording reaches the skeleton. So:

- **`rig_compat.py`** (host-side, no credits) reads the rest pose out of the cached GLB and
  compares it with the reference's, in a body frame built from the rig itself. Three
  verdicts: `compatible`, `normalise` (same bones, a pose or a proportion differs: the import
  absorbs it) and `fail` (a bone missing or re-parented, or proportions that are not the same
  kind of body: generate again). `fetch_monsters.py` runs it after the rig stage, keeps the
  verdict in `task.json` and exits non-zero on a fail; nothing is deleted.
  `rig_compat.py --table adventurer_01` prints every cached rig against one.
- **The tolerances are in one block** at the top of `rig_compat.py`, with the measured table
  they came from. Don't tune them to make a rig pass: `adventurer_02` (clavicles 39° off,
  arms 21-30°) is `normalise` and the wendigo is `fail`, and both are right.

## What the import normalises (nothing here names a character)

A body whose spec names `compatible_with` goes through the same importer as any other, plus:

| what differs on a generated body | what absorbs it |
|---|---|
| which bones got a physics body (the importer's choice: one body came with no `Head`) | `physics_template.py`: the reference's body set, every joint reseated on this rig's bones |
| capsule axes and sizes (they are the reference's in that copy) | `combat/capsule_fit.py`: refitted on the vertices' own axes, cut where a limb tapers |
| clavicles resting far off the source's (the shoulders set back) | `clavicle_align.py` in the retarget pose; `CLAVICLE_DIR` in the keyed poses (`combat/body_pose.py`, `hold_pose.py`) |
| the two hands' spacing in the two-handed ready poses | `two_hands.py`: the left wrist put back on the source's spacing |
| hand size against a handle | `combat/grip.py` `_eased`: the handle eased out of a joint that would stand in it |
| hand size and wrist place against the shotgun's pump | `combat/pump_seat.py`: the hand moved to where its own fingers close on the wood |
| where the crawl clip carries the hips | `combat/body_pose.crawl_hips_z`: measured off the body's own clip |

Each of these was a constant measured on `adventurer_01`, or an accident of its rig, until
`adventurer_02` was worn through them as a rehearsal. **If a new body fails a check, find what
is still measured on one body and make it measured on the worn one. Never loosen a verifier
bound and never add a number for one character.**

## Traps

- **A swap by hand needs `Content/Weapons/Anims/*.uasset` removed first** (the swap script
  does it). The weapons build keys those seven pose clips on the worn skeleton; one left on
  another body's is deleted through the editor, 3-4 minutes apiece, and a cold run dies at its
  15-minute limit half way through the build.
- **The entry points purge `asset_pipeline` from `sys.modules` as they load**, so one cannot
  import another: `import_body.py` loads its three steps with `runpy.run_path`.
- **A re-import drops the finger bones** `build_retarget.py` added, and a retarget regenerates
  clips the built Blueprints hold. `import_body.py` therefore touches only characters with no
  mesh yet; `main(only={...})` is the deliberate re-import.
- **Regenerating a spec** (a failed rig, or a changed prompt): move
  `assets/cache/meshy/<id>` aside first. `fetch_monsters.py` refuses a prompt that differs
  from the cached one, and with the same prompt it would resume the model already paid for.
- **Never cold-run while an editor is open**, including a warm `$UEPY_SERVE` one: close it
  (`uepy.py --close-editors`) before `swap_player_body.py`.

## Where this stands (2026-10-03)

- `adventurer_03` (the man in skin-tight shorts) is generated, imported and proven: worn, it
  passes every verifier and the slots, throw, clothing, stance, shotgun-hands, sight-hands,
  hold-pose and gait probes, with nothing in the repo tuned for it. It took two previews: the
  first, worded "boxer briefs", came back in loose boxing shorts
  (`assets/cache/meshy/_adventurer_03_attempt1`, preview only). 60 credits in all.
- **The player wears `adventurer_03`**, which is also the clothing base body
  (`CLOTHING_BASE_BODY`). Back to the dressed one is
  `swap_player_body.py adventurer_01`.
- Three more things turned out to be one body's accident, and are general now: which side of
  a flat open hand is the palm (`palm_twist.hand_frame`: the two hands vote together), a
  handle no easing fully fits (`grip._eased` goes as far as it may), and how the guard's lean
  is checked (off the chest's own turn, not where the neck ends up).

## Bound bodies: the mannequin's skeleton instead of the body's own

The long-term flow, built beside the one above and not yet switched on.
`mannequin_bind/__init__.py` says why and is the module map; this is how to run it.

```bash
python3 Scripts/asset_pipeline/bind_to_mannequin.py adventurer_03   # host-side, seconds, no editor
python3 Scripts/dev/uepy.py --cold Scripts/asset_pipeline/import_bound.py   # editor closed
# then: player_body.PLAYER_RIG = "mannequin", and the weapons build
```

The bind reads `assets/cache/meshy/<id>/rigged/*rigged_character*.glb` and the mannequin's
reference skeleton straight out of `SKM_Manny_Simple.uasset`, and writes
`assets/cache/meshy/<id>/bound/<id>_mannequin.glb` with a `bind_report.json`. `--check`
checks without writing; `--all` does every cached body (the wendigo is refused: not a man).

**Where it stands (2026-10-03).** Worn: `player_body.PLAYER_RIG = "mannequin"`, and the
player is `/Game/Sourced/Bound/SKM_Adventurer03` on the stock `ABP_Unarmed`.

```bash
python3 Scripts/asset_pipeline/bind_to_mannequin.py adventurer_03
rm Content/Weapons/Anims/*.uasset          # keyed on the skeleton worn before
python3 Scripts/dev/uepy.py --cold --summary Scripts/asset_pipeline/import_bound.py \
    Scripts/asset_pipeline/retarget_ual_to_mannequin.py Scripts/build_weapons_and_combat.py \
    Scripts/build_survival.py Scripts/build_graphics_menu.py Scripts/build_clothing.py
```

Back to the per-body skeleton: `PLAYER_RIG = "own"` and `swap_player_body.py adventurer_03`.

- Host half: tested (`dev/tests/test_mannequin_bind.py`); the Khronos glTF validator
  passes the bound files with no errors or warnings.
- Import: on `SK_Mannequin` itself, every reference rotation the mannequin's, the
  mannequin's physics asset copied beside the mesh (the importer's own had no head body).
- Clips: `retarget_ual_to_mannequin.py` puts the Quaternius library on the mannequin once
  (`/Game/Sourced/Quaternius/UAL/Mannequin`); `SKIN_BOUND` takes its crouch, crawl, kneel
  and throw from there. `bound_look.py` photographs the bound body, the per-body one and
  Quinn in the same poses into `Saved/Renders/bound_look/`.
- Builds pass; survival, menu, clothing and NPC verifiers pass; a 25 s headless game runs
  with no Blueprint errors. **`verify_weapons_and_combat.py` is 1788/1794.** The six:
  - four on the shotgun's hands (thumb over the stock's wrist, a finger 1.8 cm in the
    pump, one 2.9 cm off it against 2.5 allowed, the fist 1 cm from the stock): the pose
    is solved for the body and lands 1-2 cm off on this one;
  - the throw's ready pose 5 cm from the clip's own frame;
  - `calf_l`/`calf_r` of `A_AimShotgun` not the rifle pose's. Not understood yet.

Things the first runs found, all fixed: the importer names a mesh after its FILE; a pelvis
left on Meshy's high Hips joint floats the body in every clip (`mannequin_bind/fit.py`);
the mannequin's own clips key corrective bones its simple mesh does not have
(`combat/hold_pose.py`, `shotgun_pose.py` leave those tracks out).

Not done:

- **The probes** (`Scripts/probes`) pick the worn skin out of `(SKIN_ADVENTURER,
  SKIN_QUINN)` and have not been run on the bound body.
- **`adventurer_02` and `zombie_01` have fingers the bind cannot find**; they are weighted
  by the mannequin's layout and not curled, and the report says so.
- **Capsules** are the mannequin's, not refitted to this body's limbs.
- **Monsters** are still per-body (their Mixamo set would need one retarget onto the
  mannequin, as the Quaternius one got).
- **The per-body passes are not deleted**: `clavicle_align.py`, `palm_twist.py`,
  `two_hands.py`, `finger_rig.py` and the retargeted clip sets go when this flow has been
  played, not before.

One finding to carry back to the per-body flow: on all four cached bodies the palm side
`palm_twist.hand_frame` picks (the cloud's skew) is the BACK of the hand by the thumb's
side, which cannot be wrong (`mannequin_bind/hand_frame.py`). It is harmless there if the
mannequin's is signed the same way, and worth one look.

## Looking at a generated body

- **Don't judge a texture from a cold capture.** `Scripts/dev/render_character.py`, and the
  portrait before `item_icons/capture._full_textures`, photograph a body a moment after the
  editor starts, on its lowest mips: a Meshy atlas is hundreds of islands packed edge to edge,
  and at those mips every island wears its neighbour's colour (skin blotches on dark shorts).
  Look at it in a windowed game instead:
  `OW_HOT_SHOTS=1 python3 Scripts/dev/uepy.py --game --windowed --probe Scripts/probes/probe_hot_blade.py`
  saves front views to `Saved/Screenshots/MacEditor/`.
- The stage thumbnails Meshy returns are saved beside the model
  (`<id>_<stage>_thumbnail.png`): look at the preview's before paying for the rest.

## The MetaHuman: Epic's Taro drawn over the hidden mannequin (2026-10-07)

`player_body.PLAYER_RIG = "metahuman"`. The player's own mesh is still SK_Mannequin
(SKM_Manny_Simple, hidden) running `ABP_Unarmed` with every slot, pose and clip as before;
the MetaHuman body hangs under it and retargets its pose every frame. Nothing in the weapons
build is keyed on the MetaHuman; `metahuman_paths.py` is the one place that names it.

```bash
python3 Scripts/asset_pipeline/import_metahuman.py            # host-side: Taro + his Common, 1.1 GB
python3 Scripts/dev/uepy.py --cold Scripts/asset_pipeline/build_metahuman_retarget.py
python3 Scripts/dev/uepy.py --cold Scripts/build_weapons_and_combat.py      # wears it
python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_metahuman_body.py
python3 Scripts/dev/uepy.py --game --windowed --probe Scripts/probes/probe_metahuman_look.py  # pictures
```

- **The source is the sample project** (`~/Documents/Unreal Projects/MetaHumans 5.8`), which
  mounts at the same `/Game/MetaHumans/...` paths: a file copy is the editor's Migrate.
  `metahuman_manifest.txt` is BP_Taro's dependency closure (441 packages); `--manifest`
  recomputes it on the sample. Plugins it needs are in the .uproject: RigLogic, HairStrands,
  AlembicHairImporter, MetaHumanRuntime, LiveLink (Face_AnimBP has Live Link nodes).
- **The bridge is an IK retargeter, not Copy Pose**: `IK_MetaHuman` is the mannequin's chain
  table on `metahuman_base_skel` (same core bone names), `RTG_MetaHuman_from_Mannequin` maps
  them exactly with no pose alignment (both A-pose), and `ABP_MetaHuman_Retarget` is the
  sample's own retargeting anim BP duplicated and pointed at it (one Retarget Pose From Mesh
  node reading the parent component). The sample's `RTG_MetaHuman_m_med_nrw` is
  MetaHuman-to-MetaHuman and is not the bridge.
- **The component tree is BP_Taro's** (`combat/metahuman_body.py`): Body under Mesh; Face,
  Torso, Legs, Feet under Body; six grooms under Face; a MetaHumanComponentUE (finds Body and
  Face by name, gives the jeans a leader pose and the hoodie and shoes their post-process
  copy-pose anim BPs) and a LODSync. The garments tick only when rendered (the component sets
  that at BeginPlay); a headless probe must set ALWAYS_TICK on them before measuring.
- **Five skeletal meshes now, not in tree order**: anything that wants "the player's mesh"
  takes the component named `Mesh` (`skin.mannequin_component`, `verify.common._mesh_asset`),
  never the first SkeletalMeshComponent. Per-view hides (OwnerNoSee behind a scope, the head
  down the sights, both back on death) reach the parts through
  `weapon_component/body_parts.py`: a loop over OwnerMesh's children.
- Measured (probe_metahuman_body): the MetaHuman's head, hands and feet land within 7 cm of
  the mannequin's standing, falling and dead; the face and garments within 0 cm of the body.

## The Game Animation Sample: the motion-matching set, copied (2026-10-08)

Epic's Game Animation Sample ("GAS" here; nothing to do with the Gameplay Ability System) is
in the project under `/Game/GAS`: **2723 packages, 2.7 GB** (the MetaHuman's 441 and 1.1 GB
beside it), not committed (`.gitignore`). Since G3 the player's base movement is its anim
blueprint and databases (`Scripts/combat/CLAUDE.md`, "The motion-matching base").

```bash
python3 Scripts/asset_pipeline/import_gas.py                 # host-side copy; --check, --manifest
python3 Scripts/dev/uepy.py Scripts/asset_pipeline/patch_gas_notifies.py
python3 Scripts/dev/uepy.py Scripts/asset_pipeline/check_gas_load.py   # in a fresh editor
```

- **What came across** (`gas_paths.py`, `gas_manifest.txt`): the UEFN mannequin's meshes,
  rigs and every clip (2355 packages under `Characters/UEFN_Mannequin`: 155 PoseSearch
  databases, their schemas, and the `CHT_PoseSearchDatabases`, `_Dense`, `_Sparse` and
  `_ExtremeSparse` choosers), `SandboxCharacter_CMC_ABP` and what it reaches
  (`BPI_SandboxCharacter_ABP`/`_Pawn`, `Blueprints/Data`, the notifies, two anim modifiers,
  the foley sounds and their submixes, the curve compression settings), and two components
  the anim blueprint does not reach but the wiring will: `AC_PostABPTick` and
  `AC_TraversalLogic` (with `LevelBlock_Traversable`, the block it looks for).
- **What stayed** (`gas_paths.EXCLUDED`): the Mover variant and its three choosers, the smart
  objects, the isolated examples, the other characters. Also `SandboxCharacter_CMC` itself,
  and so `AC_PreCMCTick` and `AC_VisualOverrideManager`, which cast to it or to `GM_Sandbox`
  and would bring the sample's cameras, game mode and `/Game/Input`.
  `gas_manifest_cut.txt` lists each reference into the excluded set that was cut.
- **It lies one folder down, and loads through redirects.** The sample mounts its content at
  `/Game/Characters`, `/Game/Blueprints`, `/Game/Audio`; a copy to the same paths would land
  in the game's own `Content/Audio`. So `/Game/<Folder>` there is `/Game/GAS/<Folder>` here
  (`gas_paths.gas()`), the files are still byte copies that name each other by the sample's
  paths, and `[CoreRedirects]` in `Config/DefaultEngine.ini` points those names here
  (`gas_paths.REDIRECTED`; one line per folder, and never a folder the game keeps content
  in: `dev/tests/test_gas_import.py`). **Name a GAS asset by its `/Game/GAS` path.** A
  package saved in this project is written with the new paths. The asset registry applies
  the redirects too: a copied package's dependencies read back as `/Game/GAS` names.
- **Three packages are changed after the copy** (`gas_paths.PATCHED`; the copy keeps a
  patched file). `SandboxCharacter_CMC_ABP` is the weapons build's to patch
  (`combat/gas_locomotion.py`: what it reads of its character, its montage slot, the
  server branch), where it lies, because the sample's choosers take an object of its
  class and of no other. The other two are `patch_gas_notifies.py`'s
  (`gas_paths.PATCHED_NOTIFIES`): `BP_AnimNotify_TriggerRagdoll` and
  `BP_NotifyState_OverrideMovementMode` cast to the Mover character and do nothing for any
  other, so without it they fail to compile on every load of a clip that carries one. Their
  graphs are removed; the class and its variables stay. The copy keeps a patched file.
- **Plugins** it needs, now in the .uproject: PoseSearch, Chooser, AnimationWarping,
  MotionWarping, AnimationLocomotionLibrary, AnimationLayering, and four the first load
  asked for by name: DrawDebugLibrary (`BFL_HelpfulFunctions`), CurveExpression and
  MovieSceneAnimMixer (the anim blueprint's nodes), and Mover (the anim blueprint imports
  `/Script/Mover` though the Mover variant is not here; it enables NetworkPrediction).
- **Settings carried from the sample's config:** its `Foley.*` and `MotionMatching.*`
  gameplay tags (`Config/Tags/GAS.ini`; without them the first load logged 3,300 invalid-tag warnings as the clips
  load), the 13 `DDCvar.*` console variables its blueprints read by name, the PoseSearch
  buffer size, and its three collision channels in the sample's slots (the traversal trace is
  stored as `ECC_GameTraceChannel1`; all three ignore everything by default). Not carried:
  the sample's change to the `Ragdoll` profile.
- **A missing package is a log line, not a Python error.** `check_gas_load.py` loads all
  2723 and reads the editor's log back between two markers; `Saved/gas_load.txt` is the
  report. Clean today but for one of the sample's own montage warnings
  (`M_LookAtPOI_test_patrol_walk_01`).
- **The game-wide Blueprint scans leave `/Game/GAS` out**, as they do `/Game/Fab` and
  `/Game/Sourced` (`net/state_checks.EXCLUDED`, `dev/graph_fingerprint.py`): it is content
  nobody here authors. What they found in it the day it arrived is what the wiring has to
  face when one of these goes onto the player:
  - `AC_TraversalLogic` has a Server event of its own, `PerformTraversalAction_Server`, that
    asks no RPC guard (`combat/verify/guard.py` allows Server events on the weapon component
    alone);
  - `SandboxCharacter_CMC_ABP`'s `Debug_ExperimentalStateMachine` asks for a player by index
    (`net/input_checks.py`);
  - `LevelBlock` draws a random number no row of `net/random_consts.py` covers.

## The skeleton bridge: how the GAS clips reach the MetaHuman (2026-10-08)

The sample's clips, databases and anim blueprint are on `SK_UEFN_Mannequin`; the player's
hidden mesh is `SK_Mannequin`. **The choice: the hidden mesh becomes `SKM_UEFN_Mannequin`**
(bridge (a)), and the MetaHuman follows it through a second retargeter whose source rig is on
that skeleton. The sample then plays as it shipped: nothing of its 2355 packages is
retargeted, copied or re-pointed. Proven on one idle (G2), and **worn by the game since
G3**: `combat/skin.SKIN_GAS`, on `SKM_UEFN_Player`, a copy of the sample's mesh with the
game's sockets.

```bash
python3 Scripts/dev/uepy.py Scripts/asset_pipeline/build_gas_bridge.py
python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_gas_idle.py
python3 Scripts/dev/uepy.py Scripts/asset_pipeline/measure_gas_bridge.py   # Saved/gas_bridge.txt
```

- **What is built** (`gas_bridge_paths.py`, under `/Game/Sourced/MetaHuman`, beside the
  mannequin's bridge and touching none of it): `IK_UEFN_Mannequin_Source` (the mannequin's
  chain table, `rig_chains.CHAINS_MANNEQUIN`, on the UEFN mesh: every chain bone has the
  same name there, so the map onto `IK_MetaHuman` is exact), `RTG_MetaHuman_from_UEFN`,
  `ABP_MetaHuman_Retarget_UEFN` (what the Body component wears over a UEFN parent) and
  `ABP_GasIdle` (one sequence player of `M_Neutral_Stand_Idle_Loop`; the sample has no
  `M_Neutral_Idle_Loop`), and `SKM_UEFN_Player` (`gas_player_mesh.py`): the sample's mesh
  copied, on the same skeleton, with `HandGrip_R`, `HandGrip_L`, `weapon_r_muzzle` and
  `foot_l/r_Socket` added as the mannequin has them (same bone, same offset in that bone's
  space). The sample's own mesh stays a byte copy.
  - **A socket can be made from Python after all**: `SkeletalMeshSocket(outer=mesh)`,
    `mesh.add_socket(socket, False)`, then `mesh.rename_socket("Socket", name)` (a new
    one is named `Socket`; `SocketName` and `BoneName` are read-only as properties) and
    `socket.set_socket_parent(mesh, bone)`. It is a mesh socket, not the skeleton's.
- **The proof is a probe that wears it for one run**: `probe_gas_idle.py` puts the UEFN
  mesh and `ABP_GasIdle` on the live player's Mesh component and the UEFN retarget blueprint
  on Body, checks them, and puts the mannequin back. Measured: the hidden mesh's pose is
  0.06 cm from a frame of the clip; the MetaHuman follows within 4.1 cm (head 4.1, hands
  3.7, feet 2.5, fingertips 5.7), against 6.6 cm on the mannequin, by the same measure and
  the same 12 cm tolerance as `probe_metahuman_body` (`probes/metahuman_follow.py`).
- **This retargeter aligns its retarget pose; the mannequin's does not.** The UEFN
  mannequin rests with its arms at another angle (its hand is 20.7° and 12.5 cm from
  Manny's in the reference pose). Unaligned, the MetaHuman's hands hung 11.5 cm off the
  idle's; with `auto_align_all_bones(TARGET, CHAIN_TO_CHAIN)` they are 3.7 cm
  (`metahuman_retarget.build_retargeter(align=True)`). The fingers were measured at their
  tips, not looked at: a windowed look is owed when the game wears this.
- **A sequence player's clip is not a Python property.** `ABP_GasIdle`'s node comes from the
  palette entry `Animation|Sequences|Play'<clip name>'`, which exists only while the clip is
  loaded; the clip is read back out of the node's `export_text()` (`gas_idle_abp.playing`).
  A running anim instance does not say what it plays either, so the probe reads the graph
  and then proves the pose against the clip's frames.

What bridge (a) costs, measured (`measure_gas_bridge.py`), for the task that makes the game
wear it:

- **Bones: nothing the game names is missing.** The UEFN skeleton has 93 bones to the
  mannequin's 89 and lacks only `center_of_mass`, `interaction` and `thigh_twist_02_l/r`,
  none of which a script names. Every bone `combat/` sets by name (`hand_r`, `head`,
  `spine_01/03/05`, `pelvis`, `neck_01`, the arms, the legs) is there, as is every retarget
  chain end. It adds `weapon_l/r`, `attach`, `prop_01` and `props_root`.
- **Sockets: every one the game uses is missing.** The mannequin has `HandGrip_R`,
  `HandGrip_L`, `weapon_r_muzzle`, `foot_l/r_Socket`; the UEFN has `palm_l/r_Socket`,
  `RagdollTrace`, `prop_01_Socket`. `HandGrip_R` (`skin.grip`, where every held item
  attaches; in the probe's run the held gun has no socket to hold to) has to be added to a
  skeleton that is an uncommitted byte copy, so by a patch script and a row in
  `gas_paths.PATCHED`, as the two notifies are; `grip._BoneGrip` is the fallback that
  needs no socket. The hand's rest rotation differs by 20.7°, so the socket's offset is
  measured again, not copied.
  **G3 did otherwise, and cheaper:** the sockets are on a copy of the mesh
  (`SKM_UEFN_Player`, above), not on the skeleton, and are the mannequin's offsets
  copied: a socket's offset is in its bone's own space, which the rest pose does not
  move. What is not re-measured is the smaller hand. G4 put a gun back into an aimed
  hand and looked: the grips solve against the retargeted ready poses as they did against
  the mannequin's (`combat/verify/grip_fit.py` is green), and only the shotgun's grip
  thumb needed laying again for this hand (`combat/shotgun_pose.SHOTGUN_THUMBS`).
- **Every clip the player has today stops playing** (as reasoned in G2; in G3 the worn
  graph's one montage slot is out of the pose line, so whether a mannequin clip would
  play on the UEFN mesh by bone name was not put to the test). Neither skeleton lists the other as
  compatible, so `ABP_Unarmed` and what it plays (41 clips and a blend space on
  `SK_Mannequin` reached from the player's blueprint, the Quaternius library retargeted
  onto the mannequin, the seven poses the weapons build keys on the worn skeleton) do not
  run on the UEFN mesh. The weapon layers, the stances, the throw and the hit reactions
  each need retargeting onto `SK_UEFN_Mannequin` (the rig built here is a ready target:
  same chain table) or a compatible-skeleton declaration, which was not tried.
  **G4 retargeted them** (`retarget_to_uefn.py`, after `build_gas_bridge.py`): the
  mannequin's two ready poses, punch and six flinches, read off `SKM_Manny_Simple`
  through `RTG_UEFN_from_Mannequin`, into `/Game/Sourced/Characters/Anims/UEFN_Player`,
  and Quaternius's crouch, crawl, kneel and throw, read off the packs' own rigs (one
  retarget, not two), into `/Game/Sourced/Quaternius/UAL/UEFN_Player`. The target rig is
  `IK_UEFN_Mannequin_Source`; the retargeter is the plain one (`plain_retarget.py`: in
  place, the target's pose aligned chain to chain) and every copy has its root motion
  flag off. `combat/skin.SKIN_GAS` names them. A compatible-skeleton declaration was not
  tried: the two rest 20.7° apart at the hand.
- **Ragdoll and hit bodies: another physics asset, same body names.** `PA_UEFN_Mannequin`
  has the mannequin's 22 bodies plus `spine_01`, so `HeadBones`/`LimbBones` and the bone a
  thrown blade lodges in carry over by name; the capsules are the sample's, fitted to a
  body 10 cm shorter at the head (152 against 162.6 cm) and never run through
  `combat/hit_bodies.fit_hit_bodies`. The sample's change to the `Ragdoll` collision
  profile was not carried (G1).
- **Whatever matches the worn mesh by path.** `skin.SKINS` / `skin_of_mesh` and the
  verifiers that read `SKIN_METAHUMAN.mesh` know `SKM_Manny_Simple`; a UEFN skin is a new
  row, and `combat/server_pose.py` poses "the mesh the game runs on", which this becomes.

What bridge (b) would have cost (the hidden mesh stays `SK_Mannequin`, the databases are
retargeted to it): not tried, since (a) held. It keeps every item above as it is, and pays
on the other side: the clips behind 155 databases retargeted onto a body 10 cm taller with
its arms at another rest angle, on disk; the databases, their schemas (which name the
skeleton) and the four choosers duplicated and re-pointed; `SandboxCharacter_CMC_ABP`
copied onto the other skeleton; and all of it redone whenever the sample is re-imported.
The motion-matching features (foot positions, trajectories) would be searched on retargeted
poses, which is where a retarget shows first. It is the fallback if the weapon layers
cannot be brought onto the UEFN skeleton.
