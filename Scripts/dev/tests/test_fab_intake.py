"""asset_pipeline/fab_intake: the scan and the promote, on packs built in a temp folder.

No real package is read: a "package" here is the package tag followed by
whatever names the test wants found, which is all the scan looks at.
"""

import os
import tempfile
import unittest

import _paths  # noqa: F401

from asset_pipeline.fab_intake import manifest, promote, rules
from asset_pipeline.fab_intake.scan import scan

PACKAGE = rules.PACKAGE_TAG + b"\0" * 32 + b"StaticMesh\0"


def _write(root, rel, data=PACKAGE):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    return path


class FabIntakeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.src = os.path.join(tmp.name, "pack", "data")
        self.project = os.path.join(tmp.name, "project")
        self.intake = os.path.join(tmp.name, "intake")
        _write(self.src, "Content/Pack/Meshes/SM_Rock.uasset")
        _write(self.src, "Content/Pack/Textures/T_Rock.uasset")

    def whats(self, report, level):
        return [f"{f.path}: {f.what}" for f in report.at(level)]

    def test_clean_pack(self):
        report = scan(self.src)
        self.assertEqual(report.verdict, "clean", report.findings)
        self.assertEqual(report.tops(), ["Pack"])
        self.assertEqual(len(report.files), 2)

    def test_script_and_config_block(self):
        _write(self.src, "Content/Pack/setup.py", b"import os\n")
        _write(self.src, "Config/DefaultEngine.ini", b"[x]\n")
        report = scan(self.src)
        blocks = "\n".join(self.whats(report, rules.BLOCK))
        self.assertIn("Pack/setup.py: file type .py", blocks)
        self.assertIn("Config: outside Content/", blocks)

    def test_content_python_blocks(self):
        _write(self.src, "Content/Python/T_Fine.uasset")
        self.assertIn("auto-loads", "\n".join(self.whats(scan(self.src), rules.BLOCK)))

    def test_binary_behind_a_package_extension_blocks(self):
        _write(self.src, "Content/Pack/SM_Fake.uasset", b"\xcf\xfa\xed\xfe" + b"\0" * 64)
        blocks = "\n".join(self.whats(scan(self.src), rules.BLOCK))
        self.assertIn("SM_Fake.uasset: is a Mach-O binary", blocks)
        self.assertIn("SM_Fake.uasset: is not an Unreal package", blocks)

    def test_symlink_blocks(self):
        os.symlink("/etc/hosts", os.path.join(self.src, "Content", "Pack", "T_Link.uasset"))
        self.assertIn("symbolic link", "\n".join(self.whats(scan(self.src), rules.BLOCK)))

    def test_names_ask_for_review_and_notes(self):
        _write(self.src, "Content/Pack/EUW_Tool.uasset",
               PACKAGE + b"/Script/Blutility\0ExecutePythonCommand\0")
        _write(self.src, "Content/Pack/BP_Door.uasset", PACKAGE + b"BlueprintGeneratedClass\0")
        report = scan(self.src)
        self.assertEqual(report.verdict, "review")
        self.assertEqual(len(report.at(rules.REVIEW)), 2)
        self.assertEqual(self.whats(report, rules.NOTE), ["Pack/BP_Door.uasset: Blueprint"])

    def test_project_source_needs_only(self):
        _write(self.src, "Quarantine.uproject", b"{}")
        _write(self.src, "Config/DefaultEngine.ini", b"[x]\n")
        _write(self.src, "Content/Other/SM_Other.uasset")
        self.assertEqual(scan(self.src).verdict, "blocked")
        report = scan(self.src, only=["Pack"])
        self.assertEqual(report.verdict, "clean", report.findings)
        self.assertEqual(report.tops(), ["Pack"])
        self.assertEqual(scan(self.src, only=["Absent"]).verdict, "blocked")

    def test_promote_copies_then_verify_sees_a_change(self):
        report = scan(self.src)
        copied, same, record = promote.promote(report, self.project, self.intake)
        self.assertEqual((copied, same), (2, 0))
        self.assertTrue(os.path.isfile(record))
        dest = os.path.join(self.project, "Content", "Pack", "Meshes", "SM_Rock.uasset")
        self.assertTrue(os.path.isfile(dest))
        self.assertEqual(promote.verify(self.project, self.intake), [])
        self.assertEqual(promote.promote(report, self.project, self.intake)[:2], (0, 2))
        with open(dest, "ab") as fh:
            fh.write(b"x")
        self.assertEqual(promote.verify(self.project, self.intake),
                         [("Pack.json", "Pack/Meshes/SM_Rock.uasset", "changed")])
        self.assertEqual(promote.conflicts(report, self.project), ["Pack/Meshes/SM_Rock.uasset"])

    def test_manifest_names_a_changed_and_an_extra_file(self):
        import hashlib
        import json

        def decimals(path):
            with open(path, "rb") as fh:
                return "".join(f"{b:03d}" for b in hashlib.sha1(fh.read()).digest())

        rels = ["Content/Pack/Meshes/SM_Rock.uasset", "Content/Pack/Textures/T_Rock.uasset"]
        listed = os.path.join(os.path.dirname(self.src), "manifest")
        with open(listed, "w") as fh:
            json.dump({"FileManifestList": [
                {"Filename": r, "FileHash": decimals(os.path.join(self.src, r))}
                for r in rels]}, fh)
        self.assertEqual(manifest.check(self.src, listed), [])
        _write(self.src, rels[0], PACKAGE + b"tampered")
        _write(self.src, "Content/Pack/SM_Extra.uasset")
        whats = sorted(f.what for f in manifest.check(self.src, listed))
        self.assertEqual(whats, ["differs from what Epic served (sha1)",
                                 "on disk but not in the manifest"])


if __name__ == "__main__":
    unittest.main()
