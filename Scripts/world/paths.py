"""/Game paths, class paths and actor tags for the world package."""

DAY_NIGHT_BP_PATH = "/Game/World/BP_DayNightCycle"
DAY_NIGHT_CLASS_PATH = f"{DAY_NIGHT_BP_PATH}.BP_DayNightCycle_C"
SKY_MATERIAL_PATH = "/Game/World/Materials/M_DayNightSky"

SKY_SPHERE_MESH_PATH = "/Engine/EngineSky/SM_SkySphere.SM_SkySphere"
# The star map, drawn from world/star_catalogue.csv (world/star_texture.py).
STARS_TEXTURE_PATH = "/Game/World/Textures/T_NightSkyStars"

# On the cycle actor placed in each level (so a re-run replaces it).
DAY_NIGHT_TAG = "OW_DayNight"
# On the level's own static sky rig -- its directional light, sky light, fog,
# clouds and sky dome. The cycle destroys everything carrying it at BeginPlay
# and supplies its own, so the levels' generated lighting stays as generated
# (and verified), and a level without a cycle actor still plays at night.
STATIC_SKY_TAG = "OW_StaticSky"
