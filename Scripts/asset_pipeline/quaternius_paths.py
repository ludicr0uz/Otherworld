"""quaternius_paths -- where the Quaternius packs come from, where they land,
and which of their clips and models the game uses.

Constants only (no ``unreal``).  Shared by import_quaternius.py and its
modules.  combat/skin.py and combat/weapon_models.py spell the paths they use
out themselves (combat imports nothing from here); import_quaternius.py
checks the two agree.

Five downloads, all by Quaternius and all CC0 (public domain; each zip's
License.txt says so), kept in the git-ignored cache under readable names:

    Universal Animation Library[Standard].zip    UAL1: 43 clips + mannequin
    Universal Animation Library 2[Standard].zip  UAL2: 43 more, same rig
    Ultimate Gun Pack.zip                        40 low-poly guns (FBX)
    Survival Pack.zip                            ~70 survival props (FBX)
    Zombie.zip                                   one rigged, animated zombie

The two UAL packs each ship a GLB for Unreal ("Unreal-Godot/"), on a 65-bone
skeleton named the Epic mannequin's way (pelvis, spine_01..03, clavicle_l,
thigh_l ... but ``Head``, and no twist bones).  The _RM variant has root
motion baked in; the plain one is in place, which is the one imported, since
the player is moved by CharacterMovement.
"""

import os

from asset_pipeline.player_body import PLAYER_NAME

# ─── Host side: the zips, kept in the git-ignored cache ─────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
QUATERNIUS_CACHE = os.path.join(REPO_ROOT, "assets", "cache", "quaternius")

# (zip stem, short name, the GLB inside the zip)
UAL_PACKS = (
    ("Universal Animation Library[Standard]", "UAL1",
     "Universal Animation Library[Standard]/Unreal-Godot/UAL1_Standard.glb"),
    ("Universal Animation Library 2[Standard]", "UAL2",
     "Universal Animation Library 2[Standard]/Unreal-Godot/UAL2_Standard.glb"),
)

# (zip stem, short name, folder of FBX files inside the zip).  Every FBX in the
# folder becomes one static mesh.
PROP_PACKS = (
    ("Ultimate Gun Pack", "Guns", "FBX"),
    ("Survival Pack", "Survival", "FBX"),
)

# (zip stem, short name, the FBX inside the zip): a skinned character.
ZOMBIE_PACK = ("Zombie", "Zombie", "FBX/Zombie.fbx")

# ─── Editor side ────────────────────────────────────────────────────────────
# Outside /Game/Sourced/Characters on purpose: build_retarget.py treats every
# skeletal mesh under that folder as a monster to animate.
QUATERNIUS_ROOT = "/Game/Sourced/Quaternius"
# Each pack is imported here first and then renamed into its own folder: the
# importers name things their own way (UAL1_StandardCrouch_Idle_Loop, Metal).
STAGING_DIR = f"{QUATERNIUS_ROOT}/_Import"
RIG_DIR = "/Game/Sourced/Characters/Rigs"


def pack_dir(short):
    return f"{QUATERNIUS_ROOT}/{short}"


def ual_mesh(short):
    return f"{pack_dir(short)}/SKM_{short}"


def ual_skeleton(short):
    return f"{pack_dir(short)}/SK_{short}"


def ual_source_clip(short, clip):
    """A UAL clip as imported, on the pack's own skeleton: A_UAL1_Crouch_Idle_Loop."""
    return f"{pack_dir(short)}/A_{short}_{clip}"


def ual_ik_rig(short):
    return f"{RIG_DIR}/IK_{short}"


def prop_mesh(short, stem):
    """One FBX of a prop pack: SM_Axe in Quaternius/Survival."""
    return f"{pack_dir(short)}/SM_{stem}"


# ─── Per character: the retargeted copies ───────────────────────────────────
# Not under Anims/<Character>, which build_retarget.py wipes and regenerates on
# every run, and not anywhere under Anims/ at all: the combat verifier reads
# each folder there as a creature family owing six hit reactions.
# Who gets them is the player (player_body.PLAYER_BODY, the one setting).
UAL_CHARACTERS = (PLAYER_NAME,)


def ual_retargeter_path(character, short):
    return f"{RIG_DIR}/RTG_{character}_from_{short}"


def ual_anim_dir(character):
    return f"{QUATERNIUS_ROOT}/UAL/{character}"


def ual_prefix(character):
    return f"A_{character}_"


def ual_clip(character, short, clip):
    """A_Adventurer01_UAL1_Crouch_Idle_Loop."""
    return f"{ual_anim_dir(character)}/{ual_prefix(character)}{short}_{clip}"


# ─── What the game uses ─────────────────────────────────────────────────────
# The player's low stances (combat/stance_clips.py).  Neither pack has a crawl:
# the swim is the one clip that moves a body lying face down, and with the arms
# pulling and the legs kicking it is what the prone crawl plays.
CROUCH_IDLE = ("UAL1", "Crouch_Idle_Loop")
CROUCH_WALK = ("UAL1", "Crouch_Fwd_Loop")
PRONE_CRAWL = ("UAL1", "Swim_Fwd_Loop")
# Searching a body: down on one knee, the hands working in front. The clip
# kneels, works and stands again; the game holds its middle (stance_clips.py).
SEARCH_KNEEL = ("UAL1", "Fixing_Kneeling")
# Throwing what is in hand (combat/weapon_component/throw_windup.py).
THROW = ("UAL2", "OverhandThrow")
# Picking an item up off the ground (combat/weapon_component/pickup_clip.py):
# the harvest bends down and reaches the right hand to the floor, 2.5 s, in
# place. UAL1's PickUp_Table reaches a table, waist high, and is no use here.
PICKUP = ("UAL2", "Farm_Harvest")
# The empty-handed punch (combat/weapon_component/punch.py): a right cross and
# a left jab, one of the two at random on each swing.
PUNCH_CROSS = ("UAL1", "Punch_Cross")
PUNCH_JAB = ("UAL1", "Punch_Jab")
# The axe swung at a tree (combat/weapon_component/punch.py, the knife's
# Strike's `tree`): a two-handed chop at a trunk, played in place of the axe's
# swing when the blow's sweep would meet a tree.
TREE_CHOP = ("UAL2", "TreeChopping_Loop")
# The clip the hands are calibrated on (palm_twist): hands at rest.
PALM_CALIBRATION = ("UAL1", "Idle_Loop")

# ─── What the creatures use ─────────────────────────────────────────────────
# The zombie's swing (npc/melee.py plays NpcVariant.melee): UAL2's scratch, a
# two-handed claw that sweeps the hands about 1.4 m, in place, 1.8 s.  Not
# Mixamo's "Zombie Scratch Idle", which is the zombie scratching itself.
# Only these clips are retargeted onto a creature (ual_creatures.py), with
# PALM_CALIBRATION beside them for the palms.  forest_generator/npc_placement.py
# spells the result out as a literal; ual_creatures.py checks the two agree.
ZOMBIE_MELEE = ("UAL2", "Zombie_Scratch")
UAL_CREATURE_CLIPS = {"Zombie01": (ZOMBIE_MELEE,)}
