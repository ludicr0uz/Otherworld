"""The second table: what is cut from the Sonniss 2016-2019 archive files and
from the Freesound previews. Same row shape as `manifest.py`, which explains it.

These fill what the first round left open: creature voices, gun handling,
blades and gore, eating, matches, wood, the forest by day and by night, a
tension bed, a heartbeat, darker menu sounds. The names do not repeat any of
the first table's, so a rating already given stays with its take.
"""

from sound_candidates.freesound_previews import NEEDS

A = "sonniss_archive"
VOX = 0.80
HIT = 0.85
BED = dict(peak=0.5, stereo=True)


def _bed(seconds=90.0):
    return dict(peak=0.5, stereo=True, seconds=seconds)


CREATURES = (
    ("split", "creatures/zombie/infected_vocal", f"{A}/2016/*INFECTED ZONE/ZombieVocal*.wav", dict(peak=VOX, limit=10)),
    ("each", "creatures/zombie/zombie_groan", f"{A}/2019/Glitchedtones - Zombie/*.wav", dict(peak=VOX)),
    ("split", "creatures/zombie/infected_bite", f"{A}/2016/*INFECTED ZONE/Bite*.wav", dict(peak=VOX, limit=4)),
    ("each", "creatures/zombie/monster_bite", f"{A}/2018/*Girardot - Monsters/Monster Bite*.wav", dict(peak=VOX)),
    ("each", "creatures/zombie/pain_death", f"{A}/2016/*Monsters/Monster_Pain_Death*.wav", dict(peak=VOX)),
    ("each", "creatures/zombie/struggle_grunt", f"{A}/2016/*Monsters/Monster_Struggle*.wav", dict(peak=VOX)),
    ("each", "creatures/zombie/creature_pain", f"{A}/2017/*CREATURES ZONE/*Pain*.wav", dict(peak=VOX)),
    ("each", "creatures/zombie/creature_attack", f"{A}/2017/*CREATURES ZONE/*Attack*.wav", dict(peak=VOX)),
    ("each", "creatures/zombie/six_monsters", f"{A}/2018/*6Monsters/*.wav", dict(peak=VOX)),
    ("each", "creatures/zombie/take_damage", f"{A}/2018/*Monster Within/*TakeDamage*.wav", dict(peak=VOX)),
    # The troll roars were the wendigo's best takes; these are a troll again,
    # from another library, with the hurt and the death the first one lacked.
    ("each", "creatures/wendigo/troll2_growl", f"{A}/2017/*Troll Monster*/*growl*.wav", dict(peak=0.9)),
    ("each", "creatures/wendigo/troll2_taunt", f"{A}/2017/*Troll Monster*/*taunt*.wav", dict(peak=0.9)),
    ("each", "creatures/wendigo/troll2_hurt", f"{A}/2017/*Troll Monster*/*hurt*.wav", dict(peak=0.9)),
    ("each", "creatures/wendigo/troll2_death", f"{A}/2017/*Troll Monster*/*death*.wav", dict(peak=0.9)),
    ("each", "creatures/wendigo/yeti_breathe", f"{A}/2018/*Yeti Monster/*breathe*.wav", dict(peak=0.8)),
    ("each", "creatures/wendigo/yeti_groan", f"{A}/2018/*Yeti Monster/*groan*.wav", dict(peak=0.9)),
    ("each", "creatures/wendigo/yeti_grumble", f"{A}/2018/*Yeti Monster/*grumble*.wav", dict(peak=0.9)),
    ("each", "creatures/wendigo/yeti_sniff", f"{A}/2018/*Yeti Monster/*sniff*.wav", dict(peak=0.8)),
    ("each", "creatures/wendigo/roar_growl", f"{A}/2016/*Monsters/Monster_Roar_Growl*.wav", dict(peak=0.9)),
    ("split", "creatures/wendigo/monster_growl", f"{A}/2018/*Girardot - Monsters/Monster Growls*.wav", dict(peak=0.9, limit=5)),
    ("each", "creatures/wendigo/low_growl", f"{A}/2017/*Mouthy/*growl*.wav", dict(peak=0.9)),
    ("each", "creatures/wendigo/dino_roar", f"{A}/2018/*Dino - Roars*/*.wav", dict(peak=0.9)),
    ("each", "creatures/wendigo/large_beast", f"{A}/2018/*Monster Within/*Large Beast*.wav", dict(peak=0.9)),
    ("each", "creatures/wendigo/hunter_attack", f"{A}/2018/*Monster Within/*Hunter*.wav", dict(peak=0.9)),
)

WEAPONS = (
    # Real firearms being handled. Each file is a run of takes; which take is
    # the magazine going in and which the bolt is for whoever listens.
    ("split", "weapons/handling_rifle_mag", f"{A}/2016/*Gun Foley*/Heckler*mag_in*.wav", dict(peak=0.9, limit=8)),
    ("split", "weapons/handling_shotgun_cock", f"{A}/2016/*Gun Foley*/SAIGA*cocking.wav", dict(peak=0.9, limit=6)),
    ("split", "weapons/handling_smg_cock_dry", f"{A}/2016/*Gun Foley*/Steyr*.wav", dict(peak=0.9, limit=8)),
    ("each", "weapons/shotgun_pump", f"{A}/2016/TS Sound*/Shotgun_Quick Pump*.wav", dict(peak=0.9)),
    ("split", "weapons/shotgun_shell_load", f"{A}/2016/TS Sound*/Shell Load*.wav", dict(peak=0.9, limit=6)),
)

PLAYER = (
    ("each", "player/pain_shout", f"{A}/2016/*Humans/Male_Shout-of-Pain*.wav", dict(peak=VOX)),
    ("each", "player/pain_grunt", f"{A}/2019/*Fight Vocalizations/*Pain Hurt*.wav", dict(peak=VOX)),
    ("each", "player/grunt_shout", f"{A}/2016/*Humans/Male_Grunt*.wav", dict(peak=VOX)),
    ("each", "player/fight_grunt", f"{A}/2019/*Fight Vocalizations/*David*.wav", dict(peak=VOX)),
    ("each", "player/battle_shout", f"{A}/2017/*Human Vocalizations/*battle_shout*.wav", dict(peak=VOX)),
    ("each", "player/death", f"{A}/2017/*Human Vocalizations/*death*.wav", dict(peak=VOX)),
    ("each", "player/scared_breath", f"{A}/2017/*Breathing In Hell/*.wav", dict(peak=0.6)),
    ("each", "player/breathing_run_loop", f"{A}/2018/*Punch and Combat*/voice_male_breathing*.wav", dict(peak=0.6)),
    ("mkloop", "player/heartbeat_stethoscope", f"{A}/2016/*STETHOSCOPE/*Heartbeat*.wav", dict(peak=0.7, seconds=20.0)),
    ("each", "player/heartbeat_panic", f"{A}/2018/*Human/Heartbeat*.wav", dict(peak=0.7, stereo=True)),
    ("each", "player/eating_apple", f"{A}/2016/*Everyday Actions*/EatingApple*.wav", dict(peak=0.6)),
    ("each", "player/eating_crunch", f"{A}/2017/*Eats and Drinks/CHIP*.wav", dict(peak=0.6)),
    ("each", "player/drinking_sip", f"{A}/2019/*WakeyWakey/*drink*.wav", dict(peak=0.6)),
)

MELEE = (
    ("each", "melee/stab", f"{A}/2016/*Dark Materials/*stab*.wav", dict(peak=HIT)),
    ("each", "melee/stab_punch", f"{A}/2016/*Just Gore _ Add On/Stab*.wav", dict(peak=HIT)),
    ("split", "melee/stab_dagger", f"{A}/2018/*Bones & Blood*/*stab dagger*.wav", dict(peak=HIT, limit=5)),
    ("split", "melee/stab_clean", f"{A}/2019/*BLOODBATH/PM_BB_CLEAN_STABS*.wav", dict(peak=HIT, limit=4)),
    ("each", "melee/chop_flesh", f"{A}/2019/*BLOODBATH/PM_BB_DESIGNED*.wav", dict(peak=HIT)),
    ("each", "melee/gore", f"{A}/2019/Sound Spark*Gore/*.wav", dict(peak=HIT)),
    ("each", "melee/gore_weapon", f"{A}/2018/SoundMorph - Gore/*.wav", dict(peak=HIT)),
    ("each", "melee/crunch_rip", f"{A}/2016/*Just Gore _ Add On/Crunch*.wav", dict(peak=HIT)),
    ("each", "melee/splatter", f"{A}/2016/*Just Gore _ Add On/Splatter*.wav", dict(peak=HIT)),
    ("each", "melee/punch_wet", f"{A}/2018/*Punch and Combat*/punch*.wav", dict(peak=HIT)),
    ("each", "melee/knife_swing", f"{A}/2018/*Punch and Combat*/whoosh*.wav", dict(peak=0.7)),
)

IMPACTS = (
    ("each", "impacts/bullet_body", f"{A}/2017/*Bullet Impact Sounds/*body*.wav", dict(peak=0.8)),
    ("each", "impacts/bullet_hard", f"{A}/2017/*Bullet Impact Sounds/*concrete*.wav", dict(peak=0.8)),
    ("each", "impacts/bullet_single", f"{A}/2018/*Guns & Explosions/Bullet Impact*.wav", dict(peak=0.8)),
    ("split", "impacts/bullet_multi", f"{A}/2019/*Natural Disasters/*Bullet Impacts*.wav", dict(peak=0.8, limit=6)),
    ("each", "impacts/bullet_dirt", f"{A}/2017/*Rock,Brick and Dirt*/*.wav", dict(peak=0.8)),
    ("each", "impacts/wood_impact", f"{A}/2017/*Wood Impacts and Debris/*.wav", dict(peak=HIT)),
    ("split", "impacts/wood_break", f"{A}/2019/*Broken/*WOOD Break*.wav", dict(peak=HIT, limit=6)),
    ("each", "impacts/branch_crush", f"{A}/2019/*Wood Sound Effects/*crushing_branches*.wav", dict(peak=0.7)),
    ("each", "impacts/log_fall", f"{A}/2019/*Wood Sound Effects/*falling_log*.wav", dict(peak=0.7)),
)

FIRE = (
    # Two minutes of matches scratched, snapped and lit, cut at its silences.
    ("split", "fire/match", f"{A}/2017/*Meridian/*matches*.wav", dict(peak=0.7, limit=14, gap_ms=350.0)),
)

FOOTSTEPS = (
    ("split", "footsteps/leaves2_walk", f"{A}/2018/*Footsteps on Leaves/FX3280*.wav", dict(peak=0.5, limit=12)),
    ("split", "footsteps/leaves2_run", f"{A}/2018/*Footsteps on Leaves/FX3282*.wav", dict(peak=0.5, limit=10)),
    ("split", "footsteps/grass2_walk", f"{A}/2017/*Extended Footsteps/*Grass*.wav", dict(peak=0.5, limit=12)),
)

AMBIENCE = (
    ("mkloop", "ambience/north_woods_day_ravens", f"{A}/2018/*Winter Forest*/*day raven*.wav", _bed()),
    ("mkloop", "ambience/north_woods_morning_crows", f"{A}/2018/*Winter Forest*/*morning crow*.wav", _bed()),
    ("mkloop", "ambience/north_woods_night_wolves", f"{A}/2018/*Winter Forest*/*night dark moon*.wav", _bed(100.0)),
    ("mkloop", "ambience/north_woods_blizzard", f"{A}/2018/*Winter Forest*/*blizzard*.wav", _bed()),
    ("mkloop", "ambience/northwest_forest_birds_wind", f"{A}/2017/*Pacific Northwest*/*.wav", _bed()),
    ("mkloop", "ambience/night_crickets_gusts", f"{A}/2018/*Wilderness Crickets/*Kiger*.WAV", _bed()),
    ("mkloop", "ambience/night_crickets_quiet", f"{A}/2018/*Wilderness Crickets/*quiet lime*.WAV", _bed(85.0)),
    ("mkloop", "ambience/night_crickets_interlude", f"{A}/2018/*Wilderness Crickets/*Interlude*.wav", _bed(85.0)),
    ("mkloop", "ambience/night_crickets_owls", f"{A}/2019/*Natural ambiences*/05*.WAV", _bed(120.0)),
    ("mkloop", "ambience/night_owl_river_distant", f"{A}/2019/*Natural ambiences*/43*.WAV", _bed(80.0)),
    ("mkloop", "ambience/wind_treeline", f"{A}/2017/*Wind In Trees/*Treeline*.wav", _bed()),
    ("mkloop", "ambience/wind_tall_grass", f"{A}/2017/*Wind In Trees/*Grass,Tall*.wav", _bed()),
    ("mkloop", "ambience/wind_mountain_grass", f"{A}/2019/*Natural ambiences*/38*.WAV", _bed()),
    ("mkloop", "ambience/wind_squeaking_tree", f"{A}/2018/*Bora wind*/*.wav", _bed()),
    ("each", "ambience/oneshot_owl_chirp", f"{A}/2018/*Desert Birds/*Owl Chirp*.WAV", BED),
    ("split", "ambience/oneshot_owl_screech", f"{A}/2018/*Desert Birds/*Owl Screeches*.WAV", dict(peak=0.5, stereo=True, limit=6, gap_ms=600.0)),
    ("each", "ambience/oneshot_tree_creak", f"{A}/2019/*Wood Sound Effects/*creaking_tree*.wav", BED),
)

TENSION = (
    ("loop", "tension/drone_dungeon_rumble", f"{A}/2016/*Drone Collection/Drone_Dungeon*.wav", BED),
    ("loop", "tension/drone_evolving", f"{A}/2016/*Drone Collection/Drone_Evolving*.wav", BED),
    ("loop", "tension/drone_swirling_wind", f"{A}/2016/*Drone Collection/Drone_Horror*.wav", BED),
    ("mkloop", "tension/drone_dark_eerie", f"{A}/2017/*Subtext Drone*/*.wav", _bed()),
    ("mkloop", "tension/ambience_cinematic", f"{A}/2016/*Cinematic Tension*/*ambience*.wav", _bed(80.0)),
    ("each", "tension/low_oscillating", f"{A}/2016/*TENSION/*low oscillating*.wav", BED),
    ("each", "tension/warbley_tone", f"{A}/2016/*TENSION/*warbley*.wav", BED),
    ("each", "tension/distorted_perception", f"{A}/2018/*DISTORTED PERCEPTION/*.wav", BED),
    ("mkloop", "tension/growl_entity_drone", f"{A}/2018/*3D Moving Drones/*.wav", _bed(60.0)),
    ("mkloop", "tension/zither", f"{A}/2017/*Granular Textures/*.wav", _bed(70.0)),
    ("each", "tension/paranormal_drone", f"{A}/2019/*Paranormal/Drone*.wav", BED),
)

STINGERS = (
    ("each", "stingers/bedlam", f"{A}/2018/*Bedlam Stingers*/*.wav", dict(peak=0.7, stereo=True)),
    ("each", "stingers/cinematic_impact", f"{A}/2016/*Cinematic Tension*/*impact*.wav", dict(peak=0.7, stereo=True)),
    ("each", "stingers/cinematic_rise", f"{A}/2016/*Cinematic Tension*/*rise*.wav", dict(peak=0.7, stereo=True)),
    ("each", "stingers/cinematic_effect", f"{A}/2016/*Cinematic Tension*/*sound-effect*.wav", dict(peak=0.7, stereo=True)),
    ("each", "stingers/eerie_passby", f"{A}/2019/*Paranormal/Eerie*.wav", dict(peak=0.7, stereo=True)),
    ("each", "stingers/dare_tension", f"{A}/2019/*Dare Small Pack/*.wav", dict(peak=0.7, stereo=True)),
)

UI = (
    ("each", "ui/mechanical", f"{A}/2019/InspectorJ - UI - Mechanical/*.wav", dict(peak=0.5)),
    ("each", "ui/dark", f"{A}/2017/*Dark Sci-Fi UI*/*.wav", dict(peak=0.5)),
    ("each", "ui/menu_confirm", f"{A}/2019/*Ambient Puzzle*/Menu Confirm.wav", dict(peak=0.5)),
    ("each", "inventory/grab_pickup", f"{A}/2018/*Punch and Combat*/foley_object*.wav", dict(peak=0.5)),
    ("each", "inventory/wood_handling", f"{A}/2019/*Wood Sound Effects/*handling*.wav", dict(peak=0.5)),
)

# A preview keeps its Freesound id as its name (`named`), so a take that is
# liked can be found again and downloaded as the original. A need nobody has
# fetched yet has no folder: `optional` skips it.
FREESOUND = tuple(
    ("each", f"freesound/{need}", f"freesound_previews/{need}/*.mp3",
     dict(peak=0.6, named=True, optional=True))
    for need, _query, _longest, _count in NEEDS
)

ROWS = (CREATURES + WEAPONS + PLAYER + MELEE + IMPACTS + FIRE + FOOTSTEPS
        + AMBIENCE + TENSION + STINGERS + UI + FREESOUND)

LICENCES = {
    "sonniss_archive": ("Sonniss GDC Game Audio Bundles 2016-2019",
                        "Sonniss GDC licence (royalty-free, no attribution, NOT CC0)",
                        "https://sonniss.com/gameaudiogdc/"),
    "freesound_previews": ("Freesound previews (MP3: fetch the original before shipping one)",
                           "CC0", "https://freesound.org"),
}
