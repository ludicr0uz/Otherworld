"""The weapon component's own sounds: a swing through the air, the axe on a
trunk, a match struck.

Each is an array of takes on the component and one of them drawn per play,
as the footsteps are (footsteps._author_random_sound, which this plays
through): an empty array is silence, not an error, so a checkout with no
sounds installed still builds and plays.

    SwingSounds   a punch, a slash, an axe swing: as the clip starts, at the
                  player (punch._author_swing)
    ChopSounds    the axe landing on a tree: at the cut (chop.py)
    MatchSounds   the strike that lights a campfire: where the fire is laid
                  (light.py)

Which takes they are is the selection's (combat/audio.py names them). Their
volume is their SoundClass's row on the SOUND SETTINGS tab, and how far they
carry their attenuation profile: nothing here says either.
"""

from combat.audio import AXE_CHOP_NAMES, CREATURE_AUDIO_DIR, MATCH_NAMES, MELEE_SWING_NAMES
from combat.footsteps import _author_random_sound
from uebp.graph import _assets
from combat.weapon_component import vars as WV

SOUND_TAKES = {
    WV.SwingSounds: MELEE_SWING_NAMES,
    WV.ChopSounds: AXE_CHOP_NAMES,
    WV.MatchSounds: MATCH_NAMES,
}


def sound_defaults():
    """{variable: its takes, loaded}, for the component's defaults. A take
    that was never imported is left out."""
    eas = _assets()
    return {var: [eas.load_asset(f"{CREATURE_AUDIO_DIR}/{n}") for n in names
                  if eas.does_asset_exist(f"{CREATURE_AUDIO_DIR}/{n}")]
            for var, names in SOUND_TAKES.items()}


def _author_sound(ed, var, at_pin, exec_in):
    """Play one of ``var``'s takes at ``at_pin``. Returns the exec pin after."""
    _made, after = _author_random_sound(ed, var, at_pin, exec_in)
    return after
