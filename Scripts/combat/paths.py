"""Asset paths and generated-class paths for everything under /Game/Weapons,
plus the stock assets (character, game mode, ABP, NPC) this package patches.
Constants only.
"""



# ─── Paths ───────────────────────────────────────────────────────────────────

WEAPON_DIR = "/Game/Weapons"
AUDIO_DIR = f"{WEAPON_DIR}/Audio"
# Where Scripts/asset_pipeline/import_ui_art.py puts the generated HUD art.
UI_ART_DIR = "/Game/UI/Art"
MAT_METAL = f"{WEAPON_DIR}/M_Gunmetal"
MAT_WOOD = f"{WEAPON_DIR}/M_GunWood"
MAT_BLOOD = f"{WEAPON_DIR}/M_Blood"
MAT_BRASS = f"{WEAPON_DIR}/M_Brass"
# What a bullet knocks off the scenery (bullet_impact.py): chips and dust.
MAT_IMPACT_CHIP = f"{WEAPON_DIR}/M_ImpactChip"
MAT_IMPACT_DUST = f"{WEAPON_DIR}/M_ImpactDust"
MAT_THROW_ARC = f"{WEAPON_DIR}/M_ThrowArc"

ITEM_BP_PATH = f"{WEAPON_DIR}/BP_WeaponItem"
SHOTGUN_BP_PATH = f"{WEAPON_DIR}/BP_Shotgun"
PISTOL_BP_PATH = f"{WEAPON_DIR}/BP_Pistol"
SMG_BP_PATH = f"{WEAPON_DIR}/BP_SMG"
RIFLE_BP_PATH = f"{WEAPON_DIR}/BP_AssaultRifle"
SNIPER_BP_PATH = f"{WEAPON_DIR}/BP_SniperRifle"
# The knife: a melee item, not a gun (knife.py), and its slash clip, which
# knife_anim.py keys for whatever body the player wears.
KNIFE_BP_PATH = f"{WEAPON_DIR}/BP_Knife"
KNIFE_ANIM_PATH = f"{WEAPON_DIR}/Anims/A_KnifeSlash"
# The hold poses (combat/hold_pose.py): food and water carried, the knife ready.
HOLD_ITEM_ANIM_PATH = f"{WEAPON_DIR}/Anims/A_HoldItem"
HOLD_KNIFE_ANIM_PATH = f"{WEAPON_DIR}/Anims/A_HoldKnife"
HEALTH_BP_PATH = f"{WEAPON_DIR}/BP_HealthComponent"
WEAPON_COMP_BP_PATH = f"{WEAPON_DIR}/BP_WeaponComponent"
BLOOD_BP_PATH = f"{WEAPON_DIR}/BP_BloodSplash"
# The burst where a bullet hits anything that does not bleed (bullet_impact.py).
BULLET_IMPACT_BP_PATH = f"{WEAPON_DIR}/BP_BulletImpact"
AMMO_BP_PATH = f"{WEAPON_DIR}/BP_AmmoPickup"
# The dotted arc drawn while a throw is aimed (throw_arc.py).
THROW_ARC_BP_PATH = f"{WEAPON_DIR}/BP_ThrowArc"
# The settings SaveGame. It lives beside the weapons rather than under /Game/UI
# because this file builds it, and Scripts/forest_generator/asset_sources.py
# names exactly one builder per content directory -- a second directory owned by
# a second script is the thing that table exists to prevent.
SETTINGS_BP_PATH = f"{WEAPON_DIR}/BP_Settings"
# One slot, index 0. There are no profiles and no per-level settings: a keybind
# the player set once has to be there the next time the game is opened, which is
# the whole requirement.
SETTINGS_SLOT = "OtherworldSettings"
SETTINGS_USER_INDEX = 0

CHARACTER_BP_PATH = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter"
GAME_MODE_BP_PATH = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode"
NPC_BP_PATH = "/Game/Forest/NPC/BP_ForestWanderer"
ABP_PATH = "/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed"

CHARACTER_CLASS_PATH = f"{CHARACTER_BP_PATH}.BP_ThirdPersonCharacter_C"
GAME_MODE_CLASS_PATH = f"{GAME_MODE_BP_PATH}.BP_ThirdPersonGameMode_C"
NPC_CLASS_PATH = f"{NPC_BP_PATH}.BP_ForestWanderer_C"
ITEM_CLASS_PATH = f"{ITEM_BP_PATH}.BP_WeaponItem_C"
HEALTH_CLASS_PATH = f"{HEALTH_BP_PATH}.BP_HealthComponent_C"
WEAPON_COMP_CLASS_PATH = f"{WEAPON_COMP_BP_PATH}.BP_WeaponComponent_C"
BLOOD_CLASS_PATH = f"{BLOOD_BP_PATH}.BP_BloodSplash_C"
BULLET_IMPACT_CLASS_PATH = f"{BULLET_IMPACT_BP_PATH}.BP_BulletImpact_C"
AMMO_CLASS_PATH = f"{AMMO_BP_PATH}.BP_AmmoPickup_C"
THROW_ARC_CLASS_PATH = f"{THROW_ARC_BP_PATH}.BP_ThrowArc_C"
SETTINGS_CLASS_PATH = f"{SETTINGS_BP_PATH}.BP_Settings_C"

CUBE = "/Engine/BasicShapes/Cube"          # 100 cm box
CYLINDER = "/Engine/BasicShapes/Cylinder"  # 100 cm tall, 50 cm radius, axis +Z
SPHERE = "/Engine/BasicShapes/Sphere"      # 100 cm diameter
