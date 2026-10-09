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

from combat.paths import HEALTH_CLASS_PATH, ITEM_CLASS_PATH, WEAPON_COMP_CLASS_PATH
from survival.paths import SURVIVAL_CLASS_PATH
from uebp.vars import BOOL, FLOAT, INT, Var, array, cls

PROFILE_BP_PATH = "/Game/UI/BP_Profile"
PROFILE_CLASS_PATH = f"{PROFILE_BP_PATH}.BP_Profile_C"
PROFILE_SLOT = "OtherworldProfile"
PROFILE_USER_INDEX = 0

# The stats, as (field on BP_Profile, the component class that owns it, its
# variable there). All floats. The kill count is an int on the GameMode and
# is handled on its own (KILLS_FIELD).
STAT_FIELDS = ((Var("Health", FLOAT), HEALTH_CLASS_PATH, "Health"),
               (Var("Stamina", FLOAT), WEAPON_COMP_CLASS_PATH, "Stamina"),
               (Var("Hunger", FLOAT), SURVIVAL_CLASS_PATH, "Hunger"),
               (Var("Thirst", FLOAT), SURVIVAL_CLASS_PATH, "Thirst"),
               (Var("Temperature", FLOAT), SURVIVAL_CLASS_PATH, "Temperature"))
KILLS_FIELD = Var("Kills", INT)
EQUIPPED_FIELD = Var("EquippedIndex", INT)

# The inventory, as parallel arrays indexed like BP_WeaponComponent.Inventory:
# which class each item is, the ammunition that lives on each item, and the
# slot it is in (combat/slot_tuning.py: the hand, a weapon slot, the bag).
# Classes of BP_WeaponItem, not of Actor: SpawnActorFromClass types its return
# from the Class pin, and the spawned item goes into an array of BP_WeaponItem.
ITEM_CLASSES_FIELD = Var("ItemClasses", array(cls(ITEM_CLASS_PATH)))
ITEM_FIELDS = ((Var("ItemLoaded", array(INT)), "Loaded"), (Var("ItemReserve", array(INT)), "Reserve"),
               (Var("ItemSlot", array(INT)), "Slot"))
# BP_Profile's fields, which profile_asset.py declares.
PROFILE_TABLE = (*(field for field, _owner, _var in STAT_FIELDS), KILLS_FIELD, EQUIPPED_FIELD,
                 ITEM_CLASSES_FIELD, *(field for field, _item_var in ITEM_FIELDS))

# --- the countdown -----------------------------------------------------------
# The M panel's "save and exit" row starts it (Enter or a click on the row;
# EXIT_ACTION is what PauseClick is matched against).
EXIT_ACTION = "save_exit"
EXIT_ROW_LABEL = "Save and Exit"

# The countdown is the weapon component's (combat/ask_consts.py has its
# variables and its length). The HUD's own: set once the countdown is over
# and the profile written, so it is written once.
EXIT_LEAVING_VAR = Var("ExitLeaving", BOOL, False)
# Set once the profile has been looked for (and applied, if there was one).
PROFILE_CHECKED_VAR = Var("ProfileChecked", BOOL, False)
# Set once a dead player's profile has been deleted, so it is deleted once.
PROFILE_FORGOTTEN_VAR = Var("ProfileForgotten", BOOL, False)
# The HUD's three, which save_exit.py declares.
HUD_TABLE = (EXIT_LEAVING_VAR, PROFILE_CHECKED_VAR, PROFILE_FORGOTTEN_VAR)

# --- the banner --------------------------------------------------------------
EXIT_BANNER_PREFIX = "SAVING AND EXITING IN  "
EXIT_CALLED_OFF_TEXT = "EXIT CALLED OFF  -  you were hit"
EXIT_CALLED_OFF_SHOWN_S = 3.0
