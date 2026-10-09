# Combat: the firing gate and debug mode

Part of `Scripts/combat/CLAUDE.md`, which indexes it.

## Firing gate and debug mode

- **The fire gate:**
  ```
  outer: (tapped OR holding) AND IsValid(Held) AND NOT Sprinting AND NOT Blocking
  inner: (Loaded > 0 AND cooled) AND (tapped OR (holding AND Held.Automatic))
  ```
  - **The gate is the local player's; the shot is the server's** (M19,
    `weapon_component/shot.py`). Past the inner gate the Tick kicks the view, plays the
    shot's sound and calls `Server_Fire(AimPoint)` (C++ since W1:
    `OtherworldWeaponComponentBase`), which asks again for itself (a valid
    `Held`, a living owner, a gun, a round, the cooldown with 0.1 s of grace) before it
    spends and raises `ShotFired`, where the graph traces. A client of a server also spends its own copy's round and stamps
    its own cooldown, so its next frame's gate is right before any answer comes.
  - Anything read off `Held` must stay inside the outer gate, per the nested-Branch gotcha in the
    root CLAUDE.md. The verifier pins that exactly one Branch reads `Automatic`, together with
    `Loaded` and `NextFireTime`.
  - Consumables branch off it: `Held.Consumable` plus a tap goes to `weapon_component/consume.py`.
    A garment is Consumable too: behind the tap, `Held.ClothingSlot >= 0` sends it to
    `weapon_component/wear.py` instead, which wears it and spends the press the same way.
  - **The press that eats is spent.** Eating equips the next item in the same frame, while the
    key is still down. `TriggerSpent` is set by the consume chain, the outer gate requires
    `NOT TriggerSpent`, and `TriggerSpent &= IsInputKeyDown` runs just before the gate. Without
    it, a weapon in the next slot fired once on the same press.
  - **The HUD raises it too.** While the mouse cursor shows over a running game (the M panel,
    the loot window), `DrawHUD` sets `TriggerSpent` every frame, so a click on a menu row
    neither fires, slashes nor punches (`graphics_menu/cursor.py`, `author_hold_fire`).
- **Empty hands punch** (`weapon_component/punch.py`, tuning `COMBAT.punch_*`). The fire
  gate's False arm runs the punch's press gate: tap AND `NOT IsValid(Held)` AND not sprinting,
  not blocking, not a spent press, off cooldown (`NextPunchTime`). It reads nothing off `Held`.
  - The press only sets `PunchQueued`; the swing stage consumes it, so a probe can punch
    without a key (`Scripts/probes/probe_punch.py`).
  - The swing plays the worn skin's punch (`PlayerSkin.punch`: on the motion-matching
    skin Lyra's `MM_Pistol_Melee`, retargeted by `asset_pipeline/import_lyra.py` and
    played from `punch_clip_start_s`; on the older skins the mannequin's `MM_Attack_01`,
    retargeted by `build_retarget` as `MELEE_SOURCE`) into `DefaultSlot`, upper body only. A flinch or a
    sprint re-equip stops it (same montage group, or the equip's `StopSlot`).
  - The blow lands `punch_impact_s` later (`PunchPending`/`PunchDueTime`): a sphere sweep from
    the chest along the actor's forward, then the same Health/LastDamageTime/DamagedByPlayer/
    LastHitFrom writes a pellet makes. No blood, no hit zones.
  - `IsSlotActive` turns true one anim update after the play, not on it; a probe asks
    `is_playing_slot_animation` first.
  - The verifier's older counts (ready-pose plays, traces, the fire gate, LastHitFrom writes)
    set the punch's nodes aside with `verify/punch.is_punch_*`.
- **The knife slashes** (`weapon_component/knife.py`, tuning `COMBAT.knife_*`). Its press is
  inside the fire gate, since it reads `Held.Melee`: the Consumable branch's False arm asks
  `Melee`, and a tap off `NextKnifeTime` sets `KnifeQueued`. Anything not Melee goes on to the
  guns' ready gate, so the knife never reaches the ammunition or cooldown tests of a gun.
  - The axe (`axe.py`) is `Melee` too and has no stage of its own: it takes this branch and
    swings the knife's Strike (`probes/probe_axe.py`).
  - A blow that strikes something with no health goes on to `weapon_component/chop.py`
    (`_author_blow`'s `scenery`, given by the knife stage only): the axe on a tree cuts wood.
  - **The matches light** (`weapon_component/light.py`): the Melee branch's False arm asks
    `Held.Lights`, and a tap runs the strike (one `BP_Wood` out of `Inventory`, a campfire on
    the ground ahead). Anything that does not Light goes on to the guns' ready gate. It reads
    `Held`, so it sits inside the fire gate and inherits "not sprinting, not blocking, not a
    spent press, not while V is down".
  - Wood in hand (`wood.py`) is neither Melee nor Consumable: the fire key reaches the guns'
    ready gate and "fires" no pellets, with no sound, kick or noise.
  - The swing and the blow are the punch's (`punch._author_swing`), run on the `KNIFE` Strike
    with its own variables (`KnifeQueued/Pending`, `NextKnifeTime`, `KnifeDueTime`, `KnifeAnim`).
    They run every frame whatever is held, so a slash put away mid-swing still lands.
  - The clip is `A_KnifeSlash` (Mixamo's stab), or `A_AxeSwing` while the axe's ready pose is in
    hand (`melee_clips.py`), each cut to strike `COMBAT.knife_impact_s` in; the ready-pose
    keepalive puts the ready pose back afterwards.
  - The blow: a 25 cm sphere 150 cm forward, 35 HP, the pellet's stamps. No blood, no hit zones.
  - `Scripts/probes/probe_knife.py` equips the knife, writes `KnifeQueued` and sees the clip, the
    35 HP and the ready pose come back. `verify/knife.py`'s `is_melee_*` set both attacks' nodes
    aside in the older counts.
- **Reload stores `Min(MagazineSize − Loaded, Reserve)` into `ReloadTake` once.** Recomputing it
  after `Loaded` rises means free ammo. The reload is the `ReloadNow` event: R calls
  `Server_Reload`, which runs it, and a client of a server runs it on its own copy first.
- **Debug mode:**
  - `DebugMode` lives on the GameMode, because a component can't reach the HUD. It is on by
    default and persisted as `BP_Settings.DebugMode`. The HUD copies it at BeginPlay, and D writes
    both it and the save.
  - It shows the FPS readout, pellet tracers, per-impact damage (`39.0 (x1.5)`, only on actors
    with a health component) and wanderer numbers.
  - The tracer (`weapon_component/tracer.py`) is a separate `DrawDebugLine` behind a Branch,
    since the enum pin can't be driven. Every trace's `DrawDebugType` is `None`.
    - It lasts `TRACE_DEBUG_SECONDS` (3 s) and stops where the pellet did, with a point there:
      red to an impact, blue out to the weapon's range on a miss.
    - **Both ends come off the trace's own hit result** (`TraceStart`, then `Location` or
      `TraceEnd`). The trace's `End` is fed by the pure pellet cone, so a tracer wired to it
      drew a second, different pellet: the shotgun's lines were not its pellets'.
      `verify/tracer.py` walks the tracer's pure inputs for a random node.
  - It also shows each wanderer's sight cone (`Scripts/npc/CLAUDE.md`).
  - Readers copy the flag once: the weapon component per shot, the HUD per `DrawHUD`.
