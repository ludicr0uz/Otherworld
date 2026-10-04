"""asset_pipeline/mannequin_bind: the pieces on made-up data, and the whole
bind on the cached bodies where there are any (skipped where there are not:
assets/cache and Content/ are git-ignored)."""

import math
import os
import struct
import tempfile
import unittest

import _paths  # noqa: F401

from asset_pipeline.mannequin_bind import (
    bind, body, check, finger_fit, fit, glb, hand_frame, lbs, paths,
    ref_skeleton, repose, space, weights, xform)
from asset_pipeline.mannequin_bind.bone_map import SIDES, finger_bone

HAVE_MANNEQUIN = os.path.isfile(paths.mannequin_mesh_file())


def cached(spec_id):
    try:
        body.rigged_glb(spec_id)
        return True
    except FileNotFoundError:
        return False


def close(case, a, b, places=6):
    for x, y in zip(a, b):
        case.assertAlmostEqual(x, y, places=places)


class Xform(unittest.TestCase):
    def test_swing_takes_one_direction_onto_another_even_opposite(self):
        for a, b in (((1, 0, 0), (0, 1, 0)), ((1, 2, 3), (-3, 1, 2)),
                     ((0, 0, 1), (0, 0, -1)), ((1, 0, 0), (-1, 0, 0))):
            q = xform.swing(a, b)
            close(self, xform.turn(q, xform.unit(a)), xform.unit(b))

    def test_a_matrix_and_its_quaternion_are_the_same_turn(self):
        q = xform.axis_angle((1, 2, 3), 77.0)
        close(self, xform.mat_vec(xform.q_to_mat(q), (0.3, -1.0, 2.0)),
              xform.turn(q, (0.3, -1.0, 2.0)))
        back = xform.mat_to_q(xform.q_to_mat(q))
        self.assertAlmostEqual(abs(xform.dot(q, back)), 1.0, places=9)

    def test_frame_turn_carries_both_axes(self):
        q = xform.frame_turn((1, 0, 0), (0, 0, 1), (0, 1, 0), (1, 0, 0))
        close(self, xform.turn(q, (1, 0, 0)), (0, 1, 0))
        close(self, xform.turn(q, (0, 0, 1)), (1, 0, 0))

    def test_split_twist_recovers_a_roll_and_a_bend(self):
        axis = xform.unit((1.0, 1.0, 0.0))
        roll = xform.axis_angle(axis, 110.0)
        bend = xform.axis_angle((0, 0, 1), 25.0)
        swing, degrees = repose.split_twist(xform.mul(bend, roll), axis)
        self.assertAlmostEqual(degrees, 110.0, places=4)
        self.assertAlmostEqual(xform.angle_deg(swing), 25.0, places=4)
        _swing, back = repose.split_twist(xform.axis_angle(axis, -110.0), axis)
        self.assertAlmostEqual(back, -110.0, places=4)


class Space(unittest.TestCase):
    def test_a_turn_converted_is_the_turn_of_the_converted(self):
        """The reason a quaternion is not swapped like a direction."""
        q = xform.axis_angle((0.2, 1.0, -0.4), 63.0)
        v = (3.0, -2.0, 5.0)
        there = space.dir_swap(xform.turn(q, v))
        close(self, xform.turn(space.quat_swap(q), space.dir_swap(v)), there)

    def test_points_go_there_and_back(self):
        p = (12.5, -3.0, 96.0)
        close(self, space.point_to_ue(space.point_to_gltf(p)), p)
        close(self, space.point_to_gltf(p), (0.125, 0.96, -0.03))


def blob_of(names, parents, local_q, local_t, junk=b"\x00" * 40):
    """An FReferenceSkeleton as a .uasset holds it, inside some junk."""
    out = junk + b"\x05\x00\x00\x00root\x00" + junk     # a decoy: a string, no skeleton
    out += struct.pack("<i", len(names))
    for name, parent in zip(names, parents):
        raw = name.encode("ascii") + b"\x00"
        out += struct.pack("<iiii", 7, 0, parent, len(raw)) + raw
    out += struct.pack("<i", len(names))
    for q, t in zip(local_q, local_t):
        out += struct.pack("<10d", *q, *t, 1.0, 1.0, 1.0)
    return out + junk


class RefSkeletonFile(unittest.TestCase):
    NAMES = ("root", "pelvis", "spine_01", "thigh_l")
    PARENTS = (-1, 0, 1, 1)
    Q = ((0, 0, 0, 1), xform.axis_angle((0, 1, 0), 90.0),
         xform.axis_angle((0, 0, 1), 10.0), xform.axis_angle((1, 0, 0), 180.0))
    T = ((0, 0, 0), (0, 2, 96), (4, 0, 0), (-2, 0, -10))

    def read(self, blob):
        with tempfile.NamedTemporaryFile(suffix=".uasset", delete=False) as fh:
            fh.write(blob)
        try:
            return ref_skeleton.read_uasset(fh.name)
        finally:
            os.unlink(fh.name)

    def test_it_is_found_past_a_decoy_and_read_whole(self):
        sk = self.read(blob_of(self.NAMES, self.PARENTS, self.Q, self.T))
        self.assertEqual(sk.names, self.NAMES)
        self.assertEqual(sk.parents, self.PARENTS)
        close(self, sk.pos("pelvis"), (0, 2, 96))
        # spine_01 is 4 along the pelvis's x, which a quarter turn about y
        # points down.
        close(self, sk.pos("spine_01"), (0, 2, 92))
        self.assertEqual(sk.children("pelvis"), ["spine_01", "thigh_l"])
        self.assertEqual(sk.descendants("pelvis"), ["spine_01", "thigh_l"])

    def test_a_file_with_none_says_so(self):
        with self.assertRaises(ValueError):
            self.read(b"\x00" * 64 + b"\x05\x00\x00\x00root\x00" + b"\x00" * 64)

    def test_component_and_local_poses_are_two_views_of_one_skeleton(self):
        sk = ref_skeleton.from_local(self.NAMES, self.PARENTS, self.Q, self.T)
        again = ref_skeleton.from_component(sk.names, sk.parents, sk.comp_q, sk.comp_t)
        for a, b in zip(sk.local_t, again.local_t):
            close(self, a, b)
        for a, b in zip(sk.local_q, again.local_q):
            self.assertAlmostEqual(abs(xform.dot(a, b)), 1.0, places=9)


class Weights(unittest.TestCase):
    def test_hat_shares_between_the_two_nodes_either_side(self):
        nodes = [(0.0, "a"), (0.5, "b"), (1.0, "c")]
        self.assertEqual(weights.hat(nodes, -1.0), {"a": 1.0})
        self.assertEqual(weights.hat(nodes, 2.0), {"c": 1.0})
        got = weights.hat(nodes, 0.4)
        self.assertAlmostEqual(got["a"], 0.2)
        self.assertAlmostEqual(got["b"], 0.8)
        self.assertEqual(weights.hat(nodes, 0.5), {"b": 1.0})

    def test_prune_keeps_the_largest_and_sums_to_one(self):
        got = weights.prune({"a": 0.4, "b": 0.3, "c": 0.2, "d": 0.06, "e": 0.04})
        self.assertEqual(set(got), {"a", "b", "c", "d"})
        self.assertAlmostEqual(sum(got.values()), 1.0)

    def test_an_upper_limb_keeps_its_bone_at_the_far_end_and_a_lower_at_the_near(self):
        names = ("root", "upperarm_l", "upperarm_twist_01_l", "upperarm_twist_02_l",
                 "lowerarm_l")
        sk = ref_skeleton.from_local(
            names, (-1, 0, 1, 1, 1), [(0, 0, 0, 1)] * 5,
            [(0, 0, 0), (0, 0, 0), (10, 0, 0), (20, 0, 0), (30, 0, 0)])
        upper, _start, _line = weights.limb_nodes(sk, "upperarm_l", "lowerarm_l", True)
        self.assertEqual([b for _u, b in upper],
                         ["upperarm_twist_01_l", "upperarm_twist_02_l", "upperarm_l"])
        lower, _start, _line = weights.limb_nodes(sk, "upperarm_l", "lowerarm_l", False)
        self.assertEqual(lower[0], (0.0, "upperarm_l"))


class Lbs(unittest.TestCase):
    def test_a_vertex_between_two_bones_goes_half_way(self):
        still = lbs.about(xform.IDENTITY, (0, 0, 0), (0, 0, 0))
        moved = lbs.about(xform.IDENTITY, (0, 0, 0), (0, 0, 10))
        got = lbs.points([(1, 2, 3)], [{"a": 0.5, "b": 0.5}], {"a": still, "b": moved})
        close(self, got[0], (1, 2, 8))

    def test_a_reference_pose_moves_nothing(self):
        sk = ref_skeleton.from_local(
            ("root", "a"), (-1, 0), [(0, 0, 0, 1), xform.axis_angle((0, 0, 1), 30)],
            [(0, 0, 0), (5, 0, 0)])
        moves = lbs.pose_moves(sk, {})
        close(self, lbs.points([(7, 1, 2)], [{"a": 1.0}], moves)[0], (7, 1, 2))


class FingerPieces(unittest.TestCase):
    def test_a_seam_does_not_cut_a_finger_in_two(self):
        """Two strips that meet only at doubled vertices are one piece."""
        flat = {0: (5, 0, 0), 1: (6, 0, 0), 2: (6, 1, 0),
                3: (6, 0, 0), 4: (7, 0, 0), 5: (7, 1, 0)}       # 3 doubles 1
        flat.update({i: (5.0 + 0.1 * i, 0.5, 0.0) for i in range(6, 20)})
        tris = [(0, 1, 2), (3, 4, 5)] + [(i, i + 1, 0) for i in range(6, 19)] \
            + [(19, 4, 5)]
        at, edges = {}, set()
        for a, b, c in tris:
            edges.update(((a, b), (b, c), (a, c)))
        for i, p in flat.items():
            key = tuple(round(c / finger_fit.WELD_CM) for c in p)
            if key in at:
                edges.add((at[key], i))
            at.setdefault(key, i)
        pieces = finger_fit._pieces(list(flat), edges, lambda i: True)
        self.assertEqual(len(pieces), 1)


@unittest.skipUnless(HAVE_MANNEQUIN, "no mannequin mesh in this checkout's data")
class Mannequin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mann = ref_skeleton.read_uasset(paths.mannequin_mesh_file())

    def test_it_is_the_89_bone_mesh_standing_on_the_ground_facing_y(self):
        m = self.mann
        self.assertEqual(len(m.names), 89)
        self.assertEqual(m.names[0], "root")
        self.assertEqual(m.parent_name("hand_l"), "lowerarm_l")
        self.assertGreater(m.pos("pelvis")[2], 90.0)
        self.assertGreater(m.pos("clavicle_l")[0], 0.0)         # left is +X
        self.assertGreater(m.pos("ball_l")[1], m.pos("foot_l")[1])   # toes at +Y
        close(self, m.pos("ik_foot_l"), m.pos("foot_l"), places=2)

    def test_the_thumb_rule_gives_the_mannequins_own_palm(self):
        """hand_frame.palm_from_thumb against the one hand whose palm is
        known without it: the side the mannequin's fingers curl to."""
        for s, _side in SIDES:
            finger, palm = hand_frame.mannequin_frame(self.mann, s)
            thumb = xform.sub(self.mann.pos(finger_bone("thumb", 3, s)),
                              self.mann.pos(f"hand_{s}"))
            thumb = xform.unit(xform.sub(thumb, xform.scale(finger, xform.dot(thumb, finger))))
            got = hand_frame.palm_from_thumb(finger, thumb, right=(s == "r"))
            self.assertGreater(xform.dot(got, palm), 0.7)


@unittest.skipUnless(HAVE_MANNEQUIN and cached("adventurer_03"),
                     "adventurer_03 is not in this checkout's cache")
class BindAdventurer03(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mann = ref_skeleton.read_uasset(paths.mannequin_mesh_file())
        cls.body = body.load("adventurer_03")
        cls.bound = bind.bind_body(cls.body, cls.mann)
        cls.scratch = tempfile.TemporaryDirectory()
        cls.path = os.path.join(cls.scratch.name, "bound.glb")
        bind.write(cls.body, cls.bound, cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.scratch.cleanup()

    def test_nothing_the_bind_must_have_is_missing(self):
        self.assertEqual(check.structure(self.bound, self.mann), [])

    def test_the_file_reads_back_as_the_body_that_was_bound(self):
        self.assertEqual(check.read_back(self.path, self.bound), [])

    def test_only_translations_differ_from_the_mannequin(self):
        sk = self.bound.skeleton
        for a, b in zip(sk.local_q, self.mann.local_q):
            self.assertAlmostEqual(abs(xform.dot(a, b)), 1.0, places=6)
        self.assertNotAlmostEqual(sk.pos("hand_l")[2], self.mann.pos("hand_l")[2], places=1)

    def test_the_mannequins_reference_pose_is_this_bodys_rest(self):
        """Played the mannequin's own reference pose, no vertex moves: the
        property that makes a mannequin clip mean the same thing here."""
        sk = self.bound.skeleton
        pose = {n: self.mann.local_q[i] for i, n in enumerate(self.mann.names)}
        moved = lbs.points(self.bound.verts[::50], self.bound.weights[::50],
                           lbs.pose_moves(sk, pose))
        for a, b in zip(moved, self.bound.verts[::50]):
            close(self, a, b, places=4)

    def test_the_palms_were_turned_over_and_the_wrists_left_straight(self):
        r = self.bound.report
        self.assertLess(r["forearm_roll_deg"]["LeftForeArm"], -90.0)
        self.assertGreater(r["forearm_roll_deg"]["RightForeArm"], 90.0)
        for s in "lr":
            self.assertLess(r["wrist_bend_deg"][s], 15.0)
        self.assertEqual(r["notes"], [])

    def test_fingers_were_found_and_lie_along_the_mannequins(self):
        self.assertEqual(self.bound.report["fingers_found"], {"l": True, "r": True})
        sk = self.bound.skeleton
        for s, _side in SIDES:
            for f in ("index", "middle", "ring", "pinky", "thumb"):
                for j in (1, 2):
                    a, b = finger_bone(f, j, s), finger_bone(f, j + 1, s)
                    got = xform.sub(sk.pos(b), sk.pos(a))
                    want = xform.sub(self.mann.pos(b), self.mann.pos(a))
                    self.assertLess(xform.angle_between(got, want), 0.1, f"{a}")

    def test_a_lifted_clavicle_no_longer_takes_the_ribs_with_it(self):
        for s, m in check.clavicle_lift(self.body, self.bound).items():
            self.assertGreater(m["clavicle_weight_before"], 0.2, s)
            self.assertLess(m["clavicle_weight_after"], 0.08, s)
            self.assertLess(m["moved_cm_after"], 0.5 * m["moved_cm_before"], s)

    def test_the_repose_is_a_pose_and_not_a_reshaping(self):
        s = check.stretch(self.body, self.bound)
        self.assertAlmostEqual(s["p50"], 1.0, places=2)
        self.assertGreater(s["p01"], 0.75)
        self.assertLess(s["p99"], 1.45)

    def test_the_body_is_still_its_own_height_and_side_to_side(self):
        top = max(v[2] for v in self.bound.verts)
        self.assertAlmostEqual(top, 180.0, delta=3.0)
        sk = self.bound.skeleton
        self.assertAlmostEqual(sk.pos("hand_l")[2], sk.pos("hand_r")[2], delta=3.0)
        self.assertAlmostEqual(sk.pos("hand_l")[0], -sk.pos("hand_r")[0], delta=4.0)

    def test_the_pelvis_sits_over_the_hip_joints_as_the_mannequins_does(self):
        """Not on Meshy's Hips, 9.5 cm up: a clip drives the pelvis's height
        scaled by where the reference pelvis is, and from up there the body
        stood 11 cm off the ground in MM_Idle (fit.py)."""
        sk, m = self.bound.skeleton, self.mann
        mine = xform.sub(sk.pos("pelvis"), xform.lerp(sk.pos("thigh_l"), sk.pos("thigh_r"), 0.5))
        theirs = xform.sub(m.pos("pelvis"), xform.lerp(m.pos("thigh_l"), m.pos("thigh_r"), 0.5))
        close(self, mine, theirs, places=4)
        # ...so the pelvis's height is to the mannequin's as the hip joints'.
        self.assertAlmostEqual(sk.pos("pelvis")[2] / m.pos("pelvis")[2],
                               sk.pos("thigh_l")[2] / m.pos("thigh_l")[2], delta=0.03)

    def test_twist_bones_hold_the_middle_of_a_limb(self):
        sk = self.bound.skeleton
        a, b = sk.pos("lowerarm_l"), sk.pos("hand_l")
        mid = xform.lerp(a, b, 0.5)
        near = min(range(len(self.bound.verts)),
                   key=lambda i: xform.length(xform.sub(self.bound.verts[i], mid)))
        held = self.bound.weights[near]
        self.assertGreater(sum(w for bone, w in held.items() if "lowerarm_twist" in bone), 0.5)


@unittest.skipUnless(HAVE_MANNEQUIN and cached("wendigo_01"),
                     "wendigo_01 is not in this checkout's cache")
class NotAMan(unittest.TestCase):
    def test_a_body_the_mannequin_does_not_fit_is_refused(self):
        mann = ref_skeleton.read_uasset(paths.mannequin_mesh_file())
        with self.assertRaises(ValueError):
            bind.bind_body(body.load("wendigo_01"), mann)


class GlbRoundTrip(unittest.TestCase):
    def test_a_fit_helper_walks_a_line_by_length(self):
        line = [(0, 0, 0), (0, 0, 10), (0, 10, 10)]
        close(self, fit._along(line, 0.25), (0, 0, 5))
        close(self, fit._along(line, 0.75), (0, 5, 10))
        self.assertEqual([round(s, 3) for s in fit._shares(
            [(0, 0, 0), (0, 0, 2), (0, 0, 6), (0, 0, 10)])], [0.2, 0.6])

    def test_an_accessor_is_read_with_or_without_a_stride(self):
        data = struct.pack("<3f4x3f4x", 1, 2, 3, 4, 5, 6)
        doc = {"accessors": [{"bufferView": 0, "componentType": glb.FLOAT,
                              "count": 2, "type": "VEC3"}],
               "bufferViews": [{"buffer": 0, "byteLength": len(data), "byteStride": 16}]}
        self.assertEqual(glb.accessor(doc, data, 0), [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)])
        self.assertTrue(math.isclose(glb.accessor(doc, data, 0)[1][2], 6.0))


if __name__ == "__main__":
    unittest.main()
