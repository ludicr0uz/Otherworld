"""combat/use_tuning.USE_BIND: the use key is one of the weapon component's
binds, by name. The I panel reads that variable off the component
(graphics_menu/inv_drag.py); a name that is no bind would compile to nothing.

    python3 -m unittest discover -s Scripts/dev/tests
"""

import unittest

import _paths  # noqa: F401

from combat.tuning import POLLED_BINDS, SIGHTS_KEY
from combat.use_tuning import USE_BIND


class UseBind(unittest.TestCase):
    def test_it_is_the_sights_bind(self):
        self.assertEqual(dict(POLLED_BINDS).get(USE_BIND), SIGHTS_KEY)


if __name__ == "__main__":
    unittest.main()
