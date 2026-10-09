import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401

from devteam import fast, gate
from devteam import limits as pacing
from devteam.accounting import describe_time, merge_results, token_usage
from devteam.session import (
    FAIL_MARK, Narrator, build_cmd, build_fix_prompt, build_prompt, fast_note,
    session_env,
)
from devteam import triage
from devteam.tasks import Task, parse_tasks, requeue, tick


class TasksTest(unittest.TestCase):

    def test_items_hints_and_continuations(self):
        tasks = parse_tasks("# queue\nintro text\n"
                            "- [ ] First task\n  more of it\n  effort: low\n"
                            "- [x] Done one\n"
                            "- [ ] Third\n  Model: sonnet\n")
        self.assertEqual([t.text for t in tasks], ["First task\nmore of it", "Done one", "Third"])
        self.assertEqual((tasks[0].effort, tasks[0].model), ("low", None))
        self.assertTrue(tasks[1].done)
        self.assertEqual(tasks[2].model, "sonnet")

    def test_a_hint_must_be_the_whole_line(self):
        (task,) = parse_tasks("- [ ] Tune it\n  effort: low means less work here\n")
        self.assertIsNone(task.effort)
        self.assertIn("effort: low means less work here", task.text)

    def test_tick_marks_only_that_task(self):
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "tasks.md")
            with open(path, "w") as fh:
                fh.write("- [ ] a\n- [ ] b\n  effort: low\n")
            with open(path) as fh:
                tasks = parse_tasks(fh.read())
            self.assertTrue(tick(path, tasks[1]))
            with open(path) as fh:
                self.assertEqual(fh.read(), "- [ ] a\n- [x] b\n  effort: low\n")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertFalse(tick(path, tasks[1]))   # nothing unticked to find
                self.assertFalse(tick(path + ".gone", tasks[0]))
        finally:
            shutil.rmtree(tmp)


class RequeueTest(unittest.TestCase):
    """The queue after the task file is read again, mid-run."""

    def test_an_added_task_joins_the_queue_in_file_order(self):
        (b,) = parse_tasks("- [ ] b\n")
        queue, added, dropped = requeue(
            [b], [], parse_tasks("- [x] a\n- [ ] new first\n- [ ] b\n- [ ] new last\n"))
        self.assertEqual([t.text for t in queue], ["new first", "b", "new last"])
        self.assertEqual([t.text for t in added], ["new first", "new last"])
        self.assertEqual(dropped, [])

    def test_nothing_new_leaves_the_queue_alone(self):
        waiting = parse_tasks("- [ ] b\n- [ ] c\n")
        queue, added, dropped = requeue(waiting, [], parse_tasks("- [x] a\n- [ ] b\n- [ ] c\n"))
        self.assertEqual([t.text for t in queue], ["b", "c"])
        self.assertEqual((added, dropped), ([], []))

    def test_a_waiting_task_ticked_or_deleted_is_dropped(self):
        waiting = parse_tasks("- [ ] b\n- [ ] c\n- [ ] d\n")
        queue, added, dropped = requeue(waiting, [], parse_tasks("- [x] b\n- [ ] d\n"))
        self.assertEqual([t.text for t in queue], ["d"])
        self.assertEqual(added, [])
        self.assertEqual([t.text for t in dropped], ["b", "c"])

    def test_a_failed_task_is_not_queued_again(self):
        (failed,) = parse_tasks("- [ ] a\n")
        queue, added, _dropped = requeue([], [failed], parse_tasks("- [ ] a\n- [ ] b\n"))
        self.assertEqual([t.text for t in queue], ["b"])
        self.assertEqual([t.text for t in added], ["b"])

    def test_a_second_copy_of_a_failed_task_is_new_work(self):
        (failed,) = parse_tasks("- [ ] a\n")
        queue, added, _dropped = requeue([], [failed], parse_tasks("- [ ] a\n- [ ] a\n"))
        self.assertEqual([t.text for t in queue], ["a"])
        self.assertEqual(len(added), 1)

    def test_a_waiting_task_keeps_its_triage_unless_the_file_has_a_hint(self):
        waiting = parse_tasks("- [ ] b\n- [ ] c\n")
        for t in waiting:
            t.effort, t.triage = "low", "one constant"
        queue, _added, _dropped = requeue(
            waiting, [], parse_tasks("- [ ] b\n- [ ] c\n  effort: high\n"))
        self.assertEqual([(t.effort, t.triage) for t in queue],
                         [("low", "one constant"), ("high", None)])

    def test_the_queue_carries_the_file_s_new_line_numbers(self):
        (b,) = parse_tasks("- [ ] b\n")
        queue, _added, _dropped = requeue([b], [], parse_tasks("# queue\n\n- [ ] new\n- [ ] b\n"))
        self.assertEqual([t.line for t in queue], [2, 3])


def load_cli():
    """Scripts/dev/dev-team as a module (it has no .py to import it by)."""
    path = os.path.join(_paths.DEV, "dev-team")
    loader = importlib.machinery.SourceFileLoader("dev_team_cli", path)
    spec = importlib.util.spec_from_loader("dev_team_cli", loader)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.object(sys, "dont_write_bytecode", True):
        loader.exec_module(module)
    return module


class LoopTest(unittest.TestCase):
    """dev-team's own loop, with the session, the editors and git stubbed out."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.path = os.path.join(self.tmp, "tasks.md")
        self.cli = load_cli()
        self.ran = []

    def write(self, text, mode="w"):
        with open(self.path, mode) as fh:
            fh.write(text)

    def run_cli(self, during, *flags, fail=()):
        """Run the queue; ``during`` maps a task's text to what its session
        does to the task file while it works. Returns (exit code, output)."""
        def run_one(task, n, total, *_rest):
            self.ran.append((n, total, task.text))
            if task.text in during:
                during[task.text]()
            ok = task.text not in fail
            return ok, ["report" if ok else "FAILED: no"], {}, None, None

        out = io.StringIO()
        argv = ["dev-team", "-t", self.path, "--no-triage", "--no-gate", *flags]
        with mock.patch.multiple(self.cli, run_one=run_one, close_editors=lambda: True,
                                 git_head=lambda root: None,
                                 LOG_ROOT=os.path.join(self.tmp, "logs")), \
                mock.patch.object(self.cli.server, "stop", lambda serve_dir: False), \
                mock.patch.object(sys, "argv", argv), \
                contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as stop:
            self.cli.main()
        return stop.exception.code, out.getvalue()

    def test_a_task_added_during_the_last_task_is_run(self):
        self.write("- [ ] a\n")
        code, out = self.run_cli({"a": lambda: self.write("- [ ] b\n  more\n", "a")})
        self.assertEqual(self.ran, [(1, 1, "a"), (2, 2, "b\nmore")])
        self.assertEqual(code, 0)
        self.assertIn("1 new task(s) in tasks.md", out)
        with open(self.path) as fh:
            self.assertEqual(fh.read(), "- [x] a\n- [x] b\n  more\n")

    def test_the_total_grows_and_the_file_s_order_is_kept(self):
        self.write("- [ ] a\n- [ ] c\n")
        self.run_cli({"a": lambda: self.write("- [ ] a\n- [ ] b\n- [ ] c\n")})
        self.assertEqual(self.ran, [(1, 2, "a"), (2, 3, "b"), (3, 3, "c")])

    def test_a_waiting_task_deleted_from_the_file_is_not_run(self):
        self.write("- [ ] a\n- [ ] b\n")
        code, out = self.run_cli({"a": lambda: self.write("- [ ] a\n")})
        self.assertEqual(self.ran, [(1, 2, "a")])
        self.assertEqual(code, 0)
        self.assertIn("so not run: b", out)

    def test_a_failed_task_is_not_picked_up_again(self):
        self.write("- [ ] a\n- [ ] b\n")
        code, _out = self.run_cli({}, "--keep-going", fail=("a",))
        self.assertEqual([text for _n, _total, text in self.ran], ["a", "b"])
        self.assertEqual(code, 1)
        with open(self.path) as fh:
            self.assertEqual(fh.read(), "- [ ] a\n- [x] b\n")

    def test_a_failure_stops_the_run_before_the_file_is_read_again(self):
        self.write("- [ ] a\n")
        code, out = self.run_cli({"a": lambda: self.write("- [ ] b\n", "a")}, fail=("a",))
        self.assertEqual(len(self.ran), 1)
        self.assertEqual(code, 1)
        self.assertNotIn("new task(s)", out)

    def test_a_task_file_that_goes_away_keeps_the_queue(self):
        self.write("- [ ] a\n- [ ] b\n")
        gone = []

        def remove():
            if not gone:
                gone.append(os.rename(self.path, self.path + ".gone"))
        _code, out = self.run_cli({"a": remove, "b": remove})
        self.assertEqual([text for _n, _total, text in self.ran], ["a", "b"])
        self.assertIn("keeping the queue as it was", out)


def row(label, passed, failed, failures=()):
    return {"label": label, "passed": passed, "failed": failed, "ok": failed == 0,
            "failures": list(failures), "tracebacks": [], "errors": []}


class GateTest(unittest.TestCase):

    def test_targets_skip_the_retired_level_verifier(self):
        tmp = tempfile.mkdtemp()
        try:
            for rel in ("Scripts/verify_a.py", "Scripts/verify_level.py",
                        "Scripts/generated_levels/L1/verify_L1.py", "Scripts/build_a.py"):
                os.makedirs(os.path.dirname(os.path.join(tmp, rel)), exist_ok=True)
                open(os.path.join(tmp, rel), "w").close()
            names = [os.path.basename(p) for p in gate.sweep_targets(tmp)]
            self.assertEqual(names, ["verify_a.py", "verify_L1.py"])
        finally:
            shutil.rmtree(tmp)

    def test_nothing_changed(self):
        before = {"a": row("a", 10, 0)}
        self.assertEqual(gate.regressions(before, {"a": row("a", 12, 0)}), [])

    def test_a_new_failure_is_a_regression(self):
        problems = gate.regressions({"a": row("a", 10, 0)},
                                    {"a": row("a", 9, 1, ["heal gated — ['']"])})
        self.assertEqual(len(problems), 1)
        self.assertIn("a: 9/10 FAILED (was 10/10)", problems[0])
        self.assertIn("heal gated", problems[0])

    def test_a_failure_that_was_already_there_is_not(self):
        before = {"a": row("a", 9, 1)}
        self.assertEqual(gate.regressions(before, {"a": row("a", 9, 1)}), [])
        self.assertEqual(len(gate.regressions(before, {"a": row("a", 8, 2)})), 1)

    def test_a_suite_that_stops_reporting(self):
        problems = gate.regressions({"a": row("a", 1, 0)}, {})
        self.assertIn("did not report", problems[0])

    def test_a_new_failing_suite(self):
        problems = gate.regressions({}, {"b": row("b", 0, 1)})
        self.assertIn("(new)", problems[0])

    def test_a_broken_sweep(self):
        self.assertIn("failed to run", gate.regressions({"a": row("a", 1, 0)}, None)[0])

    def test_no_baseline_still_judges_the_after_sweep(self):
        self.assertEqual(gate.regressions(None, {"a": row("a", 1, 0)}), [])

    def test_tables(self):
        before, after = {"a": row("a", 10, 0)}, {"a": row("a", 11, 1)}
        self.assertIn("| a | 10/10 |", gate.table(before))
        self.assertIn("| a | 10/10 | 11/12 FAILED |", gate.table(before, after))


class SessionTest(unittest.TestCase):

    def test_first_task_is_not_pointed_at_an_empty_progress_file(self):
        prompt = build_prompt(Task("Do X"), 1, 2, "/run/progress.md", "| t |", True)
        self.assertNotIn("/run/progress.md", prompt)
        self.assertIn("Do X", prompt)
        self.assertIn("| t |", prompt)
        self.assertIn("Issues encountered", prompt)

    def test_later_tasks_are(self):
        prompt = build_prompt(Task("Do Y"), 2, 2, "/run/progress.md", "| t |", False)
        self.assertIn("/run/progress.md", prompt)
        self.assertNotIn("Issues encountered", prompt)

    def test_a_broken_baseline_says_so(self):
        prompt = build_prompt(Task("Do X"), 1, 1, "/p", None, True)
        self.assertIn("could not get a baseline", prompt)

    def test_fix_prompt(self):
        prompt = build_fix_prompt(["a: 9/10"], "| a |", True)
        self.assertIn("- a: 9/10", prompt)
        self.assertIn("a new commit", prompt)
        self.assertIn(FAIL_MARK, prompt)

    def test_cmd_drops_mcp_and_passes_hints(self):
        cmd = build_cmd("go", "auto", name="n", model="opus", effort="low", budget=3)
        self.assertIn("--strict-mcp-config", cmd)
        self.assertEqual(cmd[cmd.index("--effort") + 1], "low")
        self.assertEqual(cmd[cmd.index("--model") + 1], "opus")
        self.assertEqual(cmd[cmd.index("--max-budget-usd") + 1], "3")
        self.assertIn("--name", cmd)

    def test_resume_replaces_the_name(self):
        cmd = build_cmd("fix", "auto", name="n", resume="abc")
        self.assertEqual(cmd[cmd.index("--resume") + 1], "abc")
        self.assertNotIn("--name", cmd)

    def test_session_env(self):
        env = session_env({"PATH": "/bin", "UEPY_COLD": "1"}, "/p/Saved/uepy/devteam")
        self.assertEqual((env["UEPY_SERVE"], env["UEPY_OUTPUT"]),
                         ("/p/Saved/uepy/devteam", "summary"))
        self.assertNotIn("UEPY_COLD", env)          # it would bypass the warm editor
        self.assertEqual(env["ENABLE_CLAUDEAI_MCP_SERVERS"], "false")
        self.assertEqual(env["PATH"], "/bin")

    def test_cmd_allows_the_everyday_commands(self):
        cmd = build_cmd("go", "auto")
        allow = json.loads(cmd[cmd.index("--settings") + 1])["permissions"]["allow"]
        for rule in ("Bash(cd *)", "Bash(sed -n *)", "Bash(grep *)", "Bash(git log *)",
                     "Bash(python3 Scripts/dev/uepy.py *)"):
            self.assertIn(rule, allow)
        self.assertFalse([r for r in allow if r in ("Bash", "Bash(*)", "Bash(python3 *)")])
        self.assertEqual(cmd[cmd.index("--permission-mode") + 1], "auto")

    def test_cmd_asks_for_fast_mode_only_when_told(self):
        def settings(cmd):
            return json.loads(cmd[cmd.index("--settings") + 1])
        self.assertNotIn("fastMode", settings(build_cmd("go", "auto")))
        fast_cmd = settings(build_cmd("go", "auto", resume="abc", fast=True))
        self.assertIs(fast_cmd["fastMode"], True)
        self.assertIn("Bash(cd *)", fast_cmd["permissions"]["allow"])

    def test_fast_note_speaks_only_when_fast_mode_was_asked_for(self):
        self.assertEqual(fast_note({"fast_mode_state": "on"}), "fast mode on")
        self.assertEqual(fast_note({"fast_mode_state": "off",
                                    "fast_mode_disabled_reason": "sdk_opt_in_required"}), "")
        self.assertEqual(fast_note({"fast_mode_state": "off",
                                    "fast_mode_disabled_reason": "extra_usage_disabled"}),
                         "fast mode off: extra_usage_disabled")
        self.assertEqual(fast_note({}), "")

    def test_prompt_describes_the_warm_editor(self):
        prompt = build_prompt(Task("Do X"), 1, 1, "/p", "| t |", True)
        self.assertIn("UEPY_SERVE", prompt)
        self.assertNotIn("UEPY_COLD=1", prompt)

    def test_prompt_forbids_background_runs(self):
        prompt = build_prompt(Task("Do X"), 1, 1, "/p", "| t |", True)
        self.assertIn("never run_in_background", prompt)
        self.assertIn("--probe A --probe B", prompt)

    def test_follow_up_prompts(self):
        from devteam.session import build_limit_resumed_prompt, build_uncommitted_prompt
        self.assertIn("commit as asked", build_limit_resumed_prompt(True))
        self.assertNotIn("commit as asked", build_limit_resumed_prompt(False))
        self.assertIn(FAIL_MARK, build_limit_resumed_prompt(False))
        prompt = build_uncommitted_prompt()
        self.assertIn("without a commit", prompt)
        self.assertIn("foreground", prompt)
        self.assertIn(FAIL_MARK, prompt)

    def test_narrator_strips_the_cd_prefix(self):
        root = "/Users/me/Unreal Projects/Otherworld"
        n = Narrator(root)
        self.assertEqual(n.describe({"name": "Bash", "input": {
            "command": f'cd "{root}/Scripts"; ls'}}), "Bash: [Scripts] ls")
        self.assertEqual(n.describe({"name": "Read", "input": {
            "file_path": f"{root}/CLAUDE.md"}}), "Read: CLAUDE.md")


def limits(used, resets):
    return {"status": "allowed", "unifiedWindows": {
        "five_hour": {"utilization": used, "resetsAt": resets},
        "seven_day": {"utilization": 0.9, "resetsAt": resets}}}


class FastTest(unittest.TestCase):

    def test_fast_while_the_session_limit_is_under_half(self):
        self.assertTrue(fast.Meter("auto", limits(0.49, 2000)).decide(1000)[0])
        on, why = fast.Meter("auto", limits(0.5, 2000)).decide(1000)
        self.assertFalse(on)
        self.assertIn("50%", why)

    def test_the_weekly_window_is_not_the_session_limit(self):
        self.assertEqual(fast.utilization(limits(0.2, 2000), 1000), 0.2)

    def test_a_reading_from_a_window_that_has_reset_is_an_empty_window(self):
        self.assertEqual(fast.utilization(limits(0.8, 900), 1000), 0.0)
        self.assertTrue(fast.Meter("auto", limits(0.8, 900)).decide(1000)[0])

    def test_no_reading_runs_at_standard_speed(self):
        for info in (None, {}, {"unifiedWindows": {"seven_day": {"utilization": 0.1}}}):
            self.assertIsNone(fast.utilization(info, 1000))
            self.assertFalse(fast.Meter("auto", info).decide(1000)[0])

    def test_on_and_off_override_the_rule(self):
        self.assertTrue(fast.Meter("on", limits(0.9, 2000)).decide(1000)[0])
        self.assertFalse(fast.Meter("off", limits(0.1, 2000)).decide(1000)[0])

    def test_a_session_updates_the_reading(self):
        meter = fast.Meter("auto", limits(0.1, 2000))
        meter.see(limits(0.6, 2000))
        meter.see(None)                              # an event with nothing in it
        self.assertFalse(meter.decide(1000)[0])

    def test_last_seen_reads_the_newest_transcript(self):
        tmp = tempfile.mkdtemp()
        try:
            for stamp, used, age in (("20260101-000000", 0.7, 100), ("20260102-000000", 0.3, 0)):
                os.makedirs(os.path.join(tmp, stamp))
                path = os.path.join(tmp, stamp, "task-01.jsonl")
                with open(path, "w") as fh:
                    fh.write(json.dumps({"type": "assistant"}) + "\nnot json\n")
                    for u in (0.01, used):
                        fh.write(json.dumps({"type": "rate_limit_event",
                                             "rate_limit_info": limits(u, 2000)}) + "\n")
                os.utime(path, (1000 - age, 1000 - age))
            self.assertEqual(fast.utilization(fast.last_seen(tmp), 1000), 0.3)
            self.assertIsNone(fast.last_seen(os.path.join(tmp, "nowhere")))
        finally:
            shutil.rmtree(tmp)


class FakeClock(object):
    """time.time and time.sleep for a wait, without the waiting."""

    def __init__(self, start):
        self.now, self.slept = start, []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


class FakePauser(object):
    def __init__(self, after=None):
        self.requested, self.after, self.ticks = False, after, 0

    @contextlib.contextmanager
    def watching(self, on_pause=None):
        yield self


class LimitsTest(unittest.TestCase):

    def wait(self, info, start, refused=False, pauser=None):
        clock, said = FakeClock(start), []
        waited = pacing.wait(fast.Meter("auto", info), pauser, refused=refused,
                             now=clock.time, sleep=clock.sleep, say=said.append)
        return waited, clock, said

    def test_room_means_no_wait(self):
        waited, clock, said = self.wait(limits(0.9, 2000), 1000)
        self.assertEqual((waited, clock.slept, said), (0, [], []))
        self.assertEqual(self.wait(None, 1000)[0], 0)

    def test_a_spent_window_is_slept_through_to_its_reset(self):
        waited, clock, said = self.wait(limits(0.95, 2000), 1000)
        self.assertEqual(clock.now, 2000 + pacing.MARGIN)
        self.assertEqual(waited, 1000 + pacing.MARGIN)
        self.assertTrue(all(s <= pacing.TICK for s in clock.slept))
        self.assertIn("session limit at 95%", said[0])
        self.assertIn("has reset", said[-1])

    def test_a_reading_from_a_window_that_has_reset_is_room(self):
        self.assertEqual(self.wait(limits(1.0, 900), 1000)[0], 0)

    def test_a_refused_session_waits_for_the_reset_it_was_told(self):
        info = {"status": "rejected", "resetsAt": 1500, "rateLimitType": "five_hour",
                "unifiedWindows": {"five_hour": {"utilization": 1, "resetsAt": 1500}}}
        waited, clock, _said = self.wait(info, 1000, refused=True)
        self.assertEqual(clock.now, 1500 + pacing.MARGIN)

    def test_a_refused_session_with_no_reset_time_waits_the_fallback(self):
        waited, clock, said = self.wait(limits(0.3, 900), 1000, refused=True)
        self.assertEqual(waited, pacing.FALLBACK)
        self.assertIn("no reset time", said[0])

    def test_a_typed_pause_ends_the_wait(self):
        pauser = FakePauser()
        clock, said = FakeClock(1000), []

        def sleep(seconds):
            clock.sleep(seconds)
            pauser.requested = True
        pacing.wait(fast.Meter("auto", limits(0.99, 5000)), pauser,
                    now=clock.time, sleep=sleep, say=said.append)
        self.assertEqual(len(clock.slept), 1)
        self.assertFalse([s for s in said if "has reset" in s])

    def test_limited_recognises_the_session_limit_result(self):
        self.assertTrue(pacing.limited({"is_error": True, "api_error_status": 429,
                                        "result": "You've hit your session limit"}))
        self.assertTrue(pacing.limited({"is_error": True,
                                        "result": "You've hit your session limit · resets 11:50pm"}))
        self.assertFalse(pacing.limited({"is_error": True, "result": "FAILED: no"}))
        self.assertFalse(pacing.limited({"is_error": False, "api_error_status": 429}))
        self.assertFalse(pacing.limited({}))
        self.assertFalse(pacing.limited(None))

    def test_reset_at_prefers_the_event_s_own_window(self):
        self.assertEqual(pacing.reset_at({"resetsAt": 10, "unifiedWindows": {
            "five_hour": {"resetsAt": 20}}}), 10)
        self.assertEqual(pacing.reset_at(limits(0.1, 20)), 20)
        self.assertIsNone(pacing.reset_at({}))
        self.assertIsNone(pacing.reset_at(None))


class TriageTest(unittest.TestCase):

    def test_prompt_numbers_every_task(self):
        prompt = triage.build_prompt([Task("Raise X"), Task("Add Y\nwith Z")])
        self.assertIn("1. Raise X", prompt)
        self.assertIn("2. Add Y\nwith Z", prompt)

    def test_cmd_has_no_tools(self):
        cmd = triage.build_cmd("p")
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")
        self.assertEqual(cmd[cmd.index("--model") + 1], "haiku")
        self.assertIn("--strict-mcp-config", cmd)

    def test_parse_keeps_only_low(self):
        text = ('Sure:\n{"tasks": [{"n": 1, "effort": "low", "why": "one  constant"},'
                ' {"n": 2, "effort": "default", "why": "new UI"},'
                ' {"n": 3, "effort": "high", "why": "x"}, {"n": 9, "effort": "low"}]}')
        self.assertEqual(triage.parse(text, 3), {1: ("low", "one constant")})

    def test_parse_survives_junk(self):
        self.assertEqual(triage.parse("no json here", 2), {})
        self.assertEqual(triage.parse('{"tasks": [1, {"n": "1", "effort": "low"}]}', 2), {})
        self.assertEqual(triage.parse(None, 2), {})

    def fake(self, stdout, returncode=0):
        class P(object):
            pass
        p = P()
        p.stdout, p.returncode = stdout, returncode
        return lambda *a, **k: p

    def test_triage_sets_effort_and_reason(self):
        tasks = [Task("Raise X"), Task("Add Y")]
        answer = json.dumps({"total_cost_usd": 0.01, "is_error": False, "result":
                             '{"tasks": [{"n": 2, "effort": "low", "why": "tuning"}]}'})
        cost, error = triage.triage(tasks, "/p", run=self.fake(answer))
        self.assertEqual((cost, error), (0.01, None))
        self.assertEqual([(t.effort, t.triage) for t in tasks],
                         [(None, None), ("low", "tuning")])

    def test_a_failed_call_changes_nothing(self):
        tasks = [Task("Raise X")]
        _cost, error = triage.triage(tasks, "/p", run=self.fake("not json", 1))
        self.assertIn("failed", error)
        self.assertIsNone(tasks[0].effort)
        answer = json.dumps({"is_error": True, "result": "rate limited"})
        _cost, error = triage.triage(tasks, "/p", run=self.fake(answer))
        self.assertIn("rate limited", error)
        self.assertIsNone(tasks[0].effort)


class AccountingTest(unittest.TestCase):

    def test_merge_adds_costs_times_and_models(self):
        a = {"total_cost_usd": 1.0, "duration_ms": 1000, "session_id": "s",
             "modelUsage": {"m": {"inputTokens": 1, "outputTokens": 2,
                                  "cacheReadInputTokens": 3, "cacheCreationInputTokens": 4}}}
        b = {"total_cost_usd": 0.5, "duration_ms": 500, "session_id": "s", "result": "fixed",
             "modelUsage": {"m": {"inputTokens": 1, "outputTokens": 1,
                                  "cacheReadInputTokens": 1, "cacheCreationInputTokens": 1}}}
        m = merge_results(a, b)
        self.assertEqual((m["total_cost_usd"], m["duration_ms"]), (1.5, 1500))
        self.assertEqual(m["result"], "fixed")
        self.assertEqual(token_usage(m)["total"], 14)

    def test_merge_into_nothing(self):
        self.assertEqual(merge_results({}, {"x": 1}), {"x": 1})

    def test_describe_time(self):
        self.assertEqual(describe_time(1206031), "20m 06s")
        self.assertEqual(describe_time(3_700_000), "1h 01m 40s")


if __name__ == "__main__":
    unittest.main()


class KnownFailuresTest(unittest.TestCase):

    def test_parse(self):
        rows = gate.parse_known("# c\n\na.py | pose x | since 2026-01-02 | why | more\nbad\n")
        self.assertEqual(rows, [{"target": "a.py", "check": "pose x",
                                 "since": "2026-01-02", "why": "why | more"}])

    def test_shipped_file_parses(self):
        self.assertEqual(len(gate.load_known()), 0)

    def test_listed_check_is_not_a_regression(self):
        known = gate.parse_known("a | pose x | since d | w")
        after = {"a": row("a", 9, 1, ["pose x is off"])}
        self.assertEqual(gate.regressions({"a": row("a", 10, 0)}, after, known), [])
        self.assertEqual(len(gate.regressions({"a": row("a", 10, 0)}, after)), 1)
        mixed = {"a": row("a", 8, 2, ["pose x is off", "other"])}
        self.assertEqual(len(gate.regressions({"a": row("a", 10, 0)}, mixed, known)), 1)

    def test_known_report(self):
        known = gate.parse_known("a | pose x | since d | w\nb | y | since d | w")
        standing, fixed = gate.known_report(
            known, {"a": row("a", 9, 1, ["pose x"]), "b": row("b", 5, 0)})
        self.assertEqual(len(standing), 1)
        self.assertIn("remove the line", fixed[0])

    def test_prompt_names_the_rule(self):
        task = mock.Mock(text="t")
        self.assertIn("known_failures.md",
                      build_prompt(task, 1, 1, "/p", "| t |", False))
        self.assertIn("known_failures.md", build_prompt(task, 1, 1, "/p", None, False))
