"""The gate's probe set: parsing sets.py, reading a launch's output, comparing."""

import os
import tempfile
import unittest

from devteam import gate, probe_gate
from probes import sets

GAME_OUT = """\
[probe] ok    probe_a  3/3 checks passed
         PASS x
[probe] FAIL  probe_b  1/3 checks passed
         PASS x
         FAIL heal gated -- detail
         FAIL other
[probe] FAIL  probe_c  2/2 checks passed
"""
NET_OUT = """\
[probe] ok    probe_net_x @ server  2/2 checks passed
[probe] ok    probe_net_x @ client 1  1/1 checks passed
[probe] FAIL  probe_net_y @ client 2: no results -- it never finished (see client2.log)
"""


class SetsTest(unittest.TestCase):
    def test_smoke_names_exist_and_are_sized(self):
        self.assertEqual(sets.missing(sets.SMOKE), [])
        self.assertEqual(sets.SMOKE["clients"], 2)
        self.assertTrue(8 <= len(sets.SMOKE["game"]) <= 14)
        self.assertTrue(6 <= len(sets.SMOKE["net"]) <= 10)

    def test_resolve(self):
        self.assertEqual(sets.resolve("smoke")["net"], sets.SMOKE["net"])
        with self.assertRaises(ValueError):
            sets.resolve("nonsense")

    def test_resolve_returns_a_copy(self):
        sets.resolve("SMOKE")["game"].append("x")
        self.assertNotIn("x", sets.SMOKE["game"])

    def test_parse(self):
        self.assertEqual(sets.parse("a, b  c,d"), ["a", "b", "c", "d"])

    def test_full_covers_every_probe_but_load(self):
        with tempfile.TemporaryDirectory() as d:
            for name, body in (("probe_g", "SYSTEMS = ('npc',)\n"),
                               ("probe_n", "SYSTEMS = ('net',)\nRUNS_ON = ('server', 'client 3')\n"),
                               ("probe_s", "SYSTEMS = ('net',)\nRUNS_ON = ('server', 'client', 'standalone')\n"),
                               ("probe_t", "SYSTEMS = ('title',)\n"),
                               ("probe_l", "SYSTEMS = ('load',)\n")):
                with open(os.path.join(d, name + ".py"), "w") as fh:
                    fh.write(body)
            got = sets.full(d)
        self.assertEqual(got["game"], ["probe_g", "probe_s"])
        self.assertEqual(got["net"], ["probe_n"])
        self.assertEqual(got["title"], ["probe_t"])
        self.assertEqual(got["clients"], 3)

    def test_full_matches_the_probe_files(self):
        got = sets.full()
        names = got["game"] + got["title"] + got["net"]
        self.assertEqual(sets.missing(got), [])
        self.assertEqual(len(names), len(set(names)))


class ParseOutputTest(unittest.TestCase):
    def test_game(self):
        rows = probe_gate.parse_output(GAME_OUT, ["probe_a", "probe_b", "probe_c", "probe_d"])
        self.assertTrue(rows["probe:probe_a"]["ok"])
        self.assertEqual(rows["probe:probe_b"]["failed"], 2)
        self.assertEqual(rows["probe:probe_b"]["failures"], ["heal gated -- detail", "other"])
        self.assertFalse(rows["probe:probe_c"]["ok"])           # raised, every check passing
        self.assertGreaterEqual(rows["probe:probe_c"]["failed"], 1)
        self.assertFalse(rows["probe:probe_d"]["ok"])           # never reported

    def test_net_sums_processes_and_names_no_result(self):
        rows = probe_gate.parse_output(NET_OUT, ["probe_net_x", "probe_net_y"])
        self.assertEqual((rows["probe:probe_net_x"]["passed"], rows["probe:probe_net_x"]["ok"]), (3, True))
        self.assertFalse(rows["probe:probe_net_y"]["ok"])

    def test_a_dead_launch_fails_every_probe(self):
        rows = probe_gate.parse_output("", ["a", "b"])
        self.assertEqual(sorted(rows), ["probe:a", "probe:b"])
        self.assertFalse(any(r["ok"] for r in rows.values()))

    def test_launches(self):
        out = probe_gate.launches(sets.SMOKE)
        self.assertEqual([l[0] for l in out], ["game", "net"])
        self.assertEqual(out[1][1], ["--net", "--clients", "2"])
        self.assertEqual(probe_gate.launches({"game": [], "title": [], "net": []}), [])


class CompareTest(unittest.TestCase):
    def rows(self, out, names):
        return probe_gate.parse_output(out, names)

    def test_newly_failing_probe_is_a_regression(self):
        before = {"probe:probe_a": {"ok": True, "passed": 3, "failed": 0}}
        after = self.rows("[probe] FAIL  probe_a  1/3 checks passed\n         FAIL boom\n", ["probe_a"])
        problems = gate.regressions(before, after)
        self.assertEqual(len(problems), 1)
        self.assertIn("probe:probe_a", problems[0])
        self.assertIn("boom", problems[0])

    def test_failing_before_and_no_worse_is_not_blamed(self):
        out = "[probe] FAIL  probe_b  1/3 checks passed\n         FAIL x\n"
        self.assertEqual(gate.regressions(self.rows(out, ["probe_b"]), self.rows(out, ["probe_b"])), [])

    def test_table_shows_probe_rows(self):
        before = self.rows("[probe] ok    probe_a  3/3 checks passed\n", ["probe_a"])
        self.assertIn("| probe:probe_a | 3/3 |", gate.table(before))


if __name__ == "__main__":
    unittest.main()
