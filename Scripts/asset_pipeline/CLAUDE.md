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
