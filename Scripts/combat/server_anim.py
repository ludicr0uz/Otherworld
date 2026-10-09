"""The one IsDedicatedServer branch of an anim graph (task A4): a dedicated
server evaluates only what moves a hit-box bone for a reason of the game's.
server_anim_consts.py says what that is, and why; this authors it, for the
player's anim Blueprint (the weapons build) and each wanderer's (the NPC
build).

THE BRANCH
----------
A Blend Poses by bool on ServerPose, spliced into the local-space chain
round the slots a server does not play (server_anim_consts.SERVER_SLOTS):

    player    ... -> [aim blend: DefaultSlot] -> [hit blend: HitSlot] -+-> Slot(FullBodySlot) -> ControlRig --(false)--+
                                                                       +---------------------------------------(true)---+-> LocalToComponent -> ...

    wanderer  ... -> [DefaultSlot] -> [HitSlot] -+-> Slot(FullBodySlot) --(false)--+
                                                 +-------------------------(true)---+-> Output

A blend by bool neither updates nor evaluates the arm it does not take (its
blend times are 0). What a server skips is the player's foot IK (the Control
Rig, which traces the ground under both feet: 5.5 ms of a 32-player server's
frame) and FullBodySlot. The aim's and the flinch's blends are on both arms,
for two reasons (server_anim_consts.py has both at length):

  * each moves a hit box a shooter is aiming at;
  * it was once a matter of wiring too: these graphs feed a blend's output to
    the next blend's base AND to that blend's slot, the engine updates a node
    once per link that reaches it, and so an arm that left a blend out played
    the locomotion under it at another speed than a client's. That is gone:
    such a pose is a cached pose now, updated once a frame however many read
    it (uebp/pose_share.py), which this patch puts in as its last step.

It is where the next thing for the eye goes: a node put on the client arm is
never run on a server, and verify/server_anim.py fails a server arm that
holds anything unlisted.

The player's component-space tail (the guard, the hips' lift, the aim's
pitch, the support hand's IK) is shared too: there is no blend by bool for a
component-space pose. Each of its nodes costs nothing at weight 0, and the
one that is for the eye alone, the support hand's IK, is never given a
weight on a server (weapon_component/support_hand.py).

ServerPose is the anim Blueprint's own variable, written once by the event
graph's BlueprintInitializeAnimation from IsDedicatedServer.

ORDER
-----
Last of the anim graph's patches, and unpatch_server_anim first of them: the
other builders (anim_blueprint.py, aim_pitch.py, body_pose.py,
stance_clips.py) then meet the chain they were written against. The cached
poses go the same way: the unpatch takes them out (pose_share.unshare), so
the builders follow plain links, and the patch puts them back before its
compile (pose_share.share), which is the last one before a body runs the
graph. The later
animation tasks rebuild these graphs; whatever they put in goes on the
client arm, and verify/server_anim.py must stay green.
"""

from combat.anim_blueprint import AIM_SLOT, _slot_name, _slot_node
from combat.log import _log
from combat.server_anim_consts import (
    BRANCH_CLASS, CLIENT_PIN, COSMETIC_CLASSES, FLAG_PIN, LAYER_CLASS, SERVER_PIN,
    SERVER_POSE_VAR, SERVER_SLOTS, SLOT_CLASS,
)
from uebp.graph import BEL, BGE, PIN, _assets, _connect, _declare, _node, _palette, _pin, _set, out, then
from uebp.layout import arrange
from uebp.nodes.palette import NODE_BLEND_BY_BOOL
from uebp.nodes.system import FN_IS_DEDICATED_SERVER
from uebp.pose_share import share, unshare
from uebp.vars import BOOL

INIT_EVENT = "BlueprintInitializeAnimation"


def _class(node):
    return node.get_class().get_name()


def _fed(pin):
    return list(PIN.list_connected_pins(pin))


def _graphs(anim_bp):
    bp = _assets().load_asset(anim_bp)
    if not bp:
        raise RuntimeError(f"could not load {anim_bp}")
    ed = BGE.get_graph_editor_by_name(bp, "AnimGraph")
    events = BGE.get_graph_editor_by_name(bp, "EventGraph")
    if not ed or not events:
        raise RuntimeError(f"{anim_bp} has no AnimGraph or no EventGraph")
    return bp, ed, events


def _flag_writes(events):
    return [n for n in events.list_all_nodes()
            if str(BEL.get_node_title(n)) == f"Set {SERVER_POSE_VAR}"]


def _remove(ed, events):
    """Take the branch and the flag's write out, joining what each split,
    and the cached poses with them (the plain links back). Returns how many
    branches there were."""
    unshare(ed)
    branches = [n for n in ed.list_all_nodes() if _class(n) == BRANCH_CLASS]
    for branch in branches:
        client = _fed(_pin(branch, CLIENT_PIN))
        onward = _fed(out(branch, "Pose"))
        flags = [PIN.get_owning_node(q) for q in _fed(_pin(branch, FLAG_PIN))]
        ed.remove_nodes([branch] + flags)
        if not client or not onward:
            raise RuntimeError("the server branch was wired to nothing on one side; "
                               "refusing to guess how the chain went")
        for pin in onward:
            _connect(client[0], pin)
    for put in _flag_writes(events):
        before = _fed(_pin(put, "execute"))
        after = _fed(then(put))
        asked = [PIN.get_owning_node(q) for q in _fed(_pin(put, SERVER_POSE_VAR))]
        events.remove_nodes([put] + asked)
        for a in before:
            for b in after:
                _connect(a, b)
    return len(branches)


def unpatch_server_anim(anim_bp):
    """Before the other anim graph builders run: the chain without the branch.
    Not compiled or saved here; the builders that follow do both."""
    _bp, ed, events = _graphs(anim_bp)
    if _remove(ed, events):
        _log(f"{anim_bp.rsplit('/', 1)[1]}: server branch taken out for the rebuild")


def _slot_fed(node, kind):
    """Whether ``node`` is a layered blend one of the server's slots feeds."""
    return _class(node) == LAYER_CLASS and any(
        _class(PIN.get_owning_node(q)) == SLOT_CLASS
        and _slot_name(PIN.get_owning_node(q)) in SERVER_SLOTS[kind]
        for p in BEL.list_input_pins(node) for q in _fed(p))


def _eye_segment(ed, kind):
    """(the pose pin the server arm takes, the last node for the eye).

    From the aim blend (the layered blend DefaultSlot feeds), down the pose
    line for as long as the next node is a slot, a layered blend or the
    Control Rig. A blend's
    output feeds both the next blend's base and that blend's slot, so the line
    follows the blend. The server takes the pose after the last blend one of
    its own slots feeds (before the aim blend, with none), and what follows on
    the line is for the eye.
    """
    aim_slot = _slot_node(ed, AIM_SLOT)
    fed = _fed(out(aim_slot, "Pose")) if aim_slot else []
    aim_blend = PIN.get_owning_node(fed[0]) if fed else None
    if aim_blend is None or _class(aim_blend) != LAYER_CLASS:
        raise RuntimeError(f"no layered blend after Slot({AIM_SLOT}): run "
                           "patch_anim_blueprint first")
    line = [aim_blend]
    while True:
        nxt = [PIN.get_owning_node(q) for q in _fed(out(line[-1], "Pose"))
               if _class(PIN.get_owning_node(q)) in COSMETIC_CLASSES]
        if not nxt:
            break
        line.append(next((n for n in nxt if _class(n) == LAYER_CLASS), nxt[0]))
    kept = 0
    while kept < len(line) and _slot_fed(line[kept], kind):
        kept += 1
    if kept == len(line):
        raise RuntimeError("nothing for the eye follows the server's slots: there "
                           "is no arm for a server to skip")
    if kept:
        return out(line[kept - 1], "Pose"), line[-1]
    base = _fed(_pin(aim_blend, "BasePose"))
    if not base:
        raise RuntimeError("the aim blend has no base pose")
    return base[0], line[-1]


def _author_flag(events):
    """ServerPose = IsDedicatedServer, once, first thing the anim instance does."""
    inits = [n for n in events.list_all_nodes()
             if INIT_EVENT in str(BEL.get_node_title(n)).replace(" ", "")]
    if len(inits) != 1:
        raise RuntimeError(f"expected one {INIT_EVENT} event, found {len(inits)}")
    after = _fed(then(inits[0]))
    put = events.add_set_member_variable_node(SERVER_POSE_VAR)
    asked = _node(events, FN_IS_DEDICATED_SERVER)
    _connect(out(asked), _pin(put, SERVER_POSE_VAR))
    PIN.break_pin_links(then(inits[0]))
    _connect(then(inits[0]), _pin(put, "execute"))
    for pin in after:
        _connect(then(put), pin)
    events.add_comment_to_nodes(
        f"{SERVER_POSE_VAR}: this machine is a dedicated server, which draws nothing. "
        "The AnimGraph's one branch reads it (Scripts/combat/server_anim.py).",
        [put, asked])


def patch_server_anim(anim_bp, kind):
    """Splice the server branch into ``anim_bp`` (see the module docstring).
    ``kind`` is whose graph it is (server_anim_consts.PLAYER or WANDERER).
    Re-running replaces the previous branch."""
    bp, ed, events = _graphs(anim_bp)
    _remove(ed, events)
    _declare(ed, SERVER_POSE_VAR, BOOL())

    tap, last = _eye_segment(ed, kind)
    eye_out = out(last, "Pose")
    onward = _fed(eye_out)
    if not onward:
        raise RuntimeError("the last node for the eye feeds nothing")
    PIN.break_pin_links(eye_out)

    branch = _palette(ed, NODE_BLEND_BY_BOOL)
    flag = ed.add_get_member_variable_node(SERVER_POSE_VAR)
    _connect(out(flag, SERVER_POSE_VAR), _pin(branch, FLAG_PIN))
    _connect(tap, _pin(branch, SERVER_PIN))
    _connect(eye_out, _pin(branch, CLIENT_PIN))
    # No blend between the arms: the flag never changes, and a blend time
    # would have both arms run for its length at every spawn.
    # On the node's own struct and on its pins: a compile takes the pins', and
    # a pin left at its default is not saved, so the struct must agree.
    inner = branch.get_editor_property("node")
    inner.set_editor_property("blend_time", [0.0, 0.0])
    branch.set_editor_property("node", inner)
    _set(branch, "BlendTime_0", 0.0)
    _set(branch, "BlendTime_1", 0.0)
    for pin in onward:
        _connect(out(branch, "Pose"), pin)
    ed.add_comment_to_nodes(
        f"The one IsDedicatedServer branch ({SERVER_POSE_VAR}): a dedicated server takes "
        "the pose from before the nodes that are for the eye alone (the full-body slot, "
        "the foot IK), which it then neither updates nor evaluates; what is left moves the hit "
        "bodies and the gun. A machine with a screen takes the other arm. A new node "
        "for the eye goes on that arm. See Scripts/combat/server_anim.py.", [branch, flag])
    _author_flag(events)
    # Last, over the whole graph: no pose is left linked to two inputs.
    shared = share(ed)

    arrange(ed)
    arrange(events)
    if not BEL.compile_blueprint(bp):
        raise RuntimeError(f"{anim_bp} failed to compile after the server branch")
    _assets().save_loaded_asset(bp)
    _log(f"{bp.get_name()}: a dedicated server plays {list(SERVER_SLOTS[kind]) or 'no slot'} "
         f"and skips the chain's last {_class(last)[len('AnimGraphNode_'):]}; "
         f"{shared} cached pose(s) where a pose feeds two inputs")
    return bp
