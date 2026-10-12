"""item_icons/portrait.py: the I panel's pictures, one per set of the garments
drawn on the body. Pure, so the table and its index are held here, without
an editor: the HUD's graph adds the same bits (graphics_menu/wear_portrait.py).

    python3 -m unittest discover -s Scripts/dev/tests
"""

import unittest

import _paths  # noqa: F401

from clothing.specs import GARMENTS
from combat.wear_tuning import WEAR_SLOTS
from item_icons import portrait as P


class PortraitTable(unittest.TestCase):
    def test_one_picture_per_set_of_drawn_garments(self):
        drawn = [g for g in GARMENTS if g.worn]
        self.assertEqual(sorted(g.display for g in P.DRAWN), sorted(g.display for g in drawn))
        self.assertEqual(len(P.PORTRAITS), 2 ** len(drawn))
        self.assertEqual([p.index for p in P.PORTRAITS], list(range(len(P.PORTRAITS))))
        self.assertEqual(len({p.texture for p in P.PORTRAITS}), len(P.PORTRAITS))
        self.assertEqual(len({p.passes for p in P.PORTRAITS}), len(P.PORTRAITS))

    def test_the_bare_one_keeps_its_names(self):
        bare = P.PORTRAITS[0]
        self.assertEqual((bare.garments, bare.texture, bare.passes),
                         ((), P.PORTRAIT_TEXTURE, P.PORTRAIT))

    def test_bits_follow_the_slots(self):
        self.assertEqual(list(P.DRAWN_SLOTS), sorted(P.DRAWN_SLOTS))
        for bit, garment in enumerate(P.DRAWN):
            one = P.PORTRAITS[1 << bit]
            self.assertEqual(one.garments, (garment,))
            self.assertEqual(one.meshes, (garment.worn[1],))
            self.assertEqual(one.texture, f"{P.PORTRAIT_TEXTURE}_{garment.display}")

    def test_index_of_what_is_worn(self):
        slot = WEAR_SLOTS.index
        self.assertEqual(P.portrait_index(set()), 0)
        # A garment nothing draws changes nothing.
        self.assertEqual(P.portrait_index({slot("hat"), slot("gloves")}), 0)
        for portrait in P.PORTRAITS:
            worn = {g.slot_index for g in portrait.garments}
            self.assertEqual(P.portrait_index(worn | {slot("hat")}), portrait.index)
        everything = P.PORTRAITS[-1]
        self.assertEqual(everything.garments, P.DRAWN)


if __name__ == "__main__":
    unittest.main()
