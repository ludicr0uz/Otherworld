"""Who keeps quiet until it hunts: a wendigo on patrol makes no sound. And who
keeps its timed voice for the patrol: a zombie's growls on the timer are its
patrol's, and once it hunts it is heard as it goes aggro and as it swings
(Sound/sound_monsters.py: AggroVoices, AttackVoices), not on the timer.

Constants only -- no `unreal` import -- like npc_drawn.py and npc_stalk.py.
The builder is Scripts/npc/stats.py (the voice on a timer), the checks
Scripts/npc/verify_voice.py and, in the game, Scripts/probes/probe_wendigo_quiet.py.

Every wanderer growls every NPC_VOICE_MIN_S-NPC_VOICE_MAX_S (npc_placement.py).
A creature listed here does so only once it is Aggro: while it patrols, its
next growl is kept NPC_VOICE_MIN_S off, so the timer never comes due and the
first growl of a hunt does not land on top of its roar.
"""

# Silent until Aggro. A creature without a row growls on patrol too.
NPC_QUIET_ON_PATROL = ("Wendigo",)


# The timer's voice only while it patrols: Aggro, the next one is kept
# NPC_VOICE_MIN_S off the same way.
NPC_QUIET_ON_HUNT = ("Zombie",)


def quiet_on_patrol(key):
    return key in NPC_QUIET_ON_PATROL


def quiet_on_hunt(key):
    return key in NPC_QUIET_ON_HUNT
