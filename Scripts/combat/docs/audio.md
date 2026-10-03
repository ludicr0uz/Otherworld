# Combat: audio

Part of `Scripts/combat/CLAUDE.md`, which indexes it.

## Audio (`audio.py`, `Scripts/fetch_weapon_sounds.py`)

- **The nine weapon sounds are cut from CC0 recordings.**
  - The five gunshots all come from *The Free Firearm Sound Library*, so they share room and
    distance. The handling sounds come from two OpenGameArt packs.
  - The license is **CC0 only**, because there is no credits screen.
  - The fetcher downloads and caches into `assets/cache/sounds` using curl, bsdtar (for 7z),
    afconvert and `wave`, and cuts into `assets/generated/sounds`.
- **Rules baked into the samples:**
  - mono 44.1 kHz 16-bit, because a stereo sound can't be spatialised;
  - automatics cut quieter (peak < 0.80), with `length ÷ FireInterval ≤ 12` asserted;
  - shots truncated and faded, handling sounds not;
  - `_count_shots()` raises unless a gunshot cut has exactly one onset. One "single shot" take
    was a four-round burst.
- **`ReloadSound` is per weapon:** pump, magazine or hand-fed. `DryFireSound` is shared.
- **Where each sound fires:**
  - The dry click fires on the ready gate's False arm when `empty AND cooled AND tapped`.
  - The reload clack fires only on the reload's True arm.
- **Attenuation:** four `USoundAttenuation` assets in `/Game/Audio`, all `NATURAL_SOUND` and
  spherical:
  - `A_Att_Gunfire`: 2 m → 100 m, with a low-pass;
  - `A_Att_Creature`: 1.5 → 40 m;
  - `A_Att_WendigoRoar`: 1.5 m → 1.75 × the wendigo's aggro range (`ROAR_REACH_X_AGGRO`;
    35 m of sight, so 61 m), so a roar is always heard by the player it is for. The range is
    read from `npc/monster_tuning.csv` when the weapons build runs: after saving a new aggro
    range from the MONSTER SETTINGS tab, re-run `build_weapons_and_combat.py` (the verifier
    fails until then). Capped at the 100 m ceiling;
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
  silent, at most 2). A "sound" is a row of `sound_tuning.SOUND_STATS`: the footsteps (four
  takes, one row, 0.4: they drowned the forest at 1), each gun's shot, the dry click, the
  three reloads, the melee hit, the zombie's growl, the wendigo's roar.
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
