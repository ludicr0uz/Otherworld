"""devteam/timing.py and devteam/tasklog.py: where a task's time went, and the
spreadsheet row and printout made of it."""

import csv
import json
import os
import shutil
import tempfile
import unittest

import _paths  # noqa: F401

from devteam import tasklog, timing
from devteam.session import build_system
from devteam.tasks import Task


def stamp(seconds):
    return f"2026-10-13T17:{seconds // 60:02d}:{seconds % 60:02d}.000Z"


def call(at, ident, name="Bash", command=""):
    return {"type": "assistant", "timestamp": stamp(at), "message": {"content": [
        {"type": "tool_use", "id": ident, "name": name, "input": {"command": command}}]}}


def result(at, ident):
    return {"type": "user", "timestamp": stamp(at), "message": {"content": [
        {"type": "tool_result", "tool_use_id": ident}]}}


RESULT = {
    "session_id": "abc", "num_turns": 7, "total_cost_usd": 3.0, "duration_ms": 600000,
    "modelUsage": {"claude-opus-5-5": {
        "inputTokens": 1000, "outputTokens": 2000, "cacheReadInputTokens": 100000,
        "cacheCreationInputTokens": 5000, "costUSD": 3.0}},
}
REPORT = """The campfire is in and committed.

Verified by verify_camp.py.

Summary:
A campfire now warms the player within 5 m.
It burns for three minutes.
Decisions:
- Warmth falls off linearly: the task named no curve.
**Challenges:**
- The timer did not replicate; moved it to the game state."""


class StageOfTest(unittest.TestCase):

    def test_a_command_is_the_slowest_thing_it_holds(self):
        uepy = "cd /p && python3 Scripts/dev/uepy.py "
        for command, stage in (
                (uepy + "Scripts/build_x.py", "editor scripts"),
                (uepy + "--verify-for", "verifiers"),
                (uepy + "Scripts/verify_x.py", "verifiers"),
                (uepy + "--game --probe p.py --verify-for", "game probes"),
                (uepy + "--wait Saved/run --timeout 900", "game probes"),
                (uepy + "--net --clients 2 --probe p.py", "multiplayer probes"),
                (uepy + "--compile", "C++ compile"),
                ("python3 -m unittest discover -s Scripts/dev/tests", "unit tests"),
                ("git add -A && git commit -m x", "commit"),
                ("git -C /p commit -m x", "commit"),
                ("until grep -q done f; do sleep 5; done", "waiting"),
                ("sed -n 1,40p a.py; grep -n commit b.py", "reading and editing")):
            self.assertEqual(timing.stage_of("Bash", command), stage, command)

    def test_other_tools(self):
        self.assertEqual(timing.stage_of("Edit"), "reading and editing")
        self.assertEqual(timing.stage_of("Task"), "subagents")
        self.assertEqual(timing.stage_of("WebSearch"), "other tools")

    def test_every_stage_named_is_a_column(self):
        for name in ("Read", "Task", "WebFetch"):
            self.assertIn(timing.stage_of(name), timing.STAGES)


class ClockTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.log = os.path.join(self.tmp, "task-01.jsonl")

    def write(self, *events):
        with open(self.log, "w") as fh:
            fh.write("not json\n")
            for event in events:
                fh.write(json.dumps(event) + "\n")

    def test_a_call_runs_from_its_message_to_its_result(self):
        self.write(call(0, "a", command="python3 Scripts/dev/uepy.py --verify-for"),
                   result(90, "a"),
                   call(100, "b", name="Read"), result(101, "b"),
                   {"type": "system", "subtype": "compact_boundary",
                    "compact_metadata": {"duration_ms": 75000}})
        self.assertEqual(timing.tool_time(self.log),
                         {"verifiers": 90.0, "reading and editing": 1.0, "compaction": 75.0})

    def test_calls_side_by_side_are_not_counted_twice(self):
        self.write(call(0, "a", name="Read"), call(0, "b", name="WebSearch"),
                   result(10, "a"), result(30, "b"))
        self.assertEqual(timing.tool_time(self.log),
                         {"reading and editing": 10.0, "other tools": 20.0})

    def test_a_subagent_s_own_calls_are_the_task_call_s(self):
        inner = dict(call(5, "x", name="Read"), parent_tool_use_id="a")
        self.write(call(0, "a", name="Task"), inner, result(60, "a"))
        self.assertEqual(timing.tool_time(self.log), {"subagents": 60.0})

    def test_no_transcript_is_no_tool_time(self):
        self.assertEqual(timing.tool_time(os.path.join(self.tmp, "none.jsonl")), {})

    def test_the_model_has_what_the_tools_did_not(self):
        stages = timing.breakdown({"session": 600, "after sweeps": 147, "limit wait": 0.01},
                                  {"verifiers": 90.0, "compaction": 75.0, "odd": 35.0})
        self.assertEqual(stages, {"model": 400.0, "verifiers": 90.0, "other tools": 35.0,
                                  "compaction": 75.0, "after sweeps": 147})
        self.assertEqual(timing.total(stages), 747.0)
        self.assertEqual(list(stages), [s for s in timing.STAGES if s in stages])

    def test_with_no_session_on_the_clock_the_result_s_time_is_used(self):
        self.assertEqual(timing.breakdown({}, {"commit": 10.0}, 60000),
                         {"model": 50.0, "commit": 10.0})

    def test_describe_is_longest_first_with_shares(self):
        self.assertEqual(timing.describe({"model": 30.0, "verifiers": 90.0}),
                         "verifiers 1m 30s (75%), model 0m 30s (25%)")

    def test_the_clock_is_kept_across_a_pause(self):
        path = timing.path(self.tmp, 1)
        first = timing.Stages(path, resume=False)
        first.begin()
        timing.spend(first, "session", 100)
        with timing.timed(first, "limit wait"):
            pass
        first["baseline"] = "cached"                 # the gate table's side of it
        again = timing.Stages(path)                  # the resumed half
        again.begin()
        timing.spend(again, "session", 50)
        timing.spend(again, "after sweeps", 20)
        closing = timing.Stages(path)                # the write-up
        closing.finish(now=closing.began + 100)
        self.assertEqual(closing.spent["session"], 150)
        self.assertAlmostEqual(closing.spent[timing.OWN], 30, places=3)
        self.assertEqual(closing.started, first.started)
        self.assertEqual(dict(again), {})

    def test_a_new_task_does_not_take_up_an_old_clock(self):
        path = timing.path(self.tmp, 1)
        timing.Stages(path).add("session", 100)
        self.assertEqual(timing.Stages(path, resume=False).spent, {})

    def test_a_plain_dict_keeps_no_clock(self):
        plain = {}
        timing.spend(plain, "session", 5)
        self.assertEqual(plain, {})


class RecordTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.run_dir = os.path.join(self.tmp, "20261013-120000")
        os.makedirs(self.run_dir)

    def record(self, reports=(REPORT,), **more):
        stages = {"model": 400.0, "verifiers": 200.0, "after sweeps": 147.0}
        return tasklog.build(Task("Add a campfire.\nIt burns 3 minutes."), 2, "done",
                             "low (triage: one constant)", "claude-opus-5-5", RESULT,
                             stages, list(reports), commits="aaa..bbb", run="r", **more)

    def test_the_report_s_sections_are_read(self):
        said = tasklog.sections([REPORT])
        self.assertEqual(said["summary"], "A campfire now warms the player within 5 m.\n"
                                          "It burns for three minutes.")
        self.assertEqual(said["decisions"],
                         "- Warmth falls off linearly: the task named no curve.")
        self.assertEqual(said["challenges"],
                         "- The timer did not replicate; moved it to the game state.")

    def test_headings_may_be_markdown_or_hold_their_text(self):
        said = tasklog.sections(["## Summary\nDone.\n\n### Decisions:\nnone\nChallenges: none"])
        self.assertEqual(said, {"summary": "Done.", "decisions": "none", "challenges": "none"})

    def test_a_sentence_that_starts_with_the_word_is_no_heading(self):
        self.assertEqual(tasklog.sections(["Decisions were hard here."])["decisions"], "")

    def test_a_fix_session_s_sections_follow_the_first_s(self):
        said = tasklog.sections([REPORT, "", "Fixed.\nChallenges:\n- The gate regressed."])
        self.assertTrue(said["challenges"].endswith(
            "game state.\n\n- The gate regressed."), said["challenges"])

    def test_the_system_prompt_asks_for_the_sections(self):
        prompt = build_system(True)
        for name in tasklog.SECTIONS:
            self.assertIn(f"\n{name.capitalize()}:\n", prompt)

    def test_a_report_without_sections_still_fills_the_row(self):
        messages = ("Camp: a fire\n\nBody.\n\nIssues encountered:\n- The timer did not "
                    "replicate.\n  Moved it.\n\nCo-Authored-By: X <x@y>\nTime: 3m 00s\n")
        record = self.record(reports=["The campfire is in.\nSecond line.\n\nMore."],
                             messages=messages)
        self.assertEqual(record["summary"], "The campfire is in. Second line.")
        self.assertEqual(record["decisions"], "")
        self.assertEqual(record["challenges"], "- The timer did not replicate.\n  Moved it.")

    def test_issues_none_on_the_heading_s_line(self):
        self.assertEqual(tasklog.issues("x\n\nIssues encountered: none\n\nTime: 1m"), "none")

    def test_the_cost_is_shared_out_by_price_and_adds_up(self):
        split = tasklog.cost_split(RESULT)
        self.assertAlmostEqual(sum(split.values()), 3.0)
        # 1000*4 : 2000*20 : 100000*0.2 : 5000*8 = 4 : 40 : 20 : 40
        self.assertAlmostEqual(split["input"], 3.0 * 4 / 104)
        self.assertAlmostEqual(split["cache_read"], 3.0 * 20 / 104)
        self.assertAlmostEqual(split["output"], split["cache_write"])

    def test_a_result_with_no_models_is_shared_out_too(self):
        split = tasklog.cost_split({"total_cost_usd": 1.0, "usage": {"output_tokens": 10}})
        self.assertAlmostEqual(split["output"], 1.0)
        self.assertEqual(sum(tasklog.cost_split({}).values()), 0.0)

    def test_the_row_has_every_column(self):
        cells = dict(zip(tasklog.COLUMNS, tasklog.row(self.record())))
        self.assertEqual(len(cells), len(tasklog.COLUMNS))
        self.assertEqual(cells["task"], "Add a campfire.")
        self.assertEqual(cells["effort"], "low (triage: one constant)")
        self.assertEqual(cells["total (min)"], "12.45")
        self.assertEqual(cells["model (min)"], "6.67")
        self.assertEqual(cells["game probes (min)"], "")
        self.assertEqual((cells["tokens"], cells["cache read tokens"]), (108000, 100000))
        self.assertEqual(cells["cost ($)"], "3.00")
        self.assertEqual(cells["output ($)"], "1.15")
        self.assertIn("linearly", cells["decisions"])

    def test_rows_are_appended_under_one_header(self):
        path = tasklog.append(self.tmp, self.record())
        tasklog.append(self.tmp, self.record())
        with open(path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(rows[0], tasklog.COLUMNS)
        self.assertEqual(len(rows), 3)
        self.assertIn("\n", rows[1][tasklog.COLUMNS.index("summary")])

    def test_a_log_with_other_columns_is_set_aside(self):
        path = os.path.join(self.tmp, tasklog.NAME)
        with open(path, "w") as fh:
            fh.write("date,task\n2026-10-01,old\n")
        tasklog.append(self.tmp, self.record())
        with open(path, newline="", encoding="utf-8-sig") as fh:
            self.assertEqual(len(list(csv.reader(fh))), 2)
        kept = [f for f in os.listdir(self.tmp) if f.startswith("task_log-")]
        self.assertEqual(len(kept), 1)

    def test_a_task_is_written_up_from_its_run_directory(self):
        clock = timing.Stages(timing.path(self.run_dir, 2), resume=False)
        clock.begin()
        clock.add("session", 600)
        clock.add("after sweeps", 147)
        with open(os.path.join(self.run_dir, "task-02.jsonl"), "w") as fh:
            for event in (call(0, "a", command="python3 Scripts/dev/uepy.py --verify-for"),
                          result(200, "a")):
                fh.write(json.dumps(event) + "\n")
        task = Task("Add a campfire.")
        record = tasklog.record_task(task, 2, "done", "default", "m", RESULT, [REPORT],
                                     self.run_dir, self.tmp, None, None)
        self.assertIs(task.record, record)
        self.assertEqual(record["log"], os.path.join(self.tmp, tasklog.NAME))
        self.assertEqual(record["stages"]["model"], 400.0)
        self.assertEqual(record["stages"]["verifiers"], 200.0)
        self.assertEqual(record["run"], "20261013-120000")

    def test_the_printout_puts_time_cost_and_tokens_beside_each_task(self):
        done, paused, waiting = Task("Add a campfire."), Task("Paused one"), Task("Later")
        done.record = self.record()
        other = Task("Another")
        other.record = self.record()
        out = tasklog.printout([(done, "done"), (other, "FAILED"), (paused, "paused")],
                               [waiting])
        self.assertEqual(out[0], "         done  Add a campfire.  -- 12m 27s, $3.00, "
                                 "108,000 tokens")
        self.assertEqual(out[1].strip(), "time    model 6m 40s (54%), verifiers 3m 20s (27%), "
                                         "after sweeps 2m 27s (20%)")
        self.assertEqual(out[2].strip(), "tokens  input 1,000, output 2,000, "
                                         "cache read 100,000, cache write 5,000")
        self.assertEqual(out[3].strip(), "cost    input $0.12, output $1.15, "
                                         "cache read $0.58, cache write $1.15")
        self.assertEqual(out[8], "       paused  Paused one")
        self.assertEqual(out[9], "      not run  Later")
        self.assertEqual(out[10], "       in all  2 tasks  -- 24m 54s, $6.00, 216,000 tokens")
        self.assertEqual(len(out), 12)


if __name__ == "__main__":
    unittest.main()
