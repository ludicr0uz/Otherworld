"""asset_pipeline/player_clips.csv and the command that rewrites it
(Scripts/dev/swap_clip.py): the roles, the one-row edit, where a new FBX is
registered, and the strike read off a swing's hand. Pure: the editor's half
(player_clip_swap.py) is proven by a swap.

    python3 -m unittest discover -s Scripts/dev/tests
"""

import os
import re
import tempfile
import unittest

import _paths  # noqa: F401

import swap_clip as S
from asset_pipeline import mixamo_paths as M
from asset_pipeline import player_clips as C

# The right hand's place ahead of the body (cm, 30 fps) through the first
# 1.5 s of the two swings the game shipped with, as retargeted.
STAB = [-16.2, -16.3, -16.5, -16.7, -16.9, -17.1, -17.1, -17.2, -17.4, -17.9, -18.5, -19.1,
        -19.6, -20.0, -20.6, -21.0, -20.8, -20.0, -19.3, -18.4, -15.3, -8.2, 2.2, 13.1, 22.3,
        30.4, 37.9, 43.9, 47.6, 49.5, 50.7, 51.3, 51.5, 51.6, 51.7, 51.7, 51.6, 51.4, 51.2,
        51.0, 50.9, 50.8, 50.9, 50.8, 50.2]
CHOP = [-12.8, -16.2, -20.7, -25.8, -30.9, -36.1, -41.5, -46.6, -50.7, -53.8, -56.4, -58.6,
        -60.1, -60.8, -59.5, -55.9, -51.5, -44.6, -34.2, -20.9, -4.2, 19.4, 39.1, 56.0, 67.3,
        69.1, 60.0, 45.1, 38.7, 35.3, 31.8, 28.5, 25.8, 23.6, 21.9, 21.3, 21.3, 21.7, 22.4,
        23.9, 25.5, 28.2, 31.2, 34.4, 36.6]

TABLE = ("role,pack,clip,hit_s\n"
         "knife_swing,Knife,Stabbing,0.97\n"
         "axe_ready,MeleeAxe,StandingIdle,\n"
         "axe_swing,MeleeAxe,StandingMeleeAttackDownward,0.85\n")
PACKS = (("Axe Pack", "MeleeAxe"), ("Player", "Player"))


def _source(*parts):
    with open(os.path.join(_paths.SCRIPTS, *parts), encoding="utf-8") as f:
        return f.read()


class TheTable(unittest.TestCase):
    def test_every_role_has_one_row_and_every_row_a_role(self):
        roles = [r.role for r in C.read_rows()]
        self.assertEqual(sorted(roles), sorted(C.ROLES),
                         "player_clips.csv and player_clips.ROLES name different roles")

    def test_a_swing_has_a_strike_and_nothing_else_does(self):
        for row in C.read_rows():
            self.assertEqual(row.hit_s is not None, row.role in C.SWINGS,
                             f"{row.role}: hit_s is for a swing, and every swing has one")

    def test_every_pack_is_a_player_pack(self):
        shorts = {short for _, short in M.PLAYER_PACKS}
        for row in C.read_rows():
            self.assertIn(row.pack, shorts, f"{row.role}: no PLAYER_PACKS row for {row.pack}")
        self.assertIn(S.LOOSE, shorts)

    def test_mixamo_paths_reads_the_table(self):
        for row in C.read_rows():
            self.assertEqual(M.PLAYER_CLIPS[row.role], (row.pack, row.clip))
            self.assertEqual(M.PLAYER_HIT_S[row.role], row.hit_s)

    def test_the_melee_bake_names_roles_of_the_table(self):
        text = _source("combat", "melee_clips.py")
        named = set(re.findall(r'MeleeClip\([A-Z_]+, "(\w+)"', text))
        self.assertEqual(named, set(C.ROLES) - {"prone_crawl"})
        for swing in C.SWINGS:
            self.assertIn(f'PLAYER_HIT_S["{swing}"]', text,
                          f"{swing}: its strike is the table's, not a literal")

    def test_every_rebuild_step_is_a_step_of_the_weapons_build(self):
        steps = set(re.findall(r'Step\("(\w+)"', _source("combat", "build_steps.py")))
        for role, (_, needs) in C.ROLES.items():
            self.assertLessEqual(set(needs), steps, f"{role}: no such build step")


class TheRowEdit(unittest.TestCase):
    def test_one_line_changes(self):
        new = C.set_row(TABLE, C.Row("axe_swing", "Player", "GreatSwordSlash", 1.1))
        before, after = TABLE.splitlines(), new.splitlines()
        changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        self.assertEqual(len(before), len(after))
        self.assertEqual(changed, [3])
        self.assertEqual(after[3], "axe_swing,Player,GreatSwordSlash,1.10")

    def test_swapping_back_restores_the_text(self):
        old = next(r for r in C.parse(TABLE) if r.role == "axe_swing")
        there = C.set_row(TABLE, C.Row("axe_swing", "Player", "Other", 0.5))
        self.assertEqual(C.set_row(there, old), TABLE)

    def test_a_ready_pose_has_an_empty_strike(self):
        new = C.set_row(TABLE, C.Row("axe_ready", "MeleeAxe", "CrouchIdle", None))
        self.assertIn("axe_ready,MeleeAxe,CrouchIdle,\n", new)

    def test_an_unknown_role_is_refused_and_the_roles_named(self):
        with self.assertRaises(ValueError) as raised:
            C.set_row(TABLE, C.Row("sword_swing", "Player", "Slash", 1.0))
        for role in ("knife_swing", "axe_ready", "axe_swing"):
            self.assertIn(role, str(raised.exception))

    def test_the_file_is_rewritten_and_the_old_row_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.csv")
            with open(path, "w", encoding="utf-8") as f:
                f.write(TABLE)
            old = C.write_row(C.Row("knife_swing", "Knife", "Slash", 0.6), path)
            self.assertEqual(old, C.Row("knife_swing", "Knife", "Stabbing", 0.97))
            self.assertEqual(C.read_rows(path)[0], C.Row("knife_swing", "Knife", "Slash", 0.6))

    def test_a_malformed_table_raises(self):
        for text in ("pack,role\n", C.HEADER + "\naxe_swing,MeleeAxe\n",
                     C.HEADER + "\naxe_swing,,X,\n"):
            with self.assertRaises(ValueError):
                C.parse(text)


class ThePlan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = os.path.join(self.tmp.name, "cache")
        os.makedirs(os.path.join(self.cache, "Axe Pack"))
        self.rows = C.parse(TABLE)

    def _fbx(self, *parts, data=b"fbx"):
        path = os.path.join(self.tmp.name, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def _plan(self, role, fbx):
        return S.plan(role, fbx, self.rows, self.cache, PACKS)

    def test_an_unknown_role_names_the_roles(self):
        with self.assertRaises(ValueError) as raised:
            self._plan("sword_swing", self._fbx("dl", "Slash.fbx"))
        self.assertIn("axe_swing", str(raised.exception))
        self.assertIn("knife_swing", str(raised.exception))

    def test_a_clip_of_a_cached_pack_stays_where_it_is(self):
        fbx = self._fbx("cache", "Axe Pack", "standing melee attack horizontal.fbx")
        p = self._plan("axe_swing", fbx)
        self.assertEqual((p.pack, p.clip, p.copy_to),
                         ("MeleeAxe", "StandingMeleeAttackHorizontal", None))
        self.assertEqual(p.old.clip, "StandingMeleeAttackDownward")

    def test_a_download_from_outside_goes_to_the_loose_pack(self):
        p = self._plan("axe_swing", self._fbx("dl", "Great Sword Slash.fbx"))
        self.assertEqual((p.pack, p.clip), ("Player", "GreatSwordSlash"))
        self.assertEqual(p.copy_to, os.path.join(self.cache, "Player", "Great Sword Slash.fbx"))
        self.assertFalse(os.path.exists(p.copy_to), "a plan copies nothing")

    def test_the_same_download_twice_is_not_copied_again(self):
        self._fbx("cache", "Player", "Slash.fbx")
        self.assertIsNone(self._plan("axe_swing", self._fbx("dl", "Slash.fbx")).copy_to)

    def test_another_file_by_that_name_is_refused(self):
        self._fbx("cache", "Player", "Slash.fbx", data=b"the old one")
        with self.assertRaises(ValueError) as raised:
            self._plan("axe_swing", self._fbx("dl", "Slash.fbx"))
        self.assertIn("rename", str(raised.exception))

    def test_not_an_fbx_is_refused(self):
        for path in (os.path.join(self.tmp.name, "missing.fbx"), self._fbx("dl", "Slash.zip")):
            with self.assertRaises(ValueError):
                self._plan("axe_swing", path)

    def test_the_steps_are_the_roles(self):
        fbx = self._fbx("dl", "Idle.fbx")
        self.assertEqual(self._plan("axe_ready", fbx).steps, ("axe",))
        self.assertEqual(self._plan("axe_swing", fbx).steps, ())

    def test_the_way_back_names_the_old_strike(self):
        line = S.undo_line(C.Row("axe_swing", "Nowhere", "Chop", 0.85))
        self.assertTrue(line.startswith("python3 Scripts/dev/swap_clip.py axe_swing "))
        self.assertTrue(line.endswith("--hit-s 0.85"))


class TheStrike(unittest.TestCase):
    def test_the_stab_strikes_where_it_was_read_by_eye(self):
        self.assertEqual(C.strike_s(STAB, 30), 0.97)

    def test_the_chop_strikes_within_a_frame_of_where_it_was_read_by_eye(self):
        self.assertAlmostEqual(C.strike_s(CHOP, 30), 0.85, delta=1.0 / 30)

    def test_the_strike_follows_the_fastest_frame_forward(self):
        for path in (STAB, CHOP):
            steps = [b - a for a, b in zip(path, path[1:])]
            fastest = steps.index(max(steps)) / 30.0
            self.assertGreater(C.strike_s(path, 30), fastest)

    def test_a_hand_that_goes_nowhere_has_no_strike(self):
        self.assertIsNone(C.strike_s([0.0, 5.0, 10.0, 12.0, 11.0], 30))
        self.assertIsNone(C.strike_s([], 30))

    def test_a_thrust_that_never_slows_strikes_at_the_end(self):
        self.assertEqual(C.strike_s([0.0, 20.0, 40.0, 60.0], 30), 0.1)

    def test_the_report_says_when_the_row_differs_from_the_strike_read(self):
        lines = S.report({"old": "axe_swing,A,B,0.85", "new": "axe_swing,A,B,0.85", "made": [],
                          "length_s": 2.27, "detected_s": 0.83, "impact_s": 0.24,
                          "reach_cm": [-61.0, 69.0], "checks": [["a chop", False]]})
        text = "\n".join(lines)
        self.assertIn("read at 0.83 s", text)
        self.assertIn("the row has 0.85, as given", text)
        self.assertIn("starts 0.61 s in", text)
        self.assertIn("FAIL      a chop", text)


if __name__ == "__main__":
    unittest.main()
