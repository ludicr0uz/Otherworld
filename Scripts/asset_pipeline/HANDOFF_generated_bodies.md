# Generated player bodies: what was built, where it stands, how to resume

Written 2026-10-03. Branch `night-mode`, HEAD `a8657c0`, about 110 commits ahead of origin,
nothing pushed. The short working guide is `Scripts/asset_pipeline/CLAUDE.md`; this file is
the history and the troubleshooting detail behind it.

## 1. The goal and the outcome

**Goal:** write a description, get a humanoid body from Meshy that replaces the player's body
by changing one setting, with no per-character hand-tuning, for any number of future bodies.

**Outcome:**

- The pipeline exists and is proven on two bodies that were not compatible as generated
  (`adventurer_02`, `adventurer_03`).
- **The player currently wears `adventurer_03`** (the man in skin-tight dark shorts). It is
  also the clothing base body.
- A swap takes about 4 minutes 20 seconds. It is a rebuild, not an instant mesh change
  (section 8 says why, and what would make it instant).

Current settings, in `Scripts/asset_pipeline/player_body.py`:

```python
PLAYER_BODY = "adventurer_03"
CLOTHING_BASE_BODY = "adventurer_03"
```

Last verified state with `adventurer_03` worn:

| suite | result |
|---|---|
| verify_weapons_and_combat | 1768/1768 |
| verify_survival | 129/129 |
| verify_graphics_menu | 405/405 |
| verify_clothing | 100/100 |
| verify_npc_blueprints | 417/417 |

Probes passed on `adventurer_03` (each run alone, see section 7): slots, throw, clothing,
stance_clips, shotgun_hands, sight_hands, hold_poses, player_gait, hot_blade (windowed),
inventory_window (windowed). With `adventurer_01` worn the weapons suite reads 1766/1766
(two checks exist only for a body that names `compatible_with`).

## 2. Commands

All from the project root. **Close the Unreal editor first** for anything that runs cold.

```bash
# Put the player in a body (writes the setting, imports if needed, retargets, rebuilds,
# re-renders the portrait, verifies). About 4-5 minutes.
python3 Scripts/asset_pipeline/swap_player_body.py adventurer_03
python3 Scripts/asset_pipeline/swap_player_body.py adventurer_01      # back to the dressed body
python3 Scripts/asset_pipeline/swap_player_body.py --plan <id>        # print the steps only
python3 Scripts/asset_pipeline/swap_player_body.py --check            # verifiers only

# Generate a new body (Meshy credits: preview 20, refine 10, remesh 5, rig 5)
#   1. add a MonsterSpec to Scripts/asset_pipeline/catalog.py with compatible_with="adventurer_01"
python3 Scripts/asset_pipeline/fetch_monsters.py <id> --through preview   # 20 credits, then LOOK
#   2. view assets/cache/meshy/<id>/<id>_preview_thumbnail.png
python3 Scripts/asset_pipeline/fetch_monsters.py <id>                     # the rest + rig check
python3 Scripts/asset_pipeline/swap_player_body.py <id>

# Free checks
python3 Scripts/asset_pipeline/fetch_monsters.py --status                 # stages, credits, verdicts
python3 Scripts/asset_pipeline/fetch_monsters.py --gate                   # re-run rig check offline
python3 Scripts/asset_pipeline/rig_compat.py <id> [<reference id>]        # per-segment report
python3 Scripts/asset_pipeline/rig_compat.py --table adventurer_01        # every cached rig
python3 -m unittest discover -s Scripts/dev/tests                         # 213+ host tests

# Look at the worn body in a real game (the only trustworthy picture, see 6.9)
OW_HOT_SHOTS=1 python3 Scripts/dev/uepy.py --game --windowed --probe Scripts/probes/probe_hot_blade.py
python3 Scripts/dev/uepy.py --game --windowed --probe Scripts/probes/probe_inventory_window.py
#   -> Saved/Screenshots/MacEditor/ScreenShot*.png
```

## 3. Why it is built this way

- **Meshy's rigger cannot be steered.** It takes a mesh and a height and returns its own
  24-bone Mixamo-named rig. Bone names and hierarchy are the same every time; rest pose,
  bone orientations, proportions and hand size are different every time. No prompt wording
  reaches the skeleton. An earlier attempt to fix compatibility by rewording prompts was
  reverted (`a137bfd`): it did nothing to the rig and tripped the fetcher's
  prompt-changed guard for the cached characters.
- **So compatibility is checked after generation and absorbed at import**, never asked for.
- **Each body is on its own skeleton** (`SK_Adventurer03`), with the mannequin's animation
  retargeted onto it. Sharing one skeleton between Meshy bodies was tried early in the
  project and fails: rest-pose bone orientations differ, so one body wears another's neck.
- **"Compatible" means "goes through the pipeline with no numbers of its own"**, not
  "shares a skeleton". That is why a swap is a rebuild.

## 4. The pieces (commits, files)

| commit | what |
|---|---|
| `6d70aa1` | Rig compatibility gate |
| `e58320d` | One setting for the player's body; the swap script |
| `e4fd913` | Import-time normalisation (the bulk of the work) |
| `e7d690f` | Docs |
| `fa7d5b8` | `adventurer_03` generated and proven; four more general fixes |
| `a8657c0` | Player switched to `adventurer_03`; swap sped up from ~12 to ~4 minutes |

(`b71d2b0`..`4899776` in between are five unrelated dev-team tasks from the same night:
wind, menu naming, default jog, I-panel portrait, clothing icons.)

### 4.1 Gate (host-side, no editor, no credits)

- `catalog.py`: `MonsterSpec.compatible_with` = the spec id of the body this one must replace.
- `rig_compat.py`: reads the rest pose from the cached rigged GLB's JSON chunk, builds a body
  frame from the rig itself (up = hips to head, left = right thigh to left thigh), and per
  segment compares direction (degrees) and length (ratio after normalising stature).
  Verdicts: `compatible`, `normalise`, `fail`. Tolerances are one block at the top of the
  file. Tests: `Scripts/dev/tests/test_rig_compat.py`.
- `fetch_monsters.py`: runs the gate after the rig stage, records it in
  `assets/cache/meshy/<id>/task.json` under `rig_compat`, exits non-zero on `fail`, deletes
  nothing. `--through <stage>` stops after a stage; `--gate` re-checks offline; each stage's
  thumbnail is saved as `<id>_<stage>_thumbnail.png`.
- `import_characters.py` refuses a spec whose recorded verdict is `fail`.

Measured table (worst segment per group against `adventurer_01`: angle in degrees / length ratio):

| rig | arms | clavicles | legs | spine | verdict |
|---|---|---|---|---|---|
| adventurer_01 | 0.0 / 1.00 | 0.0 / 1.00 | 0.0 / 1.00 | 0.0 / 1.00 | compatible |
| adventurer_02 | 24.6 / 0.83 | 39.4 / 1.48 | 4.3 / 1.19 | 6.4 / 1.58 | normalise |
| adventurer_03 | 11.1 / 0.83 | 24.7 / 1.27 | 6.6 / 1.18 | 22.5 / 1.50 | normalise |
| zombie_01 | 35.6 / 1.05 | 2.9 / 0.98 | 10.9 / 1.18 | 1.0 / 0.83 | normalise |
| wendigo_01 | 55.7 / 1.56 | 22.3 / 1.20 | 57.6 / 1.48 | 49.9 / 4.55 | fail |

Tolerances: `normalise` past 10 degrees or 10% length. `fail` past 60 degrees (arms,
clavicles), 20 (legs), 30 (spine), or length off by 25% (arms), 30% (legs), 80% (clavicles,
spine). Note `adventurer_03`'s spine angle (22.5) is the closest anything has come to a fail
line; a future body past 30 there would be rejected and may deserve a look at whether the
spine line is too tight.

### 4.2 Normalisation (what absorbs each difference; nothing names a character)

| what differs on a generated body | what absorbs it | file |
|---|---|---|
| which bones got a physics body (the importer's choice; `adventurer_02` came with no `Head` or `Spine01` body) | the reference's physics asset is copied; every joint is reseated on this rig's bones (they were up to 24 cm off in a plain copy) | `asset_pipeline/physics_template.py`, called from `import_characters.py` |
| capsule axes and sizes | refitted on the vertices' own principal axes; a body is cut into 2-4 capsules where that covers 5% less silhouette (`SPLIT_GAIN`) | `combat/capsule_fit.py` (pure, tested), `combat/hit_bodies.py` |
| clavicles resting far off the source's | turned onto the source's line in the retarget pose when more than 30 degrees off | `asset_pipeline/clavicle_align.py` (called in `retarget_rig.build_retargeter`) |
| the same, in the procedurally keyed poses | the guard and hold poses start from the clavicle, set straight out to the side (`CLAVICLE_DIR`) | `combat/body_pose.py`, `combat/hold_pose.py` |
| hand spacing in the two-handed ready poses | left wrist put back on the source's spacing by a two-bone reach when more than 3 cm off | `asset_pipeline/two_hands.py` (called in `build_retarget.py`) |
| hand size against a handle | the handle is eased out of a finger joint that would stand in it, up to 0.4 cm, as far as helps | `combat/grip.py` `_eased` |
| hand size and wrist place against the shotgun's pump | the shaped left hand is moved to where its own finger joints ride 0.75 cm off the wood; the left arm is turned to carry it | `combat/pump_seat.py` (pure, tested), `combat/shotgun_pose.py` |
| where the left hand is held down the sights | each gun carries its own `SupportPoint` (read off its own ready pose); the old `SupportRifle` flag and its two fixed points are gone | `combat/support_hand.py`, `combat/weapon_component/support_hand.py`, `pose_weights.py`, `weapon_items.py`, `weapon_specs.py` |
| where the crawl clip carries the hips | measured off the worn body's own clip | `combat/body_pose.crawl_hips_z` |
| which side of a flat open hand is the palm | the two hands vote together (mirror images) | `asset_pipeline/palm_twist.hand_frame` |

### 4.3 One setting, and the swap

- `asset_pipeline/player_body.py`: `PLAYER_BODY`, `CLOTHING_BASE_BODY`, `name_of()`,
  `reference_of()`.
- Derived from it: `combat/skin.py` (`ADVENTURER`, `SKIN_ADVENTURER`),
  `quaternius_paths.UAL_CHARACTERS`, `clothing/specs.py` (`BASE_BODY_*`),
  `item_icons/portrait.py`.
- `combat/verify/body_setting.py` checks that all of those agree, that the player wears the
  named body and not the mannequin fallback, and that a body with a reference has a physics
  body on every bone the reference has.
- `swap_player_body.py` steps: write the setting; delete `Content/Weapons/Anims/*.uasset`;
  one cold editor running `import_body.py`, `retarget_player_clips.py`, then the weapons,
  survival, menu and clothing builds; `build_item_icons.py Character` (portrait); verifiers
  in a fresh editor.
- `import_body.py`: imports only catalog characters that are cached but have no mesh in
  `Content/` yet (import, materials, retarget). `main(only={...})` forces a re-import.
- `retarget_player_clips.py`: retargets the 86 Quaternius clips onto the player's body from
  the packs already imported (17 s). Falls back to the whole `import_quaternius.py` (6 min)
  if a pack is missing.

## 5. History of the three bodies

- **adventurer_01**: the original dressed adventurer. The reference. Everything was once
  measured on it, which is what made every other body fail.
- **adventurer_02**: man in loose boxers, generated before this work. Not compatible as
  generated (clavicles 39 degrees back, shoulders 13 cm behind the spine, shorter upper
  arms, no head physics body). An earlier session tried to swap it in by re-tuning constants
  and loosening the hit-capsule bound; that was interrupted and stashed (`stash@{0}`, still
  there, never popped). It was then used as free test data: worn through the new path it
  passed 1747/1747. Never meant to be used. It still has `compatible_with="adventurer_01"`.
- **adventurer_03**: the first body generated through the pipeline. 60 Meshy credits:
  - attempt 1 (20 credits, preview only): prompt said "tight-fitting boxer briefs" and came
    back in loose boxing shorts with arms raised level. Kept at
    `assets/cache/meshy/_adventurer_03_attempt1`.
  - attempt 2 (40 credits): prompt says "skin-tight compression shorts" and spells the pose
    out ("arms lowered 45 degrees from the body and palms facing down, feet parallel").
    Came back right. Gate verdict `normalise`.
  - Lesson: avoid the word "boxer"; say the pose in words as well as `pose_mode`.

Clip-normalisation numbers logged at build time, for reference:

| | adventurer_01 | adventurer_02 | adventurer_03 |
|---|---|---|---|
| clavicle turned in retarget pose | none | 40.0 / 39.1 deg | none (24 deg, under the 30 line) |
| left hand off source spacing, rifle / pistol pose | under 3 cm (left alone) | 12.5 / 16.9 cm | 5.0 / 11.3 cm |
| shotgun support hand moved onto the pump | 0.2 cm | 3.5 cm | 3.9 cm |
| hit bodies: overhang / uncovered (limits 0.20 / 0.06) | 0.13 / 0.03 | 0.17 / 0.05 | 0.15 / 0.04 |
| palm roll corrected in retarget | about 90 deg | 90 deg | 148 deg (palms-up bind pose) |

## 6. Troubleshooting: every failure met, its cause, its fix

1. **Weapons build takes 25 minutes, or a cold run dies at 900 s mid-build.** The seven pose
   clips in `Content/Weapons/Anims` are keyed on the previous body's skeleton. The build
   deletes each through the editor (`hold_pose._copy_of`), 3-4 minutes apiece. Fix: delete
   `Content/Weapons/Anims/*.uasset` with the editor closed (the swap script does it). They
   are regenerated by the build.
2. **Editor segfaults in `UBlueprintGraphEditor::AddCallFunctionNode`.** Running
   `build_weapons_and_combat.py` twice in one editor process. Use a fresh editor per weapons
   build (`uepy.py --cold`).
3. **`KeyError: 'asset_pipeline.build_retarget'`** when importing one pipeline entry point
   from another. Each purges `asset_pipeline` from `sys.modules` as it loads. Load siblings
   with `runpy.run_path(path, run_name="something")["main"]`, as `import_body.py` does.
4. **`print()` output missing from a cold run.** Only `unreal.log_warning` is captured cold.
5. **Hit-capsule overhang check fails on a bare body (0.28 vs 0.20).** Was: one capsule per
   bone, on axes copied from another body's bone frames. Fixed by `capsule_fit.py`. If a
   future body fails it, look at `SPLIT_GAIN`/`SPLIT_DEPTH` and the per-body ray counts, not
   at the bound. Never raise `COVERAGE_MAX_OVERHANG`.
6. **`RuntimeError: <Body>: N finger problems` ("moves only 0 vertices") in
   `build_retarget`.** The hand frame picked the wrong palm side on a flat open hand (skew
   along the flat axis near zero: -0.03 on `adventurer_03`'s left, where a curled hand reads
   0.2-0.5). Fixed by the two-hand vote in `palm_twist.hand_frame`. If it recurs, both
   hands are probably flat: compare the `p` vectors of the two hands (they must mirror in x)
   and the per-finger vertex counts.
7. **"Stick: no finger passes through the Grip" / wood "sink no more than 1.8 cm".** Small
   hand, thick handle. Fixed by `grip._eased` (best effort up to 0.4 cm). If a still smaller
   hand fails, the honest fix is opening the fingers per handle thickness, not the bound.
8. **Shotgun: left hand in the wood or off it, at the hip or down the sights.** At the hip
   it is the pose (`pump_seat.py`). Down the sights it is the support-hand IK target, which
   must be the shotgun's own `SupportPoint`; `verify/support_hand.py` re-measures each gun's.
9. **A body looks blotched or scrambled in a capture.** Not a texture or UV fault. Meshy's
   remeshed atlas is hundreds of islands packed edge to edge; a capture taken a moment after
   a cold editor boots samples the lowest mips, where every island's edge is its
   neighbour's colour. UVs and textures were verified identical to Meshy's files (9369 of
   9369 sampled corners match the GLB's UVs; texture bytes identical between the remesh and
   rigged GLBs). The portrait capture now forces full mips
   (`item_icons/capture._full_textures`). `Scripts/dev/render_character.py` still has the
   problem; do not judge a body from it. Use a windowed game.
10. **"gun guard ... chest leans back" fails on a new body.** The old check looked at where
    the neck ended up, which depends on the rig. It now reads the chest's own lean
    (15 +/- 2 degrees). A failure now is a real pose problem.
11. **Meshy `HTTP 402 "API key credit limit reached"`** with credits in the account. The
    limit is on the API key, set in Meshy's dashboard. `GET /openapi/v1/balance` (free)
    shows the account balance. The key is in the environment or git-ignored `assets/.env`.
12. **`fetch_monsters.py` refuses: "the prompt changed since <id> was generated".** Move
    `assets/cache/meshy/<id>` aside (prefix it with `_`; importers skip `_` folders) and run
    again. Never edit the prompt of a body you want to keep.
13. **Probes fail when several run in one game** (clothing position, stance hands, sight
    hands). They pass alone: state leaks between probes. Run each in its own `--game`.
14. **`probe_inventory_window` fails headless.** By design: it needs `--windowed`.
15. **A physics asset half replaced** (mesh has none) after an import that errored inside
    `physics_template.adopt`. Re-run the import for that id: `adopt` handles an existing copy.
16. **A stuck or leftover headless editor.** `python3 Scripts/dev/uepy.py --list`, then
    `--close-editors`; a `$UEPY_SERVE` warm editor may need `kill -9`. Never run a cold
    build with any editor open.

## 7. Rules that must keep holding

- Never loosen a verifier bound and never add a constant for one character. If a new body
  fails a check, find what is still measured on one body and make it measured on the worn
  one. Each row of table 4.2 was found that way.
- No Meshy call without the user's go-ahead and a credit cap. Use `--through preview` and
  look at the thumbnail before paying for the rest.
- Do not pop or drop `stash@{0}` without the user (it is the abandoned `adventurer_02`
  re-tune; its general mechanisms were taken, its tuned constants were not).
  `stash@{1}` is a redundant older stash the user may drop; `stash@{2}` is unrelated.
- Do not push; do not rewrite history. Commits end with the Claude co-author line.
- `Scripts/dev/tasks.md` has uncommitted ticks from the dev-team run; left for the user.

## 8. Open items and the planned next step

**Known gaps**

- A swap is a 4-minute rebuild, not an instant change. The user accepted this for now.
- Garments are still not drawn on the body; wearing one changes only state.
- The picked body's portrait is static; it is re-rendered by the swap script only.
- `Scripts/dev/render_character.py` captures low mips (6.9).
- The jog task (dev-team, `b2b5d45`) found that a blend space edited from Python is not
  rebaked in game. `asset_pipeline/mixamo_locomotion.py` edits the zombie's the same way and
  was not checked.
- Feel checks nobody has done with `adventurer_03`: a play session for the guard, the hold
  poses, the shotgun's left hand, the ragdoll (its joints were reseated), and hit feel with
  the multi-capsule bodies (all characters' hit bodies changed, zombie and wendigo included).
- `adventurer_03`'s shorts end mid-thigh. If garments must cover them, shorter ones need a
  new body.

**Deferred by the user: making swaps instant / scaling to many bodies.** Two routes were
discussed, neither started:

1. *Prebuild per body.* Keep each body's clips and pose clips in its own folder; store the
   per-body numbers (grip locations, support points, pose-clip references, anim blueprint)
   in a table keyed by body instead of compiling one body's values into the Blueprints; the
   swap then sets mesh, anim blueprint and table row. Import costs minutes once; switching
   is instant and could happen in a running game. Touches the weapon builders, the weapon
   component and their verifiers.
2. *True shared skeleton.* Re-bind each generated mesh onto the reference skeleton outside
   Unreal, before import (re-pose the mesh into the reference's rest pose with its own skin
   weights, rewrite bone orientations, re-bind), host-side in Python on the GLB or with
   headless Blender. Then a new body reuses `adventurer_01`'s animations outright. Unproven.
   Risks: distortion where proportions differ, and the finger bones (added after import
   today). A no-credit feasibility test on `adventurer_03`'s cached files was offered and
   not run. Unreal 5.8's Python exposes no skin transfer, per the note in `combat/skin.py`
   (not re-tested in this work).
