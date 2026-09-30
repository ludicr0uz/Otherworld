import os
import shutil
import tempfile
import unittest

import _paths  # noqa: F401

from devteam import gate
from devteam.accounting import describe_time, merge_results, token_usage
from devteam.session import (
    FAIL_MARK, Narrator, build_cmd, build_fix_prompt, build_prompt, session_env,
)
from devteam.tasks import Task, parse_tasks, tick


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
            tick(path, tasks[1])
            with open(path) as fh:
                self.assertEqual(fh.read(), "- [ ] a\n- [x] b\n  effort: low\n")
        finally:
            shutil.rmtree(tmp)


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
        env = session_env({"PATH": "/bin"})
        self.assertEqual((env["UEPY_COLD"], env["UEPY_OUTPUT"]), ("1", "summary"))
        self.assertEqual(env["ENABLE_CLAUDEAI_MCP_SERVERS"], "false")
        self.assertEqual(env["PATH"], "/bin")

    def test_narrator_strips_the_cd_prefix(self):
        root = "/Users/me/Unreal Projects/Otherworld"
        n = Narrator(root)
        self.assertEqual(n.describe({"name": "Bash", "input": {
            "command": f'cd "{root}/Scripts"; ls'}}), "Bash: [Scripts] ls")
        self.assertEqual(n.describe({"name": "Read", "input": {
            "file_path": f"{root}/CLAUDE.md"}}), "Read: CLAUDE.md")


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
