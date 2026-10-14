# Animation library viewer

Browse and compare every animation sequence under `/Game`, by category, as
animated skeletons: the Game Animation Sample, Lyra, Mixamo, Quaternius, the
stock mannequin's, the MetaHuman's, the clips the game bakes, and every Fab
pack (`export_poses.py` finds them through the asset registry, so a pack added
to the project is on the page after the three commands below; `SOURCES` there
only gives a folder a nicer name). A skeleton that is not a body (a gun, a
face) is left out and counted in `Saved/AnimLibrary/export_summary.txt`; the
creatures' retargeted copies are left out too, as the original is listed.
A rerun samples only the clips it has not written yet.

    python3 Scripts/dev/uepy.py --cold --summary Scripts/dev/anim_library/export_poses.py   # ~90 s
    python3 Scripts/dev/uepy.py --cold --summary Scripts/dev/anim_library/export_usage.py   # ~60 s, optional
    python3 Scripts/dev/anim_library/build_library.py                                       # 1 s
    python3 Scripts/dev/anim_library/serve.py                                               # http://localhost:8765/

Everything is written under `Saved/AnimLibrary/` (not committed).

## What it shows

Each clip is sampled in the editor through `AnimPoseExtensions` (exact, any
rig, no GPU) into the body's joints: spine, head, arms to the hand, legs to the
toe. Fingers and helper bones are left out, since this is for choosing a
motion, not judging a grip. Frames are 15 per second, up to 60 per clip.

- The figure faces the same way for every rig (taken from the thighs at frame
  0) and is centred on the pelvis, so a clip that travels stays on the spot.
  Height is kept, so a jump reads as a jump.
- "m/s" is the pelvis's forward travel over the clip. Clips without root motion
  say "in place". Check: the Sample's run loop reads 4.99 m/s against 500 cm/s
  in its curve, walk 1.96 against 200, sprint 6.98 against 700.
- A clip is sampled as authored: an asset whose rate scale is negative (the
  Free Animation Library's backward crawls are its forward ones at -1) shows
  playing forward.
- Additive clips (hit-react overlays, aim offsets) have no pose of their own
  and show "additive: no pose".
- The Lyra clips are on Lyra's mannequin and the Sample's on the UEFN one: the
  drawn bodies differ, the motion is each rig's own, not retargeted. Clips
  already retargeted for the player carry the tag "on the player".

## Using it

- Left: category counts (they follow the other filters). Top: search (every
  word must match name, folder, tag or source), source, sort, loops only, hide
  right-foot twins (the Sample ships each clip as an L-foot and an R-foot
  variant), same duration.
- `+` on a card pins it to the Compare tray at the bottom. Pins survive a
  reload. "same duration" plays every clip over the same two seconds, which
  compares shape and not length.
- The detail view and the compare tray draw a shaded mannequin (tapered
  limbs, torso, head, hands and feet from the same joints; blue rim left,
  orange right). The grid keeps stick figures, for speed. The button beside
  "Pin to compare" switches back; the choice is remembered.
- Click a card for the detail view: drag to turn, scrub, slow down, copy the
  asset path.
- A link carries a view: `#cat=sprint&q=relaxed&pin=M_Neutral_Sprint_Loop_F,A_UAL1_Sprint_Loop&open=<clip>`.

## What "used" means

Highlighted green, "in game": the game plays it (or its retargeted copy). The
evidence is listed in the detail view, from three sources: a game asset that
references it in the asset registry (a weapon Blueprint, the weapons component,
a creature's blend space), a build table that picks it (Mixamo's player and
zombie clips, Lyra's punch and ready poses), or a name that appears in the
build scripts (not tests, probes or verifiers). A name in code is weaker
evidence than a reference: it may be a fallback for another body.

Dashed, "mm pool": the clip is in a pose-search database the player's anim
Blueprint can reach (Dense, Sparse, Extreme Sparse, the state-machine data).
The motion matching may pick it; whether it does depends on the chooser. The
Relaxed databases are not reachable; the one Relaxed clip used is
`M_Relaxed_Sprint_Loop_F`, which the weapons build puts in the neutral sprint-loop
databases in place of the neutral forward loop (`combat/gas_sprint.py`).
Run `export_usage.py` again after the graph changes.

## Wrong category

Categories are guessed from names and folders (`build_library.py`,
`CATEGORIES`, first match wins). To correct one, add `<clip name>,<category>` to
`category_overrides.csv` beside it and run `build_library.py` again; no editor
run is needed.

## Why skeletons and not video

A cold editor never ticks, so a mesh set to a time keeps its reference pose,
and a headless game renders nothing. The pose at a time is exact through
`AnimPoseExtensions`, and the browser draws it. A rendered MetaHuman preview
would need a windowed game run per clip.
