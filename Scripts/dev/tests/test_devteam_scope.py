"""What a change reaches in the verifier sweep (devteam/scope.py), and the
gate's sweeps scoped by it (work._cached_baseline, work._after_sweep)."""
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import _paths  # noqa: F401

from devteam import baseline_cache, scope, work
from test_devteam import row
from test_devteam_pause import Args, FakePauser

WEAPONS = "verify_weapons_and_combat.py"
MENU = "verify_graphics_menu.py"
SUITES = [WEAPONS, MENU, "verify_clothing.py", "verify_Lvl_Probe_50m.py"]


class Reach(unittest.TestCase):
    def test_paths_no_suite_reads(self):
        for p in ("docs/history/menu.md", "Scripts/dev/devteam/work.py", "Scripts/dev/tasks.md",
                  "Scripts/probes/probe_axe.py", "CLAUDE.md", "Scripts/combat/CLAUDE.md",
                  "Build/Mac/x.json", "Content/Python/init_unreal.py", ".gitignore"):
            self.assertEqual(scope.suites_for([p]), set(), p)

    def test_paths_mapped_to_their_suites(self):
        self.assertEqual(scope.suites_for(["Scripts/combat/axe.py"]), {WEAPONS})
        self.assertEqual(scope.suites_for(["Scripts/graphics_menu/tune_tab.py"]), {MENU})
        self.assertEqual(scope.suites_for(["Content/UI/BP_HUD.uasset"]), {MENU})
        self.assertEqual(scope.suites_for(["Content/Weapons/BP_Axe.uasset"]), {WEAPONS})
        self.assertEqual(scope.suites_for(["Scripts/build_clothing.py"]), {"verify_clothing.py"})
        self.assertEqual(scope.suites_for(["Scripts/verify_survival.py"]), {"verify_survival.py"})
        self.assertEqual(scope.suites_for(["Scripts/generated_levels/Lvl_Probe_50m/level.py"]),
                         {"verify_Lvl_Probe_50m.py"})
        self.assertEqual(scope.suites_for(["Scripts/combat/axe.py", "docs/a.md",
                                           "Scripts/graphics_menu/tune_tab.py"]),
                         {WEAPONS, MENU})

    def test_paths_every_suite_may_feel_and_unknown_ones_mean_the_whole_sweep(self):
        for p in ("Scripts/uebp/nodes/actor.py", "Scripts/combat/verify/common.py",
                  "Source/Otherworld/Private/X.cpp", "Config/DefaultEngine.ini",
                  "Content/Characters/Taro.uasset", "Scripts/new_tool.py",
                  "Content/NewFolder/x.uasset", "Scripts/item_icons/portrait.py"):
            self.assertIsNone(scope.suites_for([p]), p)
        self.assertIsNone(scope.suites_for(["Scripts/combat/axe.py", "Source/X.cpp"]))

    def test_changed_and_relevant(self):
        before = {"a": "1", "b": "2", "c": "3"}
        after = {"a": "1", "b": "9", "d": "4"}
        self.assertEqual(scope.changed(before, after), ["b", "c", "d"])
        files = {"Scripts/combat/axe.py": "a", "docs/x.md": "d", "Source/X.cpp": "s"}
        self.assertEqual(sorted(scope.relevant(files)), ["Scripts/combat/axe.py", "Source/X.cpp"])


class Snapshot(unittest.TestCase):
    def test_tracked_dirty_and_untracked_files_by_content(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)

        def git(*args):
            subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)

        git("init", "-q")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        os.makedirs(os.path.join(root, "Scripts"))
        with open(os.path.join(root, "Scripts", "a.py"), "w") as fh:
            fh.write("one\n")
        git("add", "-A")
        git("commit", "-q", "-m", "a")
        first = scope.snapshot(root)
        self.assertEqual(sorted(first), ["Scripts/a.py"])
        with open(os.path.join(root, "Scripts", "a.py"), "w") as fh:
            fh.write("two\n")
        with open(os.path.join(root, "Scripts", "b.py"), "w") as fh:
            fh.write("new\n")
        second = scope.snapshot(root)
        self.assertEqual(scope.changed(first, second), ["Scripts/a.py", "Scripts/b.py"])
        git("add", "-A")
        git("commit", "-q", "-m", "b")
        self.assertEqual(scope.snapshot(root), second)     # a commit of the same bytes
        os.remove(os.path.join(root, "Scripts", "b.py"))
        self.assertEqual(sorted(scope.snapshot(root)), ["Scripts/a.py"])


class ScopedGate(unittest.TestCase):
    """work.run_one with the cache real (in a temp root), sweeps scripted and
    the tree's snapshots scripted per call."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.snapshots = []             # what scope.snapshot answers, in turn
        self.sweeps = []                # (serve_dir is warm, suites) per run_sweep
        self.steps = []

        def run_sweep(root, log_path, serve_dir=None, suites=None):
            self.sweeps.append((serve_dir is not None, None if suites is None else sorted(suites)))
            return {s: row(s, 3, 0) for s in SUITES if suites is None or s in suites}

        def snapshot(root):
            return dict(self.snapshots.pop(0))

        for target, name, fake in (
                (work, "run_session", lambda *a, **k: (True, "report", {
                    "session_id": "sid", "total_cost_usd": 1.0, "duration_ms": 1000})),
                (work.gate, "run_sweep", run_sweep),
                (work.gate, "sweep_targets", lambda root: [f"/r/{s}" for s in SUITES]),
                (work, "close_editors", lambda: True),
                (work, "tree_state", lambda: ("h", "")),
                (work, "tree_fingerprint", lambda: "f"),
                (work, "git_head", lambda root: "h"),
                (work, "step", lambda text, **k: self.steps.append(text)),
                (work.scope, "snapshot", snapshot),
                (work, "ROOT", self.tmp),
                (work, "print", lambda *a, **k: None)):
            patcher = mock.patch.object(target, name, fake, create=True)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.meter = mock.Mock()
        self.meter.decide.return_value = (False, "test")

    def run_one(self, *snapshots, args=None):
        self.snapshots = list(snapshots)
        from devteam.tasks import Task
        return work.run_one(Task("Do it"), 1, 1, args or Args(), self.tmp,
                            os.path.join(self.tmp, "p.md"), {}, self.meter, FakePauser())

    def test_first_run_sweeps_everything_and_caches_it(self):
        files = {"Scripts/combat/axe.py": "a1", "docs/x.md": "d1"}
        ok, _r, _res, table, after = self.run_one(files, files)
        self.assertTrue(ok)
        self.assertEqual(self.sweeps, [(True, None)])        # the baseline, warm
        self.assertIn("after: tree unchanged; the baseline stands", " ".join(self.steps))
        self.assertIn("Sweep time: baseline", table)
        self.assertIn("after skipped", table)
        self.assertEqual(sorted(after), sorted(SUITES))
        self.assertEqual(baseline_cache.exact(self.tmp, files)[WEAPONS]["passed"], 3)

    def test_a_docs_only_commit_is_the_same_tree(self):
        files = {"Scripts/combat/axe.py": "a1", "docs/x.md": "d1"}
        self.run_one(files, files)
        self.sweeps.clear()
        moved = dict(files, **{"docs/x.md": "d2", "Scripts/dev/tasks.md": "t"})
        during = dict(moved, **{"docs/x.md": "d3", "Scripts/probes/probe_x.py": "p"})
        _ok, _r, _res, table, after = self.run_one(moved, during)
        self.assertEqual(self.sweeps, [])
        joined = " ".join(self.steps)
        self.assertIn("baseline from the cache (tree unchanged)", joined)
        self.assertIn("after: 2 changed path(s) reach no verifier; the baseline stands", joined)
        self.assertIn("Sweep time: baseline cached, after skipped", table)
        self.assertEqual(sorted(after), sorted(SUITES))

    def test_a_change_sweeps_the_suites_it_reaches_and_carries_the_rest(self):
        files = {"Scripts/combat/axe.py": "a1", "Scripts/graphics_menu/t.py": "m1"}
        self.run_one(files, files)
        self.sweeps.clear()
        self.steps.clear()
        before = dict(files, **{"Scripts/graphics_menu/t.py": "m2"})
        during = dict(before, **{"Scripts/combat/axe.py": "a2", "docs/new.md": "n"})
        _ok, _r, _res, table, after = self.run_one(before, during)
        self.assertEqual(self.sweeps, [(True, [MENU]), (False, [WEAPONS])])
        joined = " ".join(self.steps)
        self.assertIn(f"1 changed path(s) reach 1 of 4 suite(s): {MENU}; the rest of the "
                      "baseline from the cache", joined)
        self.assertIn(f"after: 1 changed path(s) reach 1 of 4 suite(s): {WEAPONS}; the rest "
                      "from the baseline", joined)
        self.assertEqual(sorted(after), sorted(SUITES))
        self.assertIn("1 of 4 suites", table)
        self.assertEqual(sorted(baseline_cache.exact(self.tmp, before)), sorted(SUITES))

    def test_a_shared_path_or_an_unknown_one_sweeps_everything(self):
        files = {"Scripts/combat/axe.py": "a1"}
        self.run_one(files, files)
        self.sweeps.clear()
        before = dict(files, **{"Source/X.cpp": "s1"})
        during = dict(before, **{"Scripts/brand_new.py": "u"})
        self.run_one(before, during)
        self.assertEqual(self.sweeps, [(True, None), (False, None)])
        self.assertIn("reach every suite; sweeping the whole baseline", " ".join(self.steps))

    def test_check_baseline_sweeps_everything_both_times(self):
        files = {"Scripts/combat/axe.py": "a1"}
        self.run_one(files, files)
        self.sweeps.clear()

        class Full(Args):
            check_baseline = True
        self.run_one(files, files, args=Full())
        self.assertEqual(self.sweeps, [(True, None), (False, None)])

    def test_a_cache_older_than_a_day_is_swept_again(self):
        files = {"Scripts/combat/axe.py": "a1"}
        self.run_one(files, files)
        self.sweeps.clear()
        with mock.patch.object(work.baseline_cache, "MAX_AGE_S", -1):
            self.run_one(files, files)
        self.assertEqual(self.sweeps, [(True, None)])


if __name__ == "__main__":
    unittest.main()
