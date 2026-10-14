import ast
import os
import sys
import tempfile
import unittest

import _paths

ROOT = os.path.dirname(_paths.SCRIPTS)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import package_game  # noqa: E402


class HostTest(unittest.TestCase):

    def test_each_machine_packages_for_itself(self):
        self.assertEqual(package_game.host("Darwin"), ("Mac", "RunUAT.command"))
        self.assertEqual(package_game.host("Windows"), ("Win64", "RunUAT.bat"))

    def test_another_system_is_refused(self):
        with self.assertRaises(SystemExit):
            package_game.host("Linux")


class CommandTest(unittest.TestCase):

    def command(self, engine):
        return package_game.command(engine, "/p/Otherworld.uproject", "Win64", "RunUAT.bat",
                                    "Shipping", "/out", ["-clean"])

    def test_the_command_packages_and_archives(self):
        with tempfile.TemporaryDirectory() as engine:
            argv = self.command(engine)
        self.assertEqual(argv[0], os.path.join(engine, "Build", "BatchFiles", "RunUAT.bat"))
        for wanted in ("BuildCookRun", "-project=/p/Otherworld.uproject", "-platform=Win64",
                       "-clientconfig=Shipping", "-build", "-cook", "-stage", "-pak",
                       "-package", "-archive", "-archivedirectory=/out"):
            self.assertIn(wanted, argv)
        self.assertEqual(argv[-1], "-clean")
        self.assertNotIn("-installed", argv)

    def test_an_installed_engine_compiles_no_editor(self):
        with tempfile.TemporaryDirectory() as engine:
            os.makedirs(os.path.join(engine, "Build"))
            open(os.path.join(engine, "Build", "InstalledBuild.txt"), "w").close()
            argv = self.command(engine)
        for wanted in ("-installed", "-nocompileeditor", "-skipbuildeditor", "-nocompileuat"):
            self.assertIn(wanted, argv)


class MapsToCookTest(unittest.TestCase):
    """The Single Player page's rows open the play level and the horde level
    by name, which the cooker cannot follow: a build holds them only because
    DefaultGame.ini lists them."""

    def test_a_build_ships_the_title_the_play_and_the_horde_level(self):
        tree = ast.parse(open(os.path.join(_paths.SCRIPTS, "title", "paths.py")).read())
        named = {n.targets[0].id: n.value.value for n in tree.body
                 if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)}
        ini = open(os.path.join(os.path.dirname(_paths.SCRIPTS), "Config",
                                "DefaultGame.ini")).read()
        for level in (named["TITLE_LEVEL"], named["PLAY_LEVEL"], named["HORDE_LEVEL"]):
            self.assertIn(f'+MapsToCook=(FilePath="{level}")', ini)


if __name__ == "__main__":
    unittest.main()
