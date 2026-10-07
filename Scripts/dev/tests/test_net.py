import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import _paths

sys.path.insert(0, _paths.DEV)
import uepy  # noqa: E402

from probes.net import LISTENING, Where, pick_probe  # noqa: E402
from uepylib import net, net_plan, net_report  # noqa: E402
from uepylib.net_report import ProcessReport  # noqa: E402

JOINED = "LogNet: Join succeeded: a\n"
WELCOMED = "LogNet: Welcomed by server (Level: /Game/Maps/L)\n"


def payload(name, ok=True, where="server"):
    return {"where": where, "setup_errors": [], "probes": [
        {"name": name, "notes": [], "error": None,
         "checks": [{"ok": ok, "label": "it holds", "detail": "d"}]}]}


class ArgsTest(unittest.TestCase):

    def parse(self, *argv):
        with mock.patch.object(sys, "argv", ["uepy.py", *argv]):
            return uepy.parse_args()[1]

    def test_net_defaults(self):
        args = self.parse("--net")
        self.assertTrue(args.net)
        self.assertEqual((args.clients, args.port, args.windowed, args.probe),
                         (1, net_plan.DEFAULT_PORT, False, []))
        self.assertEqual(args.map, "/Game/Maps/Lvl_Forest_200m")

    def test_net_takes_clients_probes_and_a_window(self):
        args = self.parse("--net", "--clients", "2", "--windowed", "--seconds", "9",
                          "--probe", "a.py", "--probe", "b.py")
        self.assertEqual((args.clients, args.windowed, args.seconds, args.probe),
                         (2, True, 9, ["a.py", "b.py"]))

    def test_check_args(self):
        self.assertIsNone(net_plan.check_args(2, 17777))
        self.assertIsNone(net_plan.check_args(1, 17777, 5))
        self.assertIn("at least one", net_plan.check_args(0, 17777))
        self.assertIn("at most", net_plan.check_args(net_plan.MAX_CLIENTS + 1, 17777))
        self.assertIn("--port", net_plan.check_args(1, 80))
        self.assertIn("--seconds", net_plan.check_args(1, 17777, 0))

    def test_bots_and_trace(self):
        args = self.parse("--net", "--clients", "2", "--bots", "32", "--trace")
        self.assertEqual((args.bots, args.trace), (32, True))
        self.assertEqual((self.parse("--net").bots, self.parse("--net").trace), (0, False))
        self.assertIsNone(net_plan.check_args(2, 17777, None, 0, net_plan.MAX_BOTS))
        self.assertIn("--bots", net_plan.check_args(2, 17777, None, 0, net_plan.MAX_BOTS + 1))
        self.assertIn("--bots", net_plan.check_args(2, 17777, None, 0, -1))

    def test_net_and_game_together_are_refused(self):
        with mock.patch.object(sys, "argv", ["uepy.py", "--net", "--game"]), \
                contextlib.redirect_stderr(io.StringIO()) as err, \
                self.assertRaises(SystemExit):
            uepy.main()
        self.assertIn("--net and --game", err.getvalue())

    def test_bad_clients_never_start_a_run(self):
        with mock.patch.object(sys, "argv", ["uepy.py", "--net", "--clients", "0"]), \
                mock.patch.object(net, "run_net") as run, \
                contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit):
            uepy.main()
        run.assert_not_called()


class PlanTest(unittest.TestCase):

    def setUp(self):
        self.plan = net_plan.processes("/run", 2)

    def test_the_server_then_each_client(self):
        self.assertEqual([p.name for p in self.plan], ["server", "client 1", "client 2"])
        self.assertEqual([os.path.basename(p.log) for p in self.plan],
                         ["server.log", "client1.log", "client2.log"])
        self.assertEqual(len({p.inbox for p in self.plan} | {p.results for p in self.plan}), 6)

    def test_the_server_command(self):
        cmd = net_plan.command("ed", "p.uproject", self.plan[0], 17777)
        self.assertEqual(cmd[:3], ["ed", "p.uproject", net_plan.ENTRY_URL])
        self.assertIn("-server", cmd)
        self.assertIn("-port=17777", cmd)
        self.assertIn("-abslog=/run/server.log", cmd)
        self.assertNotIn("-game", cmd)
        self.assertNotIn("-nullrhi", cmd)

    def test_a_client_draws_nothing_unless_windowed(self):
        cmd = net_plan.command("ed", "p.uproject", self.plan[1], 17777)
        self.assertIn("-game", cmd)
        self.assertIn("-nullrhi", cmd)
        self.assertNotIn("-server", cmd)
        windowed = net_plan.command("ed", "p.uproject", self.plan[2], 17777, windowed=True)
        self.assertNotIn("-nullrhi", windowed)
        self.assertIn("-windowed", windowed)
        self.assertIn(f"-WinX={net_plan.WINDOW_STEP}", windowed)

    def test_lag_delays_the_clients_packets_only(self):
        self.assertIn("-PktLag=120",
                      net_plan.command("ed", "p", self.plan[1], 17777, lag_ms=120))
        self.assertFalse([a for a in net_plan.command("ed", "p", self.plan[0], 17777,
                                                      lag_ms=120) if "PktLag" in a])
        self.assertFalse([a for a in net_plan.command("ed", "p", self.plan[1], 17777)
                          if "PktLag" in a])
        self.assertIsNone(net_plan.check_args(2, 17777, None, 120))
        self.assertIn("--lag", net_plan.check_args(2, 17777, None, -5))

    def test_trace_is_the_servers_alone(self):
        cmd = net_plan.command("ed", "p", self.plan[0], 17777, trace=True)
        self.assertIn(f"-trace={net_plan.TRACE_CHANNELS}", cmd)
        self.assertIn("-tracefile=/run/server.utrace", cmd)
        self.assertFalse([a for a in net_plan.command("ed", "p", self.plan[1], 17777, trace=True)
                          if "trace" in a])
        self.assertFalse([a for a in net_plan.command("ed", "p", self.plan[0], 17777)
                          if "trace" in a])

    def test_every_process_is_told_the_bots(self):
        for process in self.plan:
            env = net_plan.environment({}, process, "/run", 2, 17777, "/L", [], bots=16)
            self.assertEqual(env["UEPY_NET_BOTS"], "16")
        env = net_plan.environment({}, self.plan[0], "/run", 2, 17777, "/L", [])
        self.assertEqual(env["UEPY_NET_BOTS"], "0")

    def test_no_client_is_told_to_skip_the_menu(self):
        # A joined client has no title by the game's own rule; the server has no HUD.
        self.assertIn("-nomenu", net_plan.command("ed", "p", self.plan[0], 17777, level="/L"))
        for process in self.plan[1:]:
            self.assertNotIn("-nomenu",
                             net_plan.command("ed", "p", process, 17777, level="/L"))

    def test_a_left_server_returns_to_the_runs_level(self):
        for process in self.plan:
            self.assertIn(
                "-ini:Engine:[/Script/EngineSettings.GameMapsSettings]:GameDefaultMap=/L",
                net_plan.command("ed", "p", process, 17777, level="/L"))

    def test_title_starts_the_clients_alone(self):
        env = net_plan.environment({"UEPY_TITLE": "1"}, self.plan[1], "/run", 2, 17777,
                                   "/L", [])
        self.assertNotIn("UEPY_TITLE", env)
        env = net_plan.environment({}, self.plan[1], "/run", 2, 17777, "/L", [], title=True)
        self.assertEqual(env["UEPY_TITLE"], "1")

    def test_the_server_is_never_windowed(self):
        self.assertNotIn("-windowed",
                         net_plan.command("ed", "p", self.plan[0], 17777, windowed=True))

    def test_the_environment_names_the_process(self):
        env = net_plan.environment({"UEPY_SERVE": "/warm", "HOME": "/h"}, self.plan[2],
                                   "/run", 2, 17777, "/Game/Maps/L", ["/a.py", "/b.py"], 30)
        self.assertNotIn("UEPY_SERVE", env)
        self.assertEqual(env["HOME"], "/h")
        self.assertEqual(env["UEPY_INBOX_DIR"], "/run/inbox-client2")
        self.assertEqual(env["UEPY_PROBES"], os.pathsep.join(["/a.py", "/b.py"]))
        self.assertEqual(env["UEPY_PROBE_RESULTS"], "/run/client2.json")
        self.assertEqual(env["UEPY_PROBE_TIMEOUT"], "30")
        # ... and Scripts/probes/net.py reads the same process back.
        where = Where.from_env(env)
        self.assertEqual((where.name, where.role, where.index, where.clients, where.address),
                         ("client 2", "client", 2, 2, "127.0.0.1:17777"))

    def test_every_planned_name_parses(self):
        for process in self.plan:
            env = net_plan.environment({}, process, "/run", 2, 17777, "/L", [])
            self.assertEqual(Where.from_env(env).name, process.name)


class WhereTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_standalone_outside_a_network_run(self):
        where = Where.from_env({})
        self.assertEqual((where.name, where.networked, where.index), ("standalone", False, 0))

    def test_a_bad_name_is_refused(self):
        for bad in ("client", "server 1", "host", "client x"):
            with self.assertRaises(ValueError):
                Where.from_env({"UEPY_NET_WHERE": bad})

    def test_runs_on(self):
        server, one, two = Where("server"), Where("client", 1), Where("client", 2)
        for where in (server, one, two, Where()):
            self.assertTrue(where.matches(None))
        self.assertTrue(server.matches(("server", "client")))
        self.assertTrue(two.matches(("server", "client")))
        self.assertTrue(one.matches("client 1"))
        self.assertFalse(two.matches(("server", "client 1")))
        self.assertFalse(server.matches("client"))
        self.assertFalse(Where().matches(("server", "client")))
        self.assertTrue(Where().matches(("standalone", "server")))

    def test_the_board_carries_a_value_between_processes(self):
        server = Where("server", 0, 2, self.tmp)
        client = Where("client", 2, 2, self.tmp)
        self.assertIsNone(client.posted("server", LISTENING))
        server.post(LISTENING)
        client.post("seen", {"hp": 40})
        self.assertIs(client.posted("server", LISTENING), True)
        self.assertEqual(server.posted("client 2", "seen"), {"hp": 40})
        self.assertIsNone(server.posted("client 1", "seen"))

    def test_standalone_keeps_its_own_posts(self):
        where = Where()
        where.post("k", 3)
        self.assertEqual(where.posted("standalone", "k"), 3)
        self.assertIsNone(where.posted("server", "k"))

    def test_pick_probe_prefers_the_role(self):
        both = {"probe": lambda p: "any", "probe_server": lambda p: "server"}
        self.assertEqual(pick_probe(both, Where("server"))(None), "server")
        self.assertEqual(pick_probe(both, Where("client", 1))(None), "any")
        self.assertIsNone(pick_probe({"probe_server": both["probe"]}, Where("client", 1)))
        self.assertIsNone(pick_probe({"probe": 3}, Where()))


class ReportTest(unittest.TestCase):

    def clean(self, name="p"):
        return [ProcessReport("server", JOINED * 2, payload(name)),
                ProcessReport("client 1", WELCOMED, payload(name, where="client 1")),
                ProcessReport("client 2", WELCOMED, payload(name, where="client 2"))]

    def test_a_clean_run(self):
        lines, ok = net_report.report(self.clean(), 2, ["p"])
        self.assertTrue(ok)
        self.assertEqual(lines[0].split(),
                         ["process", "joins", "bp", "errors", "accessed", "None", "net", "failures",
                          "corrections"])
        self.assertEqual(lines[1].split(), ["server", "2/2", "0", "0", "0", "0"])
        self.assertEqual(lines[3].split(), ["client", "2", "1/1", "0", "0", "0", "0"])
        self.assertIn("[probe] ok    p @ server  1/1 checks passed", lines)
        self.assertIn("[probe] ok    p @ client 2  1/1 checks passed", lines)

    def test_a_client_that_never_joined_fails_it(self):
        reports = self.clean()
        reports[0].text = JOINED
        reports[2].text = "booting\n"
        lines, ok = net_report.summary(reports, 2)
        self.assertFalse(ok)
        self.assertEqual(lines[1].split()[:2], ["server", "1/2"])
        self.assertEqual(lines[3].split()[:3], ["client", "2", "0/1"])

    def test_errors_are_counted_per_process_and_fail_it(self):
        reports = self.clean()
        reports[1].text += ("Blueprint Runtime Error: \"Accessed None trying to read X\"\n"
                            "LogNet: Warning: Network Failure: GameNetDriver[ConnectionLost]\n")
        lines, ok = net_report.summary(reports, 2)
        self.assertFalse(ok)
        self.assertEqual(lines[2].split(), ["client", "1", "1/1", "1", "1", "1", "0"])
        self.assertEqual(lines[1].split(), ["server", "2/2", "0", "0", "0", "0"])
        self.assertEqual(sum(1 for l in lines if l.startswith("  | client 1: ")), 2)

    def test_corrections_are_counted_and_fail_nothing(self):
        # A probe says how many a run may have; the report only counts them.
        reports = self.clean()
        reports[2].text += ("LogOtherworldMove: MOVE-CORRECTION 1 BP_C_0: 14.2 cm off\n"
                            "LogOtherworldMove: MOVE-CORRECTION 2 BP_C_0: 3.0 cm off\n")
        lines, ok = net_report.summary(reports, 2)
        self.assertTrue(ok)
        self.assertEqual(lines[0].split()[-1], "corrections")
        self.assertEqual(lines[3].split(), ["client", "2", "1/1", "0", "0", "0", "2"])

    def test_a_process_that_died_fails_it(self):
        reports = self.clean()
        reports[0].exit_code = 3
        lines, ok = net_report.summary(reports, 2)
        self.assertFalse(ok)
        self.assertIn("died (exit 3)", lines[1])

    def test_no_log_fails_it(self):
        reports = self.clean()
        reports[1].text = ""
        lines, ok = net_report.summary(reports, 2)
        self.assertFalse(ok)
        self.assertIn("  | client 1: no log", lines)

    def test_a_failed_check_in_one_process_fails_the_run(self):
        reports = self.clean()
        reports[2].payload = payload("p", ok=False)
        lines, ok = net_report.report(reports, 2, ["p"])
        self.assertFalse(ok)
        self.assertIn("[probe] FAIL  p @ client 2  0/1 checks passed", lines)
        self.assertIn("[probe] ok    p @ client 1  1/1 checks passed", lines)

    def test_a_process_with_no_results_fails_the_run(self):
        reports = self.clean()
        reports[1].payload = None
        reports[1].log = "/run/client1.log"
        lines, ok = net_report.probes(reports, ["p"])
        self.assertFalse(ok)
        self.assertTrue(any("client 1: no results" in l and "client1.log" in l for l in lines))

    def test_setup_errors_name_their_process(self):
        reports = self.clean()
        reports[0].payload = {"probes": [], "setup_errors": ["never came up"]}
        lines, ok = net_report.probes(reports, ["p"])
        self.assertFalse(ok)
        self.assertIn("[probe] SETUP FAILED: server: never came up", lines)

    def test_a_probe_that_ran_nowhere_fails_the_run(self):
        lines, ok = net_report.probes(self.clean("p"), ["p", "q"])
        self.assertFalse(ok)
        self.assertTrue(any(l.startswith("[probe] FAIL  q ran in no process") for l in lines))

    def test_a_probe_may_skip_a_process(self):
        reports = self.clean()
        reports[1].payload = {"probes": [], "setup_errors": []}
        lines, ok = net_report.probes(reports, ["p"])
        self.assertTrue(ok)
        self.assertFalse(any("client 1" in l for l in lines))

    def test_no_probes_no_probe_section(self):
        reports = [ProcessReport("server", JOINED), ProcessReport("client 1", WELCOMED)]
        lines, ok = net_report.report(reports, 1)
        self.assertTrue(ok)
        self.assertEqual(len(lines), 3)


class RunTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_refuses_while_an_editor_is_in_pie(self):
        out = io.StringIO()
        with mock.patch.object(net, "pie_editor", lambda: {"pid": 1, "pie": True}), \
                mock.patch.object(net.subprocess, "Popen") as popen, \
                contextlib.redirect_stdout(out):
            self.assertFalse(net.run_net("/engine", "/Game/Maps/L", 2, 17777))
        popen.assert_not_called()
        self.assertIn("is in PIE", out.getvalue())

    def test_pie_is_read_from_the_editors_heartbeat(self):
        beats = {"/ui": {"pid": 1, "pie": True}}
        with mock.patch.object(net, "saved_uepy", lambda *p: "/ui"), \
                mock.patch.object(net, "serve_inbox", lambda: None), \
                mock.patch.object(net.inbox, "heartbeat", lambda d: beats.get(d)):
            self.assertEqual(net.pie_editor(), beats["/ui"])
            beats["/ui"] = {"pid": 1, "pie": False}
            self.assertIsNone(net.pie_editor())
            beats.clear()
            self.assertIsNone(net.pie_editor())

    def test_kept_slots_are_put_back(self):
        for name, text in (("A.sav.probe-backup", "mine"), ("A.sav", "the run's"),
                           ("B.sav", "untouched")):
            with open(os.path.join(self.tmp, name), "w") as fh:
                fh.write(text)
        net.put_back_kept(self.tmp)
        self.assertEqual(sorted(os.listdir(self.tmp)), ["A.sav", "B.sav"])
        with open(os.path.join(self.tmp, "A.sav")) as fh:
            self.assertEqual(fh.read(), "mine")

    def test_old_runs_are_dropped(self):
        with mock.patch.object(net, "saved_uepy", lambda *p: os.path.join(self.tmp, *p)):
            root = os.path.join(self.tmp, "net")
            for i in range(net.KEEP_RUNS + 5):
                os.makedirs(os.path.join(root, f"2025010{i:02d}"))
            fresh = net.run_dir()
            kept = sorted(os.listdir(root))
        self.assertEqual(len(kept), net.KEEP_RUNS)
        self.assertEqual(os.path.basename(fresh), kept[-1])


if __name__ == "__main__":
    unittest.main()
