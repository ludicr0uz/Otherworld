"""The M panel's dev-all-guns cheat: its row, label, request flag and guns.

A testing aid: its row in the open panel hands the player one of every gun (and
the knife and the axe) it does not already carry, so a weapon can be tried without finding its drop.
dev_guns.py authors it; the constants live here so umg_consts can label the
row without importing a graph module.
"""

from combat.paths import (
    AXE_BP_PATH, KNIFE_BP_PATH, PISTOL_BP_PATH, RIFLE_BP_PATH, SHOTGUN_BP_PATH, SMG_BP_PATH,
    SNIPER_BP_PATH,
)

# The M panel's row: its action (what PauseClick is matched against,
# umg_consts.PAUSE_ROW_ACTIONS) and its words. No key of its own: a row is
# taken with Enter or a click.
DEV_GUNS_ACTION = "dev_guns"
DEV_GUNS_ROW_LABEL = "Dev All Guns"

# The HUD's variables. The row only raises the request; Tick serves it and
# lowers it, so a probe can ask for the guns without a key press.
DEV_GUNS_REQUEST_VAR = "DevAllGunsRequested"
# Scratch for the "already carried?" scan of one gun class.
DEV_HAS_GUN_VAR = "DevHasGun"

# Every gun, issued or found, in weapon_specs order, and the knife and the axe
# (issued too, but a player who dropped one gets it back).
DEV_GUN_BP_PATHS = (SHOTGUN_BP_PATH, PISTOL_BP_PATH, SMG_BP_PATH, RIFLE_BP_PATH,
                    SNIPER_BP_PATH, KNIFE_BP_PATH, AXE_BP_PATH)
DEV_GUN_CLASS_PATHS = tuple(f"{p}.{p.rsplit('/', 1)[1]}_C" for p in DEV_GUN_BP_PATHS)
