"""uebp.layout.columns: which column each node of a graph lands in."""

import unittest

import _paths  # noqa: F401

from uebp.layout import columns


class ColumnsTest(unittest.TestCase):
    def test_an_exec_chain_runs_left_to_right(self):
        successors = {"event": ["branch"], "branch": ["call"], "call": []}
        column, back = columns(["event", "branch", "call"], successors,
                               {"event", "branch", "call"})
        self.assertEqual(column, {"event": 0, "branch": 1, "call": 2})
        self.assertEqual(back, set())

    def test_a_pure_supplier_sits_one_column_left_of_its_consumer(self):
        successors = {"event": ["a"], "a": ["b"], "b": [], "getter": ["b"]}
        column, _ = columns(["event", "a", "b", "getter"], successors, {"event", "a", "b"})
        self.assertEqual(column["getter"], column["b"] - 1)

    def test_a_pure_chain_into_the_first_node_shifts_everything_right(self):
        successors = {"get": ["add"], "add": ["event_set"], "event_set": []}
        column, _ = columns(["get", "add", "event_set"], successors, {"event_set"})
        self.assertEqual(column, {"get": 0, "add": 1, "event_set": 2})

    def test_the_longest_path_wins(self):
        successors = {"event": ["a", "c"], "a": ["b"], "b": ["c"], "c": []}
        column, _ = columns(["event", "a", "b", "c"], successors, {"event", "a", "b", "c"})
        self.assertEqual(column["c"], 3)

    def test_an_exec_loop_is_broken_not_followed_forever(self):
        successors = {"event": ["delay"], "delay": ["work"], "work": ["delay"]}
        column, back = columns(["event", "delay", "work"], successors,
                               {"event", "delay", "work"})
        self.assertEqual(back, {("work", "delay")})
        self.assertEqual(column, {"event": 0, "delay": 1, "work": 2})

    def test_an_unwired_node_gets_a_column(self):
        column, _ = columns(["lonely"], {"lonely": []}, set())
        self.assertEqual(column, {"lonely": 0})


if __name__ == "__main__":
    unittest.main()
