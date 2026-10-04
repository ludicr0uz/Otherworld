# Combat: audio

Part of `Scripts/combat/CLAUDE.md`, which indexes it.

## Audio (`audio.py`, `Scripts/Sound/`)

- **Every sound is a recording, chosen by ear.** The takes were cut from downloaded packs
  into candidates, rated on an audition page, and the chosen ones are listed in
  `Scripts/Sound/sound_candidates/selection.py`: one row per use, its takes, and whether the
  game plays it. `Scripts/Sound/install_selected_sounds.py` writes each `in game` row to
  `assets/generated/sounds/<asset>.wav` (and `SELECTED.md` beside them: what each was cut
  from). `audio.py` reads the same table for the names and how many takes there are, so a
  take added to a row is a take in the game after an install and a weapons build.
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
- **The beds are the one kind of sound that is not placed** (`audio.BED_NAMES`, in
  `/Game/Audio/Beds`): the day's birds, the night and the wind. Stereo, looping, no
  attenuation, playing on at volume zero. `BP_DayNightCycle` plays them and fades the day's
  into the night's by `DayAmount` (`Scripts/world/CLAUDE.md`). They are in a folder below
  the one the attenuation sweep reads, so "every wave in the two audio folders is placed"
  still holds.
- **The campfire's sound is a component of the fire** (`survival/campfire.py`, `Crackle`):
  a looping, placed wave that starts and ends with the actor.
- **The component's own sounds** (`weapon_component/sounds.py`), arrays of takes on
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
- **The player's voice** (`voice.py`, on `BP_HealthComponent`): a grunt when
  `LastDamageTime` moves (a blow: a drain does not stamp it, and would grunt every frame),
  on the player (`DespawnOnDeath` false) while alive; a cry as `Dead` is set. The wanderers
  have no hurt or death takes yet.
- **Where each sound fires:**
  - The dry click fires on the ready gate's False arm when `empty AND cooled AND tapped`.
  - The reload clack fires only on the reload's True arm.
- **Attenuation:** four `USoundAttenuation` assets in `/Game/Audio`, all `NATURAL_SOUND` and
  spherical (the axe's chop and a melee hit carry as a creature's voice does; the player's
  voice, a swing, a match and the campfire as foley):
  - `A_Att_Gunfire`: 2 m → 100 m, with a low-pass;
  - `A_Att_Creature`: 1.5 → 40 m;
  - `A_Att_WendigoRoar`: the one **linear** profile. Full volume to 10 m (`ROAR_FULL_CM`),
    then a straight line to silence at 1.75 × the wendigo's aggro range (`ROAR_REACH_X_AGGRO`;
    35 m of sight, so 61 m). On the natural curve a roar from 35 m was near -34 dB, barely
    heard; on the line it is about half volume there, and up close it is no louder than the
    recording. The range is read from `npc/monster_tuning.csv` when the weapons build runs:
    after saving a new aggro range from the MONSTER SETTINGS tab, re-run
    `build_weapons_and_combat.py` (the verifier fails until then). Capped at the 100 m ceiling;
  - `A_Att_Foley`: 1 → 15 m.
- **A sound with no attenuation plays at full volume from anywhere.** `apply_attenuation()` sets
  it **on the asset**, sweeps both audio folders, and raises on a wave with no profile.
  - The Python name is `d_b_attenuation_at_max`.
  - Proof it took: the engine-cached `max_distance` reads 10000 / 4000 / 1500.
  - `AreAnyListenersWithinRange` is **impure**. Left without an exec wire, it is pruned and
    reads false.
- **Distance is heard from the character, not the camera** (`weapon_component/listener.py`).
  - The engine's listener rides the camera: 2.6 m behind over the shoulder, at the eye down the
    sights. Footsteps were quiet in one view and loud in the other.
  - BeginPlay calls `SetAudioListenerAttenuationOverride(CapsuleComponent)` on the player's
    controller. Attenuation measures from the capsule. Panning still follows the camera, so the
    call is **not** `SetAudioListenerOverride`, which would move both.
  - `verify/audio.py` checks the node. A probe can't: the engine places the listener in
    `GameViewportClient::Draw`, which never runs under `-nullrhi`, so it stays at the origin.

## Volumes (`sound_tuning.py`, `sound_mix.py`)

- **Each sound has one volume, in `sound_tuning.csv`** (`sound,volume`; 1 = as recorded, 0 =
  silent, at most 2). A "sound" is a row of `sound_tuning.SOUND_STATS`: the footsteps (six
  takes, one row, 0.4: they drowned the forest at 1), each gun's shot, the dry click, the
  three reloads, the melee hit and swing, the axe's chop, the zombie's growl, the wendigo's
  roar, the player's hit and death, the match, the campfire, a blade's hit, a thrown blade in a
  body, a throw, and the three beds (the wind's at 0: silent until a better one is found).
- **A row is a `SoundClass`** (`/Game/Audio/A_Class_<Sound>`), set on each of its waves by
  `sound_mix.build_sound_mix()`, as the attenuation is: on the asset, so no play site carries
  a volume. `/Game/Audio/A_Mix_Game` is an empty `SoundMix`.
- **The volume is applied by the HUD, not baked into an asset.** On its first Tick (the
  title's too) `BP_GraphicsMenuHUD` makes the mix the base mix and calls
  `SetSoundMixClassOverride` once per class with its cell of `SoundTuneValues`, which is the
  CSV baked at build time (`graphics_menu/sound_tune_tick.py`). An override **multiplies**
  the class's own volume, so the classes and waves stay at 1 (the verifier checks): a
  volume baked into both would be squared.
- **A new wave needs a row.** `build_sound_mix()` raises on a wave of `SOUND_ATTENUATION`
  that is in no row of `SOUND_STATS`, or in two.
- **After a save from the SOUND SETTINGS tab, re-run `build_graphics_menu.py`**: the HUD's
  table is the baked CSV, and `verify_graphics_menu` fails until then. The weapons build
  does not read the volumes.
- **The stance's `StepVolume` still multiplies a footstep** (crouch 0.5, prone 0.3), on top
  of the class's.
- **What the device holds can be read in a game:** the console's
  `au.Debug.ListSoundClassVolumes` logs every class's current volume, mixes applied.
  `probes/probe_sound_tuning.py` reads the log back (the listing is written over the next
  few frames, so it waits for all of it).
