"""The names and numbers of corpse loot, shared by the roll, the HUD and the
checks. Constants only: no unreal, and no item paths (tables.py names the
items), so combat can import this without naming a survival asset.

The table and the body's contents are parallel arrays on BP_HealthComponent,
because Python cannot author a Blueprint struct:

    LootTable[i]       an item class a body of this kind may carry
    LootChances[i]     the chance (0..1) it does, rolled once per counted kill
    LootTableNames[i]  the item's own DisplayName
    LootTableIcons[i]  its inventory icon (a white silhouette) ...
    LootTableTints[i]  ... and the SlotColor that tints it: what the loot
                       window draws for it

    Loot[j], LootNames[j], LootIcons[j], LootTints[j]
                       what this body does carry, filled at the kill
"""

from uebp.vars import FLOAT, REPLICATED, STRING, Var, array, cls, obj, struct

# The classes are class-of-Actor, for DropClasses' reason: the health component
# compiles before any item it names exists.
_ITEM = array(cls("/Script/Engine.Actor"))
_TEXT = array(STRING)
_ICON = array(obj("/Script/Engine.Texture2D"))
_TINT = array(struct("/Script/CoreUObject.LinearColor"))
LOOT_TABLE_VAR = Var("LootTable", _ITEM)
LOOT_CHANCES_VAR = Var("LootChances", array(FLOAT))
LOOT_TABLE_NAMES_VAR = Var("LootTableNames", _TEXT)
LOOT_VAR = Var("Loot", _ITEM, rep=REPLICATED)
LOOT_NAMES_VAR = Var("LootNames", _TEXT, rep=REPLICATED)
LOOT_TABLE_ICONS_VAR = Var("LootTableIcons", _ICON)
LOOT_TABLE_TINTS_VAR = Var("LootTableTints", _TINT)
LOOT_ICONS_VAR = Var("LootIcons", _ICON, rep=REPLICATED)
LOOT_TINTS_VAR = Var("LootTints", _TINT, rep=REPLICATED)
# BP_HealthComponent's loot rows, in the order loot/roll.py has always declared
# them.
TABLE = (LOOT_TABLE_VAR, LOOT_CHANCES_VAR, LOOT_TABLE_NAMES_VAR, LOOT_VAR, LOOT_NAMES_VAR,
         LOOT_TABLE_ICONS_VAR, LOOT_ICONS_VAR, LOOT_TABLE_TINTS_VAR, LOOT_TINTS_VAR)

# (the table's array, the body's): a hit copies entry i of each across, and a
# take removes the row from every body array.
LOOT_ARRAYS = ((LOOT_TABLE_VAR, LOOT_VAR), (LOOT_TABLE_NAMES_VAR, LOOT_NAMES_VAR),
               (LOOT_TABLE_ICONS_VAR, LOOT_ICONS_VAR),
               (LOOT_TABLE_TINTS_VAR, LOOT_TINTS_VAR))
BODY_ARRAYS = tuple(body for _table, body in LOOT_ARRAYS)

# How close the player must stand to a body to search it: the E interact's
# reach (combat.tuning.INTERACT_RADIUS), measured to the ragdoll, not the capsule.
LOOT_RADIUS = 250.0
# How far from the body's actor the server lets a take be asked from. Wider
# than the window's reach: the window measures to the ragdoll, which lies
# where each machine's own physics left it, a step or two from the actor.
LOOT_TAKE_REACH_CM = LOOT_RADIUS + 300.0
