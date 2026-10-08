"""The Game Animation Sample's copy: its manifest, redirects and plugins agree.

Content/GAS is a byte copy of packages that still name each other by the
sample's /Game paths (Scripts/asset_pipeline/import_gas.py). It loads only
while every folder the manifest has a package in has its [CoreRedirects] line
in Config/DefaultEngine.ini, and the plugins whose classes those packages hold
are enabled. A redirect over a folder the game has content of its own in would
move the game's packages too.
"""

import json
import os
import unittest

import _paths

from asset_pipeline import gas_paths

ROOT = os.path.dirname(_paths.SCRIPTS)
MANIFEST = os.path.join(_paths.SCRIPTS, "asset_pipeline", "gas_manifest.txt")

# What the copied packages hold classes of, beyond what the game had enabled.
PLUGINS = ("PoseSearch", "Chooser", "AnimationWarping", "MotionWarping",
           "AnimationLocomotionLibrary", "AnimationLayering", "DrawDebugLibrary",
           "CurveExpression", "MovieSceneAnimMixer", "Mover")


def _manifest():
    with open(MANIFEST) as handle:
        return [line.strip() for line in handle if line.strip()]


def _excluded(pkg):
    return any(pkg.startswith(e) for e in gas_paths.EXCLUDED)


class GasImportTest(unittest.TestCase):
    def test_every_manifest_package_has_a_redirect(self):
        loose = [p for p in _manifest() if not gas_paths.redirected(p)]
        self.assertEqual(loose, [])

    def test_the_redirects_are_in_the_engine_ini(self):
        with open(os.path.join(ROOT, "Config", "DefaultEngine.ini")) as handle:
            have = {line.strip() for line in handle}
        self.assertEqual([l for l in gas_paths.redirect_lines() if l not in have], [])

    def test_no_redirect_covers_a_folder_the_game_keeps_content_in(self):
        tracked = os.path.join(ROOT, "Content")
        for old in gas_paths.REDIRECTED:
            rel = old[len("/Game/"):].rstrip("/")
            here = os.path.join(tracked, rel)
            self.assertFalse(os.path.isdir(here) or os.path.exists(here + ".uasset"),
                             f"{old} is the game's own: {here}")

    def test_nothing_excluded_is_in_the_manifest(self):
        self.assertEqual([p for p in _manifest() if _excluded(p)], [])

    def test_the_roots_and_the_patched_notifies_are_in_the_manifest(self):
        listed = set(_manifest())
        for pkg in gas_paths.ROOT_PACKAGES + gas_paths.PATCHED:
            self.assertIn(pkg, listed)

    def test_a_sample_path_maps_under_the_gas_root(self):
        self.assertEqual(gas_paths.gas("/Game/Blueprints/SandboxCharacter_CMC_ABP"),
                         gas_paths.ABP)

    def test_the_plugins_the_packages_need_are_enabled(self):
        with open(os.path.join(ROOT, "Otherworld.uproject")) as handle:
            enabled = {p["Name"] for p in json.load(handle)["Plugins"] if p["Enabled"]}
        self.assertEqual([p for p in PLUGINS if p not in enabled], [])


if __name__ == "__main__":
    unittest.main()
