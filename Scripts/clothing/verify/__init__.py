"""verify_clothing.py's sections, in the order it runs them. Each module's
run() is self-contained.

  garments    each BP_<Garment>: a BP_WeaponItem, Consumable, Dropped, its
              ClothingSlot, name, model, icon, and held in the fist
  test_items  the test garments laid in front of the 200 m map's PlayerStart
  base_body   the base body in tight shorts (player_body.CLOTHING_BASE_BODY): imported, rigged,
              animated, not yet worn
"""

SECTIONS = ("garments", "test_items", "base_body")
