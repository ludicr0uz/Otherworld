# Sound

`Scripts/Sound/__init__.py` maps the package. Entry point: `Scripts/build_sound.py`.

## One place, one build

- **Every sound is a row of its area's `SOUNDS`** (`sound_weapons.py`, `sound_monsters.py`,
  `sound_items.py`, `sound_world.py`): its key, the tab's label, its takes, its attenuation
  profile, its default volume. `catalog.py` puts the areas together.
- **Where a sound is played from is a row of the area's `BINDINGS`:** a Blueprint, a variable
  (or a component's property), a sound. The graphs read the variable; nothing in a graph names
  a wave. The Blueprint's own builder writes it (`bind.defaults_for`), and
  `build_sound.py` writes every binding again onto the Blueprints as they stand
  (`bind.apply_bindings`: CDO, compile, save, read back).
- **`build_sound.py` is the only build after a change to a mapping, a take, a profile or a
  volume** (about 4 s warm): it imports the waves, builds the attenuations, the classes and
  the mix, applies the bindings, and bakes `sound_tuning.csv` into the HUD's table. It skips
  a Blueprint that is not built yet. The weapons build still runs the asset step first, so a
  fresh checkout builds in the old order.
- **What still needs another build:** a new variable, component or play site (that
  Blueprint's builder), and a new or moved ROW of the SOUND SETTINGS tab
  (`build_graphics_menu.py`: the HUD's graph has a node per row). `catalog.TAB_ORDER` is the
  tab's order and is by position (the HUD's table and a player's saved volumes index it): add
  at the end.
- **The sound logic that is an area's own lives in its module:** the player's voice, the
  beds and their fade, and the listener in `sound_world.py`; the campfire's component in
  `sound_items.py`; the roar's curve in `sound_monsters.py`. The shared picker is `play.py`.
  When a sound plays is still its feature's graph (a shot in `weapon_component/firing.py`,
  a growl's timer in `npc/stats.py`), which calls the picker with the variable.
- **`Sound` is also the folder of the sourcing tools**, which run outside the editor and put
  `Scripts/Sound` itself on the path (`from sound_candidates import ...`). The package's
  `__init__.py` holds only a docstring, so they are unaffected.
- **Imports:** `sound_def` is constants only. The area modules import constants from
  `combat`, `npc`, `survival` and `world`, so none of those constants modules may import
  `Sound` (`forest_generator/npc_placement.py` no longer names the voices: `npc_placement` ->
  `sound_monsters` -> `npc/monster_tuning` -> `npc_placement` was a cycle).

## Audio (`waves.py`, `attenuation.py`, the sourcing tools)

- **Every sound is a recording, chosen by ear.** The takes were cut from downloaded packs
  into candidates, rated on an audition page, and the chosen ones are listed in
  `Scripts/Sound/sound_candidates/selection.py`: one row per use, its takes, and whether the
  game plays it. `Scripts/Sound/install_selected_sounds.py` writes each `in game` row to
  `assets/generated/sounds/<asset>.wav` (and `SELECTED.md` beside them: what each was cut
  from). `sound_def.takes()` reads the same table for the names and how many takes there are, so a
  take added to a row is a take in the game after an install and `build_sound.py`.
  - **Licences:** CC0 (the Free Firearm Sound Library, Nox Sound, Kenney, OpenGameArt) or the
    Sonniss GDC bundle licence, which asks for no credit either. There is no credits screen,
    so nothing that needs one is used. `assets/generated/sound_candidates/SOURCES.md` has
    each take's source.
  - **What is still missing, and what is chosen and not yet played:**
    `Scripts/Sound/docs/missing_sounds.md`.
- **`import_sounds()` re-imports a wave whose WAV is newer than its asset,** so a take chosen
  again reaches the game. One that is unchanged is skipped.
- **Rules of the samples:**
  - mono, 48 kHz (the project's rate), 16-bit: a stereo sound can't be spatialised;
  - automatics cut quieter (peak < 0.80), with `length ÷ FireInterval ≤ 12` asserted;
  - a weapon sound is 0.2 to 2.5 s; shots are truncated and faded.
- **The shots are real guns recorded close** (`manifest_guns.py`: the Sonniss 2016 bundle,
  Pole Position Production and TS Sound), picked on the audition page: a 12-gauge slug for
  the shotgun, a Glock 18 for the pistol, a Mini Uzi for the SMG, an AKM for the rifle. No
  sniper among them was liked, so the sniper's is the shot the game had from 26 September
  (a synthesised one, exported from a backup of Content: `backup_sep26_*`). The shotgun's
  reload is the first set's pump.
  - **How it got here:** the recordings cut on 26 September were never imported (the
    importer of the time skipped an asset that existed), so the game went on playing its
    synthesised shots, and "the original gunshots" meant those. The Free Firearm Sound
    Library's takes were tried in the hand and turned down twice.
  - **Gunfire heard from far off** is the selection's `shots_distant`: the Free Firearm
    Sound Library's takes and the far recordings of the guns above. Nothing plays them:
    only the player fires, and no sound carries past 100 m.
  - **An automatic's shot is not held under full scale** (the check was `peak < 0.80`):
    the cuts are levelled alike, at 0.9, so that guns are compared and not volumes.
- **The rifle's and the pistol's reloads are put together from parts** (`selection.py`'s
  `recipe`): a magazine out, a magazine in and a bolt, each at its own start, laid out by
  each part's length. `ReloadSound` is per weapon; `DryFireSound` is shared.
- **The beds are the one kind of sound that is not placed** (`catalog.BED_NAMES`, in
  `/Game/Audio/Beds`): the day's birds, the night and the wind. Stereo, looping, no
  attenuation, playing on at volume zero. `BP_DayNightCycle` plays them and fades the day's
  into the night's by `DayAmount` (`Scripts/world/CLAUDE.md`). They are in a folder below
  the one the attenuation sweep reads, so "every wave in the two audio folders is placed"
  still holds.
- **The campfire's sound is a component of the fire** (`survival/campfire.py`, `Crackle`):
  a looping, placed wave that starts and ends with the actor.
- **The component's own sounds** (`sound_weapons.py`, `sound_items.py`), arrays of takes on
  `BP_WeaponComponent`, one drawn per play; empty is silence:
  - `SwingSounds` as a punch or a slash starts;
  - `PunchHitSounds` and `BladeHitSounds` where a blow lands on a body (`Strike.hit_sounds_var`:
    the fist's, and the knife's and the axe's);
  - `ChopSounds` at the axe's cut in a tree, and where a thrown blade lodges in one;
  - `ThrowSharpSounds` as a thrown Melee item (the knife, the axe) leaves the hand and
    `ThrowSounds` as anything else does; `LodgeSounds` where a thrown blade goes into a body;
  - `MatchSounds` where a campfire is laid.
  The thrown blade's two are between steps the verifier pins (the blood, then the lodge):
  `verify/throw_strike._past_sound` looks back past a played sound.
- **The monsters' voices** (`sound_monsters.py`), four arrays on each creature's AI
  controller; empty is silence:
  - `Voices` on the Pulse's 4-9 s timer. The zombie's are its patrol growls and play only
    on patrol; the wendigo's is its roar and plays only once it hunts
    (`forest_generator/npc_voice.py`: `NPC_QUIET_ON_HUNT`, `NPC_QUIET_ON_PATROL`);
  - `AggroVoices` the once, behind the one write of `Aggro` (`npc/agro.py`). The zombie's
    growl 10; the wendigo has none (its roar is a step of its own);
  - `AttackVoices` as a swing starts, landed or not (`npc/melee.py`). The zombie's growls
    1, 2 and 4; the wendigo has none;
  - `HitSounds` where a swing lands.
  The zombie's three sets are one selection row (`zombie_growl`, `A_ZombieGrowl_01` and
  on) dealt out by take number in `sound_monsters.py` (`ZOMBIE_ATTACK_TAKES`,
  `ZOMBIE_AGGRO_TAKES`; the rest are the patrol's). Moving a take between them is that
  edit and `build_sound.py`. Each set is a row of the SOUND SETTINGS tab.
  **After the takes in `Voices` change in number, the level verifiers' expected count is
  stale** (`generated_levels/*/verify_*.py` bake `voices_of()`): regenerate the levels, or
  patch `EXPECTED_VARIANTS`' `voices` to `voices_of(key)` as the split did.
- **Footsteps are one component and a set of takes per wearer.** `BP_FootstepComponent`
  (`combat/footsteps.py`) knows a stride and an array, `Sounds`; whose feet they are is
  which takes its copy holds. The class's own are the player's (`sound_world.FOOTSTEPS`);
  a Blueprint that wears the component gets others with a `Binding(..., component=
  "FootstepComponent")` on itself, as `BP_ForestWanderer` has
  (`sound_monsters.MONSTER_FOOTSTEPS`: heavier takes, a volume row of their own). The
  creature Blueprints inherit that copy (`probes/probe_monster_sounds.py` reads it off a
  spawned zombie and wendigo). A new kind of walker (another NPC, another player's body)
  is a `Sound` row and such a binding; `combat/install.py` writes the bindings when it
  adds the component, and `build_sound.py` again. Per-creature takes (a zombie's against
  a wendigo's) can't be bound this way: Python can't reach a child Blueprint's override
  of an inherited component, so they would have to be copied on at possession, as the
  flinch clips are.
- **The player's voice** (`sound_world.py`, on `BP_HealthComponent`): a grunt when
  `LastDamageTime` moves (a blow: a drain does not stamp it, and would grunt every frame),
  on the player (`DespawnOnDeath` false) while alive; a cry as `Dead` is set. The wanderers
  have no hurt or death takes yet.
- **Where each sound fires:**
  - The dry click fires on the ready gate's False arm when `empty AND cooled AND tapped`.
  - The reload clack fires only on the reload's True arm.
- **Attenuation:** six `USoundAttenuation` assets in `/Game/Audio`, all spherical, and
  `NATURAL_SOUND` but for the three that have to be heard at a distance, which are straight
  lines (the axe's chop and a melee hit are `A_Att_Creature`; the player's voice, a swing, a
  match and the campfire are foley):
  - `A_Att_Gunfire`: 2 m → 100 m, with a low-pass;
  - `A_Att_Creature`: 1.5 → 40 m;
  - `A_Att_WendigoRoar`: the one **linear** profile. Full volume to 10 m (`ROAR_FULL_CM`),
    then a straight line to silence at 1.75 × the wendigo's aggro range (`ROAR_REACH_X_AGGRO`;
    35 m of sight, so 61 m). On the natural curve a roar from 35 m was near -34 dB, barely
    heard; on the line it is about half volume there, and up close it is no louder than the
    recording. The range is read from `npc/monster_tuning.csv` when the sound build runs:
    after saving a new aggro range from the MONSTER SETTINGS tab, re-run
    `build_sound.py` (the verifier fails until then). Capped at the 100 m ceiling;
  - `A_Att_CreatureVoice`: **linear**, full to 5 m, silent at 50 m. The zombie's patrol and
    attack growls: it sees 20 m, and there they are two thirds of full volume (on
    `A_Att_Creature` they were near -29 dB). Its aggro growl is on the roar's curve;
  - `A_Att_Footstep`: **linear**, full to 2 m, silent at 20 m. Every footstep, the player's
    and the wanderers' (the player's own are at the listener, so only others' are shaped
    by it). On the foley curve a wanderer running up was not heard coming;
  - `A_Att_Foley`: 1 → 15 m.
- **A sound with no attenuation plays at full volume from anywhere.** `apply_attenuation()` sets
  it **on the asset**, sweeps both audio folders, and raises on a wave with no profile.
  - The Python name is `d_b_attenuation_at_max`.
  - Proof it took: the engine-cached `max_distance` reads 10000 / 4000 / 1500.
  - `AreAnyListenersWithinRange` is **impure**. Left without an exec wire, it is pruned and
    reads false.
- **Distance is heard from the character, not the camera** (`sound_world._author_listener_at_character`).
  - The engine's listener rides the camera: 2.6 m behind over the shoulder, at the eye down the
    sights. Footsteps were quiet in one view and loud in the other.
  - BeginPlay calls `SetAudioListenerAttenuationOverride(CapsuleComponent)` on the player's
    controller. Attenuation measures from the capsule. Panning still follows the camera, so the
    call is **not** `SetAudioListenerOverride`, which would move both.
  - `verify/audio.py` checks the node. A probe can't: the engine places the listener in
    `GameViewportClient::Draw`, which never runs under `-nullrhi`, so it stays at the origin.

## Volumes (`tuning.py`, `mix.py`)

- **Each sound has one volume, in `sound_tuning.csv`** (`sound,volume`; 1 = as recorded, 0 =
  silent, at most 2). A "sound" is a row of `catalog.SOUND_STATS`: the footsteps (six
  takes, one row, 0.4: they drowned the forest at 1), each gun's shot, the dry click, the
  three reloads, the melee hit and swing, the axe's chop, the zombie's growl (its patrol's), the wendigo's
  roar, the player's hit and death, the match, the campfire, a blade's hit, a thrown blade in a
  body, a throw, the three beds (the wind's at 0: silent until a better one is found), and, at
  the end, the zombie's attack and aggro growls and the monsters' footsteps.
- **A row is a `SoundClass`** (`/Game/Audio/A_Class_<Sound>`), set on each of its waves by
  `mix.build_sound_mix()`, as the attenuation is: on the asset, so no play site carries
  a volume. `/Game/Audio/A_Mix_Game` is an empty `SoundMix`.
- **The volume is applied by the HUD, not baked into an asset.** On its first Tick (the
  title's too) `BP_GraphicsMenuHUD` makes the mix the base mix and calls
  `SetSoundMixClassOverride` once per class with its cell of `SoundTuneValues`, which is the
  CSV baked at build time (`graphics_menu/sound_tune_tick.py`). An override **multiplies**
  the class's own volume, so the classes and waves stay at 1 (the verifier checks): a
  volume baked into both would be squared.
- **A new wave needs a row.** `build_sound_mix()` raises on a wave of `SOUND_ATTENUATION`
  that is in no row of `SOUND_STATS`, or in two.
- **After a save from the SOUND SETTINGS tab, re-run `build_sound.py`**: the HUD's
  table is the baked CSV, and `verify_graphics_menu` fails until then
  (`build.apply_sound_volumes`; `build_graphics_menu.py` bakes it too).
- **The stance's `StepVolume` still multiplies a footstep** (crouch 0.5, prone 0.3), on top
  of the class's.
- **What the device holds can be read in a game:** the console's
  `au.Debug.ListSoundClassVolumes` logs every class's current volume, mixes applied.
  `probes/probe_sound_tuning.py` reads the log back (the listing is written over the next
  few frames, so it waits for all of it).
