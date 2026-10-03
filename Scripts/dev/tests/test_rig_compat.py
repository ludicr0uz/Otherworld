"""asset_pipeline/rig_compat.py: one rig against another, on synthetic glTF JSON.

No GLB is read: each document is built here from a table of bones, so each
test changes one thing and checks that the report names it.
"""

import math
import unittest

import _paths  # noqa: F401

from asset_pipeline import rig_compat

# bone: (parent, rest position in cm; x left, y up, z forward)
BONES = {
    "Hips": (None, (0, 96, 0)),
    "Spine02": ("Hips", (0, 110, 0)),
    "Spine01": ("Spine02", (0, 125, 0)),
    "Spine": ("Spine01", (0, 140, 0)),
    "neck": ("Spine", (0, 152, 0)),
    "Head": ("neck", (0, 159, 0)),
    "LeftShoulder": ("Spine", (4, 144, 0)),
    "LeftArm": ("LeftShoulder", (17, 144, 0)),
    "LeftForeArm": ("LeftArm", (36, 123, 0)),
    "LeftHand": ("LeftForeArm", (55, 102, 0)),
    "RightShoulder": ("Spine", (-4, 144, 0)),
    "RightArm": ("RightShoulder", (-17, 144, 0)),
    "RightForeArm": ("RightArm", (-36, 123, 0)),
    "RightHand": ("RightForeArm", (-55, 102, 0)),
    "LeftUpLeg": ("Hips", (10, 90, 0)),
    "LeftLeg": ("LeftUpLeg", (11, 50, 0)),
    "LeftFoot": ("LeftLeg", (12, 12, 0)),
    "LeftToeBase": ("LeftFoot", (12, 2, 12)),
    "RightUpLeg": ("Hips", (-10, 90, 0)),
    "RightLeg": ("RightUpLeg", (-11, 50, 0)),
    "RightFoot": ("RightLeg", (-12, 12, 0)),
    "RightToeBase": ("RightFoot", (-12, 2, 12)),
}


def doc(bones):
    """A glTF document of these bones: translations only, under a scaled root
    as Meshy exports them."""
    names = list(bones)
    index = {name: i for i, name in enumerate(names)}
    nodes = []
    for name in names:
        parent, at = bones[name]
        base = bones[parent][1] if parent else (0, 0, 0)
        node = {"name": name,
                "translation": [a - b for a, b in zip(at, base)]}
        kids = [index[n] for n in names if bones[n][0] == name]
        if kids:
            node["children"] = kids
        nodes.append(node)
    roots = [index[n] for n in names if bones[n][0] is None]
    nodes.append({"name": "Armature", "children": roots,
                  "scale": [0.01, 0.01, 0.01]})
    return {"nodes": nodes, "skins": [{"joints": list(range(len(names)))}]}


def below(bones, bone):
    out = [bone]
    for name, (parent, _at) in bones.items():
        if parent in out and name not in out:
            out.append(name)
    return out


def turned(bones, bone, degrees):
    """``bone`` and everything under it turned about a forward axis through it."""
    out = dict(bones)
    pivot = bones[bone][1]
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    for name in below(bones, bone)[1:]:
        parent, (x, y, z) = bones[name]
        dx, dy = x - pivot[0], y - pivot[1]
        out[name] = (parent, (pivot[0] + c * dx - s * dy,
                              pivot[1] + s * dx + c * dy, z))
    return out


def stretched(bones, bone, child, factor):
    """``bone``'s line to ``child`` made ``factor`` times as long."""
    out = dict(bones)
    a, b = bones[bone][1], bones[child][1]
    shift = tuple((q - p) * (factor - 1.0) for p, q in zip(a, b))
    for name in below(bones, child):
        parent, at = bones[name]
        out[name] = (parent, tuple(p + d for p, d in zip(at, shift)))
    return out


def report(bones):
    return rig_compat.compare(rig_compat.rig_from_doc(doc(bones)),
                              rig_compat.rig_from_doc(doc(BONES)))


def flagged(rep):
    return {flag["bone"] for flag in rep["flags"]}


class RigFromDoc(unittest.TestCase):
    def test_reads_parents_and_scaled_world_positions(self):
        rig = rig_compat.rig_from_doc(doc(BONES))
        self.assertEqual(len(rig), len(BONES))
        self.assertIsNone(rig["Hips"][0])
        self.assertEqual(rig["LeftHand"][0], "LeftForeArm")
        for got, want in zip(rig["LeftHand"][1], (0.55, 1.02, 0.0)):
            self.assertAlmostEqual(got, want)

    def test_rotations_are_composed_down_the_tree(self):
        nodes = [{"name": "a", "children": [1],
                  "rotation": [0, 0, math.sin(math.pi / 4), math.cos(math.pi / 4)]},
                 {"name": "b", "translation": [1, 0, 0]}]
        rig = rig_compat.rig_from_doc({"nodes": nodes, "skins": [{"joints": [0, 1]}]})
        for got, want in zip(rig["b"][1], (0.0, 1.0, 0.0)):
            self.assertAlmostEqual(got, want)


class Compare(unittest.TestCase):
    def test_identical_rigs_are_compatible(self):
        rep = report(BONES)
        self.assertEqual(rep["verdict"], "compatible")
        self.assertEqual(rep["flags"], [])
        self.assertEqual(rep["problems"], [])
        self.assertTrue(all(row["angle"] < 1e-4 for row in rep["rows"]))

    def test_scale_alone_changes_nothing(self):
        big = {n: (p, tuple(c * 1.3 for c in at)) for n, (p, at) in BONES.items()}
        self.assertEqual(report(big)["verdict"], "compatible")

    def test_a_renamed_bone_fails_and_is_named(self):
        bones = {("LeftLowerArm" if n == "LeftForeArm" else n):
                 ("LeftLowerArm" if p == "LeftForeArm" else p, at)
                 for n, (p, at) in BONES.items()}
        rep = report(bones)
        self.assertEqual(rep["verdict"], "fail")
        text = "\n".join(rep["problems"])
        self.assertIn("LeftForeArm: missing", text)
        self.assertIn("LeftLowerArm: not in the reference", text)

    def test_a_reparented_bone_fails_and_is_named(self):
        bones = dict(BONES)
        bones["LeftShoulder"] = ("Spine01", BONES["LeftShoulder"][1])
        rep = report(bones)
        self.assertEqual(rep["verdict"], "fail")
        self.assertEqual(len(rep["problems"]), 1)
        self.assertIn("LeftShoulder: parented to Spine01", rep["problems"][0])

    def test_an_arm_turned_15_degrees_names_that_arm_only(self):
        rep = report(turned(BONES, "LeftArm", 15.0))
        self.assertEqual(rep["verdict"], "normalise")
        rows = {row["segment"]: row for row in rep["rows"]}
        self.assertAlmostEqual(rows["LeftArm>LeftForeArm"]["own"], 15.0, places=3)
        # The forearm is carried round with it and has not itself moved.
        self.assertAlmostEqual(rows["LeftForeArm>LeftHand"]["angle"], 15.0, places=3)
        self.assertLess(rows["LeftForeArm>LeftHand"]["own"], 0.01)
        own = {f["bone"] for f in rep["flags"] if "rests" in f["what"]}
        self.assertEqual(own, {"LeftArm"})
        self.assertEqual(flagged(rep), {"LeftArm", "LeftForeArm"})

    def test_a_forearm_20_percent_longer_is_named(self):
        rep = report(stretched(BONES, "LeftForeArm", "LeftHand", 1.2))
        self.assertEqual(rep["verdict"], "normalise")
        self.assertEqual(flagged(rep), {"LeftForeArm"})
        self.assertIn("1.20x", rep["flags"][0]["what"])

    def test_a_proportion_past_the_fail_line_fails(self):
        rep = report(stretched(BONES, "LeftForeArm", "LeftHand", 1.5))
        self.assertEqual(rep["verdict"], "fail")
        self.assertEqual({f["bone"] for f in rep["flags"] if f["level"] == "fail"},
                         {"LeftForeArm"})

    def test_summary_is_json_shaped(self):
        import json
        out = rig_compat.summary(report(turned(BONES, "LeftArm", 15.0)))
        self.assertEqual(json.loads(json.dumps(out))["verdict"], "normalise")
        self.assertTrue(any("LeftArm" in line for line in out["flags"]))


if __name__ == "__main__":
    unittest.main()
