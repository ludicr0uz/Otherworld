import json
import os
import tempfile
import time
import unittest

import _paths  # noqa: F401

from uepylib import compile as cc


def touch(path, age):
    open(path, "w").close()
    t = time.time() - age
    os.utime(path, (t, t))


class ModulesFileTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.modules = os.path.join(self.dir, "UnrealEditor.modules")

    def write(self, mods):
        with open(self.modules, "w") as f:
            json.dump({"BuildId": "1", "Modules": mods}, f)

    def read(self):
        return json.load(open(self.modules))["Modules"]

    def test_stale_entry_is_rewritten(self):
        touch(os.path.join(self.dir, "libUnrealEditor-Otherworld.dylib"), 300)
        touch(os.path.join(self.dir, "libUnrealEditor-Otherworld-0002.dylib"), 10)
        touch(os.path.join(self.dir, "libUnrealEditor-OtherworldEditor.dylib"), 5)
        self.write({"Otherworld": "libUnrealEditor-Otherworld.dylib",
                    "OtherworldEditor": "libUnrealEditor-OtherworldEditor.dylib"})
        changed = cc.fix_modules(self.dir)
        self.assertEqual(changed, [("Otherworld", "libUnrealEditor-Otherworld.dylib",
                                    "libUnrealEditor-Otherworld-0002.dylib")])
        self.assertEqual(self.read()["Otherworld"], "libUnrealEditor-Otherworld-0002.dylib")

    def test_current_entry_untouched(self):
        touch(os.path.join(self.dir, "libUnrealEditor-Otherworld-0001.dylib"), 10)
        self.write({"Otherworld": "libUnrealEditor-Otherworld-0001.dylib"})
        self.assertEqual(cc.fix_modules(self.dir), [])

    def test_editor_module_is_not_mistaken_for_runtime(self):
        touch(os.path.join(self.dir, "libUnrealEditor-OtherworldEditor.dylib"), 1)
        touch(os.path.join(self.dir, "libUnrealEditor-Otherworld-0001.dylib"), 50)
        self.assertEqual(cc.newest_dylib(self.dir, "Otherworld"),
                         "libUnrealEditor-Otherworld-0001.dylib")

    def test_first_errors(self):
        out = "ok\nfoo.cpp:3:1: error: boom\nmore\n"
        self.assertEqual(cc.first_errors(out), ["foo.cpp:3:1: error: boom"])


if __name__ == "__main__":
    unittest.main()
