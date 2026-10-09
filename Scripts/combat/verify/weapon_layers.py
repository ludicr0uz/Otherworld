"""verify.weapon_layers -- the weapon layers over the motion-matching base
(task G4, combat/weapon_layers.py): the layers' own anim Blueprint, how the
weapon component reaches its instance on a body, and that no clip played
into a slot can pin the player where they stand.

The link in the base is verify.gas_locomotion's; what the layer graph holds
after its start (the stance clips, the pitch, the poses, the support hand,
the server branch) is each builder's own section, which reads
player_skin().anim_bp: this graph. What it looks like in a game is the pose
probes' (probe_hold_poses, probe_carry, probe_stance_clips, probe_throw,
probe_sight_hands, probe_corpse_loot).
"""

import unreal

from combat.anim_blueprint import AIM_SLOT, FULL_BODY_SLOT, HIT_SLOT, _slot_name
from combat.hit_reaction import hit_reactions
from combat.hold_pose import ROOT_MOTION
from combat.paths import (
    HOLD_ITEM_ANIM_PATH, HOLD_KNIFE_ANIM_PATH, HOLD_TORCH_ANIM_PATH, KNIFE_ANIM_PATH,
    THROW_READY_ANIM_PATH, WARD_TORCH_ANIM_PATH,
)
from combat.player_gait import GROUND_SPEED
from combat.skin import player_skin
from combat.verify.common import BEL, PIN, check, graph, load
from combat.verify.fixtures import _wg_all
from combat.weapon_layers_consts import INPUT_CLASS, LAYERS_TAG
from uebp.pose_share import fed as linked

LINKED_CALL = "GetLinkedAnimGraphInstanceByTag"
MAIN_CALL = "GetAnimInstance"
# The four graphs that write the pose variables: the sights' pitch, the pose
# weights, the support hand and the mirror of another machine's copy.
WRITERS = 4


def _cls(node):
    return node.get_class().get_name()


def _title(node):
    return str(BEL.get_node_title(node)).replace("\n", " ").replace(" ", "")


def _fed_by(node, pin):
    return [PIN.get_owning_node(q)
            for q in linked(BEL.find_input_pin(node, pin))]


def check_layer_graph(skin):
    abp = load(skin.anim_bp)
    nodes = graph(abp, "AnimGraph").list_all_nodes() if abp else []
    inputs = [n for n in nodes if _cls(n) == INPUT_CLASS]
    slots = sorted(_slot_name(n) for n in nodes if _cls(n) == "AnimGraphNode_Slot")
    check("the weapon layers' anim Blueprint takes ONE pose in (the motion matching's) "
          f"and plays the three slots over it: {AIM_SLOT}, {HIT_SLOT}, {FULL_BODY_SLOT}",
          len(inputs) == 1 and slots == sorted((AIM_SLOT, HIT_SLOT, FULL_BODY_SLOT)),
          f"{len(inputs)} input(s), slots {slots}")
    events = graph(abp).list_all_nodes() if abp else []
    sets = [n for n in events if _title(n) == f"Set{GROUND_SPEED}"]
    check(f"...and keeps {GROUND_SPEED} (what the stance clips' Move reads) from its "
          "pawn's velocity over the ground, each update",
          len(sets) == 1 and [_title(n) for n in _fed_by(sets[0], GROUND_SPEED)]
          == ["VectorLengthXY"],
          str([_title(n) for s in sets for n in _fed_by(s, GROUND_SPEED)]))


def check_reach(skin):
    """The pose variables are on the linked instance, not the mesh's own."""
    name = skin.anim_bp.rsplit("/", 1)[1]
    casts = [n for n in _wg_all if _cls(n) == "K2Node_DynamicCast"
             and name in _title(n)]
    sources = [_title(s) for c in casts for s in _fed_by(c, "Object")]
    tags = {str(PIN.get_pin_value(BEL.find_input_pin(s, "InTag")))
            for c in casts for s in _fed_by(c, "Object") if _title(s) == LINKED_CALL}
    check(f"the weapon component's {WRITERS} writers of the pose variables (the pitch, "
          f"the weights, the support hand, the mirror) cast to {name}, each from the "
          f"mesh's linked instance tagged {LAYERS_TAG}, never from its own anim instance "
          "(which is the motion matching's, and holds none of them)",
          len(casts) == WRITERS and sources == [LINKED_CALL] * WRITERS
          and tags == {LAYERS_TAG}, f"{len(casts)} cast(s) from {sources}, tags {tags}")


def check_clips_in_place(skin):
    """A montage of a clip with root motion takes the character's movement
    over: a pose held in one holds the player still (hold_pose.in_place)."""
    mesh = load(skin.mesh)
    clips = [load(p) for p in (
        skin.aim_rifle, skin.aim_pistol, skin.punch, skin.throw,
        HOLD_ITEM_ANIM_PATH, HOLD_KNIFE_ANIM_PATH, HOLD_TORCH_ANIM_PATH,
        WARD_TORCH_ANIM_PATH, THROW_READY_ANIM_PATH, KNIFE_ANIM_PATH) if p]
    clips += list(hit_reactions(mesh))
    moving = [c.get_name() if c else "missing" for c in clips
              if c is None or c.get_editor_property(ROOT_MOTION)]
    check(f"none of the {len(clips)} clips played into a slot (the ready and hold poses, "
          "the punch, the slash, the throw, the flinches) has root motion: with one out, "
          "the player can still walk", not moving, str(moving))


def run():
    skin = player_skin()
    check_clips_in_place(skin)
    if not skin.layers_tag:
        unreal.log_warning("[VERIFY] weapon_layers: the layers are in the body's own anim "
                           "Blueprint; no linked graph to check")
        return
    check_layer_graph(skin)
    check_reach(skin)
