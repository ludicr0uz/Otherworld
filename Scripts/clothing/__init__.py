"""clothing -- the garments the player wears: shirt, jacket, hat, glasses,
boots, pants, gloves and backpack.

Entry point: Scripts/build_clothing.py (the garments, then the test ones laid
on the 200 m map). Checks: Scripts/verify_clothing.py, which runs
clothing.verify. Design and traps: CLAUDE.md here.

  specs       GARMENTS: each garment's path, name, slot and stand-in model (no
              unreal: the verifier and the placement read it); BASE_BODY_*,
              the body in boxers the garments will be drawn on
  items       BP_<Garment> per row: a Consumable BP_WeaponItem with its
              ClothingSlot, Dropped, and a flat material
  placement   the test garments in a row 3 m in front of Lvl_Forest_200m's
              PlayerStart (tag OW_TestClothing, idempotent)
  verify/     the verifier's sections (verify/__init__.py lists them)

What wearing is lives elsewhere: the slots and names in
combat/wear_tuning.py, putting one on and taking one off in
combat/weapon_component/wear.py, and the I panel in graphics_menu/wear_*.py.
"""
