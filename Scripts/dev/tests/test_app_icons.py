"""The launcher icon is where each platform's packaging reads it, in a form it reads.

Scripts/build_app_icons.py writes all three. A package made without one falls
back to the engine's icon and says nothing, so the files and the one setting
that stages the Linux one are held here (root CLAUDE.md, Config).
"""

import json
import os
import struct
import unittest

import _paths

ROOT = os.path.dirname(_paths.SCRIPTS)
ICONSET = os.path.join(ROOT, "Build", "Mac", "Resources", "Assets.xcassets",
                       "AppIcon.appiconset")
ICO = os.path.join(ROOT, "Build", "Windows", "Application.ico")
BMP = os.path.join(ROOT, "Content", "Splash", "Icon.bmp")
GAME_INI = os.path.join(ROOT, "Config", "DefaultGame.ini")


def _png_size(path):
    with open(path, "rb") as handle:
        head = handle.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", path
    return struct.unpack(">II", head[16:24])


class AppIconsTest(unittest.TestCase):
    def test_mac_catalog_has_every_size_it_lists(self):
        with open(os.path.join(ICONSET, "Contents.json")) as handle:
            images = json.load(handle)["images"]
        self.assertEqual(len(images), 10)
        for image in images:
            px = int(image["size"].split("x")[0]) * int(image["scale"][0])
            self.assertEqual(_png_size(os.path.join(ICONSET, image["filename"])),
                             (px, px), image["filename"])

    def test_windows_icon_holds_the_sizes_the_shell_asks_for(self):
        with open(ICO, "rb") as handle:
            reserved, kind, count = struct.unpack("<HHH", handle.read(6))
            sizes = {handle.read(16)[0] or 256 for _ in range(count)}
        self.assertEqual((reserved, kind), (0, 1))
        self.assertLessEqual({16, 32, 48, 256}, sizes)

    def test_linux_icon_is_a_32_bit_bmp_staged_loose(self):
        with open(BMP, "rb") as handle:
            head = handle.read(30)
        self.assertEqual(head[:2], b"BM")
        self.assertEqual(struct.unpack("<H", head[28:30])[0], 32)
        with open(GAME_INI) as handle:
            ini = handle.read()
        self.assertIn("[/Script/UnrealEd.ProjectPackagingSettings]", ini)
        self.assertIn('+DirectoriesToAlwaysStageAsNonUFS=(Path="Splash")', ini)


if __name__ == "__main__":
    unittest.main()
