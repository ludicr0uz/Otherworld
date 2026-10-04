"""The whole sound table: the four areas' rows and bindings put together, and
what is derived from them -- which wave carries how far, which waves are in
which folder, and the SOUND SETTINGS tab's rows.

A new sound is a row of its area's SOUNDS (and of TAB_ORDER, at the end); a
new AREA is a module listed in AREAS.
"""

from Sound import sound_items, sound_monsters, sound_weapons, sound_world
from Sound.sound_def import (
    ATT_CREATURE, ATT_FOLEY, ATT_FOOTSTEP, ATT_GUNFIRE, ATT_VOICE, BED_DIR, CREATURE_AUDIO_DIR, WEAPON_AUDIO_DIR)
from Sound.sound_monsters import ATT_ROAR

AREAS = (sound_weapons, sound_monsters, sound_items, sound_world)
SOUNDS = tuple(s for area in AREAS for s in area.SOUNDS)
BINDINGS = tuple(b for area in AREAS for b in area.BINDINGS)
BY_KEY = {s.key: s for s in SOUNDS}
if len(BY_KEY) != len(SOUNDS):
    raise RuntimeError("two rows of the sound table share a key")

ATTENUATIONS = (ATT_GUNFIRE, ATT_CREATURE, ATT_ROAR, ATT_FOLEY, ATT_FOOTSTEP, ATT_VOICE)

# Which sound gets which, and the only table that says so. Every sound in the
# game is a WORLD sound -- something in the level made it, at a place -- so
# every one is spatialised. There is no 2D exception to make: the HUD is drawn
# with DrawText and DrawTexture and is silent, there are no menu clicks, and
# the one sound that might conventionally stay flat, the player's own weapon,
# is a third-person weapon in a third-person game -- it is visibly out there in
# the world at the end of the player's arms, and the muzzle is ~1.5 m from the
# listener, where the gunfire curve is still 1.0 anyway.
#
# The player's own FOOTSTEPS are the judgement call. They share the component
# and the profile (ATT_FOOTSTEP) with the wanderers', which means they attenuate
# too; at the third-person camera's ~3 m that costs a little volume the player
# did not ask to lose. Kept spatialised regardless, because the alternative is
# a second non-attenuated footstep path whose only purpose is to be wrong about
# where the player's feet are, and because a step that pans as you turn is the
# cheapest cue in the game that the audio is placed at all.
# The axe on a trunk carries as a creature's voice does: it is the loudest
# thing a player does without a gun, and the wanderers' hearing of it is the
# chop's own noise event, not this.
SOUND_ATTENUATION = {name: s.attenuation for s in SOUNDS if s.attenuation is not None
                     for name in s.names}


def names_in(folder):
    """Every wave of the table that lives in ``folder``."""
    return tuple(n for s in SOUNDS if s.folder == folder for n in s.names)


# The sound assets the importer brings in, and the only list of them: by folder.
SOUND_NAMES = names_in(WEAPON_AUDIO_DIR)
CREATURE_SOUND_NAMES = names_in(CREATURE_AUDIO_DIR)
BED_NAMES = names_in(BED_DIR)
LOOPING_NAMES = tuple(n for s in SOUNDS if s.looping and s.folder == CREATURE_AUDIO_DIR
                      for n in s.names)

# The SOUND SETTINGS tab's rows, in order. BY POSITION: the HUD's table, its
# graph and a player's saved volumes (graphics_menu/tune_keep.py) all index
# it, so a new sound goes at the END, and a new or moved row needs
# build_graphics_menu.py.
TAB_ORDER = (
    "footsteps", "shotgun_shot", "pistol_shot", "smg_shot", "rifle_shot", "sniper_shot",
    "dry_fire", "shotgun_reload", "rifle_reload", "pistol_reload", "melee_hit",
    "zombie_growl", "wendigo_roar", "melee_swing", "axe_chop", "player_hit",
    "player_death", "match", "campfire", "blade_hit", "blade_lodge", "throw",
    "throw_sharp", "ambience_day", "ambience_night", "ambience_wind",
    "zombie_attack_growl", "zombie_aggro_growl", "monster_footsteps",
    "grass_rustle", "player_breath", "heartbeat", "eating", "axe_head_kill",
    "handle_item", "handle_gun", "handle_blade", "handle_cloth",
)
if sorted(TAB_ORDER) != sorted(BY_KEY):
    raise RuntimeError(f"TAB_ORDER and the areas' sounds differ: "
                       f"{sorted(set(TAB_ORDER) ^ set(BY_KEY))}")

# The tab's rows: (CSV sound, the tab's label, its SoundWaves, the volume
# with no CSV).
SOUND_STATS = tuple((s.key, s.label, s.names, s.volume)
                    for s in (BY_KEY[key] for key in TAB_ORDER))
