"""verify.server_anim -- the one IsDedicatedServer branch of the player's
and each wanderer's anim graph (task A4; combat/server_anim.py authors it,
server_anim_consts.py says what a server arm may hold).

Fails on a graph without the branch, and on one whose server arm holds a
montage slot or a blend that is not a hit-box bone's. The later animation
tasks rebuild these graphs: whatever they add goes on the client arm, and
this stays green.

``check_graph`` takes the suite's own ``check``, so the NPC verifier runs it
for the wanderers too. Proof in the running game is
probes/probe_net_server_pose.py.
"""

import unreal

from combat.server_anim_consts import (
    BRANCH_CLASS, CLIENT_PIN, FLAG_PIN, IK_CLASS, LAYER_CLASS, PLAYER, RIG_CLASS,
    SERVER_ARM_CLASSES, SERVER_PIN, SERVER_POSE_VAR, SERVER_SLOTS, SLOT_CLASS, WANDERER,
)
from uebp.graph import BEL, BGE, PIN, _assets
from uebp.pose_share import fanouts, fed as linked

ANIM_NODE = "AnimGraphNode_"


def _class(node):
    return node.get_class().get_name()


def _title(node):
    return str(BEL.get_node_title(node)).replace("\n", " ")


def _sources(node, pin=None):
    """The nodes linked into ``node``'s input ``pin`` (every input with None)."""
    pins = [BEL.find_input_pin(node, pin)] if pin else BEL.list_input_pins(node)
    return [PIN.get_owning_node(q) for p in pins if p for q in linked(p)]


def arm(root, take):
    """Every anim node the output pose is made of when the branch takes its
    ``take`` pin: upstream from ``root`` along the pose links, through the
    branch by that pin alone."""
    seen, stack = [], [root]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.append(node)
        ups = _sources(node, take) if _class(node) == BRANCH_CLASS else _sources(node)
        stack.extend(n for n in ups if _class(n).startswith(ANIM_NODE))
    return seen


def _slot(node):
    return str(node.get_editor_property("node").get_editor_property("slot_name"))


def _flag_written_once(bp):
    """Whether the event graph writes ServerPose once, from IsDedicatedServer,
    straight off BlueprintInitializeAnimation."""
    events = BGE.get_graph_editor_by_name(bp, "EventGraph")
    puts = [n for n in events.list_all_nodes() if _title(n) == f"Set {SERVER_POSE_VAR}"]
    if len(puts) != 1:
        return False, f"{len(puts)} write(s)"
    asked = [_title(n).replace(" ", "") for n in _sources(puts[0], SERVER_POSE_VAR)]
    before = [_title(n).replace(" ", "") for n in _sources(puts[0], "execute")]
    return (asked == ["IsDedicatedServer"]
            and len(before) == 1 and "BlueprintInitializeAnimation" in before[0],
            f"fed by {asked}, after {before}")


def support_hand_held_at_zero(weapon_graph_nodes, var):
    """Whether BP_WeaponComponent's one write of ``var`` hangs off the false
    arm of a Branch on IsDedicatedServer (up a short chain of single links)."""
    writes = [n for n in weapon_graph_nodes if _title(n) == f"Set {var}"]
    if len(writes) != 1:
        return False
    cur = writes[0]
    for _ in range(4):
        pins = linked(BEL.find_input_pin(cur, "execute"))
        if len(pins) != 1:
            return False
        owner = PIN.get_owning_node(pins[0])
        if _title(owner) == "Branch":
            asked = [_title(n).replace(" ", "") for n in _sources(owner, "Condition")]
            return asked == ["IsDedicatedServer"] and str(PIN.get_pin_name(pins[0])) == "else"
        cur = owner
    return False


def check_no_fanout(check, name, ed):
    """No pose of a worn anim graph is linked to two inputs."""
    twice = [f"{_title(PIN.get_owning_node(pin))} -> "
             f"{sorted(_title(PIN.get_owning_node(q)) for q in links)}"
             for pin, links in (fanouts(ed) if ed else [])]
    check(f"{name}: no pose is linked to two inputs (the engine updates what is under "
          "such a pose once per link, and plays it that many times too fast: each is a "
          "cached pose, uebp/pose_share.py)", ed is not None and not twice, str(twice))


def check_graph(check, anim_bp, kind, ik_held_at_zero=None):
    """Every check of one anim graph. ``ik_held_at_zero(var)`` answers for a
    TwoBoneIK on the server arm whose weight is ``var``."""
    bp = _assets().load_asset(anim_bp)
    name = anim_bp.rsplit("/", 1)[1]
    ed = BGE.get_graph_editor_by_name(bp, "AnimGraph") if bp else None
    nodes = list(ed.list_all_nodes()) if ed else []
    branches = [n for n in nodes if _class(n) == BRANCH_CLASS]
    roots = [n for n in nodes if _class(n) == "AnimGraphNode_Root"]
    check_no_fanout(check, name, ed)
    check(f"{name} has ONE branch on what a dedicated server needs of it (a Blend "
          "Poses by bool)", len(branches) == 1 and len(roots) == 1, f"{len(branches)} branch(es)")
    if len(branches) != 1 or len(roots) != 1:
        return
    branch = branches[0]
    flag = [_title(n) for n in _sources(branch, FLAG_PIN)]
    written, how = _flag_written_once(bp)
    default = unreal.get_default_object(bp.generated_class()).get_editor_property(SERVER_POSE_VAR)
    check(f"...on {SERVER_POSE_VAR}, false by default and written once, from "
          "IsDedicatedServer, as the anim instance starts",
          flag == [f"Get {SERVER_POSE_VAR}"] and written and default is False,
          f"the branch reads {flag}; {how}; default {default!r}")
    # The node's own struct holds the times; a pin left at "" takes them.
    times = list(branch.get_editor_property("node").get_editor_property("blend_time"))
    pins = [str(PIN.get_pin_value(BEL.find_input_pin(branch, p))) for p in ("BlendTime_0", "BlendTime_1")]
    check("...with no blend between its arms: a server never runs the arm for the eye",
          times == [0.0, 0.0] and all(float(t or 0.0) == 0.0 for t in pins), f"{times} {pins}")

    server = arm(roots[0], SERVER_PIN)
    client = arm(roots[0], CLIENT_PIN)
    check("...and the output pose comes through it on both arms",
          branch in server and branch in client)
    odd = sorted({_class(n)[len(ANIM_NODE):] for n in server if _class(n) not in SERVER_ARM_CLASSES})
    check(f"{name}'s server arm holds only what moves a hit-box bone: locomotion, "
          "stance, the aim, the flinch, the guard (no Control Rig, nothing unlisted in "
          "server_anim_consts.SERVER_ARM_CLASSES)", not odd, str(odd))
    slots = sorted(_slot(n) for n in server if _class(n) == SLOT_CLASS)
    check(f"...no montage slot but {list(SERVER_SLOTS[kind]) or 'none'}: a clip that is "
          "for the eye is never blended in there",
          slots == sorted(SERVER_SLOTS[kind]), str(slots))
    loose = [n for n in server if _class(n) == LAYER_CLASS
             and not any(_class(s) == SLOT_CLASS and _slot(s) in SERVER_SLOTS[kind]
                         for s in _sources(n))]
    check("...and no layered blend but the one such a slot feeds", not loose, f"{len(loose)}")
    for ik in (n for n in server if _class(n) == IK_CLASS):
        weights = [_title(n) for n in _sources(ik, "Alpha")]
        var = weights[0][len("Get "):] if len(weights) == 1 and weights[0].startswith("Get ") else None
        check(f"...its {_title(ik)} is in the shared tail and held at weight 0 on a "
              f"server: BP_WeaponComponent writes {var} behind NOT IsDedicatedServer",
              var is not None and ik_held_at_zero is not None and ik_held_at_zero(var),
              str(weights))
    skipped = [n for n in client if n not in server]
    eye_slots = sorted(_slot(n) for n in skipped if _class(n) == SLOT_CLASS)
    all_slots = sorted(_slot(n) for n in nodes if _class(n) == SLOT_CLASS)
    rigs = [n for n in nodes if _class(n) == RIG_CLASS]
    check("...while the client arm keeps every slot: nothing a screen showed is gone",
          sorted(eye_slots + slots) == all_slots and len(eye_slots) >= 1,
          f"skipped on a server: {eye_slots}")
    check("...and the foot IK's Control Rig, where the graph has one: on the client arm, "
          "never on the server's (it traces the ground under both feet every frame)",
          all(n in client and n not in server for n in rigs), f"{len(rigs)} Control Rig(s)")


def run():
    from combat.skin import player_skin
    from combat.support_hand import SUPPORT_HAND_VAR
    from combat.verify.common import check
    from combat.verify.fixtures import wg
    from forest_generator.npc_placement import NPC_VARIANTS

    def held(var):
        return var == SUPPORT_HAND_VAR and support_hand_held_at_zero(wg, var)

    check_graph(check, player_skin().anim_bp, PLAYER, held)
    for variant in NPC_VARIANTS:
        if _assets().does_asset_exist(variant.anim_bp):
            check_graph(check, variant.anim_bp, WANDERER)
