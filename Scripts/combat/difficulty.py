"""The game's difficulty setting: its three levels, their names, and the
variable that carries the choice. Constants only.

Chosen on the settings screen (graphics_menu/difficulty.py), saved in
BP_Settings like every other setting, and copied onto the GameMode each
DrawHUD so gameplay reads one world-scoped value and never learns that a save
file exists. Declared here, in combat, because both of its homes --
BP_Settings and the GameMode's variables -- are built by
build_weapons_and_combat.py, which runs before survival and the HUD.

An int and not an enum: an enum pin is a literal and cannot be driven by a
variable (CLAUDE.md), and a user-defined enum asset needs authoring Python
cannot do. The index is what the save stores, so the order is load-bearing:
reordering DIFFICULTY_LABELS changes the difficulty of every save on disk.

What each level changes: on EASY a mushroom also heals (survival.tuning's
MUSHROOM_HEALTH_EASY). MEDIUM and SURVIVOR change nothing yet.
"""

DIFFICULTY_VAR = "Difficulty"

EASY = 0
MEDIUM = 1
SURVIVOR = 2
DIFFICULTY_LABELS = ("EASY", "MEDIUM", "SURVIVOR")
DEFAULT_DIFFICULTY = EASY
