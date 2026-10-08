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
