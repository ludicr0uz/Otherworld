"""The world's sounds, and the player's own: footsteps, the player's grunt at
a blow and cry at death, the forest's three beds, and where the world is
heard from.

SOUNDS is the area's rows of the sound table and BINDINGS where each is played
from:

    BP_FootstepComponent.Sounds        a footfall, the player's and every
                                       wanderer's (combat/footsteps.py owns
                                       the stride; it plays through Sound/play.py)
    BP_HealthComponent.HurtSounds      the player's grunt   (the voice, below)
    BP_HealthComponent.DeathSounds     the player's cry
    BP_DayNightCycle BedDay/BedNight/BedWind   the beds     (the ambience, below)

and the three pieces of sound logic that are the world's: the voice, the
ambience, and the listener.
"""

import unreal

from combat import footstep_vars as FV
from combat import health_vars as HV
from combat.game_state import LAST_DAMAGE_VAR, NEVER_DAMAGED
from combat.paths import FOOTSTEP_BP_PATH, HEALTH_BP_PATH
from Sound.bind import defaults_for
from Sound.play import _author_random_sound
from Sound.sound_def import ATT_FOLEY, BED_DIR, Binding, Sound, takes
from uebp import props as EP
from uebp.graph import (
    _add_component, _component_object, _connect, _drop_components, _must_load, _node, _pin,
    _root_handle, _set, else_, out, then)
from uebp.nodes.actor import FN_ACTOR_LOC, FN_GET_OWNER, FN_SET_LISTENER_ATTENUATION
from uebp.nodes.math import FN_GREATER_FF
from uebp.nodes.system import FN_SET_VOLUME
from world import day_night_vars as DV
from world.day_night_graph import _call, _map
from world.day_night_graph import _get as _dn_get
from world.paths import DAY_NIGHT_BP_PATH

# The footsteps were as loud as recorded and drowned the forest: under half.
FOOTSTEPS = Sound("footsteps", "footsteps", takes("footsteps"), ATT_FOLEY, volume=0.4)
PLAYER_HIT = Sound("player_hit", "player hit", takes("player_hit"), ATT_FOLEY)
PLAYER_DEATH = Sound("player_death", "player death", takes("player_death"), ATT_FOLEY)

# ── The beds ─────────────────────────────────────────────────────────────────
#
# The one kind of sound that is NOT something in the level making a noise at a
# place: the forest itself, by day and by night, and the wind. A bed is
# stereo, loops, and has no attenuation profile on purpose -- it is all round
# the player wherever they stand. They live in a folder of their own, below
# the one apply_attenuation() sweeps, so that sweep still means what it says:
# every wave in the two audio folders is placed, and a flat one there is a
# mistake. BP_DayNightCycle plays them (the ambience, below).


def _bed(key, label, volume):
    return Sound(key, label, takes(key), None, folder=BED_DIR, volume=volume)


# Under everything else; the wind silent until a better one is found: the bed
# plays, at nothing.
AMBIENCE_DAY = _bed("ambience_day", "day birds", 0.7)
AMBIENCE_NIGHT = _bed("ambience_night", "night", 0.7)
AMBIENCE_WIND = _bed("ambience_wind", "wind", 0.0)
SOUNDS = (FOOTSTEPS, PLAYER_HIT, PLAYER_DEATH, AMBIENCE_DAY, AMBIENCE_NIGHT, AMBIENCE_WIND)

BED_DAY, BED_NIGHT, BED_WIND = (s.names[0] for s in (AMBIENCE_DAY, AMBIENCE_NIGHT, AMBIENCE_WIND))
BED_DAY_COMP, BED_NIGHT_COMP, BED_WIND_COMP = "BedDay", "BedNight", "BedWind"
BEDS = ((BED_DAY_COMP, BED_DAY), (BED_NIGHT_COMP, BED_NIGHT), (BED_WIND_COMP, BED_WIND))

BINDINGS = (
    Binding(FOOTSTEP_BP_PATH, FV.Sounds, FOOTSTEPS),
    Binding(HEALTH_BP_PATH, HV.HurtSounds, PLAYER_HIT),
    Binding(HEALTH_BP_PATH, HV.DeathSounds, PLAYER_DEATH),
    Binding(DAY_NIGHT_BP_PATH, "sound", AMBIENCE_DAY, single=True, component=BED_DAY_COMP),
    Binding(DAY_NIGHT_BP_PATH, "sound", AMBIENCE_NIGHT, single=True, component=BED_NIGHT_COMP),
    Binding(DAY_NIGHT_BP_PATH, "sound", AMBIENCE_WIND, single=True, component=BED_WIND_COMP),
)


# ─── The player's voice ──────────────────────────────────────────────────────
#
# The player's voice: a grunt when a blow lands, a cry when it kills.
#
# Authored into BP_HealthComponent's Tick, because that is where a hit is
# known, whoever dealt it:
#
#     [Tick ...] --> LastDamageTime later than HeardDamageTime?    a new blow
#                  --> HeardDamageTime = LastDamageTime
#                  --> the player's (not DespawnOnDeath), and still alive?
#                  --> one of HurtSounds, at the owner
#     [... Dead = true] --> the player's? --> one of DeathSounds, at the owner
#
# A BLOW, NOT A LOSS OF HEALTH. Health also goes down by a little every frame
# while the player starves, bleeds or freezes (debuff_drain.py), and a voice
# hung on "Health went down" would grunt sixty times a second. Whatever strikes
# stamps LastDamageTime (a pellet, a fist, a wanderer's swing), and nothing that
# drains does, so the stamp moving is the blow.
#
# THE PLAYER ONLY, for now: the component is the wanderers' too, and theirs
# have no takes yet. DespawnOnDeath is what tells the two apart, as it does for
# the death menu.
#
# The blow that kills is not grunted at: the death branch cries instead.


def voice_defaults():
    """{variable: its takes, loaded}; a take never imported is left out."""
    return {**defaults_for(HEALTH_BP_PATH, BINDINGS), HV.HeardDamageTime: NEVER_DAMAGED}


def _get(ed, name):
    return out(ed.add_get_member_variable_node(name), name)


def _at_owner(ed):
    owner = _node(ed, FN_GET_OWNER)
    here = _node(ed, FN_ACTOR_LOC)
    _connect(out(owner), _pin(here, "self"))
    return out(here)


def _author_hurt_voice(ed, exec_ins):
    """A new blow on a living player: grunt. Returns the stage's exits."""
    newer = _node(ed, FN_GREATER_FF)
    _connect(_get(ed, LAST_DAMAGE_VAR), _pin(newer, "A"))
    _connect(_get(ed, HV.HeardDamageTime), _pin(newer, "B"))
    struck = ed.add_branch_node()
    _connect(out(newer), _pin(struck, "Condition"))
    for pin in exec_ins:
        _connect(pin, _pin(struck, "execute"))
    heard = ed.add_set_member_variable_node(HV.HeardDamageTime)
    _connect(_get(ed, LAST_DAMAGE_VAR), _pin(heard, HV.HeardDamageTime))
    _connect(then(struck), _pin(heard, "execute"))

    wanderer = ed.add_branch_node()
    _connect(_get(ed, HV.DespawnOnDeath), _pin(wanderer, "Condition"))
    _connect(then(heard), _pin(wanderer, "execute"))
    living = _node(ed, FN_GREATER_FF)
    _connect(_get(ed, HV.Health), _pin(living, "A"))
    _set(living, "B", 0.0)
    alive = ed.add_branch_node()
    _connect(out(living), _pin(alive, "Condition"))
    _connect(else_(wanderer), _pin(alive, "execute"))
    _made, grunted = _author_random_sound(ed, HV.HurtSounds, _at_owner(ed), then(alive))

    ed.add_comment_to_nodes(
        "The player's grunt. LastDamageTime moved, so something struck (a "
        "drain does not stamp it); on the player, still alive, one of "
        "HurtSounds is played where they stand.",
        [struck, heard, wanderer, alive])
    return (grunted, else_(struck), then(wanderer), else_(alive))


def _author_death_voice(ed, exec_in):
    """Just dead: the player cries out. Returns the stage's exits."""
    wanderer = ed.add_branch_node()
    _connect(_get(ed, HV.DespawnOnDeath), _pin(wanderer, "Condition"))
    _connect(exec_in, _pin(wanderer, "execute"))
    _made, cried = _author_random_sound(ed, HV.DeathSounds, _at_owner(ed), else_(wanderer))
    ed.add_comment_to_nodes(
        "The player's death: one of DeathSounds, the once (Dead was just set).",
        [wanderer])
    return (cried, then(wanderer))


# ─── The forest's own sound ──────────────────────────────────────────────────
#
# The forest's own sound: three beds on BP_DayNightCycle, and the Tick step
# that hands the day's over to the night's.
#
#     BedDay     the day's birds          volume = DayAmount
#     BedNight   crickets and owls        volume = 1 - DayAmount
#     BedWind    the wind, always         volume 1
#
# Three AudioComponents on the cycle actor, each playing one looping stereo
# wave (BEDS) from the moment the level starts. They are
# on the cycle because it is the one actor every level has and the one that
# knows DayAmount: the same number that fades the sun into the moon fades the
# birds into the crickets, so dusk sounds like dusk for as long as it looks
# like it.
#
# A bed has no attenuation and is not at a place: where the actor stands does
# not matter. Its loudness is its SoundClass's row on the SOUND SETTINGS tab,
# which the component's volume multiplies.
#
# A bed at volume zero goes on playing (the wave's virtualization mode, set
# at import), so the night's is in the same place in its two minutes when dusk
# comes round as it would have been had it been heard all day.


def build_beds(bp):
    """Drop and re-add the three bed components, each with its wave."""
    _drop_components(bp, {name for name, _wave in BEDS})
    root = _root_handle(bp)
    for name, wave in BEDS:
        bed = _component_object(_add_component(bp, root, unreal.AudioComponent, name))
        bed.set_editor_property("sound", _must_load(f"{BED_DIR}/{wave}"))
        bed.set_editor_property("auto_activate", True)
        # All round the player, not at the actor: a bed is not a place.
        bed.set_editor_property("allow_spatialization", False)
        bed.set_editor_property("is_ui_sound", False)


def author_ambience(ed, chain):
    """Extend the Tick chain: the day's bed by DayAmount, the night's by the rest."""
    day = _dn_get(ed, DV.DayAmount)
    night = _map(ed, _dn_get(ed, DV.DayAmount), 0.0, 1.0, 1.0, 0.0)
    birds = chain.step(_call(ed, FN_SET_VOLUME, self=_dn_get(ed, BED_DAY_COMP),
                             NewVolumeMultiplier=day))
    crickets = chain.step(_call(ed, FN_SET_VOLUME, self=_dn_get(ed, BED_NIGHT_COMP),
                                NewVolumeMultiplier=night))
    ed.add_comment_to_nodes(
        "The forest's sound follows the light: the day's bed is as loud as "
        "DayAmount, the night's as 1 - DayAmount. The wind plays on.",
        [birds, crickets])


# ─── Heard from the character, not the camera ────────────────────────────────
#
# BeginPlay: hear the world from where the character stands, not from the camera.
#
# The engine's listener sits on the camera, for panning and for distance alike.
# The camera does not stay put: over the shoulder it rides the boom about 2.6 m
# behind the character, and down the sights it travels to the gun at the eye.
# Every sound measured against it changed loudness with the view. The footsteps
# showed it most (A_Att_Foley falls off from 1 m): they were quiet behind the
# shoulder and loud down the sights.
#
# SetAudioListenerAttenuationOverride splits the two. Distance is measured from
# the character's capsule, which is the same place in every view. Direction still
# comes from the camera, so a sound on the left of the screen is still heard on
# the left. The override follows the component and never needs refreshing. A
# restart opens the level again, and the new character's BeginPlay sets it again.


def _author_listener_at_character(ed, as_char, pc_out, exec_in):
    """Pin the player controller's attenuation listener to the capsule.

    The offset pin stays empty, which compiles as zero: the listener is the
    capsule's centre. Returns the then pin.
    """
    capsule = ed.add_get_member_variable_node(EP.CAPSULE_COMPONENT, "/Script/Engine.Character")
    _connect(as_char, _pin(capsule, "self"))
    listen = _node(ed, FN_SET_LISTENER_ATTENUATION)
    _connect(pc_out, _pin(listen, "self"))
    _connect(out(capsule, EP.CAPSULE_COMPONENT), _pin(listen, "AttachToComponent"))
    _connect(exec_in, _pin(listen, "execute"))
    ed.add_comment_to_nodes(
        "Sounds fade with the distance from the character, not from the "
        "camera, so aiming down the sights does not make the footsteps "
        "louder. Panning still follows the camera.",
        [capsule, listen])
    return then(listen)
