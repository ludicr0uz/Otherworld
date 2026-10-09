"""No builder declares a member variable itself: every one is a row of a
``uebp.vars`` table, declared by ``declare(ed, TABLE)``.

Only ``uebp`` (the library) and ``dev`` (the codemods that got here) may name
``_declare`` or ``add_member_variable``.
"""

import os
import re
import unittest

import _paths  # noqa: F401

SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ALLOWED = ("uebp", "dev")
DECLARES = re.compile(r"\b_declare\(|\badd_member_variable\(")


class VarTablesTest(unittest.TestCase):
    def test_no_builder_declares_outside_a_table(self):
        found = []
        for folder, dirs, files in os.walk(SCRIPTS):
            rel = os.path.relpath(folder, SCRIPTS)
            if rel.split(os.sep)[0] in ALLOWED:
                dirs[:] = []
                continue
            for name in sorted(files):
                if not name.endswith(".py"):
                    continue
                with open(os.path.join(folder, name), encoding="utf-8") as fh:
                    for number, line in enumerate(fh, 1):
                        if DECLARES.search(line):
                            found.append(f"{os.path.normpath(os.path.join(rel, name))}:{number}")
        self.assertEqual(found, [], "declare these from a uebp.vars table")


if __name__ == "__main__":
    unittest.main()
