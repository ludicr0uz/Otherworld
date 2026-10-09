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

On the motion-matching body (G5, gas_moves.py) the line is, with both
switches on:

    Locomotion -> TwoWayBlend(PoseSlide, B = Play the sample's slide loop)
        -> TwoWayBlend(PoseProne, B = crawl) -> TwoWayBlend(PoseKneel, B = kneel)

There the crouch is the motion matching's own (the locomotion arrives
crouched: gas_locomotion.py sets the sample's Stance), so no crouch blend is
authored, and the slide is the sample's loop over it, by PoseSlide (declared
here; the weapon component eases it from the movement's IsSliding).

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

from uebp.vars import declare
from combat import anim_vars as AN
from combat.aim_pitch import OWN_POSE_CLASSES, _feeding_all, _nodes_of
from combat.aim_pitch import _remove_previous as _remove_pitch_chain
from combat.anim_blueprint import AIM_SLOT, _slot_node
from combat.body_pose import KNEEL_TIME, POSE_CROUCH, POSE_KNEEL, POSE_PRONE, move_alpha
from combat.gas_moves import crouch_on, slide_on
from combat.gas_moves_tuning import POSE_SLIDE, SLIDE_CLIP
from combat.log import _log
from uebp.graph import BEL, BGE, PIN, _assets, _connect, _palette, _pin, _set, out
from uebp.layout import arrange

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
# The crawl's still frame (Mixamo's zombie crawl): a frame of the stroke with
# the hips at the middle of their bob, so lying still they are PRONE_HIPS_CM up.
PRONE_REST_S = 0.96


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


def _player(ed, clip, rate):
    node = _palette(ed, f"Animation|Sequences|Play'{clip.get_name()}'")
    inner = node.get_editor_property("node")
    inner.set_editor_property("play_rate", rate)
    inner.set_editor_property("loop_animation", True)
    node.set_editor_property("node", inner)
    back = node.get_editor_property("node")
    if back.get_editor_property("sequence") != clip or \
            abs(back.get_editor_property("play_rate") - rate) > 1e-6:
        raise RuntimeError(f"the player for {clip.get_name()} did not keep its settings")
    return node


def _evaluator(ed, clip, time):
    """``time``: seconds into the clip, or a pin that says."""
    node = _palette(ed, f"Animation|Sequences|Evaluate'{clip.get_name()}'")
    if node.get_editor_property("node").get_editor_property("sequence") != clip:
        raise RuntimeError(f"the evaluator did not take {clip.get_name()}")
    if isinstance(time, (int, float)):
        _set(node, "ExplicitTime", time)
    else:
        _connect(time, _pin(node, "ExplicitTime"))
    return node


def _blend(ed, a, b, alpha):
    node = _palette(ed, "Animation|Blends|TwoWayBlend")
    _connect(a, _pin(node, "A"))
    _connect(b, _pin(node, "B"))
    _connect(alpha, _pin(node, "Alpha"))
    return node


def _pose(node):
    return out(node, "Pose")


def unpatch_stance_clips(skin):
    """Take the stance blends out of ``skin``'s anim BP, without compiling.

    First thing in the build, before anything compiles the BP: rerunning
    import_quaternius.py regenerates the clips, which leaves the old players
    playing nothing, and an anim BP with an empty player does not compile."""
    bp = _assets().load_asset(skin.anim_bp)
    if bp:
        _remove_previous(BGE.get_graph_editor_by_name(bp, "AnimGraph"))


def retire_player_patches(anim_bp):
    """Take the player's own patches out of ``anim_bp``, which the player no
    longer runs: the stance clips, and the chain before the output (the aim's
    pitch, the body poses, the support hand). What anim_blueprint.py put in
    stays. For ABP_Unarmed once the player's layers are in another graph: it
    is the mannequin fallback's, and what the creatures' copies are made of."""
    bp = _assets().load_asset(anim_bp)
    ed = BGE.get_graph_editor_by_name(bp, "AnimGraph")
    roots = _nodes_of(ed, "AnimGraphNode_Root")
    if not _mine(ed) and not any(_nodes_of(ed, c) for c in OWN_POSE_CLASSES):
        return
    _remove_previous(ed)
    _remove_pitch_chain(ed, roots[0])
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{anim_bp} failed to compile without the player's patches")
    _assets().save_loaded_asset(bp)
    _log(f"{bp.get_name()}: the player's stance clips, pitch, poses and support hand "
         "taken out (the player runs another anim Blueprint)")


def patch_stance_clips(skin):
    """Blend ``skin``'s crouch, crawl and kneel clips over its locomotion. Re-running
    replaces the previous blends; a skin without clips only loses them."""
    bp = _assets().load_asset(skin.anim_bp)
    if not bp:
        raise RuntimeError(f"could not load {skin.anim_bp}")
    ed = BGE.get_graph_editor_by_name(bp, "AnimGraph")
    base = _remove_previous(ed)
    ed.remove_member_variable(POSE_SLIDE)
    if skin.stance_clips:
        clips = {f: _assets().load_asset(getattr(skin, f))
                 for f in ("crouch_idle", "crouch_walk", "prone_crawl", "search_kneel")}
        if slide_on():
            clips["slide"] = _assets().load_asset(SLIDE_CLIP)
            declare(ed, AN.SLIDE)
        missing = [f for f, c in clips.items() if not c]
        if missing:
            raise RuntimeError(f"no clip for {missing}: run import_quaternius.py"
                               + (" (the slide's: import_gas.py)" if "slide" in missing else ""))
        consumers = PIN.list_connected_pins(base)
        PIN.break_pin_links(base)

        move = move_alpha(ed)
        crawl = _blend(ed, _pose(_evaluator(ed, clips["prone_crawl"], PRONE_REST_S)),
                       _pose(_player(ed, clips["prone_crawl"], PRONE_CRAWL_RATE)), move)
        weights = {w: out(ed.add_get_member_variable_node(w), w)
                   for w in (POSE_PRONE, POSE_KNEEL, KNEEL_TIME)
                   + (() if crouch_on() else (POSE_CROUCH,))}
        if crouch_on():
            # The crouch is the motion matching's own (the sample's crouch
            # set, picked on Stance: gas_locomotion.py): the locomotion
            # arrives crouched, and no clip goes over its legs.
            low = base
        else:
            crouch = _blend(ed, _pose(_player(ed, clips["crouch_idle"], 1.0)),
                            _pose(_player(ed, clips["crouch_walk"], CROUCH_WALK_RATE)),
                            move)
            low = _pose(_blend(ed, base, _pose(crouch), weights[POSE_CROUCH]))
        if slide_on():
            # The slide, over the crouch it is made in: the sample's loop,
            # which holds its own root (gas_moves_tuning.SLIDE_CLIP).
            slide = ed.add_get_member_variable_node(POSE_SLIDE)
            low = _pose(_blend(ed, low, _pose(_player(ed, clips["slide"], 1.0)),
                               out(slide, POSE_SLIDE)))
        lying = _blend(ed, low, _pose(crawl), weights[POSE_PRONE])
        kneel = _evaluator(ed, clips["search_kneel"], weights[KNEEL_TIME])
        down = _blend(ed, _pose(lying), _pose(kneel), weights[POSE_KNEEL])
        for c in consumers:
            _connect(_pose(down), c)
        ed.add_comment_to_nodes(
            "The low stances as clips (Quaternius UAL): "
            + ("the crouch is the motion matching's own, " if crouch_on() else
               f"{POSE_CROUCH} blends in the crouch, ")
            + (f"{POSE_SLIDE} the sample's slide over it, " if slide_on() else "")
            + f"{POSE_PRONE} the crawl, still or walking by GroundSpeed, "
            f"and {POSE_KNEEL} the kneel over a body being searched, held at "
            f"{KNEEL_TIME}. See Scripts/combat/stance_clips.py.", _mine(ed))

    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{skin.anim_bp} failed to compile after the stance clips")
    _assets().save_loaded_asset(bp)
    _log(f"{bp.get_name()}: stance clips "
         + (f"{skin.crouch_idle.rsplit('/', 1)[1]}, {skin.crouch_walk.rsplit('/', 1)[1]}, "
            f"{skin.prone_crawl.rsplit('/', 1)[1]}, "
            f"{skin.search_kneel.rsplit('/', 1)[1]}" if skin.stance_clips
            else "none (procedural crouch and prone)"))
    return bp
