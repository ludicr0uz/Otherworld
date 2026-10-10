"""verify_clothing.py's sections, in the order it runs them. Each module's
run() is self-contained.

  garments    each BP_<Garment>: a BP_WeaponItem, Consumable, Dropped, its
              ClothingSlot, name, model (the three with a worn mesh lie as
              it), icon, and held in the fist
  test_items  the test garments laid in front of the 200 m map's PlayerStart
"""

SECTIONS = ("garments", "test_items")
