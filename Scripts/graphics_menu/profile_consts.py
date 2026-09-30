"""The saved profile and the save-and-exit countdown: names and numbers only.

The profile is what a character carries between sessions: its stats and what
is in its inventory, never where it stood. BP_Profile (a USaveGame, slot
PROFILE_SLOT) is written when the save-and-exit countdown runs out, read the
first time a started game's HUD finds the player's loadout, and deleted the
moment the player dies -- a death costs the character.

Every consumer is the HUD, which is why the class is built by the HUD's builder
(profile_asset.py) rather than next to BP_Settings in combat.
"""

from combat.paths import HEALTH_CLASS_PATH, WEAPON_COMP_CLASS_PATH
from survival.paths import SURVIVAL_CLASS_PATH

PROFILE_BP_PATH = "/Game/UI/BP_Profile"
PROFILE_CLASS_PATH = f"{PROFILE_BP_PATH}.BP_Profile_C"
PROFILE_SLOT = "OtherworldProfile"
PROFILE_USER_INDEX = 0
NODE_CAST_PROFILE = "Utilities|Casting|CastToBP_Profile"

# The stats, as (field on BP_Profile, the component class that owns it, its
# variable there). All floats. The kill count is an int on the GameMode and
# is handled on its own (KILLS_FIELD).
STAT_FIELDS = (("Health", HEALTH_CLASS_PATH, "Health"),
               ("Stamina", WEAPON_COMP_CLASS_PATH, "Stamina"),
               ("Hunger", SURVIVAL_CLASS_PATH, "Hunger"),
               ("Thirst", SURVIVAL_CLASS_PATH, "Thirst"),
               ("Temperature", SURVIVAL_CLASS_PATH, "Temperature"))
KILLS_FIELD = "Kills"
EQUIPPED_FIELD = "EquippedIndex"

# The inventory, as parallel arrays indexed like BP_WeaponComponent.Inventory:
# which class each slot holds, and the ammunition that lives on each item.
ITEM_CLASSES_FIELD = "ItemClasses"
AMMO_FIELDS = (("ItemLoaded", "Loaded"), ("ItemReserve", "Reserve"))

# --- the countdown -----------------------------------------------------------
# X with the M panel open starts it. X rather than Enter (the PIE console) or
# S (walking); behind the MenuOpen gate like 1-4 and D, so it is a free key
# everywhere else.
EXIT_KEY = "X"
EXIT_SECONDS = 15.0
EXIT_ROW_LABEL = f"[{EXIT_KEY}]   save and exit"

# The HUD's variables. ExitStartedAt is compared with the player's
# BP_HealthComponent.LastDamageTime, which a wanderer's swing stamps
# (npc/melee.py): a hit after the start calls the exit off.
EXIT_PENDING_VAR = "ExitPending"
EXIT_AT_VAR = "ExitAt"
EXIT_STARTED_VAR = "ExitStartedAt"
EXIT_CALLED_OFF_VAR = "ExitCalledOffAt"
# Set once the profile has been looked for (and applied, if there was one).
PROFILE_CHECKED_VAR = "ProfileChecked"
# Set once a dead player's profile has been deleted, so it is deleted once.
PROFILE_FORGOTTEN_VAR = "ProfileForgotten"
NEVER = -1000.0

# --- the banner --------------------------------------------------------------
EXIT_BANNER_PREFIX = "SAVING AND EXITING IN  "
EXIT_CALLED_OFF_TEXT = "EXIT CALLED OFF  -  you were hit"
EXIT_CALLED_OFF_SHOWN_S = 3.0
EXIT_BANNER_Y = 150.0
EXIT_BANNER_HALF_W = 230.0       # px left of the viewport's centre
EXIT_BANNER_SCALE = 2.0
COL_EXIT_BANNER = "(R=1.000000,G=0.870000,B=0.450000,A=1.000000)"
COL_EXIT_CALLED_OFF = "(R=0.900000,G=0.300000,B=0.250000,A=1.000000)"
