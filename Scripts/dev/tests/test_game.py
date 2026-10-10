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

    def test_a_stale_inventory_record_is_counted_shown_and_failing(self):
        text = "LogOtherworldInventory: Warning: INVENTORY-RECORD-STALE: BP_C_0 changed"
        counts = dict(game.count_patterns(text, game.GAME_PATTERNS))
        self.assertEqual(counts["stale records"], 1)
        self.assertIn("stale records", game.FAILING)
        self.assertEqual(game.notable_lines(text), [text])

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

    def test_title_leaves_the_menu_up_and_names_the_runs_level(self):
        ini = "-ini:Engine:[/Script/EngineSettings.GameMapsSettings]:GameDefaultMap=/Game/Maps/L"
        self.assertEqual(game.title_args("/Game/Maps/L"), ["-nomenu", ini])
        self.assertEqual(game.title_args("/Game/Maps/L", title=True), [ini])
        self.assertNotIn("UEPY_TITLE", game.game_env({"UEPY_TITLE": "1"}, "/L", [], "/r", None))
        self.assertEqual(game.game_env({}, "/L", [], "/r", None, title=True)["UEPY_TITLE"], "1")


class RenderArgsTest(unittest.TestCase):

    def test_a_run_draws_nothing_unless_asked(self):
        self.assertEqual(game.render_args(False), ["-nullrhi"])

    def test_a_windowed_run_has_a_window_and_no_nullrhi(self):
        args = game.render_args(True)
        self.assertIn("-windowed", args)
        self.assertNotIn("-nullrhi", args)


class VerdictsTest(unittest.TestCase):
    """game.verdicts and game.asked_verdicts: the per-probe table --probes-for ends on."""

    def probe(self, name, ok=True, error=None):
        return {"name": name, "checks": [{"ok": ok, "label": "x", "detail": ""}],
                "notes": [], "error": error}

    def test_each_probe_in_run_order(self):
        payload = {"probes": [self.probe("a"), self.probe("b", ok=False),
                              self.probe("c", error="boom")], "setup_errors": []}
        self.assertEqual(game.verdicts(payload), [("a", True), ("b", False), ("c", False)])

    def test_a_setup_error_fails_them_all_and_no_payload_is_nothing(self):
        payload = {"probes": [self.probe("a")], "setup_errors": ["no map"]}
        self.assertEqual(game.verdicts(payload), [("a", False)])
        self.assertEqual(game.verdicts(None), [])

    def test_asked_probes_never_reported_count_as_failed(self):
        probes = ["/p/probe_a.py", "/p/probe_b.py"]
        payload = {"probes": [self.probe("probe_a")], "setup_errors": []}
        self.assertEqual(game.asked_verdicts(probes, [payload]),
                         [("probe_a", True), ("probe_b", False)])
        self.assertEqual(game.asked_verdicts(probes, [None]),
                         [("probe_a", False), ("probe_b", False)])

    def test_a_net_probe_passes_only_when_every_process_did(self):
        probes = ["/p/probe_net_x.py"]
        server = {"probes": [self.probe("probe_net_x")], "setup_errors": []}
        client = {"probes": [self.probe("probe_net_x", ok=False)], "setup_errors": []}
        self.assertEqual(game.asked_verdicts(probes, [server, client]), [("probe_net_x", False)])
        self.assertEqual(game.asked_verdicts(probes, [server, server]), [("probe_net_x", True)])


if __name__ == "__main__":
    unittest.main()
