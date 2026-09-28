"""The ABP_Unarmed patch: the upper-body layered blends and the three slots.

THE AIM POSE (the part with a real constraint behind it)
--------------------------------------------------------
The project ships a full Mannequin animation set: MF_Rifle_Idle_ADS,
MF_Pistol_Idle_ADS, directional rifle/pistol walk and jog, aim offsets. What it
does *not* ship is any Anim Blueprint that uses them -- ABP_Unarmed is the only
one, and it drives the unarmed locomotion state machines only.

Authoring a rifle locomotion state machine from Python is not possible: UBlendSpace
exposes no sample-authoring API at all, so the directional walk/jog sets cannot be
assembled into the blend spaces a locomotion graph would need.

What *is* possible is playing an animation into a slot. ABP_Unarmed's AnimGraph
has exactly one Slot node, DefaultSlot, sitting full-body between the locomotion
state machine and the Control Rig. Played as-is, an ADS idle would override the
legs too and the character would slide around in a frozen aim pose.

So patch_anim_blueprint() inserts a Layered blend per bone between the state
machine and the Control Rig: base pose = locomotion, blend pose = DefaultSlot,
branch filter = spine_01. DefaultSlot becomes upper-body-only, and
PlaySlotAnimationAsDynamicMontage(MF_Rifle_Idle_ADS, "DefaultSlot") then puts
the arms and chest in the ready pose while the legs keep walking, running and
jumping normally. One new node, one rewire, and it compiles.

Consequence worth knowing: every montage played on DefaultSlot is now
upper-body-only for this skeleton. Nothing in this project plays a full-body
montage (the NPC despawns rather than playing a death animation), but a future
death or knockdown animation would need its own slot.

The three slots (DefaultSlot, HitSlot, FullBodySlot) are named here because
this is the file that splices them into ABP_Unarmed.
"""

import unreal

from combat.graph import (
    BEL, BGE, PIN, _assets, _at, _connect, _log, _palette, _pin,
)
from combat.paths import ABP_PATH


# The slot the death montage used to play into. Kept, and still spliced into
# ABP_Unarmed by patch_anim_blueprint, because it is the only full-body slot
# either character has and the next thing that needs to override the legs will
# want it -- DefaultSlot is filtered to the upper body so the aim pose leaves
# the legs walking.
FULL_BODY_SLOT = "FullBodySlot"
# The flinch slot, between the aim blend and FullBodySlot. Why it is a slot of
# its own, and what that does not buy, is at the top of hit_reaction.py.
HIT_SLOT = "HitSlot"

# The bone the upper body blend starts at. spine_01 is the lowest spine joint,
# so arms + chest follow the aim pose and the hips and legs keep locomotion.
UPPER_BODY_ROOT = "spine_01"
UPPER_BODY_BLEND_DEPTH = 4
AIM_SLOT = "DefaultSlot"


# ─── The AnimGraph patch ─────────────────────────────────────────────────────

def _configure_blend(blend):
    """Branch filter, weight and blend space on a LayeredBoneBlend node.

    Everything here lives on the inner FAnimNode struct rather than on the graph
    node, and the struct that comes back from a read is a *copy* -- so it has to
    be read, changed, and written back wholesale.
    """
    bone = unreal.BranchFilter()
    bone.set_editor_property("bone_name", UPPER_BODY_ROOT)
    bone.set_editor_property("blend_depth", UPPER_BODY_BLEND_DEPTH)
    layer = unreal.InputBlendPose()
    layer.set_editor_property("branch_filters", [bone])
    inner = blend.get_editor_property("node")
    inner.set_editor_property("layer_setup", [layer])
    inner.set_editor_property("blend_weights", [1.0])
    inner.set_editor_property("mesh_space_rotation_blend", True)
    blend.set_editor_property("node", inner)
    back = blend.get_editor_property("node")
    if not back.get_editor_property("mesh_space_rotation_blend"):
        raise RuntimeError("the blend stayed in local space — the aim pose would "
                           "inherit the locomotion hips and aim off to one side")


def _slot_name(node):
    """The slot a Slot node plays, as a plain string."""
    return str(node.get_editor_property("node").get_editor_property("slot_name"))


def _name_slot(node, wanted):
    """Rename a Slot node's inner slot, and prove it took.

    The palette entry for a slot node is spelled with the slot's own name
    (``Slot'DefaultSlot'``) and only *registered* names appear there, so a new
    slot cannot be asked for directly. The way round it is the way the editor
    does it anyway: spawn the DefaultSlot entry, rename the node's inner slot,
    and let the compiler register the new name -- UAnimGraphNode_Slot::
    BakeDataDuringCompilation calls Skeleton->RegisterSlotNode on whatever name
    it finds, so one compile is all the registration takes.
    """
    inner = node.get_editor_property("node")
    inner.set_editor_property("slot_name", wanted)
    node.set_editor_property("node", inner)
    if _slot_name(node) != wanted:
        raise RuntimeError(f"the slot kept the name {_slot_name(node)!r}")
    return node


def _anim_nodes(ed, class_name):
    return [n for n in ed.list_all_nodes()
            if n.get_class().get_name() == class_name]


def _slot_node(ed, name):
    """The Slot node playing ``name``, or None."""
    for n in _anim_nodes(ed, "AnimGraphNode_Slot"):
        if _slot_name(n) == name:
            return n
    return None


def _ensure_hit_slot(ed, aim_blend):
    """Splice Slot(HitSlot) and a second layered blend in after the aim blend.

        aim_blend --+--------------------------> LayeredBoneBlend.BasePose --+
                    |                                                        |--> on
                    +--> Slot(HitSlot) --------> LayeredBoneBlend.Blend -----+

    filtered on the same spine root, so a hit reaction reaches the chest, the
    arms and the head and never the legs.

    It has to be a slot of its own rather than DefaultSlot -- see the block at
    HIT_SLOT. The short version: DefaultSlot is occupied for the whole time a
    weapon is held (the ready pose is a 9999-loop dynamic montage) and playing a
    second montage into one slot stops the first, so reacting there would cost
    the player their aim pose permanently.

    Both of the second blend's inputs are the SAME pose whenever nothing is
    playing -- a slot with no montage passes its source straight through -- so
    the whole insertion is a no-op at rest whatever weight it carries.

    Re-running is safe: an existing HitSlot is left wired where it is and only
    its settings are re-applied, so this never stacks a third blend on the
    chain.
    """
    already = _slot_node(ed, HIT_SLOT)
    if already:
        feeds = PIN.list_connected_pins(_pin(already, "Pose", is_input=False))
        if not feeds:
            raise RuntimeError(f"Slot({HIT_SLOT}) is in the graph but wired to "
                               "nothing — refusing to guess how it was meant to go")
        _configure_blend(PIN.get_owning_node(feeds[0]))
        return already

    out = _pin(aim_blend, "Pose", is_input=False)
    downstream = list(PIN.list_connected_pins(out))
    if not downstream:
        raise RuntimeError("the aim blend feeds nothing; graph is not what we expect")

    slot = _name_slot(_at(_palette(ed, f"Animation|Montage|Slot'{AIM_SLOT}'"),
                          -280, 900), HIT_SLOT)
    blend = _at(_palette(ed, "Animation|Blends|Layeredblendperbone"), -20, 900)

    PIN.break_pin_links(out)
    # One pose output legally drives more than one input, so the aim blend
    # reaches both the new blend's base and the slot's source with no cached
    # pose pair in between.
    _connect(out, _pin(blend, "BasePose"))
    _connect(out, _pin(slot, "Source"))
    _connect(_pin(slot, "Pose", is_input=False), _pin(blend, "BlendPoses_0"))
    for pin in downstream:
        _connect(_pin(blend, "Pose", is_input=False), pin)
    _configure_blend(blend)
    return slot


def _ensure_full_body_slot(ed):
    """Insert Slot(FullBodySlot) between the blend and the ControlRig.

        ... -> LayeredBoneBlend -> Slot(FullBodySlot) -> ControlRig -> Root

    A slot with nothing playing passes its input pose straight through, so this
    is free until something plays into it -- and when the death montage does, it
    lands *after* the upper-body blend and therefore replaces the whole body,
    legs included. Playing a death into DefaultSlot instead folds the chest over
    legs that are still standing in the locomotion pose.

    Nothing plays into it today -- the death is a ragdoll and the hit reaction
    is upper body, in HitSlot -- and a slot with nothing playing costs nothing,
    so it stays as the one full-body override either character has.

    See _name_slot for how a slot that is not in the palette gets made at all.
    """
    rigs = _anim_nodes(ed, "AnimGraphNode_ControlRig")
    if len(rigs) != 1:
        raise RuntimeError(f"expected one ControlRig node, found {len(rigs)}")
    rig = rigs[0]

    feeding = PIN.list_connected_pins(_pin(rig, "Source"))
    if not feeding:
        raise RuntimeError("ControlRig.Source is unconnected; graph is not what "
                           "we expect")
    upstream = PIN.get_owning_node(feeding[0])

    if upstream.get_class().get_name() == "AnimGraphNode_Slot":
        # Already inserted by an earlier run: re-apply the name and leave the
        # wiring alone, so re-running never stacks a second slot on the chain.
        return _name_slot(upstream, FULL_BODY_SLOT)

    slot = _name_slot(_at(_palette(ed, f"Animation|Montage|Slot'{AIM_SLOT}'"),
                          -140, 620), FULL_BODY_SLOT)
    PIN.break_pin_links(_pin(rig, "Source"))
    _connect(_pin(upstream, "Pose", is_input=False), _pin(slot, "Source"))
    _connect(_pin(slot, "Pose", is_input=False), _pin(rig, "Source"))
    return slot


def patch_anim_blueprint():
    """Make DefaultSlot upper-body-only in ABP_Unarmed.

    ABP_Unarmed ships as:

        StateMachine(locomotion) -> Slot(DefaultSlot) -> ControlRig -> Root

    so anything played into DefaultSlot replaces the *whole* body and the
    character slides around frozen in the aim pose. This inserts a layered blend
    so the slot only reaches the upper body:

        StateMachine --+-------------------> LayeredBoneBlend.BasePose ---+
                       |                                                  |--> ControlRig
                       +--> Slot(DefaultSlot) -> LayeredBoneBlend.Blend ---+

    with a spine_01 branch filter. Legs keep walking; arms and chest take the
    ready pose.

    The blend is set to **mesh space rotation blending**, and that is the
    difference between a gun that aims where you look and one that does not.
    In the default (local space) mode the aim pose's arms are hung off whatever
    the locomotion pose's hips are doing, so the ready pose loses its own pelvis
    yaw -- measured at runtime, that put the barrel a constant 21 degrees to the
    player's left (body yaw 44.6, gun yaw 23.3, every frame). In mesh space the
    blended bones keep the ready pose's own component-space orientation, so the
    arms aim where they were authored to aim no matter which way the hips are
    turned.

    There are now THREE slots on the chain, in this order, and the order is the
    design:

        StateMachine -> [aim blend: DefaultSlot]     the ready pose, upper body
                     -> [hit blend: HitSlot]         the flinch, upper body
                     -> Slot(FullBodySlot)           nothing, kept for the legs
                     -> ControlRig -> Root

    HitSlot sits downstream of DefaultSlot so a reaction overrides the ready
    pose for its second and blends back into it, rather than replacing it -- see
    _ensure_hit_slot, and the HIT_SLOT block, for why it could not just share
    DefaultSlot.

    Re-running is safe, and re-running after an edit to *this* function is too:
    an existing blend is left wired as it is but its settings are re-applied.
    """
    bp = _assets().load_asset(ABP_PATH)
    if not bp:
        raise RuntimeError(f"could not load {ABP_PATH}")
    ed = BGE.get_graph_editor_by_name(bp, "AnimGraph")
    if not ed:
        raise RuntimeError("ABP_Unarmed has no AnimGraph")

    aim_slot = _slot_node(ed, AIM_SLOT)
    if aim_slot is None:
        raise RuntimeError(f"ABP_Unarmed has no Slot({AIM_SLOT}); graph is not "
                           "what we expect")

    # The aim blend is the one DefaultSlot feeds, found by following the wire
    # rather than by taking the first LayeredBoneBlend in the list: there are
    # two of them now and list order is not graph order.
    fed = PIN.list_connected_pins(_pin(aim_slot, "Pose", is_input=False))
    aim_blend = PIN.get_owning_node(fed[0]) if fed else None
    fresh = aim_blend is None or \
        aim_blend.get_class().get_name() != "AnimGraphNode_LayeredBoneBlend"

    if fresh:
        # First run on a stock ABP_Unarmed: StateMachine -> Slot -> ControlRig.
        rigs = _anim_nodes(ed, "AnimGraphNode_ControlRig")
        if len(rigs) != 1:
            raise RuntimeError(f"expected one ControlRig in ABP_Unarmed's "
                               f"AnimGraph, found {len(rigs)}")
        rig = rigs[0]
        feeding = PIN.list_connected_pins(_pin(aim_slot, "Source"))
        if not feeding:
            raise RuntimeError("Slot.Source is unconnected; graph is not what "
                               "we expect")
        loco = PIN.get_owning_node(feeding[0])

        aim_blend = _at(_palette(ed, "Animation|Blends|Layeredblendperbone"),
                        -420, 620)
        # A pose output legally drives more than one input here, so the
        # locomotion pose reaches both the blend's base and the slot's source
        # without needing a cached-pose pair.
        _connect(_pin(loco, "Pose", is_input=False), _pin(aim_blend, "BasePose"))
        PIN.break_pin_links(_pin(rig, "Source"))
        _connect(_pin(aim_slot, "Pose", is_input=False),
                 _pin(aim_blend, "BlendPoses_0"))
        _connect(_pin(aim_blend, "Pose", is_input=False), _pin(rig, "Source"))

    _configure_blend(aim_blend)
    _ensure_hit_slot(ed, aim_blend)
    _ensure_full_body_slot(ed)

    if not BEL.compile_blueprint(bp):
        raise RuntimeError("ABP_Unarmed failed to compile after the blend patch")
    _assets().save_loaded_asset(bp)

    # Both blends, not just the aim one: an unresolvable branch filter
    # contributes no bones, so a hit blend that lost its filter would play every
    # reaction at zero weight -- invisible, and indistinguishable in the log
    # from a reaction that never fired.
    blends = _anim_nodes(ed, "AnimGraphNode_LayeredBoneBlend")
    filters = [str(f.get_editor_property("bone_name"))
               for b in blends
               for l in b.get_editor_property("node").get_editor_property("layer_setup")
               for f in l.get_editor_property("branch_filters")]
    if len(blends) != 2 or filters != [UPPER_BODY_ROOT] * 2:
        raise RuntimeError(f"expected two {UPPER_BODY_ROOT} blends, got "
                           f"{len(blends)} with filters {filters}")
    slots = sorted(_slot_name(n) for n in _anim_nodes(ed, "AnimGraphNode_Slot"))
    if slots != sorted((AIM_SLOT, HIT_SLOT, FULL_BODY_SLOT)):
        raise RuntimeError(f"ABP_Unarmed's slots are {slots}")
    _log(f"ABP_Unarmed: {AIM_SLOT} and {HIT_SLOT} are upper-body only (from "
         f"{UPPER_BODY_ROOT}), {FULL_BODY_SLOT} is full body")
    return bp
