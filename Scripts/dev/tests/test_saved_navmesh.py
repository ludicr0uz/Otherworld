"""check_saved_navmesh.py: no map on disk carries a saved RecastNavMesh.

A saved one is loaded by the game and never built, so the wanderers have no
navmesh: they stand still, or take the chase's straight line into the first
rock (npc/chase.py). A hand save in the editor (Ctrl+S) puts one back.
"""
import os
import tempfile
import unittest
from unittest import mock

from _paths import *  # noqa: F401,F403  (puts Scripts/dev on sys.path)
import check_saved_navmesh as check


class MapsOnDisk(unittest.TestCase):
    def test_no_map_carries_a_saved_navmesh(self):
        found = check.scan()
        if not found or all(state == "pointer" for _, state in found):
            self.skipTest("no map bytes on disk (git lfs pull)")
        bad = [os.path.basename(p) for p, state in found if state == "navmesh"]
        self.assertEqual(bad, [], check.FIX)


class Scan(unittest.TestCase):
    def test_tells_the_three_states_apart(self):
        with tempfile.TemporaryDirectory() as d:
            for name, data in (("Lvl_A.umap", b"..RecastNavMesh-Default.."),
                               ("Lvl_B.umap", b"..StaticMeshActor.."),
                               ("Lvl_C.umap", b"version https://git-lfs.github.com/spec/v1\n")):
                with open(os.path.join(d, name), "wb") as f:
                    f.write(data)
            with mock.patch.object(check, "MAPS", os.path.join(d, "Lvl_*.umap")):
                states = {os.path.basename(p): s for p, s in check.scan()}
        self.assertEqual(states, {"Lvl_A.umap": "navmesh", "Lvl_B.umap": "ok",
                                  "Lvl_C.umap": "pointer"})


if __name__ == "__main__":
    unittest.main()
