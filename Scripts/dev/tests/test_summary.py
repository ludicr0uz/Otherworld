import unittest

import _paths  # noqa: F401

from uepylib.summary import clean, format_target, summarize, verdict
from uepylib.targets import TargetResult

STAMP = "[2026.09.29-23.52.23:006][  2]"


def cold(line, level="Warning"):
    return f"{STAMP}LogPython: {level}: {line}"


class CleanTest(unittest.TestCase):

    def test_strips_stamp_category_and_level(self):
        self.assertEqual(clean(cold("[VERIFY] 1 passed, 0 failed")),
                         "[VERIFY] 1 passed, 0 failed")

    def test_strips_inbox_level_prefix(self):
        self.assertEqual(clean("Warning: [GUN] done"), "[GUN] done")

    def test_keeps_indentation_of_traceback_lines(self):
        self.assertEqual(clean(cold('  File "x.py", line 3', "Error")), '  File "x.py", line 3')


class TotalsTest(unittest.TestCase):

    def test_graphics_menu_format(self):
        s = summarize(cold("[VERIFY] 144/146 checks passed"))
        self.assertEqual((s.passed, s.failed, s.total), (144, 2, 146))

    def test_passed_failed_format(self):
        s = summarize("Warning: [VERIFY] 98 passed, 1 failed")
        self.assertEqual((s.passed, s.failed), (98, 1))

    def test_level_all_passed(self):
        s = summarize(cold("[VERIFY] ✅ ALL 257 CHECKS PASSED!"))
        self.assertEqual((s.passed, s.failed), (257, 0))

    def test_level_failed(self):
        s = summarize(cold("[VERIFY] ❌ 3/257 CHECKS FAILED!", "Error"))
        self.assertEqual((s.passed, s.failed), (254, 3))

    def test_several_suites_in_one_target_add_up(self):
        s = summarize("[VERIFY] 10 passed, 0 failed\n[VERIFY] 5/6 checks passed")
        self.assertEqual((s.passed, s.failed), (15, 1))

    def test_no_totals(self):
        s = summarize("Warning: [GUN] done -- five weapons")
        self.assertFalse(s.has_totals)
        self.assertEqual(s.last_tag, "[GUN] done -- five weapons")


class FailuresTest(unittest.TestCase):

    def test_detailed_fail_lines_win_over_named(self):
        text = "\n".join([
            cold("[VERIFY] ok   compiles without node errors — 0"),
            cold("[VERIFY] FAIL panel labels — ['DIFFICULTY']"),
            cold("[VERIFY] 145/146 checks passed"),
            cold("[VERIFY] failed: panel labels", "Error"),
        ])
        s = summarize(text)
        self.assertEqual(s.failures, ["panel labels — ['DIFFICULTY']"])
        self.assertEqual(s.errors, [])      # the [VERIFY] error line is not an "error"

    def test_named_failures_are_the_fallback(self):
        s = summarize("[VERIFY] 98 passed, 1 failed\n[VERIFY]   FAILED: the heal is gated")
        self.assertEqual(s.failures, ["the heal is gated"])

    def test_level_cross_lines(self):
        s = summarize(cold("  ❌ NPCs Inside Nav Bounds: FAILED (volume)") + "\n"
                      + cold("[VERIFY] ❌ 1/257 CHECKS FAILED!", "Error"))
        self.assertEqual(s.failures, ["NPCs Inside Nav Bounds: FAILED (volume)"])
        self.assertEqual(s.failed, 1)

    def test_fail_is_not_failed(self):
        s = summarize("[VERIFY]   FAILED: x")
        self.assertEqual(s.failures, ["x"])


class TracebackTest(unittest.TestCase):
    TB = "\n".join([
        "Traceback (most recent call last):",
        '  File "a.py", line 1, in <module>',
        "    main()",
        '  File "b.py", line 9, in main',
        "    raise ValueError('boom')",
        "ValueError: boom",
        "Warning: [GUN] after",
    ])

    def test_tail_and_exception_line(self):
        s = summarize(self.TB)
        self.assertEqual(len(s.tracebacks), 1)
        self.assertTrue(s.tracebacks[0].endswith("ValueError: boom"))
        self.assertEqual(len(s.tracebacks[0].splitlines()), 4)

    def test_traceback_lines_are_not_errors(self):
        text = "\n".join(cold(l, "Error") for l in self.TB.splitlines()[:-1])
        s = summarize(text)
        self.assertEqual(len(s.tracebacks), 1)
        self.assertEqual(s.errors, [])

    def test_python_errors_outside_tracebacks(self):
        s = summarize(cold("[GEN] could not load X", "Error") + "\nError: from the inbox")
        self.assertEqual(s.errors, ["[GEN] could not load X", "from the inbox"])

    def test_other_categories_errors_are_noise(self):
        s = summarize(f"{STAMP}LogAudioMixerAudioUnit: Warning: Error querying Sample Rate")
        self.assertEqual(s.errors, [])


class VerdictTest(unittest.TestCase):

    def test_failed_checks_fail_a_target_that_ran(self):
        r = TargetResult("v.py", True, 1.0, "[VERIFY] 98 passed, 1 failed")
        self.assertFalse(verdict(r, summarize(r.text)))

    def test_clean_target_passes(self):
        r = TargetResult("v.py", True, 1.0, "[VERIFY] 99 passed, 0 failed")
        self.assertTrue(verdict(r, summarize(r.text)))

    def test_transport_failure_fails(self):
        r = TargetResult("b.py", False, 1.0, "")
        self.assertFalse(verdict(r, summarize(r.text)))


class FormatTest(unittest.TestCase):

    def test_passing_verifier_is_one_line(self):
        r = TargetResult("verify_survival.py", True, 1.1, "[VERIFY] 99 passed, 0 failed")
        self.assertEqual(format_target(r, summarize(r.text)),
                         ["[uepy] ok    verify_survival.py  99/99 checks passed  (1.1s)"])

    def test_builder_shows_its_last_tag(self):
        r = TargetResult("build.py", True, 4.0, "Warning: [GUN] done -- all")
        self.assertIn("[GUN] done -- all", format_target(r, summarize(r.text))[0])

    def test_failure_lists_checks_and_count_of_the_rest(self):
        text = "\n".join(["[VERIFY] FAIL a — 1", "[VERIFY] 0 passed, 3 failed"])
        r = TargetResult("v.py", True, 1.0, text)
        lines = format_target(r, summarize(text))
        self.assertTrue(lines[0].startswith("[uepy] FAIL  v.py  0/3"))
        self.assertIn("         FAIL a — 1", lines)
        self.assertIn("         (+2 more failed checks)", lines)

    def test_unexplained_failure_shows_the_tail(self):
        r = TargetResult("b.py", False, 0.0, "line one\nline two")
        lines = format_target(r, summarize(r.text))
        self.assertEqual(lines[-1], "         | line two")


if __name__ == "__main__":
    unittest.main()
