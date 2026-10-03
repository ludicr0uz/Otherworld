"""/Game asset paths for everything the survival package builds."""

SURVIVAL_DIR = "/Game/Survival"

CONSUMABLE_BP_PATH = f"{SURVIVAL_DIR}/BP_ConsumableItem"
MUSHROOM_BP_PATH = f"{SURVIVAL_DIR}/BP_Mushroom"
CANTEEN_BP_PATH = f"{SURVIVAL_DIR}/BP_WaterCanteen"
SURVIVAL_BP_PATH = f"{SURVIVAL_DIR}/BP_SurvivalComponent"
CONSUME_ABILITY_PATH = f"{SURVIVAL_DIR}/GA_ConsumeItem"
STARVING_GE_PATH = f"{SURVIVAL_DIR}/GE_Starving"
DEHYDRATED_GE_PATH = f"{SURVIVAL_DIR}/GE_Dehydrated"
BLEEDING_GE_PATH = f"{SURVIVAL_DIR}/GE_Bleeding"
CAMPFIRE_BP_PATH = f"{SURVIVAL_DIR}/BP_Campfire"

MAT_MUSHROOM_CAP = f"{SURVIVAL_DIR}/M_MushroomCap"
MAT_MUSHROOM_STEM = f"{SURVIVAL_DIR}/M_MushroomStem"
MAT_CANTEEN = f"{SURVIVAL_DIR}/M_Canteen"

CONSUMABLE_CLASS_PATH = f"{CONSUMABLE_BP_PATH}.BP_ConsumableItem_C"
SURVIVAL_CLASS_PATH = f"{SURVIVAL_BP_PATH}.BP_SurvivalComponent_C"
MUSHROOM_CLASS_PATH = f"{MUSHROOM_BP_PATH}.BP_Mushroom_C"
CANTEEN_CLASS_PATH = f"{CANTEEN_BP_PATH}.BP_WaterCanteen_C"
BLEEDING_GE_CLASS_PATH = f"{BLEEDING_GE_PATH}.GE_Bleeding_C"
CAMPFIRE_CLASS_PATH = f"{CAMPFIRE_BP_PATH}.BP_Campfire_C"

# The player's and the wanderer's component names. Both characters get the
# ability system; only the player gets hunger and thirst.
ASC_COMPONENT = "AbilitySystem"
SURVIVAL_COMPONENT = "SurvivalComponent"

