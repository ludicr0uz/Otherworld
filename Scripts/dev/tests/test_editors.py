import unittest

import _paths  # noqa: F401

from uepylib.editors import parse_ps

PROJECT = "/Users/me/Unreal Projects/Otherworld/Otherworld.uproject"
ENGINE = "/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac"

PS = f"""\
  101 {ENGINE}/UnrealEditor.app/Contents/MacOS/UnrealEditor {PROJECT} -skipcompile
  102 {ENGINE}/UnrealEditor-Cmd {PROJECT} /Game/Maps/L -game -nullrhi
  103 /Users/me/Library/Services/UnrealEditorServices.app/Contents/MacOS/UnrealEditorServices
  104 {ENGINE}/UnrealEditor.app/Contents/MacOS/UnrealEditor /other/Other.uproject
  105 {ENGINE}/UnrealEditor.app/Contents/MacOS/UnrealEditor
  106 /usr/bin/python3 Scripts/dev/uepy.py --game {PROJECT}
garbage line
"""


class ParsePsTest(unittest.TestCase):

    def test_finds_this_projects_editor_and_game(self):
        found = parse_ps(PS, PROJECT)
        self.assertEqual([(p.pid, p.binary) for p in found],
                         [(101, "UnrealEditor"), (102, "UnrealEditor-Cmd")])
        self.assertTrue(found[0].is_ui)
        self.assertFalse(found[1].is_ui)

    def test_never_the_services_helper_or_other_projects_or_python(self):
        pids = {p.pid for p in parse_ps(PS, PROJECT)}
        self.assertNotIn(103, pids)
        self.assertNotIn(104, pids)
        self.assertNotIn(106, pids)

    def test_an_editor_without_a_project_argument_matches_by_heartbeat_pid(self):
        pids = {p.pid for p in parse_ps(PS, PROJECT, extra_pids={105})}
        self.assertIn(105, pids)

    def test_heartbeat_pid_of_something_else_is_ignored(self):
        pids = {p.pid for p in parse_ps(PS, PROJECT, extra_pids={103, 106})}
        self.assertEqual(pids, {101, 102})


if __name__ == "__main__":
    unittest.main()
