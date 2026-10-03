"""Every ``from <project module> import name`` names something that module
defines: the first thing a codemod that moves definitions breaks, and nothing
else on the host notices (the builders only import inside the editor)."""

import os
import sys
import unittest

import _paths

sys.path.insert(0, os.path.join(_paths.DEV, "codemods"))
import source  # noqa: E402


class ProjectImportsTest(unittest.TestCase):
    def test_every_imported_name_exists(self):
        self.assertEqual(source.missing_imports(source.Project()), [])


if __name__ == "__main__":
    unittest.main()
