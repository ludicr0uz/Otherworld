"""The long gun's carry: with the rifle, the sniper or the shotgun in hand and
nothing holding it up, the upper body is in the Animation Starter Pack's rifle
carry (both hands on the gun at the hip, the muzzle some 15 degrees under the
horizon; across the body at a sprint), over the motion matching's legs,
standing, walking, jogging and sprinting, and crouched (the pack's crouched
rifle at the hip, at rest and at the crouch's walk).

WHERE IT SITS
-------------
On the aim slot's source and nowhere else, after the stance blends
(stance_clips.py, whose last blend is ``down``):

    down -+--------------------------------------> LayeredBoneBlend (base)
          +-> TwoWayBlend(CarryPose, B = carry) --> Slot(DefaultSlot).Source

    carry    = TwoWayBlend(PoseCrouch, A = standing, B = crouched)
    standing = TwoWayBlend(CarrySprint, A = moving, B = Play carry_sprint)
    moving   = TwoWayBlend(Move, A = Play carry_idle, B = Play carry_jog)
    Move     = clamp(GroundSpeed / CARRY_JOG_FULL_CM_S, 0, 1)
    crouched = TwoWayBlend(Creep, A = Play carry_crouch_idle,
                           B = Play carry_crouch_walk)
    Creep    = clamp(GroundSpeed / CARRY_CROUCH_WALK_FULL_CM_S, 0, 1)

PoseCrouch is the body poses' own weight (body_pose.py), which the component
already eases to Stance == CROUCH on every machine: the carry goes down and
comes up with the body, and nothing new is declared or replicated for it.

The slot's pose is what the layered blend lays over the upper body from
spine_01, in mesh space. With no montage in it a slot hands its source on, so
the carry reaches the arms and the chest and never the legs, with no second
layered blend; and a montage (the ready pose as the gun comes up, a throw, a
pick-up) blends in over the carry and out to it, as it did over the
locomotion. The flinch's slot and the body poses are above both.

The weapon component eases the two weights on every machine's copy
(weapon_component/carry_weights.py has what they follow). The left hand is the
clips': on the fore-end within 3 cm of where the ready pose has it, measured
against the grip hand, so no IK holds it.

The blends and players are of the classes stance_clips.py owns, and it takes
them out with its own on a rerun; this runs after it, each build. A skin
without the clips (PlayerSkin.carry_idle: a checkout without the pack) gets
the two variables and no node, and the gun rides in the locomotion's hand.
"""

from combat import anim_vars as AN
from combat.body_pose import POSE_CROUCH
from combat.carry_pose_consts import (
    CARRY_CROUCH_WALK_FULL_CM_S, CARRY_JOG_FULL_CM_S, CARRY_POSE, CARRY_SPRINT)
from combat.log import _log
from combat.player_gait import GROUND_SPEED
from combat.skin import CARRY_FIELDS
from combat.stance_clips import _aim_source, _blend, _mine, _player, _pose
from uebp.graph import BEL, BGE, PIN, _assets, _connect, _node, _pin, _set, out
from uebp.layout import arrange
from uebp.nodes.math import FN_CLAMP, FN_MUL_FF
from uebp.vars import declare_missing


def carry_fields(skin):
    """The carry's five clips, standing first; Nones without them."""
    return tuple(getattr(skin, f) for f in CARRY_FIELDS)


def _move(ed, full):
    """clamp(GroundSpeed / ``full``, 0, 1), as a pin."""
    speed = ed.add_get_member_variable_node(GROUND_SPEED)
    scaled = _node(ed, FN_MUL_FF)
    _connect(out(speed, GROUND_SPEED), _pin(scaled, "A"))
    _set(scaled, "B", 1.0 / full)
    clamp = _node(ed, FN_CLAMP)
    _connect(out(scaled), _pin(clamp, "Value"))
    _set(clamp, "Min", 0.0)
    _set(clamp, "Max", 1.0)
    return out(clamp)


def patch_carry_pose(skin):
    """Put ``skin``'s carry on its aim slot's source. After patch_stance_clips,
    which took an earlier run's out."""
    bp = _assets().load_asset(skin.anim_bp)
    if not bp:
        raise RuntimeError(f"could not load {skin.anim_bp}")
    ed = BGE.get_graph_editor_by_name(bp, "AnimGraph")
    declare_missing(ed, AN.CARRY)
    if skin.carry_idle:
        clips = [_assets().load_asset(p) for p in carry_fields(skin)]
        if not all(clips):
            raise RuntimeError(f"no clip for one of {carry_fields(skin)}: run "
                               "asset_pipeline/import_asp.py")
        source = _aim_source(ed)
        fed = PIN.list_connected_pins(source)
        if len(fed) != 1:
            raise RuntimeError("the aim slot's source is fed by nothing")
        before = {n.get_name() for n in _mine(ed)}
        idle, jog, sprint, low, creep = (_pose(_player(ed, c, 1.0)) for c in clips)
        moving = _blend(ed, idle, jog, _move(ed, CARRY_JOG_FULL_CM_S))
        weights = {w: out(ed.add_get_member_variable_node(w), w)
                   for w in (CARRY_POSE, CARRY_SPRINT, POSE_CROUCH)}
        standing = _blend(ed, _pose(moving), sprint, weights[CARRY_SPRINT])
        crouched = _blend(ed, low, creep, _move(ed, CARRY_CROUCH_WALK_FULL_CM_S))
        carry = _blend(ed, _pose(standing), _pose(crouched), weights[POSE_CROUCH])
        PIN.break_pin_links(source)
        mix = _blend(ed, fed[0], _pose(carry), weights[CARRY_POSE])
        _connect(_pose(mix), source)
        ed.add_comment_to_nodes(
            f"A long gun's carry (the Animation Starter Pack's rifle set): {CARRY_POSE} "
            "puts it on the aim slot's source, so it reaches the upper body alone and "
            f"a montage in the slot plays over it; standing or jogging by GroundSpeed, "
            f"the sprint's by {CARRY_SPRINT}, the crouched pair by {POSE_CROUCH}. See "
            "Scripts/combat/carry_pose.py.",
            [n for n in _mine(ed) if n.get_name() not in before])
    arrange(ed)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{skin.anim_bp} failed to compile after the carry pose")
    _assets().save_loaded_asset(bp)
    _log(f"{bp.get_name()}: carry pose "
         + (", ".join(p.rsplit("/", 1)[1] for p in carry_fields(skin)) if skin.carry_idle
            else "none (a long gun rides in the locomotion's hand)"))
    return bp
