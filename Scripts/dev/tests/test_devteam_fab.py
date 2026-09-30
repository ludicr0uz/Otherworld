"""dev-team's Fab hand-off: every acquisition goes through the user.

Nothing here touches Fab, an editor or claude: the user is a scripted
``ask``, the session a scripted ``resume``, and the project a temp directory.
"""

import json
import os
import shutil
import tempfile
import unittest

import _paths  # noqa: F401

from asset_pipeline import fab_library
from devteam import fab
from devteam.session import FAB_MARK, build_prompt
from devteam.tasks import Task, parse_tasks

GAS = "Game Animation Sample | url: https://www.fab.com/listings/gas | at: /Game/GAS | why: locomotion"


class Project(object):
    """A temp project: Content/ folders to import into, and an empty library."""

    def __init__(self):
        self.root = tempfile.mkdtemp()
        self.library = os.path.join(self.root, "fab_library.json")

    def import_(self, content, name="A_Walk.uasset"):
        path = fab_library.content_dir(content, self.root)
        os.makedirs(path, exist_ok=True)
        open(os.path.join(path, name), "w").close()

    def items(self):
        return fab_library.load(self.library)

    def cleanup(self):
        shutil.rmtree(self.root)


class Terminal(object):
    """Scripted answers; records every prompt and every line printed."""

    def __init__(self, *answers):
        self.answers, self.asked, self.said = list(answers), [], []

    def ask(self, prompt):
        self.asked.append(prompt)
        if not self.answers:
            raise AssertionError(f"asked more than scripted: {prompt}")
        return self.answers.pop(0)

    def say(self, line):
        self.said.append(line)

    @property
    def text(self):
        return "\n".join(self.said)


class Base(unittest.TestCase):

    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.cleanup)

    def kw(self, term, interactive=True):
        return dict(ask=term.ask, say=term.say, interactive=interactive,
                    project=self.p.root, library=self.p.library)


class RequestTest(unittest.TestCase):

    def test_parse_all_fields(self):
        r = fab.parse_request("- " + GAS)
        self.assertEqual((r.name, r.url, r.at, r.why),
                         ("Game Animation Sample", "https://www.fab.com/listings/gas",
                          "/Game/GAS", "locomotion"))

    def test_only_the_name_is_required_and_unknown_fields_are_ignored(self):
        r = fab.parse_request("Paragon: Shinbi | colour: red")
        self.assertEqual((r.name, r.url, r.at), ("Paragon: Shinbi", "", ""))
        self.assertIsNone(fab.parse_request("  - "))

    def test_line_round_trips(self):
        self.assertEqual(fab.parse_request(fab.parse_request(GAS).line()).line(),
                         fab.parse_request(GAS).line())

    def test_requests_in_a_fab_report(self):
        report = (f"{FAB_MARK} needs locomotion clips\n- {GAS}\n\n- Megascans Rock | at: /Game/Fab\n"
                  "Done so far: the ABP wiring.\n- not a request")
        self.assertEqual([r.name for r in fab.requests_in(report)],
                         ["Game Animation Sample", "Megascans Rock"])

    def test_other_reports_request_nothing(self):
        self.assertEqual(fab.requests_in("Done.\n" + FAB_MARK + "\n- " + GAS), [])
        self.assertEqual(fab.requests_in("FAILED: nope"), [])
        self.assertEqual(fab.requests_in(None), [])


class TaskHintTest(unittest.TestCase):

    def test_fab_hints_repeat_and_stay_out_of_the_text(self):
        (task,) = parse_tasks(f"- [ ] Animate the wanderers\n  fab: {GAS}\n"
                              "  FAB: Megascans Rock\n  effort: low\n")
        self.assertEqual(task.text, "Animate the wanderers")
        self.assertEqual(task.fab, [GAS, "Megascans Rock"])
        self.assertEqual(task.effort, "low")

    def test_no_hints(self):
        self.assertEqual(Task("x").fab, [])


class PromptTest(unittest.TestCase):

    def test_every_session_is_told_the_contract(self):
        prompt = build_prompt(Task("Add a rock"), 1, 1, "/p.md", None, True)
        self.assertIn(FAB_MARK, prompt)
        self.assertIn("never try to sign in", prompt)
        self.assertIn("assets/cache/fab/index.md", prompt)
        self.assertIn("| at: /Game/", prompt)


class LibraryTest(Base):

    def test_content_dir(self):
        self.assertEqual(fab_library.content_dir("/Game/Fab/Rock/", "/p"), "/p/Content/Fab/Rock")
        self.assertIsNone(fab_library.content_dir("/Fab/Materials", "/p"))

    def test_record_replaces_the_same_listing(self):
        fab_library.record(fab_library.FabItem("GAS", "/Game/A", "https://f/l/1"), self.p.library)
        fab_library.record(fab_library.FabItem("Renamed", "/Game/B", "https://f/l/1/"),
                           self.p.library)
        (item,) = self.p.items()
        self.assertEqual((item.name, item.content), ("Renamed", "/Game/B"))
        self.assertTrue(item.added)

    def test_an_empty_folder_is_not_present(self):
        item = fab_library.FabItem("GAS", "/Game/GAS")
        os.makedirs(fab_library.content_dir(item.content, self.p.root))
        self.assertFalse(fab_library.is_present(item, self.p.root))
        self.p.import_("/Game/GAS")
        self.assertTrue(fab_library.is_present(item, self.p.root))

    def test_index_roots_fold_nested_folders(self):
        items = [fab_library.FabItem("a", "/Game/Fab/Megascans/Rock"),
                 fab_library.FabItem("b", "/Game/GAS/")]
        self.assertEqual(fab_library.index_roots(items), ["/Game/Fab", "/Game/GAS"])

    def test_index_md_flags_mannequin_skeletons(self):
        md = fab_library.render_index_md(
            [{"path": "/Game/GAS/SK_UEFN", "class": "Skeleton", "mannequin_bones": True},
             {"path": "/Game/GAS/A_Walk", "class": "AnimSequence", "skeleton": "/Game/GAS/SK_UEFN"}],
            [fab_library.FabItem("GAS", "/Game/GAS")])
        self.assertIn("| `/Game/GAS/SK_UEFN` | 0 | 1 | yes |", md)
        self.assertIn("**GAS** -> `/Game/GAS`", md)


class AcquireTest(Base):

    def test_nothing_is_asked_when_the_library_holds_it(self):
        self.p.import_("/Game/GAS")
        fab_library.record(fab_library.FabItem("Game Animation Sample", "/Game/GAS"),
                           self.p.library)
        term = Terminal()
        items, left = fab.acquire([fab.parse_request(GAS)], **self.kw(term))
        self.assertEqual(([i.content for i in items], left), (["/Game/GAS"], []))
        self.assertEqual(term.asked, [])

    def test_recorded_but_deleted_is_asked_again(self):
        fab_library.record(fab_library.FabItem("Game Animation Sample", "/Game/GAS"),
                           self.p.library)
        self.assertEqual(len(fab.unmet([fab.parse_request(GAS)], self.p.items(), self.p.root)), 1)

    def test_the_user_is_asked_and_it_is_recorded(self):
        self.p.import_("/Game/GAS")
        term = Terminal("")                         # accept the suggested /Game/GAS
        items, left = fab.acquire([fab.parse_request(GAS)], **self.kw(term))
        self.assertEqual(left, [])
        self.assertIn("manual action", term.text)
        self.assertIn("https://www.fab.com/listings/gas", term.text)
        self.assertIn("[/Game/GAS]", term.asked[0])
        (item,) = self.p.items()
        self.assertEqual((item.name, item.content, item.url, item.note),
                         ("Game Animation Sample", "/Game/GAS",
                          "https://www.fab.com/listings/gas", "locomotion"))
        self.assertEqual(items[0].content, "/Game/GAS")

    def test_a_folder_with_no_assets_is_asked_again(self):
        self.p.import_("/Game/Elsewhere")
        term = Terminal("/Game/GAS", "/Fab/GAS", "/Game/Elsewhere")
        items, _left = fab.acquire([fab.parse_request(GAS)], **self.kw(term))
        self.assertEqual(len(term.asked), 3)
        self.assertIn("no assets under", term.text)
        self.assertIn("is not under /Game", term.text)
        self.assertEqual(items[0].content, "/Game/Elsewhere")

    def test_skip_leaves_it_unmet_and_records_nothing(self):
        items, left = fab.acquire([fab.parse_request(GAS)], **self.kw(Terminal("s")))
        self.assertEqual((items, [r.name for r in left]), ([], ["Game Animation Sample"]))
        self.assertFalse(os.path.exists(self.p.library))

    def test_q_stops_the_run(self):
        with self.assertRaises(fab.FabStop):
            fab.acquire([fab.parse_request(GAS)], **self.kw(Terminal("q")))

    def test_without_a_terminal_nothing_is_asked(self):
        term = Terminal()
        _items, left = fab.acquire([fab.parse_request(GAS)], **self.kw(term, interactive=False))
        self.assertEqual(len(left), 1)
        self.assertEqual(term.asked, [])
        self.assertIn("no terminal", term.text)


class PreflightTest(Base):

    def test_no_hints_starts_at_once(self):
        self.assertIsNone(fab.preflight([], lambda: self.fail("closed editors")),)

    def test_met_hints_close_the_editor_the_user_imported_in(self):
        self.p.import_("/Game/GAS")
        closed = []
        blocked = fab.preflight([GAS], lambda: closed.append(1) or True, **self.kw(Terminal("")))
        self.assertIsNone(blocked)
        self.assertEqual(closed, [1])

    def test_skipped_hint_blocks_the_task(self):
        blocked = fab.preflight([GAS], lambda: True, **self.kw(Terminal("s")))
        self.assertTrue(blocked.startswith("FAILED:"))
        self.assertIn("Game Animation Sample", blocked)

    def test_an_editor_left_open_blocks_the_task(self):
        self.p.import_("/Game/GAS")
        blocked = fab.preflight([GAS], lambda: False, **self.kw(Terminal("")))
        self.assertEqual(blocked, fab.EDITOR_LEFT)


class FollowUpTest(Base):
    """A session that asks for an asset, and what dev-team does about it."""

    FAB_REPORT = f"{FAB_MARK} needs locomotion clips\n- {GAS}"

    def session(self, *replies):
        """resume(): replays (ok, report) per call and records each prompt."""
        self.prompts, replies = [], list(replies)

        def resume(prompt):
            self.prompts.append(prompt)
            ok, report = replies.pop(0)
            return ok, report, {"session_id": "s1", "total_cost_usd": 1.0}
        return resume

    def follow(self, report, resume, term, closes=True):
        first = {"session_id": "s1", "total_cost_usd": 2.0}
        return fab.follow_up(False if report.startswith(FAB_MARK) else True, report, first,
                             resume, lambda: closes, **self.kw(term))

    def test_an_ordinary_report_passes_through(self):
        ok, reports, result = self.follow("Done.", self.session(), Terminal())
        self.assertEqual((ok, reports, result["total_cost_usd"]), (True, ["Done."], 2.0))

    def test_ask_record_resume(self):
        self.p.import_("/Game/GAS")
        term = Terminal("")
        ok, reports, result = self.follow(self.FAB_REPORT, self.session((True, "Done.")), term)
        self.assertTrue(ok)
        self.assertEqual(reports, [self.FAB_REPORT, "Done."])
        self.assertEqual(result["total_cost_usd"], 3.0)
        self.assertEqual(len(term.asked), 1)
        (prompt,) = self.prompts
        self.assertIn("Game Animation Sample -> /Game/GAS", prompt)
        self.assertIn("fab_index.py", prompt)
        self.assertEqual(self.p.items()[0].content, "/Game/GAS")

    def test_skip_fails_the_task_without_resuming(self):
        ok, reports, _result = self.follow(self.FAB_REPORT, self.session(), Terminal("s"))
        self.assertFalse(ok)
        self.assertTrue(reports[-1].startswith("FAILED: needs Fab assets"))
        self.assertEqual(self.prompts, [])

    def test_no_terminal_fails_the_task_with_the_list(self):
        term = Terminal()
        ok, reports, _r = fab.follow_up(False, self.FAB_REPORT, {"session_id": "s1"},
                                        self.session(), lambda: True,
                                        **self.kw(term, interactive=False))
        self.assertFalse(ok)
        self.assertIn("Game Animation Sample", reports[-1])
        self.assertEqual((term.asked, self.prompts), ([], []))

    def test_an_editor_left_open_fails_before_resuming(self):
        self.p.import_("/Game/GAS")
        ok, reports, _r = self.follow(self.FAB_REPORT, self.session(), Terminal(""), closes=False)
        self.assertFalse(ok)
        self.assertEqual(reports[-1], fab.EDITOR_LEFT)
        self.assertEqual(self.prompts, [])

    def test_a_session_that_keeps_asking_is_cut_off(self):
        self.p.import_("/Game/GAS")
        again = (False, self.FAB_REPORT)
        resume = self.session(*[again] * fab.MAX_ROUNDS)
        term = Terminal("")                 # asked once; after that the library holds it
        ok, reports, _r = self.follow(self.FAB_REPORT, resume, term)
        self.assertFalse(ok)
        self.assertEqual(len(term.asked), 1)
        self.assertEqual(len(self.prompts), fab.MAX_ROUNDS)
        self.assertIn(f"after {fab.MAX_ROUNDS} round(s)", reports[-1])

    def test_a_second_asset_asked_for_after_the_first(self):
        self.p.import_("/Game/GAS")
        self.p.import_("/Game/Fab/Rock")
        rock = f"{FAB_MARK} and a rock\n- Megascans Rock | at: /Game/Fab/Rock"
        term = Terminal("", "")
        ok, reports, _r = self.follow(self.FAB_REPORT, self.session((False, rock), (True, "Done.")),
                                      term)
        self.assertTrue(ok)
        self.assertEqual(len(self.prompts), 2)
        self.assertEqual(sorted(i.name for i in self.p.items()),
                         ["Game Animation Sample", "Megascans Rock"])
        with open(self.p.library) as fh:
            self.assertEqual(len(json.load(fh)["items"]), 2)


if __name__ == "__main__":
    unittest.main()
