"""The probe sweep on its own (devteam/nightly.py): ``dev-team probes run``."""
import contextlib
import io
import os
import shutil
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401

from devteam import nightly, probe_gate, probe_record
from test_devteam import row

SET = {"game": ["probe_a"], "title": [], "net": ["probe_net_b"], "clients": 2}


class NightlySweep(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.logs = os.path.join(self.tmp, "logs")
        self.ran = []

    def sweep(self, name="FULL", failing=(), editors_closed=True):
        def probes(probe_set, log):
            self.ran.append((probe_gate.labels(probe_set), log))
            rows = {l: row(l, 3, 1 if l in failing else 0, ["check z"] if l in failing else [])
                    for l in probe_gate.labels(probe_set)}
            probe_record.update(self.tmp, rows, "c1")
            return rows

        out = io.StringIO()
        with mock.patch.multiple(nightly.work, probes=probes,
                                 close_editors=lambda: editors_closed), \
                mock.patch.object(nightly.sets, "resolve",
                                  lambda n: dict(SET) if n in ("FULL", "SMOKE") else
                                  (_ for _ in ()).throw(ValueError(f"no probe set '{n}'"))), \
                contextlib.redirect_stdout(out):
            code = nightly.run(name, root=self.tmp, log_root=self.logs)
        return code, out.getvalue()

    def report(self):
        run = sorted(os.listdir(self.logs))[-1]
        self.assertTrue(run.startswith("probes-"))
        with open(os.path.join(self.logs, run, "report.md")) as fh:
            return fh.read()

    def test_a_clean_sweep_records_and_reports(self):
        code, out = self.sweep()
        self.assertEqual(code, 0)
        self.assertEqual(len(self.ran), 1)
        self.assertEqual(self.ran[0][0], ["probe:probe_a", "probe:probe_net_b"])
        self.assertTrue(self.ran[0][1].endswith("sweeps.txt"))
        self.assertIn("probes: FULL starting, 2 probe(s), the probe record, which holds no "
                      "result for any of the 2 probe(s)", out)
        self.assertIn("dev-team: probes FULL ok in ", out)
        self.assertIn("2 of 2 passing, 0 newly failing  (report: ", out)
        text = self.report()
        self.assertTrue(text.startswith("# Probe sweep: FULL, ok\n"))
        self.assertIn("| probe:probe_a | missing | 3/3 |", text)
        self.assertNotIn("## Failing", text)
        self.assertEqual(sorted(probe_record.load(self.tmp)), ["probe_a", "probe_net_b"])

    def test_a_new_failure_exits_1_and_the_same_one_again_does_not(self):
        code, out = self.sweep(failing=("probe:probe_net_b",))
        self.assertEqual(code, 1)
        self.assertIn("1 of 2 passing, 1 newly failing", out)
        self.assertIn("\n  - probe:probe_net_b: 3/4 FAILED (new) -- check z", out)
        text = self.report()
        self.assertTrue(text.startswith("# Probe sweep: FULL, FAILED\n"))
        self.assertIn("## Failing\n\n- probe:probe_net_b: 3/4 FAILED\n  - check z\n", text)
        self.assertIn("## Newly failing\n\n- probe:probe_net_b: 3/4 FAILED (new)", text)
        # Failing on record and no worse: the nightly after is quiet about it.
        code, out = self.sweep(failing=("probe:probe_net_b",))
        self.assertEqual(code, 0)
        self.assertIn("1 of 2 passing, 0 newly failing", out)
        self.assertIn("| probe:probe_net_b | 3/4 FAILED | 3/4 FAILED |", self.report())
        self.assertIn("## Failing", self.report())

    def test_an_unknown_set_or_an_open_editor_exits_2(self):
        code, out = self.sweep("WEEKLY")
        self.assertEqual((code, self.ran), (2, []))
        self.assertIn("no probe set 'WEEKLY'", out)
        code, out = self.sweep(editors_closed=False)
        self.assertEqual((code, self.ran), (2, []))
        self.assertIn("an editor of this project is still running", out)
        self.assertFalse(os.path.exists(self.logs))


if __name__ == "__main__":
    unittest.main()
