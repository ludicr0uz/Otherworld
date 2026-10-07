import unittest

import _paths  # noqa: F401

from probes import bots
from probes.load_stats import connection_rows, kb, mean, percentile, summarize


def conn(name, **over):
    row = {"name": name, "player": "", "in_bytes": 0, "out_bytes": 0, "in_packets": 0,
           "out_packets": 0, "actor_channels": 0, "lag_ms": 0.0}
    row.update(over)
    return row


class StatsTest(unittest.TestCase):

    def test_percentile_is_nearest_rank(self):
        self.assertEqual(percentile(range(1, 101), 0.99), 99)
        self.assertEqual(percentile([3, 1, 2], 0.5), 2)
        self.assertEqual(percentile([7], 0.99), 7)
        self.assertEqual(percentile([], 0.99), 0.0)

    def test_summarize(self):
        self.assertEqual(summarize([1.0, 2.0, 3.0]), {"n": 3, "mean": 2.0, "p99": 3.0, "max": 3.0})
        self.assertEqual(summarize([]), {"n": 0, "mean": 0.0, "p99": 0.0, "max": 0.0})
        self.assertEqual(mean([]), 0.0)

    def test_connection_rows_are_rates_over_the_window(self):
        before = [conn("127.0.0.1:1", in_bytes=100, out_bytes=1000, in_packets=10, out_packets=100)]
        after = [conn("127.0.0.1:1", player="P", in_bytes=1000, out_bytes=91000, in_packets=100,
                      out_packets=1000, actor_channels=40, lag_ms=12.34),
                 conn("127.0.0.1:2", in_bytes=900, out_bytes=9000, actor_channels=3)]
        rows = connection_rows(before, after, 90.0)
        self.assertEqual(rows[0], {"name": "127.0.0.1:1", "player": "P", "in_bps": 10,
                                   "out_bps": 1000, "in_pps": 1.0, "out_pps": 10.0,
                                   "actor_channels": 40, "lag_ms": 12.3})
        # A connection first seen at the end is reported over its whole life.
        self.assertEqual((rows[1]["in_bps"], rows[1]["out_bps"]), (10, 100))
        self.assertEqual(connection_rows(before, after, 0.0)[0]["in_bps"], 0)

    def test_kb(self):
        self.assertEqual(kb(2048), "2.0 KB/s")


class BotsTest(unittest.TestCase):

    def test_count_reads_the_environment(self):
        self.assertEqual(bots.count({}), 0)
        self.assertEqual(bots.count({"UEPY_NET_BOTS": "32"}), 32)
        self.assertEqual(bots.count({"UEPY_NET_BOTS": "-3"}), 0)
        self.assertEqual(bots.count({"UEPY_NET_BOTS": "many"}), 0)
