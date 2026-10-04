"""The weapon component's own sounds: a swing through the air, the axe on a
trunk, a match struck.

Each is an array of takes on the component and one of them drawn per play,
as the footsteps are (footsteps._author_random_sound, which this plays
through): an empty array is silence, not an error, so a checkout with no
sounds installed still builds and plays.

    SwingSounds     a punch, a slash, an axe swing: as the clip starts, at
                    the player (punch._author_swing)
    PunchHitSounds  a fist landing on a body: at the hit (punch._author_blow)
    BladeHitSounds  a knife or an axe landing on a body: at the hit (the same
                    blow, on the knife's Strike)
    ChopSounds      the axe landing on a tree, and a thrown blade lodging in
                    one: at the cut (chop.py, throw_strike.py)
    ThrowSounds     a blunt thing thrown, as it leaves the hand, and
    ThrowSharpSounds  a Melee item (the knife, the axe) thrown (throw.py)
    LodgeSounds     a thrown blade going into a body: at the wound
                    (throw_strike.py)
    MatchSounds     the strike that lights a campfire: where the fire is laid
                    (light.py)

Which takes they are is the selection's (combat/audio.py names them). Their
volume is their SoundClass's row on the SOUND SETTINGS tab, and how far they
carry their attenuation profile: nothing here says either.
"""

from combat.audio import (
    AXE_CHOP_NAMES, BLADE_HIT_NAMES, BLADE_LODGE_NAMES, CREATURE_AUDIO_DIR, MATCH_NAMES,
    MELEE_HIT_NAMES, MELEE_SWING_NAMES, THROW_NAMES, THROW_SHARP_NAMES)
from combat.footsteps import _author_random_sound
from uebp.graph import _assets
from combat.weapon_component import vars as WV

SOUND_TAKES = {
    WV.SwingSounds: MELEE_SWING_NAMES,
    WV.ChopSounds: AXE_CHOP_NAMES,
    WV.MatchSounds: MATCH_NAMES,
    WV.ThrowSounds: THROW_NAMES,
    WV.ThrowSharpSounds: THROW_SHARP_NAMES,
    # The wanderers' blow on the player is the same thud (npc/paths.py).
    WV.PunchHitSounds: MELEE_HIT_NAMES,
    WV.BladeHitSounds: BLADE_HIT_NAMES,
    WV.LodgeSounds: BLADE_LODGE_NAMES,
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
