import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import _paths  # noqa: F401

from devteam import brief


class BriefTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="a run ")     # the project's path has a space
        self.addCleanup(shutil.rmtree, self.tmp)
        self.brief, self.notes = brief.paths(self.tmp, 3)

    def test_paths_are_the_tasks_own(self):
        self.assertEqual((os.path.basename(self.brief), os.path.basename(self.notes)),
                         ("task-03-brief.md", "task-03-notes.md"))
        self.assertNotEqual(brief.paths(self.tmp, 4), (self.brief, self.notes))

    def test_every_prompt_is_kept_word_for_word_in_order(self):
        brief.add(self.brief, "Your task (3 of 9):\n\nDo X\n\n| a | 10/10 |\n")
        brief.add(self.brief, "the gate regressed:\n- a: 9/10")
        text = brief.render(self.brief, self.notes)
        self.assertTrue(text.startswith(brief.HEADER))
        for words in ("## Prompt 1\n\nYour task (3 of 9):", "| a | 10/10 |",
                      "## Prompt 2\n\nthe gate regressed:\n- a: 9/10"):
            self.assertIn(words, text)
        self.assertLess(text.index("## Prompt 1"), text.index("## Prompt 2"))

    def test_the_notes_follow_and_their_absence_is_said(self):
        brief.add(self.brief, "Do X")
        self.assertIn(brief.NO_NOTES, brief.render(self.brief, self.notes))
        with open(self.notes, "w") as f:
            f.write("plan: A then B\nproven: A (uepy.py --verify-for)\n")
        text = brief.render(self.brief, self.notes)
        self.assertNotIn(brief.NO_NOTES, text)
        self.assertIn("proven: A (uepy.py --verify-for)", text)
        self.assertLess(text.index("## Prompt 1"), text.index("plan: A then B"))

    def test_notes_that_became_a_log_are_cut_to_their_end(self):
        brief.add(self.brief, "Do X")
        with open(self.notes, "w") as f:
            f.write("OLD " * brief.NOTES_LIMIT + "left: the commit")
        text = brief.render(self.brief, self.notes)
        self.assertIn("left: the commit", text)
        self.assertIn("(the start is cut)", text)
        self.assertLess(len(text), brief.NOTES_LIMIT + 2000)

    def test_a_missing_brief_does_not_break_the_hook(self):
        self.assertIn("(the brief is missing)", brief.render(self.brief, self.notes))

    def test_the_hook_runs_after_a_compaction_only_and_prints_the_brief(self):
        brief.add(self.brief, "Do X")
        (entry,) = brief.hooks(self.brief, self.notes)["SessionStart"]
        self.assertEqual(entry["matcher"], "compact")
        (hook,) = entry["hooks"]
        self.assertEqual(hook["type"], "command")
        json.dumps(entry)                               # it travels in --settings
        # The command as the CLI runs it: through a shell, from anywhere.
        command = hook["command"].replace("python3", sys.executable, 1)
        out = subprocess.run(command, shell=True, cwd="/", capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), brief.render(self.brief, self.notes))


if __name__ == "__main__":
    unittest.main()
