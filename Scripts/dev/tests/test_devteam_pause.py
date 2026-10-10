import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock

import _paths  # noqa: F401

from devteam import pause, work
from devteam.accounting import git
from devteam.session import build_resumed_prompt, run_session
from devteam.tasks import Task


class PauserTest(unittest.TestCase):

    def setUp(self):
        r, w = os.pipe()
        self.reader, self.writer = os.fdopen(r), os.fdopen(w, "w")
        self.addCleanup(self.reader.close)
        self.addCleanup(self.writer.close)
        self.said = []
        self.pauser = pause.Pauser(self.reader, say=self.said.append)

    def type(self, text):
        self.writer.write(text)
        self.writer.flush()

    def wait(self, cond, seconds=5):
        deadline = time.time() + seconds
        while time.time() < deadline and not cond():
            time.sleep(0.02)
        return cond()

    def test_the_word_pauses_and_calls_back_once(self):
        calls = []
        with self.pauser.watching(lambda: calls.append(1)):
            self.type("pause\n")
            self.assertTrue(self.wait(lambda: calls))
        self.assertTrue(self.pauser.requested)
        self.assertEqual(calls, [1])

    def test_case_and_spaces_do_not_matter_and_other_lines_get_a_hint(self):
        with self.pauser.watching():
            self.type("what is it doing\n")
            self.assertTrue(self.wait(lambda: self.said))
            self.assertFalse(self.pauser.requested)
            self.type("  Pause \n")
            self.assertTrue(self.wait(lambda: self.pauser.requested))
        self.assertIn("pause", self.said[0])

    def test_the_stop_word_asks_for_a_stop_and_interrupts_nothing(self):
        calls = []
        with self.pauser.watching(lambda: calls.append(1)):
            self.type("stop\n")
            self.assertTrue(self.wait(lambda: self.pauser.stop_requested))
            self.type("STOP\n")                             # a second one says nothing new
            time.sleep(0.3)
            self.type("hello\n")
            self.assertTrue(self.wait(lambda: len(self.said) == 2))
        self.assertFalse(self.pauser.requested)
        self.assertEqual(calls, [])
        self.assertIn("stopping after this task", self.said[0])
        self.assertIn("'stop'", self.said[1])

    def test_pause_after_stop_still_pauses_at_once(self):
        calls = []
        with self.pauser.watching(lambda: calls.append(1)):
            self.type("stop\n")
            self.assertTrue(self.wait(lambda: self.pauser.stop_requested))
            self.type("pause\n")
            self.assertTrue(self.wait(lambda: calls))
        self.assertTrue(self.pauser.requested)

    def test_nothing_is_read_outside_a_watch(self):
        # A prompt dev-team itself puts to the user must get its own answer.
        with self.pauser.watching():
            pass
        self.type("pause\n")
        time.sleep(0.3)
        self.assertFalse(self.pauser.requested)
        self.assertEqual(self.reader.readline(), "pause\n")

    def test_a_closed_terminal_ends_the_listening(self):
        self.writer.close()
        with self.pauser.watching():
            self.assertTrue(self.wait(lambda: not self.pauser.enabled))
        self.assertFalse(self.pauser.requested)

    def test_disabled_never_listens(self):
        quiet = pause.Pauser(self.reader, enabled=False)
        with quiet.watching(lambda: self.fail("called")):
            self.type("pause\n")
            time.sleep(0.3)
        self.assertFalse(quiet.requested)


class InterruptTest(unittest.TestCase):

    def test_a_session_that_ignores_the_first_signal_is_made_to_stop(self):
        proc = subprocess.Popen(["/bin/sh", "-c", "trap '' INT; sleep 60"],
                                start_new_session=True)
        time.sleep(0.3)
        started = time.time()
        pause.interrupt(proc, waits=((pause.signal.SIGINT, 0.5),
                                     (pause.signal.SIGKILL, 5.0)))
        self.assertIsNotNone(proc.poll())
        self.assertLess(time.time() - started, 5)

    def test_a_paused_session_returns_its_id_and_is_not_ok(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        init = json.dumps({"type": "system", "subtype": "init", "session_id": "abc"})
        r, w = os.pipe()
        reader, writer = os.fdopen(r), os.fdopen(w, "w")
        self.addCleanup(reader.close)
        self.addCleanup(writer.close)
        pauser = pause.Pauser(reader, say=lambda text: None)
        threading.Timer(0.5, lambda: (writer.write("pause\n"), writer.flush())).start()
        fast = ((pause.signal.SIGINT, 1.0), (pause.signal.SIGKILL, 5.0))
        with mock.patch("builtins.print"), mock.patch.object(pause, "INTERRUPT_WAITS", fast):
            ok, report, result = run_session(
                ["/bin/sh", "-c", f"echo '{init}'; sleep 60"], tmp,
                os.path.join(tmp, "log.jsonl"), dict(os.environ), pauser=pauser)
        self.assertFalse(ok)
        self.assertTrue(pauser.requested)
        self.assertEqual(result, {"session_id": "abc", "interrupted": True})


class SessionBackupTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.projects = os.path.join(self.tmp, "projects")
        self.home = os.path.join(self.projects, "-P-Otherworld")
        os.makedirs(os.path.join(self.home, "sid1", "subagents"))
        with open(os.path.join(self.home, "sid1.jsonl"), "w") as fh:
            fh.write('{"a": 1}\n')
        with open(os.path.join(self.home, "sid1", "subagents", "x.jsonl"), "w") as fh:
            fh.write("sub\n")
        self.backup = os.path.join(self.tmp, "backup")

    def test_backup_takes_the_transcript_and_its_side_directory(self):
        source = pause.backup_session("sid1", self.backup, self.projects)
        self.assertEqual(source, os.path.join(self.home, "sid1.jsonl"))
        self.assertTrue(os.path.isfile(os.path.join(self.backup, "sid1.jsonl")))
        self.assertTrue(os.path.isfile(os.path.join(self.backup, "sid1", "subagents", "x.jsonl")))

    def test_an_unknown_session_has_nothing_to_back_up(self):
        self.assertIsNone(pause.backup_session("nope", self.backup, self.projects))
        self.assertIsNone(pause.backup_session(None, self.backup, self.projects))

    def test_restore_puts_back_a_transcript_that_was_cleaned_up(self):
        source = pause.backup_session("sid1", self.backup, self.projects)
        shutil.rmtree(self.home)
        self.assertTrue(pause.restore_session("sid1", self.backup, source))
        with open(source) as fh:
            self.assertEqual(fh.read(), '{"a": 1}\n')
        self.assertTrue(os.path.isfile(os.path.join(self.home, "sid1", "subagents", "x.jsonl")))

    def test_restore_leaves_a_transcript_that_is_still_there(self):
        source = pause.backup_session("sid1", self.backup, self.projects)
        with open(source, "a") as fh:
            fh.write("newer\n")
        self.assertTrue(pause.restore_session("sid1", self.backup, source))
        with open(source) as fh:
            self.assertIn("newer", fh.read())

    def test_no_transcript_anywhere_cannot_be_resumed(self):
        self.assertFalse(pause.restore_session("sid1", self.backup,
                                               os.path.join(self.home, "gone.jsonl")))
        self.assertFalse(pause.restore_session(None, self.backup, None))


class Repo(unittest.TestCase):
    """A throwaway git repository on a branch called ``work``."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        for argv in (("init", "-q", "-b", "work"), ("config", "user.email", "t@example.com"),
                     ("config", "user.name", "T"), ("config", "commit.gpgsign", "false"),
                     ("config", "core.hooksPath", "hooks")):
            self.assertEqual(git(self.root, *argv).returncode, 0)
        self.write("code.py", "one\n")
        self.write("tasks.md", "- [ ] a\n- [ ] b\n")
        git(self.root, "add", "-A")
        self.assertEqual(git(self.root, "commit", "-qm", "start").returncode, 0)

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)

    def read(self, rel):
        with open(os.path.join(self.root, rel)) as fh:
            return fh.read()

    def status(self):
        return git(self.root, "status", "--porcelain").stdout.split("\n")[:-1]

    def head(self, rev="HEAD"):
        return git(self.root, "rev-parse", rev).stdout.strip()


class ParkTest(Repo):

    def dirty(self):
        self.write("code.py", "one\ntwo\n")              # the session's edit
        self.write("new/probe.py", "probe\n")            # a file it made
        self.write("tasks.md", "- [x] a\n- [ ] b\n")     # the run's tick of an earlier task

    def test_park_commits_the_work_on_a_branch_and_frees_the_tree(self):
        self.dirty()
        start = self.head()
        branch, original, error = pause.park(self.root, "t-1", "Do it", keep=["tasks.md"])
        self.assertEqual((branch, original, error), ("paused/t-1", "work", None))
        self.assertEqual(pause.current_branch(self.root), "work")
        self.assertEqual(self.head(), start)                       # work has not moved
        self.assertEqual(self.read("code.py"), "one\n")
        self.assertFalse(os.path.exists(os.path.join(self.root, "new/probe.py")))
        # The ticks of earlier tasks are the run's: they stay in the tree.
        self.assertEqual(self.status(), [" M tasks.md"])
        self.assertTrue(pause.is_wip(self.root, "t-1", "paused/t-1"))
        names = git(self.root, "show", "--name-only", "--format=", "paused/t-1").stdout.split()
        self.assertEqual(sorted(names), ["code.py", "new/probe.py"])

    def test_unpark_brings_it_all_back_uncommitted(self):
        self.dirty()
        start = self.head()
        pause.park(self.root, "t-1", "Do it", keep=["tasks.md"])
        self.assertIsNone(pause.unpark(self.root, "t-1", "paused/t-1", keep=["tasks.md"]))
        self.assertEqual(pause.current_branch(self.root), "paused/t-1")
        self.assertEqual(self.head(), start)                       # the WIP commit is gone
        self.assertEqual(self.read("code.py"), "one\ntwo\n")
        self.assertEqual(self.read("new/probe.py"), "probe\n")
        self.assertEqual(sorted(self.status()), [" M code.py", " M tasks.md", "?? new/"])

    def test_a_pause_with_nothing_to_commit_still_marks_the_branch(self):
        branch, _original, error = pause.park(self.root, "t-2", "Do it")
        self.assertIsNone(error)
        self.assertTrue(pause.is_wip(self.root, "t-2", branch))

    def test_unpark_refuses_to_check_out_over_other_work(self):
        self.dirty()
        pause.park(self.root, "t-1", "Do it", keep=["tasks.md"])
        self.write("code.py", "something else\n")
        error = pause.unpark(self.root, "t-1", "paused/t-1", keep=["tasks.md"])
        self.assertIn("uncommitted", error)
        self.assertEqual(pause.current_branch(self.root), "work")
        self.assertEqual(self.read("code.py"), "something else\n")

    def test_unpark_keeps_commits_made_on_the_branch_after_the_pause(self):
        self.dirty()
        pause.park(self.root, "t-1", "Do it", keep=["tasks.md"])
        git(self.root, "switch", "-q", "paused/t-1")
        self.write("later.py", "x\n")
        git(self.root, "add", "-A", "--", "later.py")
        git(self.root, "commit", "-qm", "by hand")
        top = self.head()
        self.assertIsNone(pause.unpark(self.root, "t-1", "paused/t-1", keep=["tasks.md"]))
        self.assertEqual(self.head(), top)           # HEAD is not the WIP commit: left alone

    def test_a_refused_wip_commit_parks_nothing(self):
        hook = os.path.join(self.root, "hooks", "pre-commit")
        self.write("hooks/pre-commit", "#!/bin/sh\necho 'too big'; exit 1\n")
        os.chmod(hook, 0o755)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "hook", "--no-verify")
        self.dirty()
        branch, original, error = pause.park(self.root, "t-1", "Do it", keep=["tasks.md"])
        self.assertIsNone(branch)
        self.assertEqual(original, "work")
        self.assertIn("too big", error)
        self.assertEqual(pause.current_branch(self.root), "work")
        self.assertEqual(self.read("code.py"), "one\ntwo\n")       # still here, uncommitted
        self.assertEqual(git(self.root, "branch", "--list", "paused/*").stdout.strip(), "")
        self.assertEqual(sorted(self.status()), [" M code.py", " M tasks.md", "?? new/"])

    def test_a_resumed_task_paused_again_reuses_its_branch(self):
        self.dirty()
        pause.park(self.root, "t-1", "Do it", keep=["tasks.md"])
        pause.unpark(self.root, "t-1", "paused/t-1", keep=["tasks.md"])
        self.write("code.py", "one\ntwo\nthree\n")
        branch, original, error = pause.park(self.root, "t-1", "Do it", branch="paused/t-1",
                                             original="work", keep=["tasks.md"])
        self.assertEqual((branch, original, error), ("paused/t-1", "work", None))
        self.assertEqual(pause.current_branch(self.root), "work")
        self.assertEqual(git(self.root, "show", "paused/t-1:code.py").stdout,
                         "one\ntwo\nthree\n")


class LandTest(Repo):

    def finish_on_branch(self):
        self.write("code.py", "one\ntwo\n")
        pause.park(self.root, "t-1", "Do it")
        pause.unpark(self.root, "t-1", "paused/t-1")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "the task")
        return self.head()

    def test_the_original_branch_is_moved_up_and_the_pause_branch_deleted(self):
        done = self.finish_on_branch()
        self.write("tasks.md", "- [x] a\n- [ ] b\n")       # uncommitted, must survive
        said = pause.land(self.root, "paused/t-1", "work")
        self.assertIn("work now has the work", said)
        self.assertEqual(pause.current_branch(self.root), "work")
        self.assertEqual(self.head(), done)
        self.assertEqual(self.status(), [" M tasks.md"])
        self.assertEqual(git(self.root, "branch", "--list", "paused/*").stdout.strip(), "")

    def test_an_original_branch_that_moved_is_left_alone(self):
        self.write("code.py", "one\ntwo\n")
        pause.park(self.root, "t-1", "Do it")
        self.write("other.py", "meanwhile\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "other work")
        moved = self.head()
        pause.unpark(self.root, "t-1", "paused/t-1")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "the task")
        said = pause.land(self.root, "paused/t-1", "work")
        self.assertIn("has moved", said)
        self.assertEqual(pause.current_branch(self.root), "paused/t-1")
        self.assertEqual(self.head("work"), moved)


class RecordTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_a_pause_is_found_by_its_branch_or_its_name(self):
        pause.save(self.tmp, "t-1", {"branch": "paused/t-1", "title": "Do it"})
        pause.save(self.tmp, "t-2", {"branch": None, "title": "Other"})
        for wanted in ("paused/t-1", "t-1"):
            self.assertEqual(pause.find(self.tmp, wanted)["title"], "Do it")
        self.assertEqual(pause.find(self.tmp, "t-2")["title"], "Other")
        self.assertIsNone(pause.find(self.tmp, "t-3"))
        self.assertEqual(len(pause.listing(self.tmp)), 2)
        pause.forget(self.tmp, "t-1")
        self.assertIsNone(pause.find(self.tmp, "t-1"))

    def test_slug(self):
        self.assertEqual(pause.slug("Fix the Axe's swing (again)!", "1004-1030"),
                         "fix-the-axe-s-swing-again-1004-1030")
        self.assertEqual(pause.slug("???", "1"), "task-1")


class Args(object):
    commit, gate, permission_mode, fix_attempts = True, True, "auto", 1
    budget = model = effort = None
    interactive = False


class FakePauser(object):
    """Requests a pause when the test says so."""

    def __init__(self):
        self.requested = False

    def watching(self, on_pause=None):
        import contextlib
        return contextlib.nullcontext()


class RunOneTest(unittest.TestCase):
    """work.run_one with its sessions and sweeps scripted."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.pauser = FakePauser()
        self.sessions, self.sweeps = [], []
        self.pause_in = None            # ("session", k) / ("sweep", k): pause during the k-th
        clean = {"v.py": {"label": "v.py", "ok": True, "passed": 3, "failed": 0}}

        def run_session(cmd, root, log_path, env, on_limits=None, pauser=None):
            self.sessions.append(cmd)
            if self.pause_in == ("session", len(self.sessions)):
                self.pauser.requested = True
                return False, "", {"session_id": "sid", "interrupted": True}
            return True, f"report {len(self.sessions)}", {
                "session_id": "sid", "total_cost_usd": 1.0, "duration_ms": 1000}

        def run_sweep(root, log_path, serve_dir=None):
            self.sweeps.append(1)
            if self.pause_in == ("sweep", len(self.sweeps)):
                self.pauser.requested = True
            return clean

        for target, name, fake in ((work, "run_session", run_session),
                                   (work.gate, "run_sweep", run_sweep),
                                   (work, "close_editors", lambda: True),
                                   (work, "tree_state", lambda: ("h", "")),
                                   (work, "tree_fingerprint", lambda: "f"),
                                   (work, "step", lambda *a, **k: None),
                                   (work.baseline_cache, "load", lambda root, state, probes=(): None),
                                   (work.baseline_cache, "save", lambda root, state, rows, probes=(): None),
                                   (work, "print", lambda *a, **k: None)):
            patcher = mock.patch.object(target, name, fake, create=True)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.meter = mock.Mock()
        self.meter.decide.return_value = (False, "test")

    def run_one(self, parked=None):
        task = Task("Do it")
        return work.run_one(task, 1, 1, Args(), self.tmp, os.path.join(self.tmp, "p.md"),
                            {}, self.meter, self.pauser, parked=parked)

    def test_an_unpaused_task_runs_as_before(self):
        ok, reports, result, table, after = self.run_one()
        self.assertTrue(ok)
        self.assertEqual((len(self.sessions), len(self.sweeps)), (1, 2))
        self.assertEqual(reports, ["report 1"])

    def test_a_pause_during_the_baseline_sweep_starts_no_session(self):
        self.pause_in = ("sweep", 1)
        with self.assertRaises(pause.Paused) as caught:
            self.run_one()
        self.assertEqual(caught.exception.stage, "start")
        self.assertEqual(self.sessions, [])

    def test_a_pause_during_the_session_keeps_what_resuming_needs(self):
        self.pause_in = ("session", 1)
        with self.assertRaises(pause.Paused) as caught:
            self.run_one()
        stop = caught.exception
        self.assertEqual(stop.stage, "session")
        self.assertEqual(stop.result["session_id"], "sid")
        self.assertIn("v.py", stop.baseline)
        self.assertEqual(len(self.sweeps), 1)            # no after-sweep on a paused task

    def test_a_pause_during_the_gate_sweep_is_the_gate_stage(self):
        self.pause_in = ("sweep", 2)
        with self.assertRaises(pause.Paused) as caught:
            self.run_one()
        stop = caught.exception
        self.assertEqual((stop.stage, stop.reports), ("gate", ["report 1"]))
        self.assertEqual(stop.result["total_cost_usd"], 1.0)

    def test_resuming_a_paused_session_resumes_it_and_runs_the_gate(self):
        parked = {"stage": "session", "branch": "paused/t-1", "reports": [],
                  "result": {"session_id": "sid", "interrupted": True},
                  "baseline": {"v.py": {"label": "v.py", "ok": True, "passed": 3, "failed": 0}}}
        ok, reports, result, table, after = self.run_one(parked)
        self.assertTrue(ok)
        (cmd,) = self.sessions
        self.assertEqual(cmd[cmd.index("--resume") + 1], "sid")
        self.assertIn("paused/t-1", cmd[cmd.index("-p") + 1])
        self.assertEqual(len(self.sweeps), 1)            # the after-sweep only: the baseline was kept
        self.assertEqual(result["total_cost_usd"], 1.0)
        self.assertIn("3/3", table)

    def test_resuming_at_the_gate_starts_no_session(self):
        parked = {"stage": "gate", "branch": "paused/t-1", "reports": ["report 1"],
                  "result": {"session_id": "sid", "total_cost_usd": 2.0}, "baseline": None}
        ok, reports, result, table, after = self.run_one(parked)
        self.assertTrue(ok)
        self.assertEqual((self.sessions, len(self.sweeps)), ([], 1))
        self.assertEqual(reports, ["report 1"])
        self.assertEqual(result["total_cost_usd"], 2.0)

    def test_a_resumed_task_can_be_paused_again(self):
        self.pause_in = ("session", 1)
        parked = {"stage": "session", "branch": "paused/t-1", "reports": [],
                  "result": {"session_id": "sid", "total_cost_usd": 2.0}, "baseline": None}
        with self.assertRaises(pause.Paused) as caught:
            self.run_one(parked)
        self.assertEqual(caught.exception.stage, "session")
        self.assertEqual(caught.exception.result["session_id"], "sid")


class PromptTest(unittest.TestCase):

    def test_the_resumed_prompt_says_what_happened_while_paused(self):
        prompt = build_resumed_prompt("paused/t-1", True)
        for words in ("paused", "paused/t-1", "killed", "re-run the builders", "commit"):
            self.assertIn(words, prompt)
        self.assertNotIn("commit on this branch", build_resumed_prompt(None, False))


if __name__ == "__main__":
    unittest.main()
