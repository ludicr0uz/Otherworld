"""verify.stance_clips -- the crouch, the crawl and the kneel as clips
(combat/stance_clips.py): the player's AnimGraph blends them over the
locomotion by PoseCrouch, PoseProne and PoseKneel, the first two still or
walking by GroundSpeed; the crouch clips put the body down with the feet on
the ground; the crawl, with body_pose's lifts, lies on the ground still and
just clears it crawling (a real prone, PlayerSkin.prone_idle, lies there by
a few cm of lift and with none more crawling); and the kneel is down for the whole stretch it is
held over.

A skin without the clips (the mannequin, or no import_quaternius.py yet) is
checked to carry no stance blend: it poses both stances procedurally, which
verify.body_pose checks.
"""

import unreal

from asset_pipeline.rig_util import _bone_world
from asset_pipeline.ik_follow import off_cm
from combat.weapon_layers_consts import INPUT_CLASS
from combat.anim_blueprint import AIM_SLOT, _slot_name
from combat.body_pose import (
    KNEEL_FROM_S, KNEEL_TIME, KNEEL_TO_S, MOVE_FULL_CM_S, POSE_CROUCH, POSE_KNEEL,
    POSE_PRONE, PRONE_CRAWL_LIFT_CM, PRONE_HIPS_CM, PRONE_MOVING, _ref, crawl_hips_z,
    pose_plan,
)
from combat.carry_pose_consts import CARRY_POSE
from combat.gas_moves import crouch_on, slide_on
from combat.gas_moves_tuning import POSE_SLIDE, SLIDE_CLIP
from combat.skin import player_skin
from combat.stance_clips import (
    BLEND_CLASS, CROUCH_WALK_RATE, EVALUATOR_CLASS, OWN_CLASSES, PLAYER_CLASS,
    PRONE_CRAWL_RATE, PRONE_REST_S, crawl_by_direction, prone_nodes,
)
from combat.crawl_consts import PRONE_LOOP_RATE
from combat.verify.crawl_direction import check_direction_clips, check_direction_tree
from combat.verify.common import BEL, PIN, check, graph, load, num_pin
from uebp.pose_share import fed as linked

# The prone capsule is 40 cm half-height: nothing of a lying body above it.
PRONE_TOP_CM = 80.0
# How far a bone of the lying body may sit under the ground: a centimetre or
# two of a knee or a foot pressed into grass.
SINK_CM = 3.0
# Mixamo's crawl rocks the hips about 7 cm either side of their middle.
CRAWL_BOB_CM = 8.0
# A real prone (PlayerSkin.prone_idle) lies on the ground as it is: its hips
# hold within this of their middle, the lift that seats it is no more than
# this, and lying still its head is this far under the capsule's top at least.
PRONE_BOB_CM = 2.0
PRONE_LIFT_MAX_CM = 6.0
PRONE_HEAD_CLEAR_CM = 30.0
# The kneel's knee on the ground: its joint sits this far under it at most on
# the adventurer's shorter shin (measured 3.9), where the clip's own rig rests
# the kneecap on the ground.
KNEEL_SINK_CM = 5.0


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ")


def _up(node, pin):
    fed = linked(BEL.find_input_pin(node, pin))
    return PIN.get_owning_node(fed[0]) if fed else None


def _feeds(node, pin, limit=12):
    seen, stack = [], [BEL.find_input_pin(node, pin)]
    while stack and len(seen) < limit:
        for q in linked(stack.pop()):
            n = PIN.get_owning_node(q)
            if n not in seen:
                seen.append(n)
                stack.extend(BEL.list_input_pins(n))
    return {_title(n) for n in seen}


def _cls(node):
    return node.get_class().get_name() if node else None


def _clip_of(node):
    seq = node.get_editor_property("node").get_editor_property("sequence") if node else None
    return seq.get_path_name().split(".")[0] if seq else None


def _rate(node):
    return node.get_editor_property("node").get_editor_property("play_rate")


def _moved_by_speed(blend):
    return {"Get GroundSpeed"} <= _feeds(blend, "Alpha") and \
        not ({f"Get {POSE_CROUCH}", f"Get {POSE_PRONE}"} & _feeds(blend, "Alpha"))


def check_stance_graph():
    skin = player_skin()
    abp = load(skin.anim_bp)
    nodes = graph(abp, "AnimGraph").list_all_nodes()
    ours = [n for n in nodes if _cls(n) in OWN_CLASSES]
    if not skin.stance_clips:
        check(f"{abp.get_name()}: no stance clips on this rig, and no stance "
              "blend left in its AnimGraph", not ours, str(len(ours)))
        return
    # The crouch's two blends and two players are not there while the crouch
    # is the motion matching's (G5); the slide adds a blend and a player.
    # A crawl by direction (P2) is eight players where the forward one was,
    # under seven blends more.
    dirs = 7 if crawl_by_direction(skin) else 0
    # A long gun's carry (carry_pose.py, checked by verify.carry_pose) is five
    # blends and five players of the same classes, after the stances.
    carry = 5 if skin.carry_idle else 0
    blends = 5 - (2 if crouch_on() else 0) + (1 if slide_on() else 0) + dirs + carry
    # A prone idle is a player where the held crawl was an evaluator.
    idle = 1 if skin.prone_idle else 0
    players = 3 - (2 if crouch_on() else 0) + (1 if slide_on() else 0) + idle + dirs + carry
    check(f"{abp.get_name()}: {blends} stance blends, {players} players, "
          f"{2 - idle} evaluator(s)"
          + (" (no crouch clip: the crouch is the motion matching's)" if crouch_on() else "")
          + (" (and the slide's)" if slide_on() else "")
          + (" (and the carry's five of each)" if carry else ""),
          sorted(_cls(n) for n in ours) == sorted([BLEND_CLASS] * blends
                                                  + [PLAYER_CLASS] * players
                                                  + [EVALUATOR_CLASS] * (2 - idle)),
          str(sorted(_cls(n) for n in ours)))

    slot = next((n for n in nodes if _cls(n) == "AnimGraphNode_Slot"
                 and _slot_name(n) == AIM_SLOT), None)
    down = _up(slot, "Source") if slot else None
    carried = _cls(down) == BLEND_CLASS and _title(_up(down, "Alpha")) == f"Get {CARRY_POSE}"
    if carried:
        # The carry's blend is on the slot's source alone, over the stances'.
        down = _up(down, "A")
    kneel = _up(down, "B") if _cls(down) == BLEND_CLASS else None
    check(f"the aim slot reads the kneel: {POSE_KNEEL} blends in the kneel clip, "
          f"held at {KNEEL_TIME}",
          _cls(down) == BLEND_CLASS and _title(_up(down, "Alpha")) == f"Get {POSE_KNEEL}"
          and _cls(kneel) == EVALUATOR_CLASS and _clip_of(kneel) == skin.search_kneel
          and _title(_up(kneel, "ExplicitTime")) == f"Get {KNEEL_TIME}",
          f"{_cls(down)} <- {_clip_of(kneel)} @ {_title(_up(kneel, 'ExplicitTime')) if kneel else None}")
    lying = _up(down, "A") if _cls(down) == BLEND_CLASS else None
    under = _up(lying, "A") if _cls(lying) == BLEND_CLASS else None
    slide = under if slide_on() else None
    if slide_on():
        under = _up(slide, "A") if _cls(slide) == BLEND_CLASS else None
        played = _up(slide, "B") if _cls(slide) == BLEND_CLASS else None
        check(f"the slide: {POSE_SLIDE} blends the sample's slide loop in over the "
              "crouch, under the crawl",
              _cls(slide) == BLEND_CLASS and _title(_up(slide, "Alpha")) == f"Get {POSE_SLIDE}"
              and _cls(played) == PLAYER_CLASS and _clip_of(played) == SLIDE_CLIP,
              f"{_cls(slide)} <- {_clip_of(played)}")
    low = None if crouch_on() else under
    loco = under if crouch_on() else (_up(low, "A") if _cls(low) == BLEND_CLASS else None)
    # The locomotion: the state machine, or in the weapon layers' graph the
    # pose the motion matching hands it (combat/weapon_layers.py).
    check("...over the stance blends: PoseProne over "
          + ("the locomotion, which crouches itself (no PoseCrouch blend)" if crouch_on()
             else "PoseCrouch over the locomotion"),
          _cls(lying) == BLEND_CLASS and _title(_up(lying, "Alpha")) == f"Get {POSE_PRONE}"
          and (crouch_on() or (_cls(low) == BLEND_CLASS
                               and _title(_up(low, "Alpha")) == f"Get {POSE_CROUCH}"))
          and _cls(loco) == (INPUT_CLASS if skin.layers_tag else "AnimGraphNode_StateMachine"),
          f"{_cls(lying)} <- {_cls(low)} <- {_cls(loco)}")
    feeds = linked(BEL.find_output_pin(down, "Pose")) if down else []
    check("...and so does the upper-body layered blend's base (the aim layer "
          "rides on the crouched, lying or kneeling body)",
          sorted(_cls(PIN.get_owning_node(p)) for p in feeds)
          == ["AnimGraphNode_LayeredBoneBlend",
              BLEND_CLASS if carried else "AnimGraphNode_Slot"],
          str([_cls(PIN.get_owning_node(p)) for p in feeds]))
    if not ((low or crouch_on()) and lying):
        return

    crouch = None
    if not crouch_on():
        crouch = _up(low, "B")
        still, walk = (_up(crouch, "A"), _up(crouch, "B")) if crouch else (None, None)
        check("crouch: the still clip, and the walking one as GroundSpeed rises",
              _cls(crouch) == BLEND_CLASS and _moved_by_speed(crouch)
              and _clip_of(still) == skin.crouch_idle and _clip_of(walk) == skin.crouch_walk
              and abs(_rate(walk) - CROUCH_WALK_RATE) < 1e-6,
              f"{_clip_of(still)} / {_clip_of(walk)}")
    crawl = _up(lying, "B")
    rest, moving = (_up(crawl, "A"), _up(crawl, "B")) if crawl else (None, None)
    want_still, want_moving = prone_nodes(skin)

    def is_node(node, want):
        cls, clip, rate = want
        return (_cls(node) == cls and _clip_of(node) == clip
                and (rate is None or abs(_rate(node) - rate) < 1e-6))

    if crawl_by_direction(skin):
        check_direction_tree(skin, crawl, is_node(rest, want_still))
    elif skin.prone_idle:
        check(f"prone: the idle loop still, and the crawl loop played at "
              f"{PRONE_LOOP_RATE:g}x as GroundSpeed rises",
              _cls(crawl) == BLEND_CLASS and _moved_by_speed(crawl)
              and is_node(rest, want_still) and is_node(moving, want_moving)
              and skin.prone_idle != skin.prone_crawl,
              f"{_clip_of(rest)} / {_clip_of(moving)} @ {_rate(moving) if moving else None}")
    else:
        check(f"prone: the crawl held at {PRONE_REST_S:g} s still, and played at "
              f"{PRONE_CRAWL_RATE:g}x as GroundSpeed rises",
              _cls(crawl) == BLEND_CLASS and _moved_by_speed(crawl)
              and is_node(rest, want_still) and num_pin(rest, "ExplicitTime") == PRONE_REST_S
              and is_node(moving, want_moving),
              f"{_clip_of(rest)} @ {num_pin(rest, 'ExplicitTime') if rest else None}")
    if crouch_on() and crawl_by_direction(skin):
        return   # no blend of this graph reads Move: the crawl's is CrawlMove
    clamp = _up(crouch or crawl, "Alpha") if (crouch or crawl) else None
    scale = _up(clamp, "Value") if clamp else None
    check(f"...Move is clamp(GroundSpeed x 1/{MOVE_FULL_CM_S:g}, 0, 1)",
          clamp is not None and num_pin(clamp, "Min") == 0.0 and num_pin(clamp, "Max") == 1.0
          and scale is not None and abs(num_pin(scale, "B") - 1.0 / MOVE_FULL_CM_S) < 1e-6)


def _samples(clip, bones, lift=0.0, n=16):
    length = clip.get_editor_property("sequence_length")
    return [{b: _bone_world(clip, b, length * i / n) + _z(lift) for b in bones}
            for i in range(n + 1)]


def _z(z):
    return unreal.Vector(0.0, 0.0, z)


def check_crouch_clips():
    skin = player_skin()
    if not skin.stance_clips or crouch_on():
        return
    b = skin.pose_bones
    feet = [b["foot_l"], b["foot_r"]]
    stand = load(skin.idle)
    head = "Head"
    stand_head = max(p[head].z for p in _samples(stand, [head], n=4))
    stand_feet = min(p[f].z for p in _samples(stand, feet, n=4) for f in feet)
    for field in ("crouch_idle", "crouch_walk"):
        poses = _samples(load(getattr(skin, field)), [head] + feet)
        top = max(p[head].z for p in poses)
        low = min(p[f].z for p in poses for f in feet)
        check(f"{field}: the head comes down at least 40 cm and the feet stay "
              "on the ground (within 8 cm of standing)",
              stand_head - top >= 40.0 and abs(low - stand_feet) < 8.0,
              f"head {stand_head:.0f} -> {top:.0f}, feet {stand_feet:.1f} -> {low:.1f}")


def check_crawl_on_ground():
    skin = player_skin()
    if not skin.stance_clips:
        return
    b = skin.pose_bones
    crawl = load(skin.prone_crawl)
    hips = b["hips"]
    lying = ["Head", hips, b["spine"], b["upperarm_l"], b["upperarm_r"],
             b["hand_l"], b["hand_r"], b["calf_l"], b["calf_r"], b["foot_l"], b["foot_r"]]
    clip_z = crawl_hips_z(skin)
    rest_lift = PRONE_HIPS_CM - clip_z
    if skin.prone_idle:
        _check_real_prone(skin, crawl, lying, rest_lift)
        return
    hips_z = [p[hips].z for p in _samples(crawl, [hips])]
    check(f"the crawl's hips stay within {CRAWL_BOB_CM:g} cm of where body_pose lifts them "
          f"from ({clip_z:g} cm, measured off this body's clip)",
          all(abs(z - clip_z) < CRAWL_BOB_CM for z in hips_z),
          f"{min(hips_z):.1f}..{max(hips_z):.1f}")

    length = crawl.get_editor_property("sequence_length")
    still = {k: _bone_world(crawl, k, PRONE_REST_S % length) + _z(rest_lift)
             for k in lying}
    check(f"prone, still: the hips lie {PRONE_HIPS_CM:g} cm up and nothing is "
          f"under the ground or above {PRONE_TOP_CM:g} cm",
          abs(still[hips].z - PRONE_HIPS_CM) < 1.0
          and min(p.z for p in still.values()) > -SINK_CM
          and max(p.z for p in still.values()) < PRONE_TOP_CM,
          f"{min(p.z for p in still.values()):.1f}..{max(p.z for p in still.values()):.1f}")
    check("prone, still: the head is ahead of the hips and the feet behind them",
          still["Head"].y > still[hips].y + 30
          and all(still[b[f"foot_{s}"]].y < still[hips].y - 50 for s in "lr"),
          f"head {still['Head'].y:.0f}, feet {still[b['foot_l']].y:.0f}")

    legs = [b["calf_l"], b["calf_r"], b["foot_l"], b["foot_r"]]
    poses = _samples(crawl, lying, lift=rest_lift + PRONE_CRAWL_LIFT_CM)
    knees = min(p[k].z for p in poses for k in legs)
    top = max(p[k].z for p in poses for k in lying)
    check(f"prone, crawling: {PRONE_CRAWL_LIFT_CM:g} cm more keeps the kicking "
          f"knees and feet out of the ground, and all of it under {PRONE_TOP_CM:g} cm",
          knees > -SINK_CM and top < PRONE_TOP_CM, f"legs from {knees:.1f}, top {top:.1f}")


def _check_real_prone(skin, crawl, lying, lift):
    """The prone that has an idle of its own: both loops lie on the ground
    by the one small lift, in place, with no root motion."""
    b = skin.pose_bones
    hips = b["hips"]
    idle = load(skin.prone_idle)
    ref = _ref(load(skin.anim_bp).get_editor_property("target_skeleton"))
    plan = pose_plan(skin, ref)
    check(f"prone: body_pose lifts the hips {lift:.1f} cm (no more than "
          f"{PRONE_LIFT_MAX_CM:g}) and nothing more while crawling",
          0.0 <= lift <= PRONE_LIFT_MAX_CM and not any(s[0] == PRONE_MOVING for s in plan)
          and [round(s[4][2], 2) for s in plan if s[0] == POSE_PRONE] == [round(lift, 2)],
          f"{[s[0] for s in plan if s[4]]}")
    for label, clip in (("still", idle), ("crawling", crawl)):
        poses = _samples(clip, lying + ["root"], lift=lift)
        low = min(p[k].z for p in poses for k in lying)
        top = max(p["Head"].z for p in poses)
        hz = [p[hips].z for p in poses]
        travel = max(max(getattr(p[k], a) for p in poses) - min(getattr(p[k], a) for p in poses)
                     for k in ("root", hips) for a in "xy")
        check(f"prone, {label}: the hips lie {PRONE_HIPS_CM:g} cm up within "
              f"{PRONE_BOB_CM:g}, no hand, knee or foot is under the ground, the head "
              f"is {PRONE_HEAD_CLEAR_CM:g} cm under the capsule's top ({PRONE_TOP_CM:g})",
              all(abs(z - PRONE_HIPS_CM) < PRONE_BOB_CM for z in hz) and low > 0.0
              and top < PRONE_TOP_CM - PRONE_HEAD_CLEAR_CM,
              f"hips {min(hz):.1f}..{max(hz):.1f}, lowest {low:.1f}, head {top:.1f}")
        check(f"prone, {label}: the clip is in place (root and hips travel under "
              "0.5 cm: no slide forward and snap back), has no root motion, and its IK "
              "feet are on its feet (the base graph's Leg IK folds the legs to them)",
              travel < 0.5 and not clip.get_editor_property("enable_root_motion")
              and off_cm(clip) < 0.5, f"{travel:.2f} cm, IK feet {off_cm(clip):.2f} cm off")
    if crawl_by_direction(skin):
        check_direction_clips(skin, lying, lift)
    still = _samples(idle, lying, lift=lift)[0]
    check("prone, still: the head is ahead of the hips and the feet behind them",
          still["Head"].y > still[hips].y + 30
          and all(still[b[f"foot_{s}"]].y < still[hips].y - 50 for s in "lr"),
          f"head {still['Head'].y:.0f}, feet {still[b['foot_l']].y:.0f}")


def check_kneel_clip():
    skin = player_skin()
    if not skin.stance_clips:
        return
    b = skin.pose_bones
    hips = b["hips"]
    legs = [b["calf_l"], b["calf_r"], b["foot_l"], b["foot_r"]]
    stand_hips = min(p[hips].z for p in _samples(load(skin.idle), [hips], n=4))
    clip = load(skin.search_kneel)
    length = clip.get_editor_property("sequence_length")
    held = [{k: _bone_world(clip, k, KNEEL_FROM_S + (KNEEL_TO_S - KNEEL_FROM_S) * i / 12)
             for k in [hips] + legs} for i in range(13)]
    top = max(p[hips].z for p in held)
    low = min(p[k].z for p in held for k in legs)
    check(f"search_kneel: held over {KNEEL_FROM_S:g}..{KNEEL_TO_S:g} s of its "
          f"{length:.1f} s, the hips stay at least 40 cm down and no knee or foot "
          f"joint goes more than {KNEEL_SINK_CM:g} cm under the ground",
          0.0 < KNEEL_FROM_S < KNEEL_TO_S < length and stand_hips - top >= 40.0
          and low > -KNEEL_SINK_CM, f"hips {stand_hips:.0f} -> {top:.0f}, legs from {low:.1f}")


def run():
    check_stance_graph()
    check_crouch_clips()
    check_kneel_clip()
    check_crawl_on_ground()
