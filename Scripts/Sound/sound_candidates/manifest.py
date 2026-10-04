"""What is cut from what: the table the candidate cutter runs.

Every row names an output under `assets/generated/sound_candidates/` and the
file or files in `assets/cache/sounds/` it is cut from. Paths are globs,
because the packs' own folder names are long and one of them changes with
the pack's version.

A row is `(op, out, source, options)`:

  each    every file the glob finds is one take: trimmed, levelled, written
          as `<out>_NN`. `limit` keeps the first N.
  split   one file holding several takes, cut apart at its silences.
  shot    a gunshot: `seconds` from its onset, with a long fade.
  loop    a bed that already loops: written whole, never trimmed.
  mkloop  a recording that does not loop: its head cross-faded into its tail.
  design  layers of other sounds, each repitched and summed. These are
          guesses made without listening and are named `designed_*`.

`stereo` rows stay stereo: beds, drones and stingers, which play flat. All
the rest are mono, because a stereo wave cannot be placed in the world.
"""

NOX = "nox/Essentials_Series_NOX_SOUND"
FEET = f"{NOX}/Footsteps_Essentials_NOX_SOUND"
VOICE = f"{NOX}/Voices_Essentials_NOX_SOUND/Voice_Essential_Male"
NATURE = f"{NOX}/Nature_Essentials_NOX_SOUND"
GUNS = "firearms/Prepared SFX Library"
KENNEY = "kenney"
OGA = "opengameart"
SON = "sonniss"

# One-shot levels. Automatics are cut quieter, as the first set was: nine SMG
# shots overlapping at 0.95 is distortion.
FOLEY = 0.50
HIT = 0.85
VOX = 0.80

WEAPONS = (
    # Near takes for the gun in the player's hands, mid takes for the same
    # gun heard from across the forest. The Nova is a pump action, which the
    # Mossberg 190 the first set used is not.
    ("shot", "weapons/shotgun_near", f"{GUNS}/Nova/O_21P.wav", dict(seconds=2.2, peak=0.95)),
    ("shot", "weapons/shotgun_far", f"{GUNS}/Nova/O_17P.wav", dict(seconds=2.5, peak=0.95)),
    ("shot", "weapons/shotgun_alt_near", f"{GUNS}/Model 12/K_22P.wav", dict(seconds=2.2, peak=0.95)),
    ("shot", "weapons/pistol_near", f"{GUNS}/1911/A_42P.wav", dict(seconds=1.4, peak=0.85)),
    ("shot", "weapons/pistol_far", f"{GUNS}/1911/A_34P.wav", dict(seconds=2.0, peak=0.85)),
    ("shot", "weapons/smg_near", f"{GUNS}/Carl Gustav M45/G_31P.wav", dict(seconds=0.8, peak=0.55)),
    ("shot", "weapons/smg_far", f"{GUNS}/Carl Gustav M45/G_20P.wav", dict(seconds=1.2, peak=0.55)),
    ("shot", "weapons/rifle_near", f"{GUNS}/AK-47/C_28P.wav", dict(seconds=1.1, peak=0.68)),
    ("shot", "weapons/rifle_far", f"{GUNS}/AK-47/C_31P.wav", dict(seconds=1.6, peak=0.68)),
    ("shot", "weapons/sniper_near", f"{GUNS}/Mosin Nagant/M_21P.wav", dict(seconds=2.6, peak=0.95)),
    ("shot", "weapons/sniper_far", f"{GUNS}/Mosin Nagant/M_26P.wav", dict(seconds=3.0, peak=0.95)),
    ("each", "weapons/dry_fire_latch", f"{SON}/*Lock And Mechanism*/MECHLtch_Click*.wav", dict(peak=0.45)),
    ("each", "weapons/dry_fire_click", f"{KENNEY}/rpg-audio/Audio/metalClick.ogg", dict(peak=0.45)),
    ("each", "weapons/dry_fire_metal_latch", f"{KENNEY}/rpg-audio/Audio/metalLatch.ogg", dict(peak=0.45)),
)

FOOTSTEPS = (
    ("each", "footsteps/grass_walk", f"{FEET}/Footsteps_Grass/Footsteps_Grass_Walk/*.wav", dict(peak=FOLEY, limit=12)),
    ("each", "footsteps/grass_run", f"{FEET}/Footsteps_Grass/Footsteps_Grass_Run/*.wav", dict(peak=FOLEY, limit=10)),
    ("each", "footsteps/leaves_walk", f"{FEET}/Footsteps_Leaves/Footsteps_Leaves_Walk/*.wav", dict(peak=FOLEY)),
    ("each", "footsteps/leaves_run", f"{FEET}/Footsteps_Leaves/Footsteps_Leaves_Run/*.wav", dict(peak=FOLEY)),
    ("each", "footsteps/dirt_walk", f"{FEET}/Footsteps_DirtyGround/Footsteps_DirtyGround_Walk/*.wav", dict(peak=FOLEY)),
    ("each", "footsteps/dirt_run", f"{FEET}/Footsteps_DirtyGround/Footsteps_DirtyGround_Run/*.wav", dict(peak=FOLEY)),
    ("each", "footsteps/dirt_land", f"{FEET}/Footsteps_DirtyGround/Footsteps_DirtyGround_Land/*Land*.wav", dict(peak=FOLEY)),
    ("each", "footsteps/grass_rustle", f"{FEET}/Footsteps_Grass/Foley_Grass/*.wav", dict(peak=FOLEY, limit=6)),
)

AMBIENCE = (
    ("loop", "ambience/day_wind_forest", f"{NATURE}/**/Ambiance_Wind_Forest_Loop_Stereo.wav", dict(peak=0.5, stereo=True)),
    ("loop", "ambience/day_birds", f"{NATURE}/**/Ambiance_Forest_Birds_Loop_Stereo.wav", dict(peak=0.5, stereo=True)),
    ("loop", "ambience/night", f"{NATURE}/**/Ambiance_Night_Loop_Stereo.wav", dict(peak=0.5, stereo=True)),
    ("loop", "ambience/wind_calm", f"{NATURE}/**/Ambiance_Wind_Calm_Loop_Stereo.wav", dict(peak=0.5, stereo=True)),
    ("mkloop", "ambience/night_crickets_connecticut", f"{SON}/*East Coast America*/*Forest Crickets*.wav", dict(peak=0.5, stereo=True)),
    ("mkloop", "ambience/wind_grass_norway", f"{SON}/*Highlands of Norway*/AMBSwmp*.wav", dict(peak=0.5, stereo=True)),
    ("loop", "ambience/drone_eerie", f"{NOX}/Sample_A_Sound_Effect/Atmosphere_Drone_Hum_Eerie_Loop_Stereo.wav", dict(peak=0.4, stereo=True)),
)

FIRE = (
    ("loop", "fire/campfire_small", f"{NATURE}/**/Ambiance_Firecamp_Small_Loop_Mono.wav", dict(peak=0.6)),
    ("loop", "fire/campfire_medium", f"{NATURE}/**/Ambiance_Firecamp_Medium_Loop_Mono.wav", dict(peak=0.6)),
    ("loop", "fire/fire_big", f"{NATURE}/**/Ambiance_Fire_Big_Loop_Mono.wav", dict(peak=0.6)),
    ("mkloop", "fire/campfire_pine_branches", f"{SON}/*Campfire - Bonfire*/24 Campfire*.wav", dict(peak=0.6, seconds=40.0)),
)

PLAYER = (
    ("each", "player/pain", f"{VOICE}/**/Voice_Male_V1_Pain_Mono_*.wav", dict(peak=VOX, limit=8)),
    ("each", "player/hit", f"{VOICE}/**/Voice_Male_V1_Hit_Short_Mono_*.wav", dict(peak=VOX, limit=8)),
    ("each", "player/effort", f"{VOICE}/**/Voice_Male_V1_Effort_Mono_*.wav", dict(peak=VOX, limit=6)),
    ("each", "player/attack", f"{VOICE}/**/Voice_Male_V1_Attack_Short_Mono_*.wav", dict(peak=VOX, limit=6)),
    ("each", "player/gasp", f"{VOICE}/**/Voice_Male_V1_Breath_Gasp_Mono_*.wav", dict(peak=0.6)),
    ("each", "player/land", f"{VOICE}/**/Voice_Male_V1_Land_Mono_*.wav", dict(peak=0.6, limit=4)),
    ("each", "player/breath_fast", f"{VOICE}/**/Voice_Male_V1_Breath_Mouth_Fast_Sequence_Mono_*.wav", dict(peak=0.6)),
    ("each", "player/panting", f"{SON}/*Vox Hominis*/HMNBrth_Panting*.wav", dict(peak=0.6)),
)

MELEE = (
    ("each", "melee/swing", f"{OGA}/swishes-sound-pack/swishes/*.wav", dict(peak=0.6)),
    ("split", "melee/swing_thud", f"{SON}/*Melee Weapons*/SWSH_SWING IMPACTS*.wav", dict(peak=HIT, limit=10)),
    ("each", "melee/blade_swing", f"{SON}/*Melee Weapons*/METLFric_SWING SCRAPE*.wav", dict(peak=0.7)),
    ("split", "melee/punch_body", f"{SON}/*Cinematic Fight*/FGHTImpt_4 x Punch*.wav", dict(peak=HIT)),
    ("each", "melee/punch_heavy", f"{KENNEY}/impact-sounds/Audio/impactPunch_heavy_*.ogg", dict(peak=HIT)),
    ("each", "melee/soft_heavy", f"{KENNEY}/impact-sounds/Audio/impactSoft_heavy_*.ogg", dict(peak=HIT)),
    ("each", "melee/gore_smash", f"{SON}/*Halloween Game*/GORESplt*.wav", dict(peak=HIT)),
    ("each", "melee/blood_splat", f"{SON}/*Tower Defense*/WOODImpt_Hit Blood*.wav", dict(peak=HIT)),
)

IMPACTS = (
    ("each", "impacts/bullet_wood", f"{KENNEY}/impact-sounds/Audio/impactWood_heavy_*.ogg", dict(peak=0.7)),
    ("each", "impacts/bullet_wood_light", f"{KENNEY}/impact-sounds/Audio/impactWood_light_*.ogg", dict(peak=0.7)),
    ("each", "impacts/bullet_ground", f"{KENNEY}/impact-sounds/Audio/impactGeneric_light_*.ogg", dict(peak=0.7)),
    ("each", "impacts/axe_chop", f"{KENNEY}/rpg-audio/Audio/chop.ogg", dict(peak=HIT)),
    ("each", "impacts/axe_wood", f"{KENNEY}/impact-sounds/Audio/impactPlank_medium_*.ogg", dict(peak=HIT)),
    ("split", "impacts/stick_on_wood", f"{SON}/*Historical Weapons*/WEAPBlnt_Spear And Stick*.wav", dict(peak=HIT, limit=8)),
)

CREATURES = (
    ("each", "creatures/zombie/monster", f"{OGA}/monster-sound-pack-volume-1/**/[Mm]onster-*.wav", dict(peak=VOX)),
    ("each", "creatures/zombie/undead_death", f"{SON}/*Humanoid Creatures*/VOXReac*.wav", dict(peak=VOX)),
    ("each", "creatures/zombie/undead_breath", f"{SON}/*Humanoid Creatures*/HMNBrth*.wav", dict(peak=VOX)),
    ("each", "creatures/zombie/humanoid_exhale", f"{SON}/*Vox Bestiae*/CREAHmn*.wav", dict(peak=VOX)),
    ("each", "creatures/zombie/grim_pain", f"{SON}/*Vox Bestiae*/CREAEthr*.wav", dict(peak=VOX)),
    ("split", "creatures/zombie/troll_idle", f"{OGA}/big-scary-troll-sounds/troll-idle-noises_0.ogg", dict(peak=VOX)),
    ("each", "creatures/wendigo/werewolf_growl", f"{SON}/*Halloween Game*/CREABeast*.wav", dict(peak=0.9)),
    ("each", "creatures/wendigo/beast_pain_yell", f"{SON}/*Humanoid Creatures*/CREAMnstr*.wav", dict(peak=0.9)),
    ("each", "creatures/wendigo/orc_attack", f"{SON}/*Humanoid Creatures*/CREAHmn*.wav", dict(peak=0.9)),
    ("each", "creatures/wendigo/trex", f"{SON}/*Dinosaurs Vol. 1/*T Rex*.wav", dict(peak=0.9)),
    ("split", "creatures/wendigo/herbivore_roar", f"{SON}/*Dinosaurs Vol. 2/*Large Herbivore Roar*.wav", dict(peak=0.9, gap_ms=400.0)),
    ("each", "creatures/wendigo/deep_roar", f"{OGA}/cc0-deep-monster-roar/monster_roar.wav", dict(peak=0.9)),
    ("split", "creatures/wendigo/troll_roar", f"{OGA}/big-scary-troll-sounds/troll-roars_0.ogg", dict(peak=0.9)),
    ("each", "creatures/wendigo/death_whistle", f"{SON}/*Death Whistle*/*Distortion*.wav", dict(peak=0.9)),
    ("each", "creatures/wendigo/death_whistle_dry", f"{SON}/*Death Whistle*/*DryPitch*.wav", dict(peak=0.9)),
    # A scream over a body: the whistle is the wendigo's shriek, the growl
    # under it the chest it comes out of.
    ("design", "creatures/wendigo/designed_roar_a", None, dict(peak=0.92, layers=(
        (f"{SON}/*Halloween Game*/CREABeast*.wav", -3, 1.0),
        (f"{SON}/*Death Whistle*/*Distortion*.wav", -5, 0.7)))),
    ("design", "creatures/wendigo/designed_roar_b", None, dict(peak=0.92, layers=(
        (f"{SON}/*Humanoid Creatures*/CREAMnstr*.wav", -4, 1.0),
        (f"{OGA}/cc0-deep-monster-roar/monster_roar.wav", 0, 0.6)))),
    ("design", "creatures/wendigo/designed_roar_c", None, dict(peak=0.92, layers=(
        (f"{SON}/*Dinosaurs Vol. 1/*T Rex*.wav", 2, 1.0),
        (f"{SON}/*Death Whistle*/*DryPitch*.wav", -7, 0.6)))),
    # A man, slowed: the cheapest zombie there is, and three takes of it.
    ("design", "creatures/zombie/designed_groan_a", None, dict(peak=VOX, layers=(
        (f"{VOICE}/**/Voice_Male_V1_Effort_Mono_01.wav", -8, 1.0),))),
    ("design", "creatures/zombie/designed_groan_b", None, dict(peak=VOX, layers=(
        (f"{VOICE}/**/Voice_Male_V1_Pain_Mono_03.wav", -9, 1.0),))),
    ("design", "creatures/zombie/designed_groan_c", None, dict(peak=VOX, layers=(
        (f"{VOICE}/**/Voice_Male_V2_Effort_Mono_02.wav", -7, 1.0),))),
)

INVENTORY = (
    ("each", "inventory/cloth", f"{KENNEY}/rpg-audio/Audio/cloth[0-9].ogg", dict(peak=FOLEY)),
    ("each", "inventory/leather", f"{KENNEY}/rpg-audio/Audio/handleSmallLeather*.ogg", dict(peak=FOLEY)),
    ("each", "inventory/drop", f"{KENNEY}/rpg-audio/Audio/dropLeather.ogg", dict(peak=FOLEY)),
    ("each", "inventory/belt", f"{KENNEY}/rpg-audio/Audio/beltHandle*.ogg", dict(peak=FOLEY)),
    ("each", "inventory/knife_draw", f"{KENNEY}/rpg-audio/Audio/drawKnife*.ogg", dict(peak=FOLEY)),
    ("each", "inventory/backpack_pickup", f"{NOX}/Sample_A_Sound_Effect/Backpack_Small_Polyester_PickUp_Stereo.wav", dict(peak=FOLEY)),
    ("each", "inventory/backpack_drop", f"{NOX}/Sample_A_Sound_Effect/Backpack_Medium_Polyester_Drop_Stereo.wav", dict(peak=FOLEY)),
    ("each", "inventory/coat_pickup", f"{NOX}/Sample_A_Sound_Effect/Cloth_Coat_PickUp_Stereo.wav", dict(peak=FOLEY)),
    ("each", "inventory/cloth_move", f"{SON}/*Foley T-Shirt*/FOLYClth_ClothMovement*.wav", dict(peak=FOLEY)),
)

UI = tuple(
    ("each", f"ui/{name}", f"{KENNEY}/interface-sounds/Audio/{name}_*.ogg", dict(peak=0.5, limit=3))
    for name in ("click", "select", "back", "confirmation", "error", "open",
                 "close", "scroll", "switch", "toggle", "drop")
) + (
    ("each", "ui/rollover", f"{KENNEY}/ui-audio/Audio/rollover[1-3].ogg", dict(peak=0.4)),
)

STINGERS = (
    ("each", "stingers/death_whistle_drone", f"{SON}/*Death Whistle*/*Drone*.wav", dict(peak=0.6, stereo=True)),
    ("each", "stingers/noise_box_hit", f"{SON}/*Sinister Textures 4*/*.wav", dict(peak=0.7, stereo=True)),
    ("each", "stingers/trailer_boom", f"{SON}/*Trailer Booms*/*.wav", dict(peak=0.7, stereo=True)),
    ("each", "stingers/jumpscare_whisper", f"{SON}/*Halloween Game*/DSGNEthr*.wav", dict(peak=0.7, stereo=True)),
    ("each", "stingers/creature_swell", f"{SON}/*Halloween Game*/UIAlert*.wav", dict(peak=0.7, stereo=True)),
)

ROWS = (WEAPONS + FOOTSTEPS + AMBIENCE + FIRE + PLAYER + MELEE + IMPACTS
        + CREATURES + INVENTORY + UI + STINGERS)

# Previews of a layered bed, for listening only: the loops are 30 s each, and
# what matters is how they sit together. `(out, seconds, ((loop, gain), ...))`.
PREVIEWS = (
    ("ambience/preview_day_mix", 90.0, (("ambience/day_wind_forest", 1.0), ("ambience/day_birds", 0.6))),
    ("ambience/preview_night_mix", 90.0, (("ambience/night", 1.0), ("ambience/wind_calm", 0.5))),
    ("ambience/preview_night_mix_connecticut", 90.0,
     (("ambience/night_crickets_connecticut", 1.0), ("ambience/wind_calm", 0.5))),
)

# Where each pack came from and under what terms, keyed by its cache folder.
LICENCES = {
    "nox": ("Nox Sound, Essentials Series", "CC0",
            "https://nox-sound-design.itch.io/essentials-series-sfx-nox-sound"),
    "firearms": ("The Free Firearm Sound Library", "CC0",
                 "https://opengameart.org/content/the-free-firearm-sound-library"),
    "kenney": ("Kenney audio packs", "CC0", "https://kenney.nl/assets/category:Audio"),
    "opengameart": ("OpenGameArt packs", "CC0", "https://opengameart.org"),
    "sonniss": ("Sonniss GDC 2026 Game Audio Bundle",
                "Sonniss GDC licence (royalty-free, no attribution, NOT CC0)",
                "https://gdc.sonniss.com/"),
}
