# Combat: the firing gate and debug mode

Part of `Scripts/combat/CLAUDE.md`, which indexes it.

## Firing gate and debug mode

- **The fire gate:**
  ```
  outer: (tapped OR holding) AND IsValid(Held) AND NOT Sprinting AND NOT Blocking
  inner: (Loaded > 0 AND cooled) AND (tapped OR (holding AND Held.Automatic))
  ```
  - Anything read off `Held` must stay inside the outer gate, per the nested-Branch gotcha in the
    root CLAUDE.md. The verifier pins that exactly one Branch reads `Automatic`, together with
    `Loaded` and `NextFireTime`.
  - Consumables branch off it: `Held.Consumable` plus a tap goes to `weapon_component/consume.py`.
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
  - The swing plays the worn skin's `MM_Attack_01` (`PlayerSkin.punch`, retargeted by
    `build_retarget` as `MELEE_SOURCE`) into `DefaultSlot`, upper body only. A flinch or a
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
  - The swing and the blow are the punch's (`punch._author_swing`), run on the `KNIFE` Strike
    with its own variables (`KnifeQueued/Pending`, `NextKnifeTime`, `KnifeDueTime`, `KnifeAnim`).
    They run every frame whatever is held, so a slash put away mid-swing still lands.
  - The clip is `A_KnifeSlash` (`knife_anim.py`), 0.6 s, starting and ending in the pistol ready
    pose the knife is held in; the ready-pose keepalive puts that pose back afterwards.
  - The blow: a 25 cm sphere 150 cm forward, 35 HP, the pellet's stamps. No blood, no hit zones.
  - `Scripts/probes/probe_knife.py` equips the knife, writes `KnifeQueued` and sees the clip, the
    35 HP and the ready pose come back. `verify/knife.py`'s `is_melee_*` set both attacks' nodes
    aside in the older counts.
- **Reload stores `Min(MagazineSize − Loaded, Reserve)` into `ReloadTake` once.** Recomputing it
  after `Loaded` rises means free ammo.
- **Debug mode:**
  - `DebugMode` lives on the GameMode, because a component can't reach the HUD. It is on by
    default and persisted as `BP_Settings.DebugMode`. The HUD copies it at BeginPlay, and D writes
    both it and the save.
  - It shows the FPS readout, pellet tracers, per-impact damage (`39.0 (x1.5)`, only on actors
    with a health component) and wanderer numbers.
  - The tracer is a separate `DrawDebugLine` behind a Branch, since the enum pin can't be driven.
    Every trace's `DrawDebugType` is `None`.
  - Readers copy the flag once: the weapon component per shot, the HUD per `DrawHUD`.
