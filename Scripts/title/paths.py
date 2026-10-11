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
# finds them).
LABEL = "Lvl_Title"
FLOOR_LABEL = f"{LABEL}_Floor"
KEY_LIGHT_LABEL = f"{LABEL}_KeyLight"
FILL_LIGHT_LABEL = f"{LABEL}_FillLight"
FOG_LABEL = f"{LABEL}_Fog"
POST_PROCESS_LABEL = f"{LABEL}_PostProcess"
CAMERA_LABEL = f"{LABEL}_Camera"
PLAYER_START_LABEL = f"{LABEL}_PlayerStart"
LABELS = (FLOOR_LABEL, KEY_LIGHT_LABEL, FILL_LIGHT_LABEL, FOG_LABEL, POST_PROCESS_LABEL,
          CAMERA_LABEL, PLAYER_START_LABEL)

# The floor: the engine's cube, scaled, its top at z = 0, in a near-black
# matte of its own (the forest's ground read as pale sand with a hard
# horizon under the stage's lights): the figure stands in a dark void.
FLOOR_MESH = "/Engine/BasicShapes/Cube"
FLOOR_MATERIAL = "/Game/Title/M_TitleFloor"
FLOOR_COLOUR = (0.004, 0.004, 0.005)
FLOOR_METALLIC = 0.0
FLOOR_ROUGHNESS = 0.9
FLOOR_SCALE = (30.0, 30.0, 1.0)         # 3000 x 3000 x 100 cm
FLOOR_Z = -50.0

# The figure spawns here, facing +X, and the camera looks back at it from
# +X, off to its left so the figure stands right of centre, clear of the
# menu at the top left. (pitch, yaw, roll) as the engine's Rotator.
PLAYER_START = (0.0, 0.0, 100.0)
PLAYER_START_YAW = 0.0
CAMERA = (430.0, 70.0, 95.0)
CAMERA_ROTATION = (-2.0, 180.0, 0.0)
CAMERA_FOV = 50.0

# A key light from the camera's side, high, warm; a dim cool fill from behind
# and the other side, without shadows. Intensity in lux, as the forest's.
KEY_LIGHT = dict(rotation=(-35.0, 150.0, 0.0), intensity=4.0,
                 color=(1.0, 0.93, 0.84))
FILL_LIGHT = dict(rotation=(-20.0, -40.0, 0.0), intensity=0.8,
                  color=(0.75, 0.82, 1.0))
# The floor fades into black with distance (nothing else is on the stage).
FOG = dict(density=0.04, height_falloff=0.2, luminance=(0.004, 0.004, 0.006))
# A fixed exposure (min = max): auto exposure over a black void would hunt.
EXPOSURE = dict(min_brightness=0.6, max_brightness=0.6, bias=0.0)
# Each of them takes its override flag on the volume's settings: without
# it the value is stored and never applied, and auto exposure greys the dark.
EXPOSURE_OVERRIDES = ("override_auto_exposure_method", "override_auto_exposure_min_brightness",
                      "override_auto_exposure_max_brightness", "override_auto_exposure_bias")
