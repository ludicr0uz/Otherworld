import unittest

import _paths  # noqa: F401

from uepylib.cold import DRIVER, END, START, split_targets

STAMP = "[2026.09.30-00.36.21:319][  2]LogPython: Warning: "


def marker(text):
    return STAMP + text


class SplitTargetsTest(unittest.TestCase):

    def test_each_target_gets_its_own_slice(self):
        log = "\n".join([
            "boot noise",
            marker(START + "a.py"),
            STAMP + "[VERIFY] 1 passed, 0 failed",
            marker(END + "a.py ok 1.5"),
            marker(START + "b.py"),
            STAMP + "[GEN] built",
            marker(END + "b.py FAILED 0.2"),
            "shutdown noise",
        ])
        a, b = split_targets(log, ["a.py", "b.py"])
        self.assertTrue(a.ok)
        self.assertEqual(a.seconds, 1.5)
        self.assertIn("1 passed", a.text)
        self.assertNotIn("boot noise", a.text)
        self.assertFalse(b.ok)
        self.assertIn("[GEN] built", b.text)
        self.assertNotIn("1 passed", b.text)

    def test_a_traceback_fails_the_target_even_if_marked_ok(self):
        log = "\n".join([marker(START + "a.py"),
                         "Traceback (most recent call last):", "ValueError: x",
                         marker(END + "a.py ok 0.1")])
        (a,) = split_targets(log, ["a.py"])
        self.assertFalse(a.ok)

    def test_a_crash_mid_script_fails_it_with_what_it_logged(self):
        log = "\n".join([marker(START + "a.py"), "half way", "Segmentation fault"])
        (a,) = split_targets(log, ["a.py"])
        self.assertFalse(a.ok)
        self.assertIn("half way", a.text)
        self.assertIn("ended mid-script", a.text)

    def test_never_started_gets_the_boot_tail(self):
        (a,) = split_targets("engine failed to boot", ["a.py"])
        self.assertFalse(a.ok)
        self.assertIn("never started", a.text)
        self.assertIn("engine failed to boot", a.text)

    def test_the_same_script_twice(self):
        log = "\n".join([marker(START + "a.py"), "first", marker(END + "a.py ok 1.0"),
                         marker(START + "a.py"), "second", marker(END + "a.py FAILED 2.0")])
        first, second = split_targets(log, ["a.py", "a.py"])
        self.assertEqual((first.text, first.ok), ("first", True))
        self.assertEqual((second.text, second.ok), ("second", False))


class DriverTest(unittest.TestCase):

    def test_driver_renders_and_compiles(self):
        # The driver runs inside the editor; here it only has to be valid Python
        # that logs its markers through unreal (print never reaches a cold log).
        source = DRIVER.format(targets=[("file", "/x/a.py", "a.py")], start=START, end=END)
        compile(source, "<driver>", "exec")
        self.assertIn("unreal.log_warning", source)
        self.assertNotIn("print(", source)


if __name__ == "__main__":
    unittest.main()
