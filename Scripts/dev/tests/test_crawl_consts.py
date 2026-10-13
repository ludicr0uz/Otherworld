"""The crawl by direction's table and weights (Scripts/combat/crawl_consts.py):
each of the eight directions plays its own loop alone, the weights never
jump as the direction turns or reverses, and the slides are what is written.
"""

import math
import unittest

import _paths  # noqa: F401

from combat import crawl_consts as C


class CrawlConsts(unittest.TestCase):
    def test_each_direction_plays_its_own_loop_alone(self):
        self.assertEqual(len(C.DIRECTIONS), 8)
        for d in C.DIRECTIONS:
            share = C.weights(d.ahead * C.CRAWL_CMS, d.right * C.CRAWL_CMS)
            self.assertAlmostEqual(share[d.name], 1.0, places=6, msg=d.name)
            self.assertAlmostEqual(sum(share.values()), 1.0, places=6)
            self.assertEqual(C.alphas(d.ahead * C.CRAWL_CMS, d.right * C.CRAWL_CMS)[0], 1.0)

    def test_backwards_is_the_mirrored_forward_loop_in_reverse(self):
        pairs = {"back": "forward", "back left": "forward right",
                 "back right": "forward left"}
        for back, fore in pairs.items():
            self.assertEqual(C.BY_NAME[back].clip, C.BY_NAME[fore].clip)
            self.assertEqual(C.BY_NAME[back].rate, -C.BY_NAME[fore].rate)
            self.assertAlmostEqual(C.BY_NAME[back].ahead, -C.BY_NAME[fore].ahead)
            self.assertAlmostEqual(C.BY_NAME[back].right, -C.BY_NAME[fore].right)
        clips = [d.clip for d in C.DIRECTIONS]
        self.assertEqual(sorted(set(clips) - {"prone_crawl"}), sorted(C.DIRECTION_FIELDS))

    def test_no_weight_jumps_as_the_direction_turns(self):
        last = None
        for i in range(0, 3601):
            a = math.radians(i / 10.0)
            share = C.weights(math.cos(a) * C.CRAWL_CMS, math.sin(a) * C.CRAWL_CMS)
            if last:
                step = max(abs(share[k] - last[k]) for k in share)
                self.assertLess(step, 0.01, f"at {i / 10.0} degrees")
            last = share

    def test_a_reversal_goes_through_lying_still(self):
        # The eased pair runs straight from one velocity to its opposite.
        for d in C.DIRECTIONS:
            last = None
            for i in range(0, 2001):
                k = 1.0 - i / 1000.0
                ahead, right = d.ahead * C.CRAWL_CMS * k, d.right * C.CRAWL_CMS * k
                move = C.alphas(ahead, right)[0]
                posed = {n: w * move for n, w in C.weights(ahead, right).items()}
                if last:
                    self.assertLess(max(abs(posed[n] - last[n]) for n in posed), 0.01,
                                    f"{d.name} at {k}")
                last = posed
            self.assertEqual(C.alphas(0.0, 0.0)[0], 0.0)

    def test_the_rates_are_capped_and_the_slides_are_the_written_ones(self):
        for d in C.DIRECTIONS:
            self.assertLessEqual(abs(d.rate), C.RATE_SCALE_RANGE[1])
        self.assertEqual(C.PRONE_LOOP_RATE, 1.27)
        self.assertLess(abs(C.SLIDE_CMS["forward"]), 0.5)
        self.assertLess(abs(C.SLIDE_CMS["back"]), 0.5)
        for name in ("forward left", "forward right", "back left", "back right"):
            self.assertAlmostEqual(C.SLIDE_CMS[name], 27.7, places=1)
        for name in ("left", "right"):
            self.assertAlmostEqual(C.SLIDE_CMS[name], 46.2, places=1)


if __name__ == "__main__":
    unittest.main()
