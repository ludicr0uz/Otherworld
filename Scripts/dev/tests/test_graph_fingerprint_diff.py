"""graph_fingerprint_diff: what counts as a difference between two builds."""

import json
import os
import tempfile
import unittest

import _paths  # noqa: F401

import graph_fingerprint_diff as gfd


def _blueprint(**changes):
    data = {
        "class": "Blueprint", "parent": "/Script/Engine.Actor",
        "variables": {"Health": {"type": "real|double|None|None", "default": 100.0}},
        "components": ["Body | /Script/Engine.SceneComponent | "],
        "graphs": {"EventGraph": {
            "nodes": {"aa#1": "K2Node_Event | Event Tick |  | then:Exec | ",
                      "bb#1": "K2Node_IfThenElse | Branch | Condition:Boolean | then:Exec | "},
            "connections": ["aa#1.then -> bb#1.execute"]}},
    }
    data.update(changes)
    return data


class DiffTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _dir(self, name, blueprints):
        path = os.path.join(self.tmp.name, name)
        os.makedirs(path)
        for key, data in blueprints.items():
            with open(os.path.join(path, key + ".json"), "w") as fh:
                json.dump(data, fh)
        return path

    def test_identical_builds_do_not_differ(self):
        a = self._dir("a", {"Game.BP_X": _blueprint()})
        b = self._dir("b", {"Game.BP_X": _blueprint()})
        self.assertEqual(gfd.diff(a, b)[0], [])
        self.assertEqual(gfd.main([a, b]), 0)

    def test_a_changed_default_is_reported(self):
        changed = _blueprint(variables={
            "Health": {"type": "real|double|None|None", "default": 50.0}})
        a = self._dir("a", {"Game.BP_X": _blueprint()})
        b = self._dir("b", {"Game.BP_X": changed})
        lines = gfd.diff(a, b)[0]
        self.assertTrue(any("~ variable Health" in line for line in lines), lines)
        self.assertEqual(gfd.main([a, b]), 1)

    def test_a_lost_connection_and_a_new_node_are_reported(self):
        graph = {"EventGraph": {
            "nodes": {"aa#1": "K2Node_Event | Event Tick |  | then:Exec | ",
                      "bb#1": "K2Node_IfThenElse | Branch | Condition:Boolean | then:Exec | ",
                      "cc#1": "K2Node_CallFunction | Delay | Duration:Float | then:Exec | "},
            "connections": []}}
        a = self._dir("a", {"Game.BP_X": _blueprint()})
        b = self._dir("b", {"Game.BP_X": _blueprint(graphs=graph)})
        lines = gfd.diff(a, b)[0]
        self.assertTrue(any("+ node cc#1" in line for line in lines), lines)
        self.assertTrue(any("- link" in line and "Event Tick" in line for line in lines), lines)

    def test_added_and_removed_blueprints_are_reported(self):
        a = self._dir("a", {"Game.BP_X": _blueprint()})
        b = self._dir("b", {"Game.BP_Y": _blueprint()})
        self.assertEqual(gfd.diff(a, b)[0], ["- Blueprint Game.BP_X", "+ Blueprint Game.BP_Y"])

    def test_an_empty_directory_is_a_failure(self):
        a = self._dir("a", {})
        b = self._dir("b", {})
        self.assertEqual(gfd.main([a, b]), 1)


if __name__ == "__main__":
    unittest.main()
