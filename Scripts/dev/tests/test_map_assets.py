"""map_assets: the host half. What a path makes a mesh, and the page built
from a scan written here; no editor.
"""

import json
import unittest

import _paths  # noqa: F401

from map_assets import page
from map_assets.kinds import CATEGORIES, ROWS, classify, pack_of


def _mesh(path, triangles=10):
    return {"path": path, "name": path.rsplit("/", 1)[1], "triangles": triangles,
            "lod0_triangles": triangles, "vertices": 12, "nanite_triangles": 0,
            "nanite_vertices": 0, "lods": 1, "materials": 1, "collision_prims": 0,
            "bytes": 0, "nanite": False, "size_cm": "1x2x3", "levels": []}


class KindsTest(unittest.TestCase):
    def test_category_and_kind_from_path(self):
        for path, expected in (
                ("/Game/PN_GrassLibrary/Meshes/SM_Clover_01", ("Environment", "grass")),
                ("/Game/Megaplant_Library/Tree_Norway_Spruce/Instances/Branch_Norway_Spruce_02",
                 ("Environment", "tree")),
                ("/Game/Megaplant_Library/Shrub_Beach_Rose/Instances/Branch_Beach_Rose_02",
                 ("Environment", "shrub")),
                ("/Game/Light_Foliage/Meshes/SM_Rock_01", ("Environment", "rock")),
                ("/Game/Light_Foliage/Meshes/SM_Thing", ("Environment", "plant")),
                ("/Game/Sourced/Quaternius/Survival/SM_Revolver_1", ("Weapons", "pistol")),
                ("/Game/Sourced/Quaternius/Survival/SM_Battery_Big", ("Items", "tool")),
                ("/Game/Sourced/Quaternius/Survival/SM_Tent", ("Items", "camp")),
                ("/Game/FPS_Weapon_Bundle/Weapons/Meshes/AR4/SM_AR4_Mag", ("Weapons", "magazine")),
                ("/Game/FPS_Weapon_Bundle/Weapons/Meshes/AR4/SK_AR4", ("Weapons", "rifle")),
                ("/Game/FPS_Weapon_Bundle/Weapons/Meshes/SMG11/SM_SMG11_Nostock_X",
                 ("Weapons", "rifle")),
                # The folder names the pack, not the part.
                ("/Game/Fab/Shotgun_Pump_Action_Wooden_Stock_Hish_Poly/SM_Shotgun_02",
                 ("Weapons", "shotgun")),
                ("/Game/Fab/Worn_Crew_Hat/SM_Hinode_Baseball_Hat", ("Clothing", "headwear")),
                ("/Game/Survival_Character/Demo/LevelPrototyping/Meshes/SM_Cube",
                 ("Structures", "blockout")),
                ("/Game/Survival_Character/Demo/Mesh/SM_Curtain", ("Structures", "structure")),
                ("/Game/Survival_Character/Meshes/SK_Survivor", ("Characters", "body")),
                ("/Game/MetaHumans/Common/Controls/faceboard_2x", ("Characters", "rig control")),
                ("/Game/NewPack/SM_Thing", ("Other", "other"))):
            self.assertEqual(classify(path), expected, path)

    def test_every_row_names_a_tab(self):
        self.assertEqual({row[0] for row in ROWS} - set(CATEGORIES), set())

    def test_pack(self):
        self.assertEqual(pack_of("/Game/Fab/CC0_Axe/SM_Axe"), "Fab/CC0_Axe")
        self.assertEqual(pack_of("/Game/PN_GrassLibrary/Meshes/SM_X"), "PN_GrassLibrary")
        self.assertEqual(pack_of("/Game/Forest/SM_X"), "Forest")
        self.assertEqual(pack_of("/Game/SM_X"), "(root)")


class PageTest(unittest.TestCase):
    def test_the_scan_is_embedded_and_classified(self):
        scan = {"scanned": "2026-10-12 19:00", "meshes": [
            _mesh("/Game/Forest/Meshes/SM_ForestRock_01", 420),
            dict(_mesh("/Game/Fab/CC0_Axe/SM_Axe"), size_cm="</script>")]}
        html = page.render(scan, {"/Game/Forest/Meshes/SM_ForestRock_01": "ab.png"},
                           {"/Game/Forest/Meshes/SM_ForestRock_01": "ab.webp"})
        body = html.split('<script id="scan" type="application/json">')[1]
        raw = body.split("</script>")[0]
        meshes = json.loads(raw)["meshes"]
        self.assertEqual([(m["category"], m["kind"]) for m in meshes],
                         [("Environment", "rock"), ("Weapons", "melee")])
        self.assertEqual(meshes[1]["size_cm"], "</script>")
        self.assertEqual([m["thumb"] for m in meshes], ["thumbs/ab.png", ""])
        self.assertEqual([m["spin"] for m in meshes], ["spins/ab.webp", ""])
        self.assertNotIn("__SCAN__", html)


if __name__ == "__main__":
    unittest.main()
