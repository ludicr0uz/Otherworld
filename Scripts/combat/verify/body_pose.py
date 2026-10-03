"""verify.body_pose -- the crouch, prone and guard poses: the player's anim BP
carries body_pose.pose_plan() as weighted ModifyBones between the aim pitch's
LocalToComponent and its spine bones, the plan puts the body where each pose
says (replayed on the reference skeleton), and the weapon component eases the
four weights from the Stance, Blocking and whether Held is two-handed.

On a rig with the stance clips the crouch is not posed here and the prone is
the crawl's corrections; verify.stance_clips checks the clips themselves.
"""

import math

from asset_pipeline.rig_util import mesh_ref_pose
from combat.body_pose import (
    KNEEL_BLEND_SPEED, KNEEL_FROM_S, KNEEL_TIME, KNEEL_TO_S, POSE_KNEEL,
    ADDITIVE, GUARD_ARMS, GUARD_GUN, GUARD_GUN_LEAN_DEG, GUARD_GUN_TURN_DEG,
    POSE_BLEND_SPEED, POSE_CROUCH, POSE_PRONE,
    POSE_WEIGHTS, PRONE_HIPS_CM, PRONE_MOVING, _conj, _mul,
    _ref, _rotator, _turn, pose_plan,
)
from combat.aim_pitch import MODIFY_BONE_CLASS
from combat.paths import ITEM_BP_PATH
from combat.skin import player_skin
from combat.verify.common import BEL, PIN, cdo, check, graph, load, num_pin
from combat.verify.fixtures import w, wg
from combat.weapon_component.pose_weights import HELD_TWO_HANDED, SEARCHING_VAR
from combat.weapon_component.stance import CROUCH, PRONE
from combat.weapon_specs import _weapon_specs


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _source(pin):
    fed = PIN.list_connected_pins(pin)
    return PIN.get_owning_node(fed[0]) if fed else None


def _feeds(pin, limit=60):
    seen, stack = [], [pin]
    while stack and len(seen) < limit:
        for q in PIN.list_connected_pins(stack.pop()):
            node = PIN.get_owning_node(q)
            if node not in seen:
                seen.append(node)
                stack.extend(x for x in BEL.list_input_pins(node)
                             if str(PIN.get_pin_name(x)) != "execute")
    return seen


def _chain(nodes):
    """The weighted ModifyBones in pose order, walking out of LocalToComponent."""
    to_cs = [n for n in nodes
             if n.get_class().get_name() == "AnimGraphNode_LocalToComponentSpace"]
    out = []
    pose = BEL.find_output_pin(to_cs[0], "ComponentPose") if len(to_cs) == 1 else None
    while pose is not None and len(out) < 64:
        nxt = PIN.list_connected_pins(pose)
        node = PIN.get_owning_node(nxt[0]) if len(nxt) == 1 else None
        if (node is None or node.get_class().get_name() != MODIFY_BONE_CLASS
                or not PIN.list_connected_pins(BEL.find_input_pin(node, "Alpha"))):
            break
        out.append(node)
        pose = BEL.find_output_pin(node, "Pose")
    return out


def _literals(node, pin, names):
    src = _source(BEL.find_input_pin(node, pin))
    return tuple(num_pin(src, n) for n in names) if src else None


# The weights that are products, not variables: what each multiplies.
PRODUCTS = {PRONE_MOVING: ("Get GroundSpeed",)}


def _weighted_by(alpha, weight):
    """Is ``alpha`` (the node on a ModifyBone's Alpha) the weight's reader?"""
    if alpha is None:
        return False
    if weight not in PRODUCTS:
        return _title(alpha) == f"Get {weight}"
    fed = {_title(n) for pin in ("A", "B") for n in _feeds(BEL.find_input_pin(alpha, pin))}
    return {f"Get {POSE_PRONE}", *PRODUCTS[weight]} <= fed


def check_anim_bp_poses():
    skin = player_skin()
    abp = load(skin.anim_bp)
    nodes = graph(abp, "AnimGraph").list_all_nodes()
    defaults = cdo(abp)
    for name in POSE_WEIGHTS:
        v = defaults.get_editor_property(name)
        check(f"{abp.get_name()} declares {name} as a float, resting at 0",
              isinstance(v, float) and v == 0.0, repr(v))

    plan = pose_plan(skin, _ref(abp.get_editor_property("target_skeleton")))
    chain = _chain(nodes)
    driven = [n for n in nodes if n.get_class().get_name() == MODIFY_BONE_CLASS
              and PIN.list_connected_pins(BEL.find_input_pin(n, "Alpha"))]
    check("the body poses are one unbroken chain out of LocalToComponent, one "
          "ModifyBone per step of pose_plan, and a rerun stacked none",
          len(chain) == len(plan) == len(driven), f"{len(chain)} {len(plan)} {len(driven)}")
    after = BEL.find_output_pin(chain[-1], "Pose") if chain else None
    nxt = PIN.list_connected_pins(after) if after else []
    check("...and it runs into the aim pitch, which turns whatever it made",
          len(nxt) == 1 and PIN.get_owning_node(nxt[0]).get_class().get_name()
          == MODIFY_BONE_CLASS)

    bad = []
    for node, (weight, bone, mode, quat, move) in zip(chain, plan):
        inner = node.get_editor_property("node")
        got_bone = str(inner.get_editor_property("bone_to_modify")
                       .get_editor_property("bone_name"))
        alpha = _source(BEL.find_input_pin(node, "Alpha"))
        want_rot = tuple(round(v, 4) for v in _rotator(quat)) if quat else None
        got_rot = _literals(node, "Rotation", ("Pitch", "Yaw", "Roll"))
        got_move = _literals(node, "Translation", ("X", "Y", "Z"))
        ok = (got_bone == bone and inner.get_editor_property("rotation_mode") == mode
              and _weighted_by(alpha, weight)
              and (quat is None or (got_rot and all(
                  abs(a - b) < 1e-3 for a, b in zip(got_rot, want_rot))))
              and (move is None or (got_move and all(
                  abs(a - round(b, 3)) < 1e-3 for a, b in zip(got_move, move)))))
        if not ok:
            bad.append(f"{weight}:{bone} got {got_bone} {got_rot} {got_move}")
    check("every step turns the planned bone by the planned rotation and "
          "translation, weighted by its pose", not bad and len(chain) == len(plan),
          "; ".join(bad[:3]))


def _replay(ref, children, steps):
    """Apply ``steps`` to the reference pose the way ModifyBone does in
    component space: the bone and everything below it turn about the bone."""
    pos = {b: t.translation for b, (t, _p) in ref.items()}
    pos = {b: (v.x, v.y, v.z) for b, v in pos.items()}
    rot = {b: (t.rotation.x, t.rotation.y, t.rotation.z, t.rotation.w)
           for b, (t, _p) in ref.items()}
    for _weight, bone, mode, quat, move in steps:
        below, stack = [], [bone]
        while stack:
            b = stack.pop()
            below.append(b)
            stack.extend(children.get(b, ()))
        if quat is not None:
            delta = quat if mode == ADDITIVE else _mul(quat, _conj(rot[bone]))
            pivot = pos[bone]
            for b in below:
                off = _turn(delta, tuple(p - q for p, q in zip(pos[b], pivot)))
                pos[b] = tuple(p + o for p, o in zip(pivot, off))
                rot[b] = _mul(delta, rot[b])
        if move is not None:
            for b in below:
                pos[b] = tuple(p + m for p, m in zip(pos[b], move))
    return pos, rot


def _angle(a, b):
    dot = abs(sum(p * q for p, q in zip(a, b)))
    return math.degrees(2 * math.acos(min(1.0, dot)))


def check_pose_geometry():
    """Replay each pose on the reference skeleton and look at where it put
    the body -- the numbers a render showed, as assertions."""
    skin = player_skin()
    abp = load(skin.anim_bp)
    ref = mesh_ref_pose(load(skin.mesh))
    children = {}
    for b, (_t, parent) in ref.items():
        children.setdefault(parent, []).append(b)
    plan = pose_plan(skin, _ref(abp.get_editor_property("target_skeleton")))
    b = skin.pose_bones
    rest = {k: (t.translation.x, t.translation.y, t.translation.z)
            for k, (t, _p) in ref.items()}
    top = max(rest, key=lambda k: rest[k][2])

    def gap(p, l_bone, r_bone):
        return math.dist(p[l_bone], p[r_bone])

    hands = (b["hand_l"], b["hand_r"])
    # With the stance clips there is nothing to replay here: verify.stance_clips
    # checks the clips, and probes/probe_stance_clips.py the armed prone in game.
    if not skin.stance_clips:
        pos, _rot = _replay(ref, children, [s for s in plan if s[0] == POSE_CROUCH])
        feet = [pos[b[f"foot_{s}"]][2] - rest[b[f"foot_{s}"]][2] for s in "lr"]
        check("crouch: the feet stay on the ground (within 3 cm)",
              all(abs(f) < 3.0 for f in feet), str([round(f, 1) for f in feet]))
        check("crouch: the top of the body comes down at least 40 cm",
              rest[top][2] - pos[top][2] >= 40.0, f"{rest[top][2] - pos[top][2]:.1f}")

        steps = [s for s in plan if s[0] == POSE_PRONE]
        pos, rot = _replay(ref, children, steps)
        check(f"prone: the hips lie {PRONE_HIPS_CM:g} cm off the ground",
              abs(pos[b["hips"]][2] - PRONE_HIPS_CM) < 0.5, f"{pos[b['hips']][2]:.1f}")
        highest = max(p[2] for p in pos.values())
        check("prone: nothing stands above the prone capsule (80 cm)",
              highest < 80.0, f"{highest:.1f}")
        check("prone: the head is ahead of the hips and the feet behind them",
              pos[top][1] > pos[b["hips"]][1] + 30
              and all(pos[b[f"foot_{s}"]][1] < pos[b["hips"]][1] - 50 for s in "lr"),
              f"head {pos[top][1]:.0f}, feet {pos[b['foot_l']][1]:.0f}")
        check("prone: both hands keep their distance, so a gun stays in both",
              abs(gap(pos, *hands) - gap(rest, *hands)) < 0.5,
              f"{gap(rest, *hands):.1f} -> {gap(pos, *hands):.1f}")
        neck = ref[b["neck"]][0].rotation
        check("prone: the head is brought back level (looks where it did standing)",
              _angle(rot[b["neck"]], (neck.x, neck.y, neck.z, neck.w)) < 1.0)

    pos, _rot = _replay(ref, children, [s for s in plan if s[0] == GUARD_ARMS])
    lh, rh = pos[b["hand_l"]], pos[b["hand_r"]]
    shoulder_z = min(rest[b["upperarm_l"]][2], rest[b["upperarm_r"]][2])
    check("fists guard: both hands up at the face, in front of it, apart",
          min(lh[2], rh[2]) > shoulder_z - 15 and min(lh[1], rh[1]) > 15
          and lh[0] > 0 > rh[0], f"L {lh} R {rh}")

    pos, rot = _replay(ref, children, [s for s in plan if s[0] == GUARD_GUN])
    check("gun guard: the chest turns as one piece, so a gun stays in both hands",
          abs(gap(pos, *hands) - gap(rest, *hands)) < 0.1)
    ref_neck = ref[b["neck"]][0].rotation
    check("gun guard: the neck turns back, so the head still faces ahead",
          _angle(rot[b["neck"]], (ref_neck.x, ref_neck.y, ref_neck.z, ref_neck.w)) < 0.5)
    def yaw(p):
        dx, dy = (p[b["clavicle_l"]][i] - p[b["clavicle_r"]][i] for i in (0, 1))
        return math.degrees(math.atan2(dy, dx))
    turned = yaw(rest) - yaw(pos)
    # The lean is read off the chest's own turn: how far it tips straight up
    # back from the way the turned chest faces. (Where the neck ends up says
    # nothing: a rig whose neck joint sits behind its chest joint carries it
    # forward in the turn.)
    chest = skin.aim_bones[-1]
    was = ref[chest][0].rotation
    added = _mul(rot[chest], _conj((was.x, was.y, was.z, was.w)))
    r = math.radians(GUARD_GUN_TURN_DEG)
    ahead = (math.sin(r), math.cos(r), 0.0)
    back = -sum(u * a for u, a in zip(_turn(added, (0.0, 0.0, 1.0)), ahead))
    leaned = math.degrees(math.asin(max(-1.0, min(1.0, back))))
    check(f"gun guard: the shoulders turn left by {GUARD_GUN_TURN_DEG:g} deg "
          f"and the chest leans back by {GUARD_GUN_LEAN_DEG:g}",
          abs(turned - GUARD_GUN_TURN_DEG) < 2.0
          and abs(leaned - GUARD_GUN_LEAN_DEG) < 2.0,
          f"turned {turned:.1f}, leaned {leaned:.1f}")


def check_weights_written():
    writes = {name: [n for n in wg if _title(n) == f"Set {name}"] for name in POSE_WEIGHTS}
    check("BP_WeaponComponent writes each of the four pose weights once a frame",
          all(len(v) == 1 for v in writes.values()),
          str({k: len(v) for k, v in writes.items()}))
    if not all(len(v) == 1 for v in writes.values()):
        return
    for name, (put,) in writes.items():
        step = _source(BEL.find_input_pin(put, name))
        check(f"...{name} is eased: FInterpTo(its own value, target) at "
              f"{POSE_BLEND_SPEED:g}", step is not None
              and num_pin(step, "InterpSpeed") == POSE_BLEND_SPEED
              and _title(_source(BEL.find_input_pin(step, "Current"))) == f"Get {name}")
    for name, value in ((POSE_CROUCH, CROUCH), (POSE_PRONE, PRONE)):
        src = _feeds(BEL.find_input_pin(writes[name][0], name))
        eq = [n for n in src if num_pin(n, "B") == value and "Get Stance" in
              {_title(x) for x in _feeds(BEL.find_input_pin(n, "A"), 3)}]
        check(f"...{name} targets Stance == {value}", len(eq) == 1)
    gun = {_title(n) for n in _feeds(BEL.find_input_pin(writes[GUARD_GUN][0], GUARD_GUN))}
    arms = {_title(n) for n in _feeds(BEL.find_input_pin(writes[GUARD_ARMS][0], GUARD_ARMS))}
    check("...GuardGun targets Blocking AND HeldTwoHanded, GuardArms Blocking "
          "AND NOT HeldTwoHanded",
          {"Get Blocking", f"Get {HELD_TWO_HANDED}"} <= gun and "NOT Boolean" not in gun
          and {"Get Blocking", f"Get {HELD_TWO_HANDED}", "NOT Boolean"} <= arms,
          f"{sorted(gun)} / {sorted(arms)}")


def check_held_two_handed():
    sets = [n for n in wg if _title(n) == f"Set {HELD_TWO_HANDED}"]
    gates = {_title(_source(BEL.find_input_pin(n, "execute"))) for n in sets
             if _source(BEL.find_input_pin(n, "execute"))}
    copied = [n for n in sets if "Get TwoHanded" in
              {_title(x) for x in _feeds(BEL.find_input_pin(n, HELD_TWO_HANDED), 3)}]
    check(f"{HELD_TWO_HANDED} is copied from Held.TwoHanded, or cleared, behind "
          "one Branch -- never read off a null Held",
          len(sets) == 2 and len(copied) == 1 and gates == {"Branch"}, str(gates))
    check(f"{HELD_TWO_HANDED} defaults to False", w.get_editor_property(HELD_TWO_HANDED)
          is False)
    base = cdo(load(ITEM_BP_PATH)).get_editor_property("TwoHanded")
    check("BP_WeaponItem.TwoHanded defaults to False (pistol, food and water)",
          base is False)
    got = {s["display"]: cdo(load(s["path"])).get_editor_property("TwoHanded")
           for s in _weapon_specs()}
    check("the long guns are two-handed and the pistol and SMG are not",
          got == {"Shotgun": True, "Pistol": False, "SMG": False, "Rifle": True,
                  "Sniper": True}, str(got))


def check_kneel_written():
    """The search's kneel (stance_clips.py blends the clip in): its weight
    and where the clip is held."""
    puts = [n for n in wg if _title(n) == f"Set {POSE_KNEEL}"]
    step = _source(BEL.find_input_pin(puts[0], POSE_KNEEL)) if len(puts) == 1 else None
    check(f"BP_WeaponComponent eases {POSE_KNEEL} once a frame: FInterpTo(its own "
          f"value, target) at {KNEEL_BLEND_SPEED:g}", step is not None
          and num_pin(step, "InterpSpeed") == KNEEL_BLEND_SPEED
          and _title(_source(BEL.find_input_pin(step, "Current"))) == f"Get {POSE_KNEEL}",
          str(len(puts)))
    src = {_title(n) for n in _feeds(BEL.find_input_pin(puts[0], POSE_KNEEL))} if puts \
        else set()
    check(f"...towards {SEARCHING_VAR} AND NOT prone (a prone player searches "
          "lying down)", {f"Get {SEARCHING_VAR}", "Get Stance", "NOT Boolean"} <= src,
          str(sorted(src)))
    check(f"{SEARCHING_VAR} defaults to False, and nothing in the component "
          "writes it (the HUD's loot window does)",
          w.get_editor_property(SEARCHING_VAR) is False
          and not [n for n in wg if _title(n) == f"Set {SEARCHING_VAR}"])
    span = KNEEL_TO_S - KNEEL_FROM_S
    times = [n for n in wg if _title(n) == f"Set {KNEEL_TIME}"]
    add = _source(BEL.find_input_pin(times[0], KNEEL_TIME)) if len(times) == 1 else None
    wave = _source(BEL.find_input_pin(add, "A")) if add else None
    back = _source(BEL.find_input_pin(wave, "A")) if wave else None
    lap = _source(BEL.find_input_pin(back, "A")) if back else None
    check(f"{KNEEL_TIME} runs up and back down the clip's working stretch: "
          f"{KNEEL_FROM_S:g} + |time mod {2 * span:g} - {span:g}|",
          lap is not None and num_pin(add, "B") == KNEEL_FROM_S
          and "Abs" in _title(wave).replace(" ", "")
          and abs(num_pin(back, "B") - span) < 1e-6
          and abs(num_pin(lap, "Divisor") - 2 * span) < 1e-6,
          f"{len(times)} writes")


def run():
    check_anim_bp_poses()
    check_pose_geometry()
    check_weights_written()
    check_held_two_handed()
    check_kneel_written()
