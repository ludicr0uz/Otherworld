"""clothing -- the garments the player wears: shirt, jacket, hat, glasses,
boots, pants, gloves and backpack.

Entry point: Scripts/build_clothing.py (the garments, the test ones laid on
the 200 m map, then the ones scattered through every generated level). Checks: Scripts/verify_clothing.py, which runs
clothing.verify. Design and traps: CLAUDE.md here.

  specs       GARMENTS: each garment's path, name, slot, stand-in model and,
              for three, the mesh it is drawn as worn (no unreal: the
              verifier and the placement read it)
  items       BP_<Garment> per row: a Consumable BP_WeaponItem with its
              ClothingSlot, WornPart and WornMesh, Dropped, and a flat
              material
  ground_model  the mesh a garment with a WornMesh lies as: one skeletal
              mesh component in its reference pose, laid flat and centred
  placement   the test garments in a row 3 m in front of Lvl_Forest_200m's
              PlayerStart (tag OW_TestClothing, idempotent)
  scatter     where the garments found in the forest go: jackets, pants and
              boots, one a hectare, seeded, off the trunks (no unreal)
  scatter_level  putting them into each generated level (tag OW_Clothing,
              idempotent)
  verify/     the verifier's sections (verify/__init__.py lists them)

What wearing is lives elsewhere: the slots and names in
combat/wear_tuning.py, putting one on and taking one off in
combat/weapon_component/wear.py, and the I panel in graphics_menu/wear_*.py.
"""
