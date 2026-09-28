# Otherworld — orchestrated task run (2026-09-27)

Eight tasks, executed strictly in order, one subagent each.
Baseline commit: `d262629 switch to night mode` (asks 1 & 2 from the prior
session — night-mode default and automatic ADS mouse-sensitivity reduction —
are already landed and verified).

| # | Task | Status |
|---|------|--------|
| 3 | Mouse sensitivity + keybind settings in main menu, persisted across runs | **done** |
| 4 | Sniper ADS scope overlay (black screen + crosshair) | **done** |
| 5 | Per-weapon recoil, as a combat-config parameter | **done** |
| 6 | ADS movement speed -50%, as a combat-config parameter | **done** |
| 7 | Realistic (not cartoony) blood splatter | **done** |
| 8 | Distance-attenuated, directional audio (max 100 m) | **done** |
| 9 | NPC death animations + 60 s corpse despawn; player stays dead until restart | **done** |
| 10 | New photorealistic adventurer skin for the player model | **done** |

## Results

### Task 3 — settings menu with persisted sensitivity and keybinds — DONE

`build_weapons_and_combat.py` gained `build_settings_savegame()`, which builds
`/Game/Weapons/BP_Settings` (parent `unreal.SaveGame`, graphless) holding
`MouseSensitivity` (real) and `Binds` (array of `Key`), plus a `BIND_VARS` tuple
fixing the index-for-index contract between `Binds[i]` and seven new `Key`
variables on `BP_WeaponComponent` (KeyFire/Aim/Sprint/Switch/Drop/Pickup/Reload,
CDO defaults equal to the old literals). Every `_set(node, "Key", LITERAL)` in
`_author_wc_tick` / `_author_sprint` / `_author_ads` is now a getter driving the
pin, and `_same()` gained an `FKey` arm ahead of its `to_tuple` arm because
`to_tuple()` is `()` for every key and would have compared equal unconditionally.
`build_graphics_menu.py` declares `Settings/MenuPage/MenuRow/Capturing/KeyPool/
BindLabels` on the HUD, loads-or-creates the save at BeginPlay (refilling `Binds`
when its length isn't 7), makes the title panel two keyboard-navigated rows
(NEW GAME / SETTINGS — `LeftMouseButton` dropped from `START_KEYS`), and adds a
nine-row settings page (sensitivity stepped by Left/Right and `FClamp`ed to
MIN..MAX, the seven binds, BACK). Rebinding runs a `ForEachLoop` over `KeyPool`
in the *true* arm of a `Branch` on `Capturing` with activation in the *false*
arm, so the Enter that arms a capture is in a different frame and a different
path — that was the trap. Saves to slot `OtherworldSettings` on every change and
pushes sensitivity plus all seven keys onto `BP_WeaponComponent` each `DrawHUD`
frame behind an `IsValid(Settings)` guard.

Files: both builders, both verifiers, `forest_generator/asset_sources.py` (note
only), `CLAUDE.md` (new "The settings screen" section).

**Verifiers: weapons 439/439 (was 383, +56, including a write-a-slot-and-read-it-
back round trip proving the FKey array serialises); HUD 102/102 (was 60, +42);
level 170/170 unaffected. Both builders clean; `--game --seconds 30` gives 0
blueprint runtime errors, 0 Accessed None, 10 NPC spawns.**

Deviations and notes: (1) a sixth HUD variable `BindLabels` was added beyond the
brief — it collapses the seven bind rows into one `ForEachLoop` with two
`DrawText`s instead of fourteen hand-placed draws; (2) navigation keys (arrows,
Enter, Space) are deliberately excluded from `KEY_POOL` so a bind can never lock
the menu shut, and the verifier asserts it; (3) an armed capture has no explicit
cancel — the next key in the pool takes it, so it is always escapable but never
cancellable; (4) the death menu's `R` restart is separate from the now-rebindable
reload key, so rebinding reload does not move restart.

### Task 4 — sniper ADS scope overlay — DONE

`build_ui_art.py` gained `scope_overlay()`, drawing `T_UI_Scope` (1024 sq., 2x
supersampled): an opaque black field with a circular hole punched through its
*alpha* (`putalpha` over an ellipse mask — `ImageDraw` replaces colour, not
alpha, so filling an ellipse with alpha 0 over black leaves black, not a hole),
a ringed inner shadow at the rim, and an etched duplex reticle — four fat posts
tapering to a fine cross, mil-dots every 0.11 r with a long tick every fifth,
drawn as a blurred white halo under a black core so it reads against foliage and
sky, clipped to the hole. `build_weapons_and_combat.py` declares `Scoped` (bool)
on `BP_WeaponItem`, defaulted from a new `scoped=` column only the sniper sets;
`build_weapon()` refuses a weapon that is scoped but does not zoom, because the
HUD fade divides by `AdsZoom - 1`. `build_graphics_menu.py` gained
`_author_scope()` and a branch in `_author_reticle`: under the existing
`AimValid` gate a Branch on `Scoped` sends the scoped arm to two black
`DrawRect` strips plus `T_UI_Scope` drawn as a square of viewport *height*
between them, and the unscoped arm to the five crosshair ticks — so the two
centre sights can never double up. The square keeps the hole circular
(stretching across 16:9 would flatten it to an ellipse); the strips keep the
corners of the world hidden, their width `FMax(cx - cy, 0)` because a portrait
viewport asks for a negative width and `DrawRect` renders that backwards rather
than not at all. Everything fades on one alpha,
`FClamp((BaseFOV/CurrentFOV - 1) / (AdsZoom - 1), 0, 1)` — deliberately not the
`Aiming` flag, which would snap the glass on a frame before the camera moved.

Files: `build_ui_art.py`, `build_weapons_and_combat.py`, `build_graphics_menu.py`,
both verifiers, `forest_generator/asset_sources.py` (note only), `CLAUDE.md`.

**Verifiers: HUD 117/117 (was 102, +15); weapons 446/446 (was 439, +7). Builders
clean; `--game --seconds 30` gives 0 blueprint runtime errors, 0 Accessed None,
0 script warnings, 10 NPC spawns.**

Notes: (1) the per-weapon flag is `Scoped` rather than a test on `AdsZoom`, since
glass and zoom factor are separate facts; the verifier asserts the sniper is the
only scoped weapon and that every scoped weapon zooms. (2) `_author_reticle` now
returns four exec tails. (3) Existing HUD counts moved: DrawRects 5 -> 7,
DrawTextures 19 -> 20, driven-`ScreenW` textures 3 -> 4. (4) The `-game` smoke run
takes no input, so the scope draw itself is covered structurally by the verifier,
not at runtime. (5) Pre-existing, untouched: `verify_shotgun_and_health.py` fails
on a missing `BP_ShotgunComponent`, a dead verifier for an asset
`retire_old_assets()` removed.

### Task 5 — per-weapon recoil, as a combat-config parameter — DONE

**The structure.** `COMBAT`, a frozen `CombatConfig` dataclass at the top of
`build_weapons_and_combat.py`, is the single home for global combat tuning:
lethality (`start_health`, `head_multiplier`, `limb_multiplier`),
sprint/stamina (4), ADS (`ads_zoom_irons/scope`, `ads_interp_speed`,
`ads_spread_scale`), look (`mouse_sensitivity_default/min/max/step`,
`ads_sens_compensation`) and recoil (4) — 20 fields. A Python object rather
than a UserDefinedStruct or DataAsset, for two reasons stated in the file:
every one of these numbers is a *pin literal* baked into a compiled graph, and
nothing under `Content/` is committed — so an in-editor edit to a generated
asset is erased by the next builder run and was never in the repo, meaning
"tunable without re-running Python" is a promise this architecture cannot keep.
Frozen, so no builder can rewrite a value the verifier then asserts. Migration
was total: all sixteen old module constants are deleted, `build_graphics_menu.py`
and both verifiers read `COMBAT.*`, and the verifier asserts via `hasattr` that
none of the old names survive, so there is no stale second copy. Per-weapon
numbers stayed in `_weapon_specs()` (also asserted). **A designer tunes combat by
editing `COMBAT` and re-running the builder.**

**Recoil.** New `recoil=` column -> `RecoilPitch` on `BP_WeaponItem`: sniper
2.4 deg, shotgun 2.2, rifle 0.85, SMG 0.45, pistol 0.30 — read against fire
interval that is 6 deg/s sustained for the AR vs 5 for the SMG, so the AR is the
one that walks off target. `_author_recoil_kick` charges `RecoilDebt` /
`RecoilYawDebt` and moves the view; `_author_recoil_recovery` runs first in Tick
and `FInterpTo`s both to zero at speed 7.0, handing back only
`recoil_recovery_fraction` 0.7 of each step — the debt always settles, but 30% of
every kick stays in the aim, which is what makes a burst climb. Horizontal is
+/-0.35x the pitch, drawn per shot. ADS steadies it to x0.65. Shared
`_author_turn_view` uses **SetControlRotation** — never `AddPitchInput` /
`AddControllerPitchInput`, which would multiply by the deprecated
`InputPitchScale` that task 3's sensitivity slider drives; the verifier bans
those titles outright. Roll is carried through, not zeroed. Two evaluation-order
traps handled and commented: `RandomFloatInRange` is pure, so the draw is made
once into `RecoilYawKick` and read back (verifier asserts exactly one reader),
and recovery turns the view *before* writing the debts because a pure give-back
read after the `Set` would compute zero.

Files: `build_weapons_and_combat.py`, `build_graphics_menu.py`, both verifiers,
`CLAUDE.md` (new "Where to tune combat, and recoil" section).

**Verifiers: weapons 480/480 (was 446, +34, including ordering assertions read
off the built CDOs, not off the table); HUD 117/117; level 170/170. Builder
clean; `--game --seconds 35` gives 0 blueprint runtime errors, 0 Accessed None,
0 script warnings, 10 NPC spawns.**

Notes: (1) SelectFloat count moved 3 -> 4. (2) The no-input `-game` run never
fires, so the recovery gate never opens; per CLAUDE.md's "a gate that never opens
looks identical to one that works" rule the positive case was proved with a
temporary probe — 1232 frames of smooth two-axis recovery holding the seeded 3:5
ratio to four figures — then the probe was removed and its absence verified.
(3) The `-game` run needs >=30 s on this machine; at 20 s NPCs have not spawned.
(4) Sprint/stamina and hit-zone multipliers were pulled into `COMBAT` beyond the
literal ask; footsteps, pickup radii, drop economy and respawn timings were
deliberately left out as not combat-feel.

### Task 6 — ADS movement speed -50%, as a combat-config parameter — DONE

`CombatConfig` gained `ads_move_speed_scale: float = 0.50` in the
`# --- aiming down the sights ---` group (21 fields now). `_author_ads` applies
it as a second `MaxWalkSpeed` write, layered after the one `_author_sprint`
already makes earlier in the same Tick. Task 5's reordering does not disturb
this: `_author_recoil_recovery` now runs first in Tick but only touches the
control rotation, so the sprint -> ADS order is unchanged, and sprint's
unconditional `Sprinting ? 900 : BaseSpeed` write is why releasing the aim key
needs no code at all — the first frame the ADS branch does not run, the player is
already back at `BaseSpeed`. The write is gated on
`AND(NOT Sprinting, IsValid(Held))`: the same "not sprinting" pin the zoom is
gated on, so the two `MaxWalkSpeed` writes can never disagree about a frame
(without it, starting a sprint mid-ADS would have been ~200 ms of 300 cm/s
before the zoom finished easing out).

**It eases rather than snapping**, on the scope overlay's fade curve node for
node: `MaxWalkSpeed = BaseSpeed * Lerp(1, 0.5, FClamp((BaseFOV/CurrentFOV - 1) /
(AdsZoom - 1), 0, 1))`. The division by `AdsZoom - 1` — which the task-3
sensitivity slowdown deliberately does *not* do — is what makes full ADS exactly
half speed on the 4x scope and on 1.5x irons alike; the raw ratio would give
0.83x on irons and 0.63x on the scope and never the number asked for, which is
right for a mouse and wrong for legs.

**Proved at runtime** with a temporary probe forcing `Aiming` off
`Sin(GetTimeSeconds)`: held, it converged on 300.024 cm/s against a 600 cm/s base
at FOV 60.0016 — 0.50004x, the residual being the interpolation's tail; toggled
at 12 rad/s, 3446 frames tracked the FOV up and down through four cycles with no
second code path and 0 Accessed None with the ADS gate open. The probe was
removed by restoring and re-running the builder, and the verifier now permanently
asserts `Aiming` is driven by `Get KeyAim` with no clock or literal standing in
for it, and that no `PrintString` survives in the component's Tick.

Files: `build_weapons_and_combat.py`, `verify_weapons_and_combat.py`, `CLAUDE.md`.

**Verifiers: weapons 499/499 (was 480, +19); HUD 117/117; level 170/170. Builder
clean; `--game --seconds 35` gives 0 blueprint runtime errors, 0 Accessed None,
0 script warnings, 10 NPC spawns.**

Notes: (1) a verifier bug was found and avoided — `num_pin(n, "Min") or -1.0`
reads a genuine `0.0` as missing, so the new clamp assertion uses an explicit
`is not None` helper; (2) the `-game` world clock is heavily dilated on this
machine (35 s wall advanced world time ~1 s), which is why the probe's forcing
frequency had to be raised; (3) no per-weapon column — "shouldering a gun slows
you down" is a fact about shoulders, same reasoning as `recoil_ads_scale`.

### Task 7 — realistic blood splatter — DONE

The old `BP_BloodSplash` read as a cartoon for three independent reasons, all
confirmed in the asset rather than guessed: `M_Blood` was *emissive*
`(0.55, 0.01, 0.01)` over a saturated base, so droplets glowed instead of being
lit; `scale = 0.55 + Jitter + 2.6*sin(pi*Age/0.7)` inflated the 0.11 core sphere
to ~0.35 — a 35 cm swelling ball of blood; and the *actor* was animated, not the
spheres, so all ten flew as one rigid cone at a single 130 cm/s under a stylised
260 cm/s^2 with no drag.

Niagara was probed before committing and is genuinely unreachable from Python in
5.8: `NiagaraSystem` exposes neither `emitter_handles` nor `exposed_parameters`,
and `UNiagaraExternalSystemEditorUtilities` (`AddEmitter`/`AddModule`/
`SetStackInputData`) is C++ statics with no `UFUNCTION`, so duplicating
`/Niagara/DefaultAssets/Templates/Systems/DirectionalBurst` would give an asset
nothing could retune; Cascade's editor module and every `ParticleModule*` type
are gone in 5.8. The replacement therefore stays on the project's existing
component technique but makes it physical: 19 droplets (14 of spray in a 34 deg
seeded cone plus 5 slow fine ones that hang at the wound), 1-3 cm across,
`M_Blood` now lit and not emissive at linear `(0.150, 0.014, 0.012)` ~ sRGB
`#6C2825` with roughness 0.22 so the wet highlight is what reads at night, each
flying the closed form of `dv/dt = g - 3.6v` under real `g = 980` — two scalars
per frame for the whole burst, one multiply-add per droplet in a `ForEachLoop`,
scale flat then cut over the last 0.14 s of a 0.45 s life. Each droplet carries
its own launch velocity in its build-time relative location over 100, which makes
the baked number read as m/s, removes any parallel table that could fall out of
step with `GetComponentsByClass` ordering, and keeps the pre-`BeginPlay` frame a
1-9 cm clump at the wound instead of a nine-metre sphere. `_author_impact` sizes
the actor by `clamp(Damage/24, 0.65, 1.6)`.

Two traps recorded: `build_materials()` skipped any material that already
existed, so a changed recipe never landed — it now re-authors in place via
`delete_all_material_expressions` + `delete_unused_expressions`, keeping every
reference alive; and the **A pin of the Kismet math nodes will not hold a
literal** (`set_pin_value` reports success, the pin reads back empty, and it
compiles as zero), so the A term is written `(e^(-kt)-1)/-k` and every constant
lives on a B pin.

Files: `build_weapons_and_combat.py`, `verify_weapons_and_combat.py`, `CLAUDE.md`.

**Verifiers: weapons 520/520 (was 499, +21); HUD 117/117. Builder clean;
`--game --seconds 35` gives 0 blueprint runtime errors, 0 Accessed None, 0 script
warnings, 10 NPC spawns.** Proved at runtime with a temporary per-droplet
`PrintString` and a forced spawn: 1236 samples over 19 droplets on 66 frames,
final radii spanning 18.5 to 146.4 cm (an 8x separation, which the old version
had none of) and Z going negative under gravity; both probes removed and their
absence asserted permanently by the verifier.

Deviations and open items: (1) damage-scaled spray was optional in the brief,
included because it was two nodes on an existing pin; (2) no before/after still
was rendered — the effect lasts 0.45 s and a real capture needs PIE timing;
(3) a deferred blood decal on the surface behind the target was deliberately left
out as scope. **Worth a look in-game:** the effect is now deliberately dark and
non-emissive, which is what stops it looking like a cartoon, but it will be
considerably subtler at night than the old glowing red — if it reads as too
subtle the dial is `BLOOD_BASE_COLOUR` and `BLOOD_ROUGHNESS`, not emissive.

### Task 8 — distance-attenuated, directional audio — DONE

**Diagnosis.** Every sound was already played correctly: five
`PlaySoundAtLocation` call sites across three Blueprints (gunshot and dry click
at the muzzle, reload clack at the weapon, footfall at the owner, growl and melee
thud at the pawn), no `PlaySound2D` anywhere, all 22 samples already mono. What
was missing was the one thing that makes any of it audible as placed: not one of
the 22 `SoundWave` assets had `AttenuationSettings`, and **a `USoundBase` with
none is not attenuated by some default** — distance falloff and spatialisation
are parsed out of the attenuation settings and out of nothing else, so every
sound played at full volume, dead centre, from anywhere on the 200 m map.

**Built.** Three `USoundAttenuation` assets in `/Game/Audio` from a new frozen
`AttenuationProfile` dataclass and `build_sound_attenuations()`: `A_Att_Gunfire`
(full volume to 2 m, inaudible past 100 m — the brief's whole allowance, spent on
the loudest thing in the game — plus the engine's distance low-pass, 20 kHz ->
2.5 kHz, so distant gunfire is a thump not a crack), `A_Att_Creature` (40 m:
growls, roars, melee thuds) and `A_Att_Foley` (15 m: footsteps, dry click, reload
clacks). All three `NATURAL_SOUND` (the dB curve, -60 dB at the edge), spherical,
`attenuate` and `spatialize` on, `SPATIALIZATION_Default` — the mixer's own
panner, which is what makes it directional; HRTF was rejected as a request for a
binaural plugin that is not installed, where the mixer falls back to the panner
anyway. `apply_attenuation()` sets the profile **on the asset, not on the node**:
the pin would work but is five chances to miss one, and the sweep walks the two
audio folders and raises on a wave it has no profile for, so a sound added later
stops the build instead of shipping audible from everywhere. Nothing stayed 2D —
no menu sounds exist, and the third-person weapon sits ~1.5 m from the listener
where the gunfire curve is still 1.0. Player footsteps share the foley profile
with the NPCs' and attenuate over the ~3 m camera boom; the alternative is a
second footstep path whose only job is to be wrong about where the player's feet
are.

Files: `build_weapons_and_combat.py`, `verify_weapons_and_combat.py`,
`generate_forest_level.py` and its generated verifier, `asset_sources.py` (note),
`CLAUDE.md` (new "Distance and direction" section).

**Verifiers: weapons 609/609 (was 520, +89); level 172/172 (was 170, +2); HUD
117/117. Builder clean; `--game --seconds 35` gives 0 blueprint runtime errors,
0 Accessed None, 0 script warnings, 10 NPC spawns.** The new checks assert each
profile's falloff, radius, dB, curve, shape and spatialisation; radius + falloff
<= 100 m for all and exactly 100 m for gunfire; a footstep carrying under a
quarter as far; a folder sweep proving all 22 waves carry a profile; and a
Blueprint sweep finding every node with a `Sound` pin and failing on any that is
2D, unwired, or carries a per-call override.

**Proved at runtime.** The strongest check reads `USoundBase.max_distance` — not
a field the builder writes; the engine caches it off whatever attenuation
resolves — giving 10000 / 4000 / 1500 per sound, end-to-end proof the link took.
From the other side a temporary probe asked `AreAnyListenersWithinRange` in a
live `-game` world: true at 5 m and false at 16 m against the 15 m foley reach,
true at 90 m and false at 105 m against the 100 m gunfire reach, agreed by all
eleven footstep components. Probe removed; note that deleting and rebuilding
`BP_FootstepComponent` dropped the graph nodes but left the `Probed` member
variable behind, and the verifier now asserts both are gone.

Two traps recorded in CLAUDE.md: `dBAttenuationAtMax` is
`d_b_attenuation_at_max` in Python; and `AreAnyListenersWithinRange` is
**impure** — left off the exec chain the compiler prunes it and the pin reads as
the default `false`, which looks exactly like "nothing is audible anywhere".

Deviations: (1) three profiles rather than one, asserted small (<= 4) by the
verifier; (2) air absorption on gunfire only is slightly beyond the literal ask —
one flag and two radii, and it is what makes 100 m gunfire sound 100 m away;
(3) the melee thud sits with the creature profile, not foley; (4) `/Game/Audio`
still has no `AssetSource` entry of its own, only a note on the
`Content/Weapons` entry.

### Task 9 — death collapse, 60 s corpses, player stays down — DONE

**Diagnosis.** Nothing had a death animation and nothing left a body. A wanderer
at 0 HP was counted, spawned a replacement and was `K2_DestroyActor`'d on the
same frame. The player at 0 HP ran `DisableMovement ->
PlaySlotAnimationAsDynamicMontage(MM_Death_Front_01) -> Delay 2.2 s -> pause`.
The asset context was the whole story: Meshy generates a walk and a run and
nothing else, and **Epic's own `MM_Death_*` set is six one-second hit reactions,
not collapses** — measured off the assets, every one ends with the pelvis at
83-88 cm and both feet on the floor after staggering 1.5-2 m backwards. That is
exactly "he gets up right away": the montage ended at 1.1 s, the locomotion state
machine underneath took the pose back, and the 2.2 s pause froze a standing man.
The animation route was tried first and disproved — retargeting the death clip
put the wendigo's hips at z=118 of a 129 standing height — then reverted in full.

**Route: physics ragdoll**, which costs no asset and which the rigs already
support — `PA_Mannequin`, `SKM_Zombie01_PhysicsAsset` and
`SKM_Wendigo01_PhysicsAsset` all exist and are not optional, since
`install_hit_zones` reads the head/limb tables off those bodies.

**Built.** One shared subgraph `_author_death_collapse`, walked into by both arms
of the death branch: `DisableMovement -> Capsule.SetCollisionEnabled(NoCollision)
-> Mesh.SetCollisionProfileName("Ragdoll") -> Mesh.SetAllBodiesSimulatePhysics`.
The capsule, not the mesh, is what blocks the player and what pellets trace
against, so switching it off is both halves of "a corpse is not in the way".
`SetAllBodiesSimulatePhysics`, never `SetSimulatePhysics` (not a UFunction on
`SkeletalMeshComponent`; the `PrimitiveComponent` one would simulate a single
creature-shaped brick). `_author_corpse` replaces the old destroy with
`GetController -> IsValid? -> DestroyActor(controller) -> Owner.SetLifeSpan(60)`.
The controller is destroyed rather than stopped because the chase, melee and
growls are one self-re-entering loop on it that never consults health — and
destroying an `AController` unpossesses on the way out, so it does not leak one
controller per kill. `SetLifeSpan` rather than a `Delay`, which would be a latent
action on a component belonging to the actor it waits to destroy. `GetController`
rather than the `Controller` member, which is not `BlueprintReadOnly`.
`_author_player_death` is now only `Delay 2.2 s -> PlayerDead -> pause`; the body
stays down because there is no montage left to blend out of, and the pause stops
physics too. The HUD's floating bar gained a `NOT Dead` term — a corpse was shot
a moment ago by definition, so the recency window put an empty bar over every
body for five seconds.

Files: `build_weapons_and_combat.py`, `build_graphics_menu.py`, both verifiers,
`CLAUDE.md`. `asset_pipeline/build_retarget.py` was edited and fully reverted.

**Verifiers: weapons 625/625 (was 609, +16); HUD 118/118; level 172/172. Builders
clean; `--game --seconds 35` gives 0 blueprint runtime errors, 0 Accessed None,
0 script warnings, 10 NPC spawns.**

**Proved at runtime** with a temporary clock forcing `Health = 0` on the ten
placed wanderers at t=2 s and the player at t=12 s, `CORPSE_SECONDS` compressed
to 6: all ten died at t=2.01 and stopped ticking at t=8.00 — 6.00 s exactly —
while ten replacements ran on; head heights fell 198-322 cm, one from 266.8 to
2.0. The player's head sat at 151.9 cm for twelve seconds and was at 1.1 cm on
the last frame before the pause, 2.20 s after death. Wall-clock tracked
world-clock at 1.00x through ten simultaneous ragdolls. Probe removed, 60.0
restored, absence asserted permanently by a new Health-writer check.

Notes: (1) a first probe run was invalid and is worth recording — killing every
wanderer on a clock kills each replacement on its first tick, producing 31,200
actors and 400 ms frames; the gate is `NpcId <= 10`. (2) The `-game` world clock
is only dilated by `-forcelogflush`; run without it, world time tracks wall time
1:1. (3) `FullBodySlot` is kept and still asserted though nothing plays into it.
(4) **Unresolved, needs one look in-game:** how the player's ragdoll reads on
camera — the spring arm stays on the standing capsule while the body collapses at
its feet, which should be fine at a 2 s glance before the menu.

### Task 10 — photorealistic adventurer skin for the player — DONE

**The route, and why the preferred one does not exist.** Option (i) — put a
generated mesh on `SK_Mannequin` so nothing downstream moves — was probed before
a credit was spent and is unreachable from this toolchain on three independent
counts: Meshy's rigging endpoint takes only a mesh and a height, with no skeleton
parameter, so it always returns its own 24-bone Mixamo-named rig (no fingers, no
twist bones); the FBX importer *merges* an incoming bone tree into the skeleton
it is given, and 24 differently-named bones do not merge into `SK_Mannequin`'s
161; and UE 5.8 exposes no skin transfer to Python (`IKRetargetBatchOperation`
handles animation assets only, `IKRetargeterController` has no mesh export, and
the editor's "retarget skeletal mesh" button has no scripted equivalent). So the
animation was moved to the mesh instead — exactly what the monsters already do —
and the feared blast radius turned out to be small, because `hit_zones()` already
derives its tables from whatever mesh a character wears, the ragdoll is
`SetAllBodiesSimulatePhysics` on that mesh's physics asset, and
`fix_retargeted_abp()` already re-points the upper-body branch filter.
**The route was proved end-to-end with zero credits first**, by temporarily
wearing the existing zombie as the player: builder clean, verifier 636/636.

**Prompt and parameters.** `catalog.ADVENTURER` — a modern-era human monster
hunter, weathered face with stubble, worn waxed canvas field jacket, low-profile
chest rig, reinforced trousers in scuffed boots, fingerless gloves, mud-stained
and blood-flecked, no backpack, A-pose, photorealistic 4k — at
`height_meters=1.80` (Quinn's, so the retargeted stride needs no scale
correction), `target_polycount=30000`, `4k`, `a-pose`, `meshy-7.1`, deliberately
matching the monsters. No backpack and no long coat were asked for because the
boom sits 260 cm behind the player and because Meshy skins loose geometry to the
nearest bone. **40 credits, one run, no retries.** Result is good — hooded field
jacket, chest rig, gloves, cargo trousers, worn boots, bearded face.
**Render: `Saved/Renders/SKM_Adventurer01.png`.**

Files: `asset_pipeline/catalog.py` (+`ADVENTURER`, `CHARACTERS`),
`fetch_monsters.py`, `asset_pipeline/build_retarget.py` (+`AIM_SOURCES`, so the
two ready poses retarget too — 23 clips per creature now, not 21),
`build_weapons_and_combat.py` (+`PlayerSkin`/`SKIN_QUINN`/`SKIN_ADVENTURER`/
`player_skin()`/`wear_skin()`/`_BoneGrip`), `verify_weapons_and_combat.py`,
`asset_sources.py`, `CLAUDE.md` (new *The player's body* section), new
`Scripts/dev/render_character.py`.

**Verifiers: weapons 636/636 (was 625, +11); HUD 118/118; level 172/172. All
builders clean; `--game --seconds 35` gives 0 blueprint runtime errors, 0
Accessed None, 0 script warnings, 10 NPC spawns.** Proved at runtime in a live
`-game` session: **animates** — driven by `A_Adventurer01_ABP_Unarmed_C`, and
over 14 s of shuttling at up to 600 cm/s the foot gap swept -7.2..+16.9 cm and
crossed zero; **ragdolls** — head 67.1 cm above the actor standing, -78.0 cm on
the frame the death pause froze the world, a 145 cm collapse; **hit zones** —
live traces gave Head x1.5, both forearms and both legs x0.75, chest x1.0.

Notes and open items: (1) **the honest cost is the hand** — a 24-bone rig cannot
close a fist, so the adventurer holds its weapon with an open hand; that is a
property of Meshy's rigger, not of the integration, and no asset in the project
would fix it. (2) The weapon attaches to the `RightHand` *bone*, not a socket:
Python cannot mint one (`SkeletalMeshSocket`'s names are read-only), so
`_BoneGrip` stands in; `_grip_rotation` solves for the barrel direction, and
measured, no hand axis is the aim — the verifier now asserts that inverted fact
instead of the mannequin's "+Y is the weapon axis". The cost is position only:
the weapon hangs off the wrist rather than mid-palm. (3) `player_skin()` falls
back to the mannequin all-or-nothing — a partly resolved skin would stand in its
bind pose forever. (4) **Build order is now load-bearing**: `build_retarget.py`
wipes and rebuilds `Anims/<Creature>/`, so `build_npc_blueprints.py` must follow
it or the wanderers point at dead anim classes; that surfaced as 4 level-verifier
failures and was fixed by re-running the NPC builder. (5) Two `-game` traps
recorded in CLAUDE.md: a `-game` process listens on `Saved/uepy` and can be
questioned live, but `EditorLevelLibrary.get_game_world()` SIGSEGVs there — use
`unreal.find_object`; and the render script's world context is not optional on
`create_render_target2d`/`export_render_target`. (6) **Worth one look in-game:**
the jacket's hip-length coat tail is skinned to the hips/thighs and may scissor
at a full run, and the open hand is most visible down the sights. (7) The Meshy
key was read only from `assets/.env` (still 600) and never printed or written
anywhere; `git grep` over the tracked tree finds nothing.

---

## Run summary

All eight tasks landed. Final verifier state:

- `verify_weapons_and_combat.py` — **636/636** (383 at the start of the run)
- `verify_graphics_menu.py` — **118/118** (60 at the start)
- `verify_Lvl_Forest_200m.py` — **172/172**
- `uepy.py --game --seconds 35` — 0 blueprint runtime errors, 0 Accessed None,
  0 script warnings, 10 NPC spawns

Pre-existing and deliberately untouched: `verify_shotgun_and_health.py` fails on
a missing `BP_ShotgunComponent`, a dead verifier for an asset
`retire_old_assets()` removed. It should be deleted or rewritten.

### Worth a look in-game (nothing blocking)

1. The new blood is dark and non-emissive by design — considerably subtler at
   night than the old glow. Dials: `BLOOD_BASE_COLOUR`, `BLOOD_ROUGHNESS`.
2. The player's ragdoll: the spring arm stays on the standing capsule while the
   body collapses at its feet.
3. The adventurer holds his weapon with an **open hand** — Meshy's rigger returns
   24 bones and no fingers, so no asset in the project can close a fist. Most
   visible down the sights.
4. The weapon hangs off the wrist rather than mid-palm (bone attachment, since
   Python cannot mint a socket).
5. The jacket's hip-length coat tail is skinned to the hips/thighs and may
   scissor at a full run.

### Structural notes

- **Build order is now load-bearing**: `build_retarget.py` wipes and rebuilds
  `Anims/<Creature>/`, so `build_npc_blueprints.py` must run after it.
- `COMBAT` in `build_weapons_and_combat.py` is the single home for combat tuning
  (21 fields). It is a Python dataclass, not an editor-editable DataAsset,
  because nothing under `Content/` is committed — an in-editor edit would be
  erased by the next builder run.
- Niagara cannot be authored from Python in UE 5.8 (the emitter-stack API has no
  `UFUNCTION`), which is a standing ceiling on VFX work in this project.
- Latent bug found and fixed in passing: `build_materials()` skipped any material
  that already existed, so changed material recipes silently never landed.

Nothing has been committed. The working tree holds all eight tasks' changes.
