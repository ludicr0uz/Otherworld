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
- **Attenuation:** three `USoundAttenuation` assets in `/Game/Audio`, all `NATURAL_SOUND` and
  spherical:
  - `A_Att_Gunfire`: 2 m → 100 m, with a low-pass;
  - `A_Att_Creature`: 1.5 → 40 m;
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
