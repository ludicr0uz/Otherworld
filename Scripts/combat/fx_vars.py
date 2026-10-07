"""The fight as everyone sees and hears it (task M21): the names of the
weapon component's cosmetic events, their parameters, and the counter a
probe reads. Constants only; the graphs are weapon_component/fx.py and the
module that owns each cosmetic.

Every cosmetic is a PAIR of custom events on BP_WeaponComponent:

    Fx_<Name>(params)          a plain event holding the sound, the clip or
                               the spawn itself: the one copy of those nodes
    Multicast_<Name>(params)   an unreliable Multicast the server calls where
                               the state changed; its gate asks whether THIS
                               copy still owes the cosmetic, counts it in
                               FxPlayed, and calls Fx_<Name>

Three gates (fx.py), one per kind of cosmetic:

    UNPREDICTED   HasAuthority OR NOT LocalInput: the owning client already
                  played it as its prediction (shot.py, punch.py, throw.py
                  call Fx_<Name> on the Branch's false arm), everyone else
                  owes it. Single player has authority, so it plays once.
    OTHERS        NOT LocalInput: the owner played it in both modes (the
                  throw's clip is the wind-up's, before the server knows).
    SCREEN        NOT IsDedicatedServer: nobody predicted it (a pellet's blood
                  and chips, a blow landing), so every machine with a screen
                  plays it, the server never.

Cosmetics travel apart from state: a lost Multicast loses a sound, never a
round or a wound. The noise the wanderers hear is written by the server's
own event (shot_noise.py), not by any of these.
"""

from uebp.vars import BOOL, FLOAT, INT, VECTOR, Var

FX_PREFIX = "Fx_"
MULTICAST_PREFIX = "Multicast_"

UNPREDICTED, OTHERS, SCREEN = "unpredicted", "others", "screen"

# --- the actor's own: the sound or the clip at the character ----------------
SHOT = "Shot"                 # Held's FireSound at the gun
RELOAD = "Reload"             # Held's ReloadSound at the gun
PUNCH = "Punch"               # the punch's clip and one of SwingSounds
SLASH = "Slash"               # the knife's
THROW = "Throw"               # the air the thrown item cuts (Start, Sharp)
THROW_CLIP = "ThrowClip"      # the overhand throw's clip, from the ready pose

# --- at a point in the world: what a blow or a pellet did where it landed ---
PELLET_HIT = "PelletHit"      # blood (Blood) or chips at (Location, Normal), sized Scale
PUNCH_HIT = "PunchHit"        # one of PunchHitSounds at Location
BLADE_HIT = "BladeHit"        # one of BladeHitSounds at Location
CHOP = "Chop"                 # chips and one of ChopSounds: the axe in a tree
STAB = "Stab"                 # blood and the stab, or the axe's kill by the head (HeadKill)
LODGE = "Lodge"               # chips and the chop's sound: a thrown blade in a trunk

LOCATION_PARAM, NORMAL_PARAM, SCALE_PARAM = "Location", "Normal", "Scale"
BLOOD_PARAM, HEAD_KILL_PARAM = "Blood", "HeadKill"
START_PARAM, SHARP_PARAM = "Start", "Sharp"
POINT_PARAMS = ((LOCATION_PARAM, VECTOR), (NORMAL_PARAM, VECTOR))
PELLET_HIT_PARAMS = POINT_PARAMS + ((SCALE_PARAM, FLOAT), (BLOOD_PARAM, BOOL))
STAB_PARAMS = POINT_PARAMS + ((HEAD_KILL_PARAM, BOOL),)
SOUND_AT_PARAMS = ((LOCATION_PARAM, VECTOR),)
THROW_FX_PARAMS = ((START_PARAM, VECTOR), (SHARP_PARAM, BOOL))

# name -> (its parameters, its gate): every cosmetic, for the verifier.
COSMETICS = {
    SHOT: ((), UNPREDICTED),
    RELOAD: ((), UNPREDICTED),
    PUNCH: ((), UNPREDICTED),
    SLASH: ((), UNPREDICTED),
    THROW: (THROW_FX_PARAMS, UNPREDICTED),
    THROW_CLIP: ((), OTHERS),
    PELLET_HIT: (PELLET_HIT_PARAMS, SCREEN),
    PUNCH_HIT: (SOUND_AT_PARAMS, SCREEN),
    BLADE_HIT: (SOUND_AT_PARAMS, SCREEN),
    CHOP: (POINT_PARAMS, SCREEN),
    STAB: (STAB_PARAMS, SCREEN),
    LODGE: (POINT_PARAMS, SCREEN),
}
# The ones the owning client predicts: Fx_<Name> is called off the authority
# Branch's false arm as well as by its Multicast.
PREDICTED = (SHOT, RELOAD, PUNCH, SLASH, THROW)


def fx_event(name):
    return FX_PREFIX + name


def multicast_event(name):
    return MULTICAST_PREFIX + name


# How many cosmetics this copy has played at the server's word (the gated arm
# of every Multicast_*): a probe's readout, never read by a graph.
FxPlayed = Var("FxPlayed", INT, 0)

TABLE = (FxPlayed,)
