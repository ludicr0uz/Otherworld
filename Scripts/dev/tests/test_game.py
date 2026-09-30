import unittest

import _paths  # noqa: F401

from uepylib import game


class CountTest(unittest.TestCase):

    def test_counts_each_pattern(self):
        text = "Accessed None x\nAccessed None y\nNPC-SPAWN #1"
        counts = dict(game.count_patterns(text, game.GAME_PATTERNS))
        self.assertEqual(counts["accessed None"], 2)
        self.assertEqual(counts["NPC spawns"], 1)
        self.assertEqual(counts["blueprint runtime errors"], 0)

    def test_notable_lines_are_capped(self):
        text = "\n".join(f"Accessed None {i}" for i in range(40))
        lines = game.notable_lines(text)
        self.assertEqual(len(lines), game.MAX_NOTABLE + 1)
        self.assertEqual(lines[-1], f"(+{40 - game.MAX_NOTABLE} more)")


class ProbeReportTest(unittest.TestCase):

    def test_all_passing(self):
        payload = {"probes": [{"name": "p", "checks": [
            {"ok": True, "label": "heals", "detail": "50 -> 60"}], "notes": [], "error": None}],
            "setup_errors": []}
        lines, ok = game.probe_report(payload)
        self.assertTrue(ok)
        self.assertEqual(lines[0], "[probe] ok    p  1/1 checks passed")
        self.assertEqual(lines[1], "         PASS heals -- 50 -> 60")

    def test_a_failed_check_fails_the_run(self):
        payload = {"probes": [{"name": "p", "checks": [
            {"ok": True, "label": "a", "detail": ""},
            {"ok": False, "label": "b", "detail": "no"}], "notes": ["n"], "error": None}]}
        lines, ok = game.probe_report(payload)
        self.assertFalse(ok)
        self.assertIn("[probe] FAIL  p  1/2 checks passed", lines)
        self.assertIn("         note: n", lines)

    def test_a_probe_error_fails_it(self):
        payload = {"probes": [{"name": "p", "checks": [], "notes": [],
                               "error": "Traceback\nValueError: x"}]}
        lines, ok = game.probe_report(payload)
        self.assertFalse(ok)
        self.assertEqual(lines[-1], "         ValueError: x")

    def test_setup_errors_fail(self):
        lines, ok = game.probe_report({"probes": [], "setup_errors": ["WRITABLE: no BP"]})
        self.assertFalse(ok)
        self.assertEqual(lines, ["[probe] SETUP FAILED: WRITABLE: no BP"])

    def test_no_results(self):
        lines, ok = game.probe_report(None)
        self.assertFalse(ok)


class GameEnvTest(unittest.TestCase):

    def test_plain_run_only_moves_the_inbox(self):
        env = game.game_env({"PATH": "/bin"}, "/Game/Maps/L", [], "/tmp/r.json", None)
        self.assertEqual(env["PATH"], "/bin")
        self.assertTrue(env["UEPY_INBOX_DIR"].endswith("/Saved/uepy/game"))
        self.assertNotIn("UEPY_PROBES", env)

    def test_probe_run_names_everything(self):
        env = game.game_env({}, "/Game/Maps/L", ["/a.py", "/b.py"], "/tmp/r.json", 30)
        self.assertEqual(env["UEPY_PROBES"].split(":"), ["/a.py", "/b.py"])
        self.assertEqual(env["UEPY_PROBE_MAP"], "/Game/Maps/L")
        self.assertEqual(env["UEPY_PROBE_RESULTS"], "/tmp/r.json")
        self.assertEqual(env["UEPY_PROBE_TIMEOUT"], "30")

    def test_the_base_environment_is_not_modified(self):
        base = {}
        game.game_env(base, "/Game/Maps/L", ["/a.py"], "/tmp/r.json", None)
        self.assertEqual(base, {})


if __name__ == "__main__":
    unittest.main()
