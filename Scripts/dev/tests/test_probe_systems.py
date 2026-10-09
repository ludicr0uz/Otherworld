"""Every probe declares a non-empty SYSTEMS tuple drawn from probes/systems.py."""

import ast
import glob
import os
import unittest

import _paths
from probes.systems import SYSTEMS

PROBES = os.path.join(_paths.SCRIPTS, "probes")


def declared(path):
    for node in ast.parse(open(path).read()).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "SYSTEMS" for t in node.targets):
            return ast.literal_eval(node.value)
    return None


class ProbeSystemsTest(unittest.TestCase):
    def test_every_probe_declares_systems(self):
        paths = glob.glob(os.path.join(PROBES, "probe_*.py"))
        self.assertTrue(paths)
        for path in paths:
            tags = declared(path)
            name = os.path.basename(path)
            self.assertTrue(tags, f"{name}: no SYSTEMS")
            for tag in tags:
                self.assertIn(tag, SYSTEMS, f"{name}: unknown system {tag}")


if __name__ == "__main__":
    unittest.main()
