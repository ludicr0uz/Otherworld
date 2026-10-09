"""Every package's map names its modules, and nothing that is not there.

The map is the ``__init__`` docstring an agent reads to find a module's owner
(package_map.py says what counts as named). Also: the root CLAUDE.md's routing
table names every CLAUDE.md under Scripts/ and Source/.
"""

import os
import shutil
import tempfile
import unittest

import _paths  # noqa: F401
import package_map


class PackageMapsTest(unittest.TestCase):
    def test_every_module_is_in_its_map(self):
        for package in package_map.packages():
            rel = os.path.relpath(package, package_map.ROOT)
            with self.subTest(package=rel):
                self.assertEqual(package_map.missing(package), [],
                                 f"not in the map: python3 Scripts/dev/package_map.py --fix {rel}")

    def test_every_name_in_a_map_exists(self):
        for package in package_map.packages():
            rel = os.path.relpath(package, package_map.ROOT)
            with self.subTest(package=rel):
                self.assertEqual(package_map.ghosts(package), [],
                                 f"{rel}/__init__.py names what is not there")

    def test_the_packages_are_found(self):
        rels = {os.path.relpath(p, package_map.SCRIPTS) for p in package_map.packages()}
        self.assertLessEqual({"combat", os.path.join("combat", "verify"), "probes",
                              os.path.join("dev", "uepylib")}, rels)


class CheckTest(unittest.TestCase):
    """The check and the fix, on a scratch package."""

    def setUp(self):
        self.pkg = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.pkg)

    def write(self, name, text):
        with open(os.path.join(self.pkg, name), "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_missing_and_ghost(self):
        self.write("__init__.py", '"""pkg.\n\n  alpha  the first\n  gone   was here once\n'
                                  '  probe_*  the probes\n  see lost_file.py\n"""\n')
        for name in ("alpha", "beta", "probe_one", "alphabet"):
            self.write(name + ".py", f'"""{name} does a thing. And more."""\n')
        self.assertEqual(package_map.missing(self.pkg), ["alphabet", "beta"])
        self.assertEqual(package_map.ghosts(self.pkg), ["gone", "lost_file.py"])

    def test_rows_and_lists(self):
        self.write("__init__.py", '"""pkg.\n\n  alpha, beta   two tables\n  alpha  beta  nope\n"""\n')
        self.write("alpha.py", "")
        self.write("beta.py", "")
        self.assertEqual(package_map.missing(self.pkg), [])
        self.assertEqual(package_map.ghosts(self.pkg), ["nope"])

    def test_fix_appends_the_first_sentence(self):
        self.write("__init__.py", '"""pkg, on one line."""\n\nX = 1\n')
        self.write("alpha.py", '"""alpha.py -- the first\nof them. Then more."""\n')
        self.write("bare.py", "X = 1\n")
        self.assertEqual(package_map.fix(self.pkg), ["alpha", "bare"])
        with open(os.path.join(self.pkg, "__init__.py"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), '"""pkg, on one line.\n\n  alpha  the first of them\n'
                                        '  bare\n"""\n\nX = 1\n')
        self.assertEqual(package_map.missing(self.pkg), [])
        self.assertEqual(package_map.fix(self.pkg), [])


class RoutingTableTest(unittest.TestCase):
    def test_root_names_every_claude_md(self):
        root = package_map.ROOT
        with open(os.path.join(root, "CLAUDE.md"), encoding="utf-8") as fh:
            text = fh.read()
        table = "\n".join(line for line in text.splitlines() if line.lstrip().startswith("|"))
        for top in ("Scripts", "Source"):
            for folder, _dirs, files in os.walk(os.path.join(root, top)):
                if "CLAUDE.md" in files:
                    rel = os.path.relpath(os.path.join(folder, "CLAUDE.md"), root)
                    with self.subTest(file=rel):
                        self.assertIn(f"`{rel}`", table, "no row of the routing table reads it")


if __name__ == "__main__":
    unittest.main()
