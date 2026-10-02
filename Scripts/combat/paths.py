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
# What a heated blade glows with (heat.py): the overlay, and each item's
# instance of it, which says where its metal is.
MAT_HOT_METAL = f"{WEAPON_DIR}/M_HotMetal"
MAT_HOT_KNIFE = f"{WEAPON_DIR}/MI_HotKnife"
MAT_HOT_AXE = f"{WEAPON_DIR}/MI_HotAxe"

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
# The axe: the other melee item (axe.py), swung through the knife's stage.
AXE_BP_PATH = f"{WEAPON_DIR}/BP_Axe"
# Wood: what a tree gives the axe (wood.py, weapon_component/chop.py).
WOOD_BP_PATH = f"{WEAPON_DIR}/BP_Wood"
# The matches: struck, with wood in the bag, to light a campfire (matches.py,
# weapon_component/light.py).
MATCHES_BP_PATH = f"{WEAPON_DIR}/BP_Matches"
# The stick: lit at a campfire, a torch until it burns out (stick.py,
# weapon_component/torch.py).
STICK_BP_PATH = f"{WEAPON_DIR}/BP_Stick"
# The hold poses (combat/hold_pose.py): food and water carried, the knife
# ready, the stick carried as a torch and held out at a creature.
HOLD_ITEM_ANIM_PATH = f"{WEAPON_DIR}/Anims/A_HoldItem"
HOLD_KNIFE_ANIM_PATH = f"{WEAPON_DIR}/Anims/A_HoldKnife"
HOLD_TORCH_ANIM_PATH = f"{WEAPON_DIR}/Anims/A_HoldTorch"
WARD_TORCH_ANIM_PATH = f"{WEAPON_DIR}/Anims/A_WardTorch"
# The shotgun's ready pose (combat/shotgun_pose.py): the rifle's, with the
# thumb over a straight stock's wrist.
SHOTGUN_AIM_ANIM_PATH = f"{WEAPON_DIR}/Anims/A_AimShotgun"
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
# On BP_WeaponComponent: the player is holding fire out in front of them (a
# lit stick, raised by the use key: weapon_component/torch.py writes it every
# frame). Nothing in combat reads it; a creature afraid of fire does
# (npc/ward.py), and keeps off the side the player faces while it is true.
FIRE_WARD_VAR = "FireWard"
BLOOD_CLASS_PATH = f"{BLOOD_BP_PATH}.BP_BloodSplash_C"
BULLET_IMPACT_CLASS_PATH = f"{BULLET_IMPACT_BP_PATH}.BP_BulletImpact_C"
AMMO_CLASS_PATH = f"{AMMO_BP_PATH}.BP_AmmoPickup_C"
THROW_ARC_CLASS_PATH = f"{THROW_ARC_BP_PATH}.BP_ThrowArc_C"
SETTINGS_CLASS_PATH = f"{SETTINGS_BP_PATH}.BP_Settings_C"

CUBE = "/Engine/BasicShapes/Cube"          # 100 cm box
CYLINDER = "/Engine/BasicShapes/Cylinder"  # 100 cm tall, 50 cm radius, axis +Z
SPHERE = "/Engine/BasicShapes/Sphere"      # 100 cm diameter
