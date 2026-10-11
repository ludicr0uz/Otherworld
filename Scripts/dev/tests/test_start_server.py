import ast
import importlib.util
import os
import unittest

import _paths


def load():
    path = os.path.join(_paths.SCRIPTS, "server", "start_server.py")
    spec = importlib.util.spec_from_file_location("start_server", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


start_server = load()


class PlayLevelTest(unittest.TestCase):
    """The server serves the level New Game opens, not the title stage."""

    def test_the_script_names_the_same_play_level(self):
        tree = ast.parse(open(os.path.join(_paths.SCRIPTS, "title", "paths.py")).read())
        named = {n.targets[0].id: n.value.value for n in tree.body
                 if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)}
        self.assertEqual(start_server.PLAY_LEVEL, named["PLAY_LEVEL"])
        self.assertNotEqual(start_server.PLAY_LEVEL, named["TITLE_LEVEL"])

    def test_map_overrides_the_play_level(self):
        self.assertIsNone(start_server.parse_args([]).map)
        self.assertEqual(start_server.parse_args(["--map", "/Game/Maps/L"]).map, "/Game/Maps/L")


if __name__ == "__main__":
    unittest.main()
