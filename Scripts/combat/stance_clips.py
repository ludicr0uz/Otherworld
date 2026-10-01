"""The player's crouch, crawl and kneel as clips: the Quaternius Universal
Animation Library's crouch (still and walking), its face-down swim and its
kneel, blended over the locomotion by PoseCrouch/PoseProne (the weights the
procedural poses read) and PoseKneel (the search of a body).

WHERE IT SITS
-------------
Between the locomotion state machine and everything that reads it (the aim
slot and the upper-body layered blend), so the aim layer, the hit slot and
the procedural poses all apply on top of a crouched or lying body:

    Locomotion -> TwoWayBlend(PoseCrouch, B = crouch) -> TwoWayBlend(PoseProne,
        B = crawl) -> TwoWayBlend(PoseKneel, B = kneel)
        -> DefaultSlot, LayeredBoneBlend (base)

    crouch = TwoWayBlend(Move, A = Play crouch_idle, B = Play crouch_walk)
    crawl  = TwoWayBlend(Move, A = Evaluate prone_crawl at PRONE_REST_S,
                               B = Play prone_crawl)
    kneel  = Evaluate search_kneel at KneelTime
    Move   = clamp(GroundSpeed / MOVE_FULL_CM_S, 0, 1)   (body_pose.move_alpha)

The kneel clip goes down on a knee, works with both hands and stands again. A
player looping it would stand up every five seconds, so it is evaluated: the
weapon component runs KneelTime up and back down the working stretch
(KNEEL_FROM_S..KNEEL_TO_S) for as long as the search lasts, and PoseKneel's
ease is what kneels and stands. Under the aim layer like the other two, so
empty hands rummage and a held gun stays held over the kneeling legs.

Lying still is the crawl held on one frame (arms reaching ahead, legs
straight): the pack has no prone idle. The clip's hips lie below the feet's
root, and body_pose.py lifts them (more while crawling, when the kick drops
the knees) and tips an aimed upper body forward: the aim layer blends in mesh space, so with a
gun in hand the chest is upright over the crawling hips until it does.

This module owns every TwoWayBlend and sequence node in the player's AnimGraph;
nothing else authors one, so a rerun takes all of them out and rejoins the
locomotion to what it fed. A skin without clips (PlayerSkin.stance_clips) gets
nothing here and keeps the procedural crouch and prone.
"""

from combat.aim_pitch import _feeding_all, _nodes_of
from combat.anim_blueprint import AIM_SLOT, _slot_node
from combat.body_pose import KNEEL_TIME, POSE_CROUCH, POSE_KNEEL, POSE_PRONE, move_alpha
from combat.graph import (
    BEL, BGE, PIN, _assets, _at, _connect, _log, _palette, _pin, _set,
)

BLEND_CLASS = "AnimGraphNode_TwoWayBlend"
PLAYER_CLASS = "AnimGraphNode_SequencePlayer"
EVALUATOR_CLASS = "AnimGraphNode_SequenceEvaluator"
OWN_CLASSES = (BLEND_CLASS, PLAYER_CLASS, EVALUATOR_CLASS)

# Play rates. The crouch walk covers about 55 cm/s where the player crouches at
# 270, so it plays at the most it can before the steps read as a scurry (the
# rule mixamo_paths.RATE_SCALE_RANGE set for the zombie); the feet slide the
# rest. The swim's stroke is read as a pull of about 80 cm, so it plays at
# 120 / 80.
CROUCH_WALK_RATE = 2.0
PRONE_CRAWL_RATE = 1.5
# The crawl's still frame: the arms reaching ahead, the legs straight behind.
PRONE_REST_S = 0.5


def _mine(ed):
    return [n for c in OWN_CLASSES for n in _nodes_of(ed, c)]


def _aim_source(ed):
    slot = _slot_node(ed, AIM_SLOT)
    if slot is None:
        raise RuntimeError(f"no {AIM_SLOT} slot: run patch_anim_blueprint first")
    return _pin(slot, "Source")


def _remove_previous(ed):
    """Take out an earlier run's blends and rejoin the locomotion to what the
    last blend fed. Returns the locomotion's output pin."""
    mine = _mine(ed)
    names = {n.get_name() for n in mine}
    src = PIN.list_connected_pins(_aim_source(ed))
    if not src:
        raise RuntimeError(f"the {AIM_SLOT} slot is fed by nothing")
    out = src[0]
    if PIN.get_owning_node(out).get_name() not in names:
        return out
    consumers = PIN.list_connected_pins(out)
    base = out
    # Down the A inputs of the stance blends to the pose that is not ours.
    while PIN.get_owning_node(base).get_name() in names:
        fed = PIN.list_connected_pins(_pin(PIN.get_owning_node(base), "A"))
        if not fed:
            raise RuntimeError("an earlier stance blend has nothing on A; "
                               "refusing to guess the locomotion")
        base = fed[0]
    ed.remove_nodes(mine + _feeding_all(mine))
    for c in consumers:
        _connect(base, c)
    return base


def _player(ed, clip, rate, x, y):
    node = _at(_palette(ed, f"Animation|Sequences|Play'{clip.get_name()}'"), x, y)
    inner = node.get_editor_property("node")
    inner.set_editor_property("play_rate", rate)
    inner.set_editor_property("loop_animation", True)
    node.set_editor_property("node", inner)
    back = node.get_editor_property("node")
    if back.get_editor_property("sequence") != clip or \
            abs(back.get_editor_property("play_rate") - rate) > 1e-6:
        raise RuntimeError(f"the player for {clip.get_name()} did not keep its settings")
    return node


def _evaluator(ed, clip, time, x, y):
    """``time``: seconds into the clip, or a pin that says."""
    node = _at(_palette(ed, f"Animation|Sequences|Evaluate'{clip.get_name()}'"), x, y)
    if node.get_editor_property("node").get_editor_property("sequence") != clip:
        raise RuntimeError(f"the evaluator did not take {clip.get_name()}")
    if isinstance(time, (int, float)):
        _set(node, "ExplicitTime", time)
    else:
        _connect(time, _pin(node, "ExplicitTime"))
    return node


def _blend(ed, a, b, alpha, x, y):
    node = _at(_palette(ed, "Animation|Blends|TwoWayBlend"), x, y)
    _connect(a, _pin(node, "A"))
    _connect(b, _pin(node, "B"))
    _connect(alpha, _pin(node, "Alpha"))
    return node


def _pose(node):
    return _pin(node, "Pose", is_input=False)


def unpatch_stance_clips(skin):
    """Take the stance blends out of ``skin``'s anim BP, without compiling.

    First thing in the build, before anything compiles the BP: rerunning
    import_quaternius.py regenerates the clips, which leaves the old players
    playing nothing, and an anim BP with an empty player does not compile."""
    bp = _assets().load_asset(skin.anim_bp)
    if bp:
        _remove_previous(BGE.get_graph_editor_by_name(bp, "AnimGraph"))


def patch_stance_clips(skin):
    """Blend ``skin``'s crouch, crawl and kneel clips over its locomotion. Re-running
    replaces the previous blends; a skin without clips only loses them."""
    bp = _assets().load_asset(skin.anim_bp)
    if not bp:
        raise RuntimeError(f"could not load {skin.anim_bp}")
    ed = BGE.get_graph_editor_by_name(bp, "AnimGraph")
    base = _remove_previous(ed)
    if skin.stance_clips:
        clips = {f: _assets().load_asset(getattr(skin, f))
                 for f in ("crouch_idle", "crouch_walk", "prone_crawl", "search_kneel")}
        missing = [f for f, c in clips.items() if not c]
        if missing:
            raise RuntimeError(f"no clip for {missing}: run import_quaternius.py")
        consumers = PIN.list_connected_pins(base)
        PIN.break_pin_links(base)

        x, y = -2200, -900
        move = move_alpha(ed, x, y + 700)
        crouch = _blend(ed, _pose(_player(ed, clips["crouch_idle"], 1.0, x, y)),
                        _pose(_player(ed, clips["crouch_walk"], CROUCH_WALK_RATE,
                                      x, y + 200)), move, x + 400, y + 100)
        crawl = _blend(ed, _pose(_evaluator(ed, clips["prone_crawl"], PRONE_REST_S,
                                            x, y + 400)),
                       _pose(_player(ed, clips["prone_crawl"], PRONE_CRAWL_RATE,
                                     x, y + 550)), move, x + 400, y + 450)
        weights = {w: _pin(_at(ed.add_get_member_variable_node(w), x + 400, y + 800 + i * 120),
                           w, is_input=False)
                   for i, w in enumerate((POSE_CROUCH, POSE_PRONE, POSE_KNEEL, KNEEL_TIME))}
        low = _blend(ed, base, _pose(crouch), weights[POSE_CROUCH], x + 800, y + 200)
        lying = _blend(ed, _pose(low), _pose(crawl), weights[POSE_PRONE], x + 1100, y + 300)
        kneel = _evaluator(ed, clips["search_kneel"], weights[KNEEL_TIME], x + 1100, y + 700)
        down = _blend(ed, _pose(lying), _pose(kneel), weights[POSE_KNEEL], x + 1400, y + 400)
        for c in consumers:
            _connect(_pose(down), c)
        ed.add_comment_to_nodes(
            f"The low stances as clips (Quaternius UAL): {POSE_CROUCH} blends in the "
            f"crouch, {POSE_PRONE} the crawl, each still or walking by GroundSpeed, "
            f"and {POSE_KNEEL} the kneel over a body being searched, held at "
            f"{KNEEL_TIME}. See Scripts/combat/stance_clips.py.", _mine(ed))

    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{skin.anim_bp} failed to compile after the stance clips")
    _assets().save_loaded_asset(bp)
    _log(f"{bp.get_name()}: stance clips "
         + (f"{skin.crouch_idle.rsplit('/', 1)[1]}, {skin.crouch_walk.rsplit('/', 1)[1]}, "
            f"{skin.prone_crawl.rsplit('/', 1)[1]}, "
            f"{skin.search_kneel.rsplit('/', 1)[1]}" if skin.stance_clips
            else "none (procedural crouch and prone)"))
    return bp
