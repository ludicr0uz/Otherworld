"""The M panel's dev-all-guns cheat: its key, label, request flag and guns.

A testing aid: [K] with the panel open hands the player one of every gun (and
the knife) it does not already carry, so a weapon can be tried without finding its drop.
dev_guns.py authors it; the constants live here so umg_consts can label the
row without importing a graph module.
"""

from combat.paths import (
    KNIFE_BP_PATH, PISTOL_BP_PATH, RIFLE_BP_PATH, SHOTGUN_BP_PATH, SMG_BP_PATH,
    SNIPER_BP_PATH,
)

# K: free in the panel and out of it. G would also drop the held gun, since
# the weapon component polls its keys whether or not the panel is open.
DEV_GUNS_KEY = "K"
DEV_GUNS_ROW_LABEL = f"[{DEV_GUNS_KEY}]   dev-all-guns"

# The HUD's variables. The key only raises the request; Tick serves it and
# lowers it, so a probe can ask for the guns without a key press.
DEV_GUNS_REQUEST_VAR = "DevAllGunsRequested"
# Scratch for the "already carried?" scan of one gun class.
DEV_HAS_GUN_VAR = "DevHasGun"

# Every gun, issued or found, in weapon_specs order, and the knife (issued too,
# but a player who dropped it gets it back).
DEV_GUN_BP_PATHS = (SHOTGUN_BP_PATH, PISTOL_BP_PATH, SMG_BP_PATH, RIFLE_BP_PATH,
                    SNIPER_BP_PATH, KNIFE_BP_PATH)
DEV_GUN_CLASS_PATHS = tuple(f"{p}.{p.rsplit('/', 1)[1]}_C" for p in DEV_GUN_BP_PATHS)
