"""mixamo_paths -- where the Mixamo packs come from, where they land, and which
clip plays which part on which creature.

Constants only (no ``unreal``).  Shared by import_mixamo.py and its modules,
and by build_retarget.py, which re-applies the locomotion after it regenerates
a creature's blend space.  forest_generator/npc_placement.py spells the
zombie's melee clip out as a literal (forest_generator imports nothing from
here); import_mixamo.py checks the two agree.

A Mixamo download is a zip of FBX files: one character ("X Bot.fbx", the
skin every clip was exported with) and one clip per file, all on Mixamo's
65-bone skeleton.  UE's FBX importer strips the ``mixamorig:`` namespace, so
the bones arrive as ``Hips``, ``Spine``, ``LeftHandIndex1``...
"""

import os
import re

from asset_pipeline.gas_bridge_paths import PLAYER_FAMILY

# ─── Host side: the zips, kept in the git-ignored cache ─────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
MIXAMO_CACHE = os.path.join(REPO_ROOT, "assets", "cache", "mixamo")

# (zip file stem, short name used in asset names).  The short name is what
# keeps the two packs' "zombie idle" and "zombie attack" apart.
PACKS = (("Scary Zombie Pack", "Scary"),
         ("Not So Scary Zombie Pack", "NotSoScary"))

# Every Mixamo download ships the character it was previewed on.  Its
# skeleton is the one every clip in the pack is keyed against.
CHARACTER_FBX = "X Bot.fbx"

# ─── Editor side ────────────────────────────────────────────────────────────
# Outside /Game/Sourced/Characters on purpose: build_retarget.py treats every
# skeletal mesh under that folder as a monster to animate.
MIXAMO_ROOT = "/Game/Sourced/Mixamo"
XBOT_DIR = f"{MIXAMO_ROOT}/XBot"
XBOT_MESH = f"{XBOT_DIR}/SKM_XBot"
XBOT_SKELETON = f"{XBOT_DIR}/SK_XBot"
IK_XBOT = "/Game/Sourced/Characters/Rigs/IK_XBot"

SOURCE_PREFIX = "A_Mx_"


def clip_stem(fbx_name):
    """'zombie biting (2).fbx' -> 'ZombieBiting2'."""
    words = re.findall(r"[A-Za-z0-9]+", os.path.splitext(fbx_name)[0])
    return "".join(w[:1].upper() + w[1:] for w in words)


def pack_dir(short):
    return f"{MIXAMO_ROOT}/{short}"


def source_clip(short, stem):
    """The clip as imported, on SK_XBot."""
    return f"{pack_dir(short)}/{SOURCE_PREFIX}{short}_{stem}"


# ─── Per creature: the retargeted copies ────────────────────────────────────
# Not under Anims/<Creature>, which build_retarget.py wipes and regenerates on
# every run, and not anywhere under Anims/ at all: the combat verifier reads
# each folder there as a creature family owing six hit reactions.
def mixamo_retargeter_path(creature):
    return f"/Game/Sourced/Characters/Rigs/RTG_{creature}_from_XBot"


def mixamo_anim_dir(creature):
    return f"{MIXAMO_ROOT}/{creature}"


def mixamo_prefix(creature):
    return f"A_{creature}_Mx_"


def mixamo_clip(creature, short, stem):
    return f"{mixamo_anim_dir(creature)}/{mixamo_prefix(creature)}{short}_{stem}"


# ─── Which clip plays what ──────────────────────────────────────────────────
# Only the zombie wears the packs: the wendigo keeps the mannequin set, which
# suits a creature that runs upright.  Every clip of both packs is still
# retargeted onto each creature listed here, so trying another one is a
# one-line change below rather than a re-import.
#
# The locomotion replaces the samples of the creature's own
# BS_Idle_Walk_Run row by row: its Speed axis has three rows (built at 0 idle,
# 300 walk, 600 jog), taken in speed order.  The wanderers orient to their
# movement, so every Direction column of a row gets the same forward clip.
#
# Each key is the speed the row is MEANT for; the row is then moved to the
# speed the clip actually covers at its rate (mixamo_locomotion), so the blend
# between rows keeps the feet planted.  Measured on X Bot: the Scary walk
# shambles at 34 cm/s and the run covers 310.
MIXAMO_CREATURES = ("Zombie01",)
LOCOMOTION = {0.0: ("Scary", "ZombieIdle"),
              300.0: ("Scary", "ZombieWalk"),
              600.0: ("Scary", "ZombieRun")}
MELEE = ("Scary", "ZombieAttack")

# The wendigo's roar, played when it goes aggro (npc/stalk.py): the Scary
# pack's scream. A creature here gets that one clip and nothing else of the
# packs. forest_generator/npc_stalk.py spells the result out as a literal;
# import_mixamo.py checks the two agree.
ROAR = ("Scary", "ZombieScream")
ROAR_CREATURES = ("Wendigo01",)

# rate = meant speed / clip speed, clamped, because a shamble played three
# times over reads as a twitch rather than a hurry.
RATE_SCALE_RANGE = (0.5, 2.0)


# ─── The player's melee set ─────────────────────────────────────────────────
# The knife's and the axe's swing and ready pose (combat/melee_clips.py bakes
# the game's clips from them).  Not PACKS: nothing of these is retargeted onto
# a creature, and only the clips named in PLAYER_CLIPS are imported (the axe
# pack has 47).  A pack is a zip, as above, or a folder of loose FBX files by
# that name (Mixamo's single downloads: "Stabbing.fbx", "Knife Idle.fbx"),
# which has no X Bot of its own and needs none: every Mixamo download is on
# the one skeleton.
PLAYER_PACKS = (("Pro Melee Axe Pack", "MeleeAxe"),
                ("Knife", "Knife"),
                ("Scary Zombie Pack", "Scary"))

# {role: (pack's short name, clip stem)}.  A new clip in a role is an edit
# here, a re-run of import_mixamo.py and the weapons build.
PLAYER_CLIPS = {
    "knife_ready": ("Knife", "KnifeIdle"),
    "knife_swing": ("Knife", "Stabbing"),
    "axe_ready": ("MeleeAxe", "StandingIdle"),
    "axe_swing": ("MeleeAxe", "StandingMeleeAttackDownward"),
    # The prone crawl (C5): the Scary pack's face-down crawl, the one clip of
    # it the player wears (the creatures' packs are imported as before).
    "prone_crawl": ("Scary", "ZombieCrawl"),
}


def player_clip(role):
    """A role's clip on the player's skeleton (SK_UEFN_Mannequin)."""
    return mixamo_clip(PLAYER_FAMILY, *PLAYER_CLIPS[role])
