"""asset_pipeline/fab_raw: the host half, on downloads built in a temp folder.

No real mesh or image is read: a file here is the few bytes its type starts
with, which is all the scan looks at.
"""

import json
import os
import tempfile
import unittest

import _paths  # noqa: F401

from asset_pipeline.fab_raw import listing, stage, textures
from asset_pipeline.fab_raw.collect import BLOCK, collect

FBX = b"Kaydara FBX Binary  \0" + b"\0" * 16
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 16
USD = b"PXR-USDC" + b"\0" * 16


def _write(root, rel, data):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    return path


class RolesTest(unittest.TestCase):
    def test_names_from_real_downloads(self):
        for stem, role, key in (
                ("T_1911_C", "basecolor", "T_1911"), ("T_1911_N", "normal", "T_1911"),
                ("T_1911_R2", "roughness", "T_1911"), ("T_1911_M", "metallic", "T_1911"),
                ("T_1911_AO", "ao", "T_1911"), ("AxeAlbedo", "basecolor", "Axe"),
                ("AxeRough", "roughness", "Axe"), ("AxeMetal", "metallic", "Axe"),
                ("Hinode_Cap_Base_color", "basecolor", "Hinode_Cap"),
                ("Hinode_Cap_Mixed_AO", "ao", "Hinode_Cap"),
                ("Puffer_Jacket_1003_bcolor", "basecolor", "Puffer_Jacket_1003"),
                ("Puffer_Jacket_1003_matal", "metallic", "Puffer_Jacket_1003"),
                ("Puffer_Bake1_PBR StoA_Diffuse", "basecolor", "Puffer_Bake1_PBR StoA"),
                ("Chullo_Hat_LOD_02_thin_Mesh_Opacity", "opacity", "Chullo_Hat_LOD_02_thin_Mesh")):
            self.assertEqual(textures.role_of(stem), (role, key), stem)

    def test_a_name_that_says_nothing(self):
        for stem in ("Floor", "T_Manny_01", "Iron", "Logo"):
            self.assertEqual(textures.role_of(stem), (None, stem), stem)

    def test_a_repeat_keeps_the_one_under_textures(self):
        sets, loose, repeats = textures.group({
            "source/x_extracted/Cap_Normal.png": 9, "textures/Cap_Normal.png": 5,
            "textures/Cap_Roughness.png": 5, "Logo.png": 1})
        self.assertEqual(sets, {"Cap": {"normal": "textures/Cap_Normal.png",
                                        "roughness": "textures/Cap_Roughness.png"}})
        self.assertEqual((loose, repeats), (["Logo.png"], ["source/x_extracted/Cap_Normal.png"]))

    def test_slots(self):
        self.assertEqual(textures.assign(["A", "B"], ["Axe"]), [("Axe", "only")] * 2)
        self.assertEqual(textures.assign(["Body_Mat", "Sleeve_Mat"], ["Jacket_Sleeve", "Jacket_Body"]),
                         [("Jacket_Body", "name"), ("Jacket_Sleeve", "name")])
        self.assertEqual(textures.assign(["x", "y"], ["P_1003", "P_1004"]),
                         [("P_1003", "order"), ("P_1004", "order")])


class CollectTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.src = os.path.join(tmp.name, "CC0_-_Axe-f0adac8a")
        _write(self.src, "fbx/metadata", json.dumps({"listing": {
            "title": "CC0 - Axe", "uid": "f0adac8a", "user": {"sellerName": "plaggy"}}})
            .encode("utf-16"))
        _write(self.src, "fbx/thumbnail.png", PNG)
        _write(self.src, "fbx/axe_extracted/source/Axe.fbx", FBX)
        _write(self.src, "fbx/axe_extracted/textures/AxeAlbedo.png", PNG)
        _write(self.src, "fbx/axe_extracted/textures/AxeNormal.png", PNG)

    def whats(self, item):
        return "\n".join(f"{f.path}: {f.what}" for f in item.at(BLOCK))

    def test_clean_item(self):
        item = collect(self.src)
        self.assertEqual(item.verdict, "clean", item.findings)
        self.assertEqual((item.title, item.slug, item.seller), ("CC0 - Axe", "CC0_Axe", "plaggy"))
        self.assertEqual(item.url, listing.LISTING_URL + "f0adac8a")
        self.assertEqual(item.meshes, ["fbx/axe_extracted/source/Axe.fbx"])
        self.assertEqual(sorted(item.sets["Axe"]), ["basecolor", "normal"])
        self.assertEqual(len(item.files), 3)        # not the metadata, not the thumbnail
        self.assertEqual(item.left, [])

    def test_utf8_metadata_and_none(self):
        _write(self.src, "fbx/metadata", json.dumps({"listing": {"title": "Axe Two"}}).encode())
        self.assertEqual(collect(self.src).title, "Axe Two")
        os.remove(os.path.join(self.src, "fbx", "metadata"))
        item = collect(self.src)
        self.assertEqual((item.title, item.url), ("CC0_-_Axe-f0adac8a", ""))

    def test_an_archive_and_a_sidecar_stay_behind(self):
        _write(self.src, "fbx/axe_extracted/source/axe.zip", b"PK\x03\x04")
        _write(self.src, "fbx/axe_extracted/Axe_Wind.json", b"{}")
        item = collect(self.src)
        self.assertEqual(item.verdict, "clean")
        self.assertEqual([rel for rel, _why in item.left],
                         ["fbx/axe_extracted/Axe_Wind.json", "fbx/axe_extracted/source/axe.zip"])
        self.assertNotIn("fbx/axe_extracted/source/axe.zip", item.files)

    def test_a_program_blocks_wherever_it_is(self):
        _write(self.src, "fbx/axe_extracted/tool.bin", b"\xcf\xfa\xed\xfe" + b"\0" * 64)
        _write(self.src, "fbx/axe_extracted/textures/AxeRough.png", b"#!/bin/sh\n")
        blocks = self.whats(collect(self.src))
        self.assertIn("tool.bin: is a Mach-O binary", blocks)
        self.assertIn("AxeRough.png: is a script with a shebang line", blocks)
        self.assertIn("AxeRough.png: does not start like a .png file", blocks)

    def test_a_link_and_no_mesh_block(self):
        os.symlink("/etc/hosts", os.path.join(self.src, "fbx", "axe_extracted", "notes.txt"))
        os.remove(os.path.join(self.src, "fbx", "axe_extracted", "source", "Axe.fbx"))
        blocks = self.whats(collect(self.src))
        self.assertIn("notes.txt: is a symbolic link", blocks)
        self.assertIn("no mesh here", blocks)

    def test_stage_writes_the_plan_and_the_files(self):
        _write(self.src, "usd/Tree_A.usd", USD)
        raw = os.path.join(self.tmp, "raw")
        with open(stage.stage(collect(self.src), raw)) as fh:
            plan = json.load(fh)
        self.assertEqual(plan["dest"], "/Game/Fab/CC0_Axe")
        self.assertEqual([(m["asset"], m["usd"]) for m in plan["meshes"]],
                         [("SM_Axe", False), ("SM_Tree_A", True)])
        self.assertEqual(plan["sets"]["Axe"], {"material": "M_Axe", "roles": {
            "basecolor": "T_AxeAlbedo", "normal": "T_AxeNormal"}})
        for rel, info in plan["files"].items():
            staged = os.path.join(raw, "CC0_Axe", stage.FILES, *rel.split("/"))
            self.assertEqual(stage.sha256(staged), info["sha256"])
        self.assertEqual([(s, done) for s, _p, done in stage.staged(raw)], [("CC0_Axe", False)])
        with self.assertRaises(RuntimeError):
            stage.stage(collect(self.src), raw)
        stage.stage(collect(self.src), raw, replace=True)

    def test_names(self):
        taken = set()
        self.assertEqual(stage.asset_name("SM_", "SM_1911_02", taken), "SM_1911_02")
        self.assertEqual(stage.asset_name("SM_", "Hinode Baseball Hat", taken), "SM_Hinode_Baseball_Hat")
        self.assertEqual(stage.asset_name("SM_", "sm_1911-02", taken), "SM_1911_02_2")

    def test_two_listings_with_one_title(self):
        raw = os.path.join(self.tmp, "raw")
        stage.stage(collect(self.src), raw)
        other = os.path.join(self.tmp, "CC0_-_Axe-99999999")
        _write(other, "fbx/metadata", json.dumps({"listing": {
            "title": "CC0 - Axe", "uid": "99999999-aaaa"}}).encode())
        _write(other, "fbx/Axe.fbx", FBX)
        item = collect(other)
        self.assertTrue(stage.name_apart(item, raw))
        self.assertEqual((item.title, item.slug), ("CC0 - Axe (99999999)", "CC0_Axe_99999999"))
        self.assertFalse(stage.name_apart(collect(self.src), raw))


if __name__ == "__main__":
    unittest.main()
