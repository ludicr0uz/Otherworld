"""The title level, by name, and the stage's numbers. Constants only: the
HUD's builder (graphics_menu) reads TITLE_LEVEL_NAME and PLAY_LEVEL, the
harness (Scripts/dev/uepylib/game.py) names TITLE_LEVEL once more, held to
this by a dev unit test."""

# The level the game opens on (DefaultEngine.ini GameDefaultMap), with no
# forest in it: the menu stands over the character on this stage.
TITLE_LEVEL = "/Game/Maps/Lvl_Title"
TITLE_LEVEL_NAME = "Lvl_Title"
# What New Game opens: the forest the game is played in.
PLAY_LEVEL = "/Game/Maps/Lvl_Forest_1000m"

# The stage's actors, by label (the builder replaces its own, the verifier
# finds them). The trees' cells are labelled as any level's are
# (forest_generator/tree_cells.py), under TREE_LABEL_PREFIX.
LABEL = "Lvl_Title"
FLOOR_LABEL = f"{LABEL}_Floor"
MOON_LABEL = f"{LABEL}_Moon"
SKY_ATMOSPHERE_LABEL = f"{LABEL}_SkyAtmosphere"
SKY_SPHERE_LABEL = f"{LABEL}_SkySphere"
SKY_LIGHT_LABEL = f"{LABEL}_SkyLight"
FOG_LABEL = f"{LABEL}_Fog"
POST_PROCESS_LABEL = f"{LABEL}_PostProcess"
CAMERA_LABEL = f"{LABEL}_Camera"
PLAYER_START_LABEL = f"{LABEL}_PlayerStart"
LABELS = (FLOOR_LABEL, MOON_LABEL, SKY_ATMOSPHERE_LABEL, SKY_SPHERE_LABEL, SKY_LIGHT_LABEL,
          FOG_LABEL, POST_PROCESS_LABEL, CAMERA_LABEL, PLAYER_START_LABEL)
TREE_LABEL_PREFIX = "HISM_Tree"
# What the stage held when it was a lit void: a rebuild takes them out.
RETIRED_LABELS = (f"{LABEL}_KeyLight", f"{LABEL}_FillLight")

# The floor: the engine's cube, scaled, its top at z = 0, in the forest's
# ground. That material tiles 40 times over the mesh's UVs, so a 200 m floor
# has the 200 m level's 5 m tiles, and its edge is far inside the night fog.
FLOOR_MESH = "/Engine/BasicShapes/Cube"
FLOOR_MATERIAL = "/Game/Forest/Materials/M_Forest_Ground_PBR"
FLOOR_SCALE = (200.0, 200.0, 1.0)       # 200 x 200 x 1 m
FLOOR_Z = -50.0

# The trees: the play level's own, those standing within this distance of
# its middle (title/forest.py), where its scatter is thickest.
TREE_RADIUS_CM = 6000.0

# The night: the forest's static night rig (forest_generator/lighting.py,
# the "night" preset: the moon, the starfield dome that lights the sky
# light, the fog, the exposure range), with no clock to turn it into day.
NIGHT_PRESET = "night"
SKY_SPHERE_MESH = "/Engine/EngineSky/SM_SkySphere"
SKY_SPHERE_MATERIAL = "/Game/Forest/Materials/Instances/MI_NightSky_Starfield"
SKY_SPHERE_SCALE = 400.0

# The figure spawns here, facing +X, and the camera looks back at it from
# +X, off to its left so the figure stands right of centre, clear of the
# menu at the top left. (pitch, yaw, roll) as the engine's Rotator.
PLAYER_START = (0.0, 0.0, 100.0)
PLAYER_START_YAW = 0.0
CAMERA = (430.0, 70.0, 95.0)
CAMERA_ROTATION = (-2.0, 180.0, 0.0)
CAMERA_FOV = 50.0

# Each exposure setting takes its override flag on the volume's settings:
# without it the value is stored and never applied, and auto exposure greys
# the dark.
EXPOSURE_OVERRIDES = ("override_auto_exposure_method", "override_auto_exposure_min_brightness",
                      "override_auto_exposure_max_brightness", "override_auto_exposure_bias")
EXPOSURE_KEYS = ("auto_exposure_min_brightness", "auto_exposure_max_brightness",
                 "auto_exposure_bias")
