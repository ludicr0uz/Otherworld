import unittest

import _paths  # noqa: F401

from probes.context import Probe
from probes.runner import DETAIL_LIMIT, Ledger, ProbeRun, Queue


class Clock(object):

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def drive(run, game, wall, ticks=100, dt=0.1):
    """Tick until the run finishes, advancing both clocks by dt per tick."""
    for _ in range(ticks):
        if run.advance():
            return True
        game.t += dt
        wall.t += dt
    return False


class LedgerTest(unittest.TestCase):

    def test_check_records_and_returns_the_verdict(self):
        ledger = Ledger("p")
        self.assertTrue(ledger.check("a", 1, "one"))
        self.assertFalse(ledger.check("b", [], "none"))
        self.assertEqual(ledger.checks, [{"ok": True, "label": "a", "detail": "one"},
                                         {"ok": False, "label": "b", "detail": "none"}])
        self.assertFalse(ledger.passed)

    def test_long_details_are_cut(self):
        ledger = Ledger("p")
        ledger.check("a", True, "x" * 1000)
        self.assertEqual(len(ledger.checks[0]["detail"]), DETAIL_LIMIT)

    def test_an_error_fails_even_with_all_checks_passing(self):
        ledger = Ledger("p")
        ledger.check("a", True)
        ledger.error = "boom"
        self.assertFalse(ledger.passed)


class ProbeRunTest(unittest.TestCase):

    def setUp(self):
        self.game, self.wall = Clock(), Clock()
        self.ledger = Ledger("p")

    def run_of(self, fn, timeout=60.0):
        return ProbeRun(self.ledger, fn, self.game, self.wall, timeout)

    def test_waits_in_game_seconds(self):
        seen = []

        def probe():
            seen.append(self.game.t)
            yield 0.5
            seen.append(self.game.t)

        self.assertTrue(drive(self.run_of(probe), self.game, self.wall))
        self.assertEqual(seen[0], 0.0)
        self.assertGreaterEqual(seen[1], 0.5)
        self.assertLess(seen[1], 0.7)

    def test_game_time_not_wall_time(self):
        # A frozen game clock never ends a time wait, however long the wall runs.
        def probe():
            yield 1.0

        run = self.run_of(probe, timeout=5.0)
        for _ in range(100):
            if run.advance():
                break
            self.wall.t += 0.1
        self.assertIn("timed out after 5 s (waiting for 1.0 s)", self.ledger.error)

    def test_waits_for_a_condition(self):
        state = {"ready": False}

        def ready():
            return state["ready"]

        def probe():
            yield ready
            self.ledger.check("got there", True)

        run = self.run_of(probe)
        for _ in range(5):
            self.assertFalse(run.advance())
        state["ready"] = True
        self.assertTrue(drive(run, self.game, self.wall))
        self.assertTrue(self.ledger.passed)

    def test_a_condition_that_never_holds_times_out(self):
        def never():
            return False

        def probe():
            yield never

        self.assertTrue(drive(self.run_of(probe, timeout=2.0), self.game, self.wall))
        self.assertIn("waiting for never", self.ledger.error)

    def test_an_exception_is_the_probes_error(self):
        def probe():
            yield 0.1
            raise ValueError("no mushroom")

        self.assertTrue(drive(self.run_of(probe), self.game, self.wall))
        self.assertIn("ValueError: no mushroom", self.ledger.error)

    def test_a_plain_function_runs_once(self):
        calls = []
        run = self.run_of(lambda: calls.append(1))
        self.assertTrue(run.advance())
        self.assertEqual(calls, [1])
        self.assertIsNone(self.ledger.error)

    def test_a_bad_yield_is_an_error(self):
        def probe():
            yield "soon"

        self.assertTrue(drive(self.run_of(probe), self.game, self.wall))
        self.assertIn("may yield seconds or a callable", self.ledger.error)

    def test_bare_yield_waits_one_tick(self):
        steps = []

        def probe():
            steps.append(1)
            yield
            steps.append(2)

        run = self.run_of(probe)
        self.assertFalse(run.advance())
        self.assertEqual(steps, [1])
        self.assertTrue(run.advance())          # resumed on the next tick, then done
        self.assertEqual(steps, [1, 2])

    def test_yield_from_a_helper_returns_its_value(self):
        def helper():
            yield 0.2
            return 42

        def probe():
            value = yield from helper()
            self.ledger.check("value", value == 42, value)

        self.assertTrue(drive(self.run_of(probe), self.game, self.wall))
        self.assertTrue(self.ledger.passed)


class QueueTest(unittest.TestCase):

    def test_runs_in_order_and_collects_results(self):
        game, wall = Clock(), Clock()
        order = []

        def make(name):
            ledger = Ledger(name)

            def probe():
                order.append(name)
                yield 0.2
                ledger.check(f"{name} ran", True)
            return ProbeRun(ledger, probe, game, wall)

        queue = Queue([make("a"), make("b")])
        for _ in range(50):
            if queue.advance():
                break
            game.t += 0.1
            wall.t += 0.1
        self.assertTrue(queue.done)
        self.assertEqual(order, ["a", "b"])
        self.assertEqual([r["name"] for r in queue.results()], ["a", "b"])
        self.assertTrue(all(r["checks"][0]["ok"] for r in queue.results()))

    def test_empty_queue_is_done(self):
        self.assertTrue(Queue([]).advance())


class ProbeContextTest(unittest.TestCase):

    def test_checks_and_notes_go_to_the_ledger(self):
        ledger = Ledger("p")
        p = Probe(ledger, "/Game/Maps/L", lambda: 0.0)
        self.assertFalse(p.check("x", False, "why"))
        p.note("hello")
        self.assertEqual(ledger.as_dict()["checks"][0]["label"], "x")
        self.assertEqual(ledger.notes, ["hello"])


if __name__ == "__main__":
    unittest.main()
