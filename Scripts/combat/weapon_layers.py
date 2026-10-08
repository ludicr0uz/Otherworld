"""The weapon layers' anim Blueprint (task G4): ABP_WeaponLayers, on the Game
Animation Sample's skeleton, linked into the motion-matching base
(weapon_layers_consts.py has the picture).

This file authors only the start of its graph, each build, from nothing:

    Input Pose --+--------------------------> [aim blend].BasePose --+--> [hit blend] ...
                 +--> Slot(DefaultSlot) ----> [aim blend].Blend -----+
    ... [hit blend] -> Slot(FullBodySlot) -> Output

the three slots anim_blueprint.py splices into ABP_Unarmed, with the same
spine_01 mesh-space blends (its _configure_blend). The sample's graph has no
upper-body slot of its own (its one slot is full body, and AnimationLayering
is not used by SandboxCharacter_CMC_ABP at all), so the upper body is a
layered blend per bone from spine_01, as it was. The builders that follow in
the weapons build put the rest in: stance_clips.py under the slots,
aim_pitch.py, body_pose.py and support_hand.py before the output,
server_anim.py's branch last.

    GroundSpeed   the event graph's one job: the pawn's speed over the
                  ground, cm/s, which the stance clips' Move reads. Not
                  scaled (player_gait.py): there is no blend space here.
    the montages  MAIN_MONTAGES on the class: the weapon component plays
                  into the body's main anim instance, and a linked instance
                  plays its own montages unless told to read the main one's.

link_node() and layers_class_path() are for gas_locomotion.py, which puts
the Linked Anim Graph node in the base.
"""

import unreal

from combat.anim_blueprint import (
    AIM_SLOT, FULL_BODY_SLOT, HIT_SLOT, _configure_blend, _name_slot,
)
from combat.gas_locomotion_consts import SKELETON
from combat.log import _log
from combat.player_gait import GROUND_SPEED
from combat.weapon_layers_consts import INPUT_CLASS, LAYERS_ABP, MAIN_MONTAGES
from uebp.graph import (
    BEL, BGE, PIN, _assets, _connect, _float_type, _node, _palette, _pin, out, then,
)
from uebp.layout import arrange
from uebp.nodes.actor import FN_VELOCITY
from uebp.nodes.locomotion import (
    FN_TRY_GET_PAWN_OWNER, NODE_EVENT_INIT_ANIM, NODE_EVENT_UPDATE_ANIM,
)
from uebp.nodes.math import FN_VSIZE_XY
from uebp.nodes.palette import NODE_INPUT_POSE, NODE_LAYERED_BLEND, NODE_SLOT_DEFAULT

ROOT_CLASS = "AnimGraphNode_Root"
INIT_EVENT, UPDATE_EVENT = "BlueprintInitializeAnimation", "BlueprintUpdateAnimation"


def layers_class_path():
    return f"{LAYERS_ABP}.{LAYERS_ABP.rsplit('/', 1)[1]}_C"


def _class(node):
    return node.get_class().get_name()


def _event(events, name, palette):
    """The event graph's ``name`` event: the one that is there (a new anim
    Blueprint ships its update event), or a new one."""
    found = [n for n in events.list_all_nodes()
             if name in str(BEL.get_node_title(n)).replace(" ", "")]
    if len(found) > 1:
        raise RuntimeError(f"{len(found)} {name} events")
    return found[0] if found else _palette(events, palette)


def _author_ground_speed(events):
    """GroundSpeed = the pawn's velocity over the ground, each update. Left
    alone when it is already there."""
    events.add_member_variable(GROUND_SPEED, _float_type())
    _event(events, INIT_EVENT, NODE_EVENT_INIT_ANIM)
    if any(str(BEL.get_node_title(n)) == f"Set {GROUND_SPEED}"
           for n in events.list_all_nodes()):
        return
    update = _event(events, UPDATE_EVENT, NODE_EVENT_UPDATE_ANIM)
    pawns = [n for n in events.list_all_nodes()
             if "TryGetPawnOwner" in str(BEL.get_node_title(n)).replace(" ", "")]
    pawn = pawns[0] if pawns else _node(events, FN_TRY_GET_PAWN_OWNER)
    velocity = _node(events, FN_VELOCITY)
    _connect(out(pawn), _pin(velocity, "self"))
    speed = _node(events, FN_VSIZE_XY)
    _connect(out(velocity), _pin(speed, "A"))
    put = events.add_set_member_variable_node(GROUND_SPEED)
    _connect(out(speed), _pin(put, GROUND_SPEED))
    PIN.break_pin_links(then(update))
    _connect(then(update), _pin(put, "execute"))
    events.add_comment_to_nodes(
        f"{GROUND_SPEED}: the pawn's speed over the ground, cm/s. The stance clips' "
        "Move reads it (still or walking). Scripts/combat/weapon_layers.py.",
        [pawn, velocity, speed, put])


def _author_slots(ed):
    """The graph from nothing: the input, the three slots, the output."""
    roots = [n for n in ed.list_all_nodes() if _class(n) == ROOT_CLASS]
    if len(roots) != 1:
        raise RuntimeError(f"{LAYERS_ABP}: expected one output pose, found {len(roots)}")
    stale = [n for n in ed.list_all_nodes() if _class(n) != ROOT_CLASS]
    if stale:
        ed.remove_nodes(stale)
    pose = out(_palette(ed, NODE_INPUT_POSE), "Pose")
    made = []
    for name in (AIM_SLOT, HIT_SLOT):
        slot = _name_slot(_palette(ed, NODE_SLOT_DEFAULT), name)
        blend = _palette(ed, NODE_LAYERED_BLEND)
        # One pose output drives both: the blend's base and the slot's source.
        _connect(pose, _pin(blend, "BasePose"))
        _connect(pose, _pin(slot, "Source"))
        _connect(out(slot, "Pose"), _pin(blend, "BlendPoses_0"))
        _configure_blend(blend)
        pose = out(blend, "Pose")
        made += [slot, blend]
    full = _name_slot(_palette(ed, NODE_SLOT_DEFAULT), FULL_BODY_SLOT)
    _connect(pose, _pin(full, "Source"))
    _connect(out(full, "Pose"), _pin(roots[0], "Result"))
    ed.add_comment_to_nodes(
        f"The weapon layers over the motion matching: {AIM_SLOT} (the ready pose, a "
        f"swing, a throw) and {HIT_SLOT} (the flinch) reach the upper body from "
        f"spine_01, in mesh space; {FULL_BODY_SLOT} the whole body. The pose in is the "
        "base graph's (SandboxCharacter_CMC_ABP links this graph in). "
        "Scripts/combat/weapon_layers.py.", made + [full])


def build_weapon_layers():
    """Create ABP_WeaponLayers, or wipe its anim graph, and author its start.
    The other anim graph builders of the weapons build follow."""
    eas = _assets()
    if not eas.does_asset_exist(LAYERS_ABP):
        factory = unreal.AnimBlueprintFactory()
        factory.set_editor_property("target_skeleton", eas.load_asset(SKELETON))
        factory.set_editor_property("parent_class", unreal.AnimInstance)
        folder, name = LAYERS_ABP.rsplit("/", 1)
        if not unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                name, folder, unreal.AnimBlueprint, factory):
            raise RuntimeError(f"could not create {LAYERS_ABP}")
    bp = eas.load_asset(LAYERS_ABP)
    ed = BGE.get_graph_editor_by_name(bp, "AnimGraph")
    events = BGE.get_graph_editor_by_name(bp, "EventGraph")
    if not ed or not events:
        raise RuntimeError(f"{LAYERS_ABP} lacks its AnimGraph or its EventGraph")
    _author_slots(ed)
    _author_ground_speed(events)
    arrange(ed)
    arrange(events)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{LAYERS_ABP} failed to compile")
    cdo = unreal.get_default_object(bp.generated_class())
    cdo.set_editor_property(MAIN_MONTAGES, True)
    if not BEL.compile_blueprint(bp) or not unreal.get_default_object(
            bp.generated_class()).get_editor_property(MAIN_MONTAGES):
        raise RuntimeError(f"{LAYERS_ABP} would play its own montages, not the body's")
    eas.save_loaded_asset(bp)
    inputs = [n for n in ed.list_all_nodes() if _class(n) == INPUT_CLASS]
    if len(inputs) != 1:
        raise RuntimeError(f"{LAYERS_ABP} has {len(inputs)} input poses")
    _log(f"{bp.get_name()}: {AIM_SLOT} and {HIT_SLOT} upper-body from spine_01, "
         f"{FULL_BODY_SLOT} full body, over the pose it is handed")
    return bp
