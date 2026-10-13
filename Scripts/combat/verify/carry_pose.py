"""verify.carry_pose -- a long gun's carry (combat/carry_pose.py): the weapon
layers' AnimGraph blends the Animation Starter Pack's rifle carry onto the aim
slot's source alone, by CarryPose, standing or jogging by GroundSpeed and the
sprint's by CarrySprint, and the crouched pair by PoseCrouch; the clips are on
the worn skeleton, in place, with the hands under the ready pose's; and the
component eases the two weights, CarryPose only for the pose the long guns
share, standing or crouched. probes/probe_carry.py shows the same in the game.

A skin without the clips is checked to have no carry blend and no weight
written.
"""

from asset_pipeline.rig_util import _bone_world
from combat.anim_blueprint import AIM_SLOT, _slot_name
from combat.carry_pose import carry_fields
from combat.body_pose import POSE_CROUCH
from combat.carry_pose_consts import (
    CARRY_ALSO_VAR, CARRY_BLEND_SPEED, CARRY_CROUCH_WALK_FULL_CM_S, CARRY_FOR_VAR,
    CARRY_JOG_FULL_CM_S, CARRY_POSE, CARRY_SPRINT, CARRY_SPRINT_BLEND_SPEED,
)
from combat.finger_pose import clips as finger_clips
from combat.gas_moves import slide_on, traversal_on
from combat.gas_moves_tuning import DOING_VAR
from combat.skin import player_skin
from combat.stance_clips import BLEND_CLASS, PLAYER_CLASS
from combat.verify.common import BEL, PIN, check, graph, load, num_pin
from combat.verify.fixtures import w, wg
from combat.weapon_component.stance import PRONE
from combat.weapon_specs import _weapon_specs
from uebp.pose_share import fed as linked

# The carry's grip hand is this far under the ready pose's at least (measured
# 29 cm standing and jogging, 40 at the sprint).
HAND_DROP_CM = 20.0
SLOT_CLASS = "AnimGraphNode_Slot"
LAYERED_CLASS = "AnimGraphNode_LayeredBoneBlend"


def _title(n):
    return str(BEL.get_node_title(n)).replace("\n", " ") if n else None


def _cls(n):
    return n.get_class().get_name() if n else None


def _up(node, pin):
    fed = linked(BEL.find_input_pin(node, pin)) if node else []
    return PIN.get_owning_node(fed[0]) if fed else None


def _behind(pin, limit=40):
    """The titles of every node behind a data pin."""
    seen, stack = [], [pin]
    while stack and len(seen) < limit:
        for q in PIN.list_connected_pins(stack.pop()):
            n = PIN.get_owning_node(q)
            if n not in seen:
                seen.append(n)
                stack.extend(x for x in BEL.list_input_pins(n)
                             if str(PIN.get_pin_name(x)) != "execute")
    return seen


def _clip_of(node):
    seq = node.get_editor_property("node").get_editor_property("sequence") if node else None
    return seq.get_path_name().split(".")[0] if seq else None


def carry_mix(nodes):
    """The blend on the aim slot's source that CarryPose weights, or None."""
    slot = next((n for n in nodes if _cls(n) == SLOT_CLASS and _slot_name(n) == AIM_SLOT),
                None)
    mix = _up(slot, "Source")
    return mix if _cls(mix) == BLEND_CLASS and _title(_up(mix, "Alpha")) == f"Get {CARRY_POSE}" \
        else None


def check_carry_graph():
    skin = player_skin()
    abp = load(skin.anim_bp)
    nodes = graph(abp, "AnimGraph").list_all_nodes()
    mix = carry_mix(nodes)
    if not skin.carry_idle:
        check(f"{abp.get_name()}: no carry clips on this rig, and no carry blend on "
              "its aim slot's source", mix is None)
        return
    check(f"{abp.get_name()}: the aim slot's source is a blend weighted by {CARRY_POSE}",
          mix is not None)
    if mix is None:
        return
    feeds = [_cls(PIN.get_owning_node(p)) for p in linked(BEL.find_output_pin(mix, "Pose"))]
    check("...which feeds that slot and nothing else: the carry reaches the upper "
          "body through the slot's layered blend, never the legs",
          feeds == [SLOT_CLASS], str(feeds))
    under = _up(mix, "A")
    onward = sorted(_cls(PIN.get_owning_node(p))
                    for p in linked(BEL.find_output_pin(under, "Pose"))) if under else []
    check("...over the stance blends' pose (on A), which is still the layered "
          "blend's base",
          onward == sorted([BLEND_CLASS, LAYERED_CLASS]), str(onward))
    by_stance = _up(mix, "B")
    carry, low = _up(by_stance, "A"), _up(by_stance, "B")
    check(f"...the carry is the crouched one by {POSE_CROUCH} over the standing one",
          _cls(by_stance) == BLEND_CLASS
          and _title(_up(by_stance, "Alpha")) == f"Get {POSE_CROUCH}"
          and _cls(carry) == BLEND_CLASS and _cls(low) == BLEND_CLASS,
          f"{_title(_up(by_stance, 'Alpha'))}: {_cls(carry)}, {_cls(low)}")
    moving, sprint = _up(carry, "A"), _up(carry, "B")
    check(f"...the standing one is the sprint's clip by {CARRY_SPRINT} over the moving one",
          _cls(carry) == BLEND_CLASS and _title(_up(carry, "Alpha")) == f"Get {CARRY_SPRINT}"
          and _cls(sprint) == PLAYER_CLASS and _clip_of(sprint) == skin.carry_sprint,
          f"{_title(_up(carry, 'Alpha'))} <- {_clip_of(sprint)}")
    idle, jog = _up(moving, "A"), _up(moving, "B")
    speed = _behind(BEL.find_input_pin(moving, "Alpha")) if moving else []
    scale = next((num_pin(n, "B") for n in speed if num_pin(n, "B")), None)
    check("...and the moving one is the standing clip, the jog's by GroundSpeed "
          f"(all of it from {CARRY_JOG_FULL_CM_S:g} cm/s)",
          _cls(moving) == BLEND_CLASS and "Get GroundSpeed" in {_title(n) for n in speed}
          and scale is not None and abs(scale - 1.0 / CARRY_JOG_FULL_CM_S) < 1e-6
          and (_clip_of(idle), _clip_of(jog)) == (skin.carry_idle, skin.carry_jog),
          f"{_clip_of(idle)}, {_clip_of(jog)}, x{scale}")
    rest, creep = _up(low, "A"), _up(low, "B")
    speed = _behind(BEL.find_input_pin(low, "Alpha")) if low else []
    scale = next((num_pin(n, "B") for n in speed if num_pin(n, "B")), None)
    check("...the crouched one is the crouched clip at rest, the crouch walk's by "
          f"GroundSpeed (all of it from {CARRY_CROUCH_WALK_FULL_CM_S:g} cm/s)",
          "Get GroundSpeed" in {_title(n) for n in speed}
          and scale is not None and abs(scale - 1.0 / CARRY_CROUCH_WALK_FULL_CM_S) < 1e-6
          and (_clip_of(rest), _clip_of(creep))
          == (skin.carry_crouch_idle, skin.carry_crouch_walk),
          f"{_clip_of(rest)}, {_clip_of(creep)}, x{scale}")
    players = [n for n in (idle, jog, sprint, rest, creep) if _cls(n) == PLAYER_CLASS]
    check("...each looping at its own rate",
          len(players) == 5 and all(
              abs(n.get_editor_property("node").get_editor_property("play_rate") - 1.0) < 1e-6
              and n.get_editor_property("node").get_editor_property("loop_animation")
              for n in players))


def check_carry_clips():
    skin = player_skin()
    if not skin.carry_idle:
        return
    worn = load(skin.mesh).get_editor_property("skeleton")
    ready = load(skin.aim_rifle)
    up = _bone_world(ready, "hand_r", 0.0).z
    for path in carry_fields(skin):
        clip = load(path)
        name = path.rsplit("/", 1)[1]
        check(f"{name} is on the worn skeleton and has no root motion (a clip in the "
              "player's graph with it drags the capsule)",
              clip.get_editor_property("skeleton") == worn
              and not clip.get_editor_property("enable_root_motion"))
        length = clip.get_play_length()
        hands = [_bone_world(clip, "hand_r", length * i / 4.0).z for i in range(4)]
        check(f"...and carries the gun low: the grip hand at least {HAND_DROP_CM:g} cm "
              "under the ready pose's, all the way round",
              max(hands) < up - HAND_DROP_CM,
              f"hand_r z {min(hands):.0f}..{max(hands):.0f} against {up:.0f}")


def check_carry_weights():
    skin = player_skin()
    writes = {name: [n for n in wg if _title(n) == f"Set {name}"]
              for name in (CARRY_POSE, CARRY_SPRINT)}
    if not skin.carry_idle:
        check("no carry clips: the component writes neither carry weight",
              not any(writes.values()))
        return
    check("BP_WeaponComponent writes each carry weight once a frame",
          all(len(v) == 1 for v in writes.values()),
          str({k: len(v) for k, v in writes.items()}))
    if not all(len(v) == 1 for v in writes.values()):
        return
    for name, speed in ((CARRY_POSE, CARRY_BLEND_SPEED),
                        (CARRY_SPRINT, CARRY_SPRINT_BLEND_SPEED)):
        put = writes[name][0]
        src = PIN.list_connected_pins(BEL.find_input_pin(put, name))
        step = PIN.get_owning_node(src[0]) if src else None
        now = PIN.list_connected_pins(BEL.find_input_pin(step, "Current")) if step else []
        check(f"...{name} is eased: FInterpTo(its own value, target) at {speed:g}",
              step is not None and num_pin(step, "InterpSpeed") == speed
              and bool(now) and _title(PIN.get_owning_node(now[0])) == f"Get {name}")
    behind = _behind(BEL.find_input_pin(writes[CARRY_POSE][0], CARRY_POSE), 80)
    reads = {_title(n) for n in behind}
    wants = {"Get Lowered", "Get HandPose", f"Get {CARRY_FOR_VAR}",
             f"Get {CARRY_ALSO_VAR}", "Get Stance",
             "Get Searching"} | ({f"Get {DOING_VAR}"} if traversal_on() else set())
    calls = {"IsSliding"} if slide_on() else set()
    check(f"...{CARRY_POSE} targets Lowered AND HandPose == {CARRY_FOR_VAR} (or one "
          f"of {CARRY_ALSO_VAR}) AND a "
          "stance, not searching" + (", not sliding" if slide_on() else "")
          + (", not in a traversal" if traversal_on() else ""),
          wants <= reads and calls <= reads, str(sorted((wants | calls) - reads)))
    stance = next((n for n in behind if _title(n) == "Get Stance"), None)
    told = [PIN.get_owning_node(p) for p in
            PIN.list_connected_pins(BEL.find_output_pin(stance, "Stance"))] if stance else []
    told = [n for n in told if n in behind]
    nots = [PIN.get_owning_node(p) for n in told
            for p in PIN.list_connected_pins(BEL.find_output_pin(n, "ReturnValue"))]
    check("...the stance being any but prone (NOT Stance == PRONE): standing and "
          "crouched both carry",
          len(told) == 1 and num_pin(told[0], "B") == PRONE
          and [_title(n) for n in nots] == ["NOT Boolean"],
          f"B {num_pin(told[0], 'B') if told else None}, then {[_title(n) for n in nots]}")
    sprint = {_title(n) for n in
              _behind(BEL.find_input_pin(writes[CARRY_SPRINT][0], CARRY_SPRINT))}
    check(f"...{CARRY_SPRINT} targets the movement's own IsSprinting, which every "
          "machine's copy has", "IsSprinting" in sprint, str(sorted(sprint)))


def check_carried_guns():
    skin = player_skin()
    if not skin.carry_idle:
        return
    pose = w.get_editor_property(CARRY_FOR_VAR)
    check(f"{CARRY_FOR_VAR} is the rifle's ready pose",
          pose is not None and pose.get_path_name().split(".")[0] == skin.aim_rifle,
          str(pose.get_path_name() if pose else None))
    also = sorted(a.get_path_name().split(".")[0] for a in w.get_editor_property(CARRY_ALSO_VAR))
    check(f"{CARRY_ALSO_VAR} is that pose with a gun's own fingers: every fitted gun's clip",
          also == sorted(finger_clips()), str(also))
    carried = sorted(sp["display"] for sp in _weapon_specs() if sp["pose"] == skin.aim_rifle)
    check("...which the rifle, the sniper and the shotgun are held in, and no "
          "one-handed gun", len(carried) == 3, str(carried))


def run():
    check_carry_graph()
    check_carry_clips()
    check_carry_weights()
    check_carried_guns()
