"""retarget_paths -- where the retargeted character assets live, and the
mannequin clips they are retargeted from.

Constants only.  Shared by build_retarget.py, which writes these assets, by
retarget_verify.py, which checks them, and by the combat verifier, which reads
HIT_SOURCES for its clip order.
"""

# The hit-reaction tuple is shared with the NPC and weapons builders, whose
# graphs index it by position; one copy of an order is the only safe number.
from forest_generator.npc_placement import NPC_HIT_REACTION_CLIPS

MANNEQUIN_MESH = "/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple"

CHARACTER_ROOT = "/Game/Sourced/Characters"
RIG_DIR = "/Game/Sourced/Characters/Rigs"
ANIM_ROOT = "/Game/Sourced/Characters/Anims"

IK_MANNEQUIN = f"{RIG_DIR}/IK_Mannequin"


# ─── One animation set per monster ──────────────────────────────────────────
#
# These used to be single constants, because every monster was bound to one
# SK_MeshyHumanoid.  They are functions now for the reason spelled out at
# length in import_characters.py: Meshy shares bone NAMES between creatures but
# not bind poses, so a clip retargeted against the wendigo puts the wendigo's
# 59-degree forward neck pitch on a zombie and its head hangs off the front of
# its body.  Each monster animates against its own bind pose or it animates
# wrong.
#
# Nothing hand-authored is duplicated by this -- the chain tables below are
# keyed by bone name and those genuinely are shared.  What multiplies is
# generated assets: roughly 22 clips, an IK Rig and a retargeter per creature.

def ik_rig_path(name):
    return f"{RIG_DIR}/IK_{name}"


def retargeter_path(name):
    return f"{RIG_DIR}/RTG_{name}_from_Mannequin"


def anim_dir(name):
    return f"{ANIM_ROOT}/{name}"


def anim_prefix(name):
    return f"A_{name}_"


def abp_path(name):
    return f"{anim_dir(name)}/{anim_prefix(name)}ABP_Unarmed"


def melee_path(name):
    return f"{anim_dir(name)}/{anim_prefix(name)}MM_Attack_01"


def aim_paths(name):
    """Where this creature's retargeted ready poses land.

    The batch operation neither searches nor replaces anything in these names,
    so the output is the source's own name behind the creature prefix.
    """
    return tuple(f"{anim_dir(name)}/{anim_prefix(name)}{src.rsplit('/', 1)[1]}"
                 for src in AIM_SOURCES)


def hit_paths(name):
    """Where this creature's six retargeted hit reactions land.

    Same shape as aim_paths, and named here for the same reason: nothing
    references them either -- the health component plays them into HitSlot by
    object reference written onto a class default, so the dependency walk that
    drives the batch cannot find them from the anim Blueprint.
    """
    return tuple(f"{anim_dir(name)}/{anim_prefix(name)}{src.rsplit('/', 1)[1]}"
                 for src in HIT_SOURCES)

# The locomotion an enemy actually needs, not the whole pistol/rifle sets.
# Two roots, not a list of clips.  Retargeting the ANIM BLUEPRINT with
# include_referenced_assets pulls in everything it plays -- BS_Idle_Walk_Run and
# the sixteen directional clips behind it, MM_Idle, and the jump set -- and,
# more importantly, produces a target-skeleton copy of the state machine that
# drives them.  A folder of loose AnimSequences is not something a Character can
# be pointed at; an anim BP is.  Listing the clips by hand, as this did at
# first, retargeted the animation and left the animation LOGIC behind on
# SK_Mannequin, which is why the monsters existed as assets but nothing in the
# game could use them.
#
# MM_Attack_01 is named separately because nothing references it: the AI
# controller plays it into a slot by path at runtime, so the dependency walk
# cannot see it.
MANNEQUIN_ANIM_DIR = "/Game/Characters/Mannequins/Anims/Unarmed"
ABP_SOURCE = f"{MANNEQUIN_ANIM_DIR}/ABP_Unarmed"
MELEE_SOURCE = "/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_01"

# The two ready poses the player holds a weapon in.  Named here for the same
# reason MM_Attack_01 is: nothing references them, because
# build_weapons_and_combat.py plays them into DefaultSlot by path at runtime,
# so the dependency walk cannot find them.
#
# They are retargeted for every creature rather than only for the one the
# player wears.  A creature that never holds a gun pays two clips for it, and
# the alternative -- a per-creature source list -- would make the set a
# creature is built with depend on a decision taken in a different file.
AIM_SOURCES = ("/Game/Characters/Mannequins/Anims/Rifle/MF_Rifle_Idle_ADS",
               "/Game/Characters/Mannequins/Anims/Pistol/MF_Pistol_Idle_ADS")

# The hit reactions: Epic's MM_HitReact_* set, the flinches it ships for this.
#
# NOT MM_Death_*, which this project played for a while on the strength of
# "they end standing, so they are staggers". They are staggers the way a man
# thrown across a room is: measured off the source assets, they carry the head
# 0.9-2.2 m, and Front_02 and Front_03 turn the whole body 105-180 deg. Played
# into the upper-body HitSlot, whose blend takes spine rotation in MESH space
# while the legs stay on locomotion, that turn became the chest spinning half
# round on walking hips. The MM_HitReact_* set moves the head 3-18 cm, turns the
# chest at most 55 deg and comes back to where it started, in place.
#
# The six chosen, and their order, are NPC_HIT_REACTION_CLIPS's -- see there for
# which Front stands in for Left and Right, since Epic authored neither.
# combat.hit_reaction.hit_reactions() sorts the retargeted copies into that
# order and the health component picks by which side the round came from.
#
# Retargeted for every creature, for the same reason the aim poses are: which
# body the player wears is a decision taken in another file.
HIT_DIR = "/Game/Characters/Mannequins/Anims/Rifle/HitReact"
HIT_SOURCES = tuple(f"{HIT_DIR}/{clip}" for clip in NPC_HIT_REACTION_CLIPS)

RETARGET_SOURCES = (ABP_SOURCE, MELEE_SOURCE) + AIM_SOURCES + HIT_SOURCES
