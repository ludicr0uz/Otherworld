"""uepylib/net_memory.py: reading ps and footprint, the peaks, the report's lines."""

import sys
import unittest
from unittest import mock

import _paths

sys.path.insert(0, _paths.DEV)

from uepylib import net_memory, net_report  # noqa: E402
from uepylib.net_memory import Meter, Usage  # noqa: E402
from uepylib.net_report import ProcessReport  # noqa: E402

PS = "11916 167312\n25484   2640\n"
# /usr/bin/footprint -p 11916 -p 25484, cut down to the lines that name a process.
FOOTPRINT = """======================================================================
UnrealEditor [11916]: 64-bit    Footprint: 4356 MB (16384 bytes per page)
======================================================================
Shared with zsh [25484]:
zsh [25484]: 64-bit    Footprint: 1712 KB (16384 bytes per page)
Shared with UnrealEditor [11916], zsh [25484]:
Summary Footprint: 4358 MB
"""
GB = 1024 * 1024


class FakeProc(object):
    def __init__(self, pid, code=None):
        self.pid, self.code = pid, code

    def poll(self):
        return self.code


class Named(object):
    def __init__(self, name):
        self.name = name


class ParseTest(unittest.TestCase):

    def test_ps(self):
        self.assertEqual(net_memory.parse_ps(PS), {11916: 167312, 25484: 2640})
        self.assertEqual(net_memory.parse_ps("ps: no such process\n"), {})

    def test_footprint_takes_each_process_once_and_not_the_summary(self):
        self.assertEqual(net_memory.parse_footprint(FOOTPRINT),
                         {11916: 4356 * 1024, 25484: 1712})
        self.assertEqual(net_memory.parse_footprint(""), {})

    def test_a_sample_is_of_the_living(self):
        with mock.patch.object(net_memory, "_run", side_effect=[PS, FOOTPRINT]):
            self.assertEqual(net_memory.sample([11916, 25484, 7]),
                             {11916: (167312, 4356 * 1024), 25484: (2640, 1712)})
        self.assertEqual(net_memory.sample([]), {})

    def test_no_footprint_tool_leaves_the_resident_size(self):
        with mock.patch.object(net_memory, "_run", side_effect=[PS, ""]):
            self.assertEqual(net_memory.sample([11916])[11916], (167312, 0))


class MeterTest(unittest.TestCase):

    def test_the_peak_and_the_last(self):
        u = Usage()
        for resident, footprint in ((2 * GB, 3 * GB), (1 * GB, 4 * GB), (GB // 2, 4 * GB)):
            u.add(resident, footprint)
        self.assertEqual((u.peak_resident, u.peak_footprint), (2 * GB, 4 * GB))
        self.assertEqual((u.last_resident, u.last_footprint), (GB // 2, 4 * GB))

    def test_a_dead_process_is_not_sampled(self):
        running = [(Named("server"), FakeProc(1)), (Named("client 1"), FakeProc(2, code=3))]
        meter = Meter()
        with mock.patch.object(net_memory, "sample", return_value={1: (GB, 2 * GB)}) as s:
            meter.read(running)
        self.assertEqual(list(s.call_args[0][0]), [1])
        self.assertEqual(list(meter.usage), ["server"])
        self.assertEqual(meter.usage["server"].peak_footprint, 2 * GB)


class LinesTest(unittest.TestCase):

    def usage(self, footprint=True):
        out = {}
        for name, resident in (("server", 2 * GB), ("client 1", 3 * GB)):
            out[name] = Usage()
            out[name].add(resident, resident + GB if footprint else 0)
        return out

    def test_a_line_each_and_the_sum(self):
        lines = net_memory.lines(self.usage(), ["server", "client 1", "client 2"])
        self.assertEqual(len(lines), 3)
        self.assertIn("server", lines[0])
        self.assertIn("peak 3.0 GB footprint, 2.0 GB resident", lines[0])
        self.assertIn("7.0 GB", lines[2])
        self.assertIn("footprint", lines[2])

    def test_resident_alone_without_the_footprint_tool(self):
        lines = net_memory.lines(self.usage(footprint=False), ["server", "client 1"])
        self.assertIn("peak 2.0 GB resident", lines[0])
        self.assertNotIn("footprint", lines[0])
        self.assertIn("5.0 GB (the peaks' sum, resident)", lines[2])

    def test_nothing_sampled_nothing_said(self):
        self.assertEqual(net_memory.lines({}, ["server"]), [])

    def test_the_report_carries_them_and_they_fail_nothing(self):
        reports = [ProcessReport("server", "LogNet: Join succeeded: a\n"),
                   ProcessReport("client 1", "LogNet: Welcomed by server\n")]
        memory = net_memory.lines(self.usage(), ["server", "client 1"])
        lines, ok = net_report.report(reports, 1, (), memory)
        self.assertTrue(ok)
        self.assertEqual(lines[3:], memory)


if __name__ == "__main__":
    unittest.main()
