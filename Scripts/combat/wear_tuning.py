"""Clothing: the slots a garment is worn in and the names the graphs share.
Constants only. The wear and the take-off are weapon_component/wear.py, the
garments Scripts/clothing, the I panel graphics_menu/wear_*.py.

A garment is a BP_WeaponItem whose ClothingSlot is one of WEAR_SLOTS' indices
(NOT_CLOTHING, -1, on every other item). It is also Consumable: the fire key
uses it rather than firing it, and that use is wearing it.

The worn ones stay actors, as everything in the bag is: Worn[slot] is the
very garment that was picked up, hidden and out of Inventory, and taking it
off puts that same actor back in the bag.
"""

# Head to foot, then the pack: the order the I panel lists them in, and the
# index each garment's ClothingSlot holds.
WEAR_SLOTS = ("hat", "glasses", "shirt", "jacket", "gloves", "pants", "boots",
              "backpack")
NOT_CLOTHING = -1

CLOTHING_SLOT_VAR = "ClothingSlot"    # on the item: its slot, or NOT_CLOTHING
WORN_VAR = "Worn"                     # on the component: Worn[slot], the garment
                                      # worn there or None (grown by the wear)
TAKE_OFF_VAR = "TakeOffSlot"          # on the component: a slot to take off
                                      # into the bag this Tick, or NOT_CLOTHING
WEAR_ITEM_VAR = "WearItem"            # the garment being put on, held still
                                      # while Held is cleared
TAKE_OFF_TO_VAR = "TakeOffTo"          # with TakeOffSlot: the hand or the bag slot
                                      # a drag dropped it on, or UNPLACED (-1)
SERVER_WEAR = "Server_Wear"            # the fire key's wear, asked of the server
                                      # (weapon_component/wear.py)
WEAR_REQUEST_VAR = "WearRequest"      # on the component: a slot code whose item
                                      # is to be worn (a drag onto the worn
                                      # grid), or NOT_CLOTHING
