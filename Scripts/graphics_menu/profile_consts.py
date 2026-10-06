"""The saved profile and the save-and-exit countdown: names and numbers only.

The profile is what a character carries between sessions: its stats and what
is in its inventory, never where it stood. BP_Profile (a USaveGame, slot
PROFILE_SLOT) is written when the save-and-exit countdown (the weapon
component's: combat/weapon_component/save_exit.py) runs out, read the
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
# which class each item is, the ammunition that lives on each item, and the
# slot it is in (combat/slot_tuning.py: the hand, a weapon slot, the bag).
ITEM_CLASSES_FIELD = "ItemClasses"
ITEM_FIELDS = (("ItemLoaded", "Loaded"), ("ItemReserve", "Reserve"), ("ItemSlot", "Slot"))

# --- the countdown -----------------------------------------------------------
# The M panel's "save and exit" row starts it (Enter or a click on the row;
# EXIT_ACTION is what PauseClick is matched against).
EXIT_ACTION = "save_exit"
EXIT_ROW_LABEL = "Save and Exit"

# The countdown is the weapon component's (combat/ask_consts.py has its
# variables and its length). The HUD's own: set once the countdown is over
# and the profile written, so it is written once.
EXIT_LEAVING_VAR = "ExitLeaving"
# Set once the profile has been looked for (and applied, if there was one).
PROFILE_CHECKED_VAR = "ProfileChecked"
# Set once a dead player's profile has been deleted, so it is deleted once.
PROFILE_FORGOTTEN_VAR = "ProfileForgotten"

# --- the banner --------------------------------------------------------------
EXIT_BANNER_PREFIX = "SAVING AND EXITING IN  "
EXIT_CALLED_OFF_TEXT = "EXIT CALLED OFF  -  you were hit"
EXIT_CALLED_OFF_SHOWN_S = 3.0
