"""verify_clothing.py's sections, in the order it runs them. Each module's
run() is self-contained.

  garments    each BP_<Garment>: a BP_WeaponItem, Consumable, Dropped, its
              ClothingSlot, name, model, icon, and held in the fist
  test_items  the test garments laid in front of the 200 m map's PlayerStart
  base_body   the player's body in boxers (SKM_Adventurer02): imported, rigged,
              animated, not yet worn
"""

SECTIONS = ("garments", "test_items", "base_body")
