"""The inventory's slots: the hand, the four weapon slots and the backpack.
Constants only. The graphs are weapon_component/slot_sync.py (where each item
is) and slot_moves.py (the keys and the moves); the HUD draws them
(graphics_menu/hud_inventory.py).

Every carried item is in Inventory, as before, and says where it is itself:
its Slot, one code over all fifteen places,

    0            HAND        the item in hand (Held, once equipped)
    1 2 3 4      weapons     primary, secondary, pistol, melee
    5 .. 14      backpack    the bag's ten slots; 5..9 are on keys 5..9
    -1           UNPLACED    just picked up, looted or taken off: the next
                             sync puts it in the first free bag slot, or in
                             the hand if the bag is full

so an item that leaves Inventory (eaten, dropped, thrown, worn) leaves its
slot with it, and nothing else has to be told. A weapon's WeaponKind is the
weapon slot it belongs in (a long gun's is PRIMARY, and fits SECONDARY too);
NOT_A_WEAPON fits no weapon slot. The hand and the bag take anything.
"""

HAND = 0
PRIMARY, SECONDARY, PISTOL_SLOT, MELEE_SLOT = 1, 2, 3, 4
WEAPON_SLOTS = (PRIMARY, SECONDARY, PISTOL_SLOT, MELEE_SLOT)
WEAPON_SLOT_NAMES = ("PRIMARY", "SECONDARY", "PISTOL", "MELEE")
BAG_FIRST = 5
BAG_SIZE = 10
BAG_LAST = BAG_FIRST + BAG_SIZE - 1
SLOT_COUNT = BAG_FIRST + BAG_SIZE          # 15 codes, 0 .. 14
UNPLACED = -1
NO_REQUEST = -1

# WeaponKind on the item: the weapon slot it goes in.
NOT_A_WEAPON = -1
LONG_GUN = PRIMARY            # shotgun, SMG, rifle, sniper: primary or secondary
PISTOL_KIND = PISTOL_SLOT
MELEE_KIND = MELEE_SLOT
# A gun row's kind by its display name; every other gun is a long gun.
GUN_KINDS = {"Pistol": PISTOL_KIND}

# On BP_WeaponItem.
SLOT_VAR = "Slot"
WEAPON_KIND_VAR = "WeaponKind"

# On BP_WeaponComponent. SlotItems[code] is the item in that slot or None,
# rebuilt every Tick by the sync from the items' own Slots: the view the
# HUD draws and the moves test for room.
SLOT_ITEMS_VAR = "SlotItems"
HAND_FROM_VAR = "HandFrom"        # the slot the hand's item came from
HAS_ROOM_VAR = "HasRoom"          # a free bag slot, or empty hands: a pick-up fits
SLOT_PICK_VAR = "SlotPick"        # scratch: the slot a search settled on
# Requests, served on the component's Tick and lowered (NO_REQUEST):
SLOT_REQUEST_VAR = "SlotRequest"  # bring this slot's item to hand (a key, a click)
MOVE_FROM_VAR = "MoveFrom"        # a drag on the HUD: from this slot ...
MOVE_TO_VAR = "MoveTo"            # ... to this one, swapping if it is filled
SLOT_WANT_VAR = "SlotWant"        # the request's copies, read after it is lowered
MOVE_SRC_VAR, MOVE_DST_VAR = "MoveSrc", "MoveDst"
# A drag released outside the inventory: set this slot's item down on the
# ground. A slot code, or SLOT_COUNT + a worn slot (wear_tuning.WEAR_SLOTS).
DROP_REQUEST_VAR = "DropRequest"
DROP_WANT_VAR = "DropWant"        # its copy, read after it is lowered
DROP_ITEM_VAR = "DropItem"        # the item being set down, held still

# The number keys: (component variable, default key, the slot it brings to
# hand). 1-4 the weapon slots, 5-9 the bag's first five. Fixed keys on the
# component, not settings binds: the settings page rebinds BIND_VARS only.
SLOT_KEYS = tuple(
    (f"KeySlot{n}", key, slot) for n, key, slot in zip(
        range(1, 10),
        ("One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"),
        (*WEAPON_SLOTS, *range(BAG_FIRST, BAG_FIRST + 5))))

# Where BeginPlay puts the issued items (inventory.STARTER_CLASS_VARS, in
# that order): the shotgun in hand, out of the primary slot; the pistol and
# the knife in theirs; the axe, the matches and the stick in the bag.
STARTER_SLOTS = (HAND, PISTOL_SLOT, MELEE_SLOT, BAG_FIRST, BAG_FIRST + 1, BAG_FIRST + 2)
STARTER_HAND_FROM = PRIMARY


def fits(kind, slot):
    """Python's copy of the graphs' rule (slot_moves._fits), for the checks."""
    if slot in WEAPON_SLOTS:
        return kind == slot or (kind == LONG_GUN and slot == SECONDARY)
    return 0 <= slot < SLOT_COUNT
