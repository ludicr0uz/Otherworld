"""What a mesh is, read off its path. No `unreal` import.

The registry does not say whether a mesh is a tree or a rifle, so the path
decides. ROWS is read top to bottom and the first row that matches names the
mesh's category (the page's tabs) and its kind within it (the chips). A row
matches by a word in the asset's own name or by a word in its folders: the
two are kept apart because a pack's folder names what the pack is and says
nothing of a part ("..._Wooden_Stock_High_Poly/SM_Shotgun_02" is a shotgun,
not a stock). All of it is lower-cased first.

A mesh no row claims is ("Other", "other"): a new pack shows up without a row
here, and a row is added only to name what it holds.
"""

# The page's tabs, in this order.
CATEGORIES = ("Environment", "Structures", "Weapons", "Items", "Clothing", "Characters",
              "Other")
FALLBACK = ("Other", "other")

# (category, kind, words in the name, words in the folders)
ROWS = (
    # A character pack's demo level is built of these, so before the rest.
    ("Structures", "blockout", (), ("levelprototyping",)),
    # Parts before whole weapons: "SM_AR4_Mag" is a magazine.
    ("Weapons", "ammo", ("shell_", "bullet", "ammo"), ()),
    ("Weapons", "magazine", ("_mag", "magazine"), ()),
    ("Weapons", "attachment", ("scope", "sight", "suppressor", "supressor", "grip",
                               "handguard", "_stock_", "stockless", "muzzle", "flash_hider",
                               "trigger", "circle_base"), ()),
    ("Weapons", "explosive", ("grenade", "g67"), ()),
    ("Weapons", "melee", ("knife", "_axe", "character_bat", "baseball_bat", "machete"), ()),
    ("Weapons", "pistol", ("pistol", "revolver", "1911", "flaregun"), ()),
    ("Weapons", "shotgun", ("shotgun", "sawedoff"), ()),
    ("Weapons", "rifle", ("rifle", "bullpup", "submachinegun", "smg", "ar4", "ka47", "ka74u",
                          "ka_val", "aks74u", "ak74u", "mauser", "m4_body", "sniper"), ()),
    ("Weapons", "other weapon", ("weapon", "gun"), ("weapon", "gun", "m4_modular")),
    ("Clothing", "headwear", ("_hat", "helmet", "beanie"), ()),
    ("Clothing", "garment", ("jacket", "puffer", "boots", "pants", "shirt", "glove"),
     ("/clothing/",)),
    ("Items", "food and drink", ("_can_", "bottle", "canteen"), ()),
    ("Items", "medical", ("bandage", "firstaid", "medkit"), ()),
    ("Items", "container", ("backpack", "trashcan", "gascan", "propanetank", "crate"), ()),
    ("Items", "camp", ("_tent", "bonfire", "campfire", "_raft"), ()),
    ("Items", "tool", ("compass", "shovel", "torch", "radio", "phone", "_match", "_pan",
                       "_pot", "battery", "beartrap"), ()),
    ("Items", "other item", (), ("/survival/",)),
    # Before "Characters": a character pack's demo has a curtain.
    ("Structures", "structure", ("ladder", "wall", "floor", "ramp", "stair", "cube", "door",
                                 "fence", "curtain"), ("/levels/",)),
    ("Characters", "hair", ("hair", "goatee", "mustache", "eyebrow", "eyelash", "beard"),
     ("hair",)),
    ("Characters", "rig control", (), ("/controls/",)),
    ("Characters", "body", ("mannequin", "manny", "quinn", "zombie", "wendigo", "adventurer"),
     ("metahuman", "character", "mannequin", "/bound/", "mixamo", "lyra", "/ual")),
    # Before "tree": a shrub's parts are branches too.
    ("Environment", "shrub", ("shrub", "bush", "hedge"),
     ("shrub", "bush", "rose", "greasewood")),
    ("Environment", "tree", ("tree", "pine", "spruce", "fir_", "birch", "oak", "trunk",
                             "sapling", "branch", "twig", "stump", "root", "log_"),
     ("tree_", "/trees/")),
    ("Environment", "grass", ("grass", "clover", "weed", "reed"), ("grass",)),
    ("Environment", "plant", ("fern", "flower", "plant", "moss", "periwinkle", "ivy", "leaf",
                              "mushroom"), ()),
    ("Environment", "rock", ("rock", "stone", "boulder", "cliff", "pebble"), ()),
    ("Environment", "terrain", ("landscape", "terrain", "ground"), ()),
    # Last: a foliage pack holds rocks too.
    ("Environment", "plant", (), ("foliage", "plant")),
)

# Folders whose packs sit one level down: /Game/Fab/<pack>, not /Game/Fab.
NESTED = ("Fab", "Forest", "Megaplant_Library", "Sourced")


def classify(path):
    """(category, kind) of the mesh at a /Game path."""
    folders, name = path.lower().rsplit("/", 1)
    folders += "/"
    for category, kind, in_name, in_folders in ROWS:
        if any(w in name for w in in_name) or any(w in folders for w in in_folders):
            return category, kind
    return FALLBACK


def pack_of(path):
    """"/Game/Fab/CC0_Axe/SM_Axe" -> "Fab/CC0_Axe"; "/Game/PN_GrassLibrary/Meshes/X"
    -> "PN_GrassLibrary"."""
    parts = path.split("/")[2:-1]
    if not parts:
        return "(root)"
    if parts[0] in NESTED and len(parts) > 1:
        return "/".join(parts[:2])
    return parts[0]
