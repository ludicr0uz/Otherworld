"""The Enhanced Input assets' names and paths (I1): the game's own mapping
context and the one action it has so far, the trigger. input_assets.py
authors them; the player's native parent (Source/Otherworld,
OtherworldCharacter) adds the context and binds the action.

The stock template's /Game/Input (its own IMC_Default: move, look, jump) is
checksummed engine content and stays untouched: this context is a second
one, under /Game/Weapons/Input.
"""

from combat.paths import WEAPON_DIR
from combat.tuning import FIRE_KEY

INPUT_DIR = f"{WEAPON_DIR}/Input"
IA_FIRE_NAME = "IA_Fire"
IMC_NAME = "IMC_Default"
IA_FIRE = f"{INPUT_DIR}/{IA_FIRE_NAME}"
IMC_DEFAULT = f"{INPUT_DIR}/{IMC_NAME}"

# (action asset, its default key): the context's rows, one per action.
MAPPINGS = ((IA_FIRE, FIRE_KEY),)

# The character's class defaults that name them (OtherworldCharacter.h).
CONTEXT_PROP = "input_context"
FIRE_ACTION_PROP = "fire_action"
