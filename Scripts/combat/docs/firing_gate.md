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
