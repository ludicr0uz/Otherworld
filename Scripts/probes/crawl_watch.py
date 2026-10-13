"""What a crawling body does, read off its joints: the measurements
probe_stance_clips.py and probe_net_crawl.py share (P2, the crawl by
direction). Not a probe.

A track is the body's joints in the mesh component's space (left +X, forward
+Y, up +Z; the origin is the capsule's bottom) tick by tick, and signature()
is what tells one direction's loop from another's:

    lean      how far the middle of the two hands is to the body's left of
              the hips: the side loops reach out to the side they go
    reach_l   how far each hand travels fore and aft against the hips: the
    reach_r   forward loop strokes with both, a diagonal with the hand
              opposite the side it goes to, a side loop with neither
    shuffle   how far a hand travels across
    pull      which way the stroking hands move while they are lifted:
              forward (+) in a loop played forwards, back (-) in reverse

OWN is each direction's signature (measured 13 Oct 2026 at 80 cm/s: forward
lean +1, reach 28/27, pull +91; left lean +8.7, reach 1/1; forward left lean
+4.3, reach 7/20, pull +118; the right side mirrors, and going back is the
loop of the opposite diagonal in reverse), and own_motion() holds a track to
its own row, which no other row passes.
"""

import unreal

from combat.skin import skin_of_mesh

# name: (lean: +1 left, -1 right, 0 neither; the hands that stroke; pull's sign)
OWN = {
    "forward": (0, "lr", 1), "back": (0, "lr", -1),
    "left": (1, "", 0), "right": (-1, "", 0),
    "forward left": (1, "r", 1), "forward right": (-1, "l", 1),
    "back left": (-1, "l", -1), "back right": (1, "r", -1),
}
# cm: a side loop's lean, a diagonal's, and what forward's stays within.
LEAN_SIDE_CM, LEAN_DIAG_CM, LEAN_NONE_CM = 6.0, 2.5, 3.0
# cm fore and aft: a hand that strokes, and one that does not.
STROKE_CM, NO_STROKE_CM = 14.0, 12.0
PULL_MIN = 40.0
LIMBS = ("hand_l", "hand_r", "calf_l", "calf_r", "foot_l", "foot_r")
SPACE = unreal.RelativeTransformSpace.RTS_COMPONENT


def always_pose(mesh):
    """A headless game renders nothing, and by default an unrendered mesh
    never refreshes its bones."""
    mesh.set_editor_property(
        "visibility_based_anim_tick_option",
        unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
        unreal.PropertyAccessChangeNotifyMode.NEVER)


def joints(player):
    """{joint: its place in the mesh component's space}."""
    mesh = player.get_editor_property("mesh")
    skin = skin_of_mesh(mesh.get_skeletal_mesh_asset().get_path_name())
    b = skin.pose_bones
    bones = {"head": skin.head, "hips": b["hips"], **{k: b[k] for k in LIMBS}}
    return {k: mesh.get_socket_transform(v, SPACE).translation for k, v in bones.items()}


def local_velocity(player):
    """(cm/s ahead, cm/s to the right) in the body's own frame."""
    v = player.get_velocity()
    return (v.dot(player.get_actor_forward_vector()), v.dot(player.get_actor_right_vector()))


def push(player, ahead, right):
    """A tick of movement input ``ahead`` and ``right`` of the body."""
    way = (player.get_actor_forward_vector() * ahead
           + player.get_actor_right_vector() * right)
    player.add_movement_input(way, 1.0, False)


def _range(values):
    return max(values) - min(values)


def signature(track):
    """``track``: [(seconds, joints()), ...] of a steady crawl."""
    poses = [j for _t, j in track]
    rel = lambda k, a: [getattr(j[k], a) - getattr(j["hips"], a) for j in poses]
    pull = 0.0
    for hand in ("hand_l", "hand_r"):
        floor = min(j[hand].z for j in poses)
        y = rel(hand, "y")
        pull += sum((0.5 * (poses[i][hand].z + poses[i + 1][hand].z) - floor)
                    * (y[i + 1] - y[i]) for i in range(len(poses) - 1))
    seconds = max(track[-1][0] - track[0][0], 1e-3)
    return {
        "lean": sum(0.5 * (a + b) for a, b in zip(rel("hand_l", "x"), rel("hand_r", "x")))
        / len(poses),
        "reach_l": _range(rel("hand_l", "y")), "reach_r": _range(rel("hand_r", "y")),
        "shuffle": max(_range(rel("hand_l", "x")), _range(rel("hand_r", "x"))),
        "pull": pull / seconds,
        "low": min(j[k].z for j in poses for k in LIMBS),
        "head": max(j["head"].z for j in poses),
        "hips": (min(j["hips"].z for j in poses), max(j["hips"].z for j in poses)),
    }


def own_motion(name, sig):
    """Does ``sig`` read as ``name``'s loop (and so as no other's)?"""
    lean, strokes, pull = OWN[name]
    need = LEAN_SIDE_CM if not strokes else LEAN_DIAG_CM
    ok = abs(sig["lean"]) < LEAN_NONE_CM if lean == 0 else sig["lean"] * lean > need
    for hand in "lr":
        reach = sig[f"reach_{hand}"]
        ok = ok and (reach > STROKE_CM if hand in strokes else reach < NO_STROKE_CM)
    return ok and (pull == 0 or sig["pull"] * pull > PULL_MIN)


def fastest_joint(track):
    """(cm/s, joint, seconds): the fastest any joint moves between two
    ticks of ``track``, in the mesh component's space. A pose that snaps is a
    joint crossing tens of cm in one tick."""
    best = (0.0, None, 0.0)
    for (t0, a), (t1, b) in zip(track, track[1:]):
        dt = max(t1 - t0, 1e-4)
        for k in a:
            speed = (b[k] - a[k]).length() / dt
            if speed > best[0]:
                best = (speed, k, t1)
    return best


def brief(sig):
    return (f"lean {sig['lean']:+.1f}, reach L {sig['reach_l']:.1f} R {sig['reach_r']:.1f}, "
            f"shuffle {sig['shuffle']:.1f}, pull {sig['pull']:+.0f}, lowest {sig['low']:.1f}, "
            f"hips {sig['hips'][0]:.1f}..{sig['hips'][1]:.1f}, head {sig['head']:.1f}")
