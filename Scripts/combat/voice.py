"""The player's voice: a grunt when a blow lands, a cry when it kills.

Authored into BP_HealthComponent's Tick, because that is where a hit is
known, whoever dealt it:

    [Tick ...] --> LastDamageTime later than HeardDamageTime?    a new blow
                 --> HeardDamageTime = LastDamageTime
                 --> the player's (not DespawnOnDeath), and still alive?
                 --> one of HurtSounds, at the owner
    [... Dead = true] --> the player's? --> one of DeathSounds, at the owner

A BLOW, NOT A LOSS OF HEALTH. Health also goes down by a little every frame
while the player starves, bleeds or freezes (debuff_drain.py), and a voice
hung on "Health went down" would grunt sixty times a second. Whatever strikes
stamps LastDamageTime (a pellet, a fist, a wanderer's swing), and nothing that
drains does, so the stamp moving is the blow.

THE PLAYER ONLY, for now: the component is the wanderers' too, and theirs
have no takes yet. DespawnOnDeath is what tells the two apart, as it does for
the death menu.

The blow that kills is not grunted at: the death branch cries instead.
"""

from combat.audio import CREATURE_AUDIO_DIR, PLAYER_DEATH_NAMES, PLAYER_HIT_NAMES
from combat.footsteps import _author_random_sound
from combat.game_state import LAST_DAMAGE_VAR, NEVER_DAMAGED
from uebp.graph import _assets, _connect, _node, _pin, _set, else_, out, then
from uebp.nodes.actor import FN_ACTOR_LOC, FN_GET_OWNER
from uebp.nodes.math import FN_GREATER_FF
from combat import health_vars as HV

SOUND_TAKES = {HV.HurtSounds: PLAYER_HIT_NAMES, HV.DeathSounds: PLAYER_DEATH_NAMES}


def voice_defaults():
    """{variable: its takes, loaded}; a take never imported is left out."""
    eas = _assets()
    found = {var: [eas.load_asset(f"{CREATURE_AUDIO_DIR}/{n}") for n in names
                   if eas.does_asset_exist(f"{CREATURE_AUDIO_DIR}/{n}")]
             for var, names in SOUND_TAKES.items()}
    return {**found, HV.HeardDamageTime: NEVER_DAMAGED}


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
