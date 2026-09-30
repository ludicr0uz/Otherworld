# Combat: Animation Blueprint authoring

Part of `Scripts/combat/CLAUDE.md`, which indexes it.

## Animation Blueprint authoring

- **AnimGraphs are authorable; blend spaces are not.** Use
  `get_graph_editor_by_name(anim_bp, "AnimGraph")`. A bare `BlueprintGraphEditor(bp)` is the
  EventGraph.
- **A pose output pin may feed two pose inputs.**
- **An anim node's settings live on its inner `node` struct.** The read is a copy: mutate it and
  write the whole struct back. These structs `repr()` as `{}`, so check them field by field.
- **New slot:**
  1. Spawn the palette entry for an *existing* slot (`Animation|Montage|Slot'DefaultSlot'`).
  2. Rename `node.slot_name`.
  3. Compile, which registers it.
- **Turning a bone:** `Animation|SkeletalControls|Transform(Modify)Bone` works on a component-space
  pose. Wrap it in `Animation|ConvertSpaces|LocalToComponent` / `ComponentToLocal`. Its
  `Rotation` pin shows by default and takes a `MakeRotator` fed by an ABP variable.
- **Hand `remove_nodes` each node once.** Several ModifyBones share one variable getter;
  `aim_pitch._feeding_all` de-duplicates what it hands over.
- **The editor sometimes dies in `AddCallFunctionNode`** (SIGBUS/SIGSEGV inside the call) on a
  second or later build in one editor session; it has hit the aim-pitch, the blood-splash, the
  combat and the HUD builds. Cause unknown. A freshly started editor has built cleanly once
  every time (the second build in the same session crashed again), so run each builder in its own
  `uepy.py --cold` launch when it recurs, and after a crash
  `Saved/Autosaves/PackageRestoreData.json` can hold a restore prompt that blocks the next boot
  headlessly.
- **Probing an ABP variable in PIE:** an anim instance's variables can't be written from Python
  (not instance editable). Write the CDO, then start PIE again: the instance copies it.
- **Sampling a pose:** `AnimPoseExtensions.get_anim_pose_at_time` → `get_bone_pose(…, WORLD)`,
  where WORLD means component space.
  - `get_reference_pose` takes a Skeleton, and its pose is not the mesh's, so compare like with
    like.
  - `compose_transforms(A, B)` is A-then-B.
- **The creatures' physics assets** are `SKM_Zombie01_PhysicsAsset` and
  `SKM_Wendigo01_PhysicsAsset`. `PA_Mannequin` is stock and untouched.
