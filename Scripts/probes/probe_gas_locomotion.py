"""The player's base movement is the Game Animation Sample's motion matching
(task G3): standing, jogging forward, sidestepping, backing up, sprinting,
in the air and landed, the anim Blueprint on the hidden mesh picks a clip of
the sample's for it, out of the sample's databases.

    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_gas_locomotion.py

What each stretch proves, read off the running anim instance
(combat/gas_locomotion.py authored what it reads of the character):

    the state     what Update_PropertiesFromCharacter made of the game's own
                  movement: Run at the jog, Sprint while the C++ movement
                  sprints, Strafe (the player faces the view), InAir in a jump
    the clip      CurrentSelectedAnim, the motion matching's pick, by its
                  name: an idle standing, a strafe to the side, a sprint
                  sprinting. Nothing here names a clip: only a word in it
    the body      the complaint that started this: sidestepping right, the
                  hips still face the way the player faces (a strafe), where
                  a turned walk would face them down the velocity
    the feet      they move against the hips while moving and not standing,
                  and BP_FootstepComponent still counts the ground covered
    the MetaHuman what is drawn keeps to the hidden mesh while it moves (the
                  root's offset and the strafe's turn reach it through the
                  retargeter), as probe_metahuman_body measures it standing
"""

SYSTEMS = ('animation', 'movement')

import math

import unreal

from combat import footstep_vars as FV
from combat.gas_locomotion_consts import ABP_LOCOMOTION, LAND_VELOCITY, LANDED_AT
from combat.paths import FOOTSTEP_BP_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.sprint_tuning import SPRINT_FORCED_VAR
from probes.metahuman_follow import BONES, FOLLOW_CM, _comp, _gap

RUNS_ON = ("standalone",)
WRITABLE = [(WEAPON_COMP_BP_PATH, SPRINT_FORCED_VAR)]

STRETCH_S = 3.0             # game seconds of each stretch
SETTLE_S = 2.0              # ...of which the start (a start, a pivot) is not read
REST_S = 1.0                # standing between two stretches
# In a strafe the hips face within this of the way the actor faces; a walk
# turned down a sideways velocity would face them 90 degrees off.
STRAFE_HIPS_WITHIN_DEG = 50.0
INDEX_WAIT_S = 60.0         # game seconds the search indices may take to load
FEET_MOVE_CM = 8.0          # a foot's travel against the hips, moving
FEET_STILL_CM = 4.0         # ...and standing


def _name(obj):
    return obj.get_name() if obj else "None"


def _off_facing(pawn, mesh, left, right):
    """Degrees between the way a pair of bones faces (the line from the left
    one to the right one is its own axis) and the way the actor faces."""
    a, b = mesh.get_socket_location(left), mesh.get_socket_location(right)
    across = unreal.Vector(b.x - a.x, b.y - a.y, 0.0).normal()
    side = pawn.get_actor_right_vector()
    dot = max(-1.0, min(1.0, across.x * side.x + across.y * side.y))
    return math.degrees(math.acos(dot))


def _hips_off_facing(pawn, mesh):
    return _off_facing(pawn, mesh, "thigh_l", "thigh_r")


def _chest_off_facing(pawn, mesh):
    return _off_facing(pawn, mesh, "upperarm_l", "upperarm_r")


def probe(p):
    yield 0.5
    pawn = p.pawn()
    mesh = pawn.get_editor_property("mesh")
    inst = mesh.get_anim_instance()
    want_class = ABP_LOCOMOTION.rsplit("/", 1)[1] + "_C"
    p.check("the player's mesh runs the motion-matching anim Blueprint",
            inst is not None and inst.get_class().get_name() == want_class,
            inst.get_class().get_name() if inst else "no anim instance")
    if inst is None or inst.get_class().get_name() != want_class:
        return
    wc = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    body = _comp(pawn, "Body")      # the MetaHuman drawn over the hidden mesh, if one is
    steps = p.component(pawn, FOOTSTEP_BP_PATH + "." + FOOTSTEP_BP_PATH.rsplit("/", 1)[1] + "_C")
    move = pawn.get_component_by_class(unreal.CharacterMovementComponent)
    world = p.world()
    now = lambda: unreal.GameplayStatics.get_time_seconds(world)
    read = lambda var: inst.get_editor_property(var)
    state = lambda var: str(read(var)).split(".")[-1].split(":")[0].strip("<> ")

    def stretch(label, fwd=0.0, right=0.0, seconds=STRETCH_S, settle=SETTLE_S):
        """Hold an input for a stretch, and keep what was seen once it settled."""
        t0, last = now(), p.get(steps, FV.Travelled)
        settle = min(settle, seconds * 0.5)
        seen = dict(clips=[], bases=[], hips=[], chest=[], drawn=[], gap=[], foot=[],
                    speed=[], footfalls=0,
                    gait=set(), mode=set(), rotation=set(), moving=set())
        while now() - t0 < seconds:
            if fwd:
                pawn.add_movement_input(pawn.get_actor_forward_vector(), fwd)
            if right:
                pawn.add_movement_input(pawn.get_actor_right_vector(), right)
            yield 0.0
            # The footstep component carries the remainder over a stride: its
            # count of ground covered falls on the frame a footfall is played.
            travelled = p.get(steps, FV.Travelled)
            seen["footfalls"] += travelled < last
            last = travelled
            if now() - t0 < settle:
                continue
            clip, base = _name(read("CurrentSelectedAnim")), _name(read("CurrentSelectedDatabase"))
            if clip not in seen["clips"]:
                seen["clips"].append(clip)
            if base not in seen["bases"]:
                seen["bases"].append(base)
            seen["hips"].append(_hips_off_facing(pawn, mesh))
            seen["chest"].append(_chest_off_facing(pawn, mesh))
            if body is not None:
                seen["drawn"].append(_hips_off_facing(pawn, body))
                seen["gap"].append(max(_gap(mesh, body, b) for b in BONES))
            pelvis, foot = mesh.get_socket_location("pelvis"), mesh.get_socket_location("foot_l")
            seen["foot"].append((foot.x - pelvis.x, foot.y - pelvis.y, foot.z - pelvis.z))
            seen["speed"].append(pawn.get_velocity().length())
            for key, var in (("gait", "Gait"), ("mode", "MovementMode"),
                             ("rotation", "RotationMode"), ("moving", "MovementState")):
                seen[key].add(state(var))
        feet = seen["foot"]
        seen["feet_cm"] = max((max(f[i] for f in feet) - min(f[i] for f in feet)
                               for i in range(3)), default=0.0)
        seen["hips_deg"] = max(seen["hips"], default=0.0)
        seen["chest_deg"] = max(seen["chest"], default=0.0)
        seen["drawn_deg"] = max(seen["drawn"], default=0.0)
        seen["gap_cm"] = max(seen["gap"], default=0.0)
        mean = lambda xs: sum(xs) / len(xs) if xs else 0.0
        seen["turn"] = (f"hips {min(seen['hips'], default=0):.0f}-{seen['hips_deg']:.0f} "
                        f"(mean {mean(seen['hips']):.0f}), chest "
                        f"{min(seen['chest'], default=0):.0f}-{seen['chest_deg']:.0f} "
                        f"(mean {mean(seen['chest']):.0f}) deg off the facing; the MetaHuman's "
                        f"hips {min(seen['drawn'], default=0):.0f}-{seen['drawn_deg']:.0f}, "
                        f"its worst bone {seen['gap_cm']:.1f} cm off the hidden mesh's")
        seen["speed_cms"] = sorted(seen["speed"])[len(seen["speed"]) // 2] if seen["speed"] else 0.0
        seen["names"] = " ".join(seen["clips"] + seen["bases"])
        seen["told"] = (f"{seen['speed_cms']:.0f} cm/s, {sorted(seen['gait'])} "
                        f"{sorted(seen['moving'])} {sorted(seen['rotation'])} "
                        f"{sorted(seen['mode'])}; {seen['clips'][:4]} from {seen['bases'][:3]}; "
                        f"{seen['turn']}, a foot travels "
                        f"{seen['feet_cm']:.0f} cm against the hips, {seen['footfalls']} footfalls")
        results[label] = seen

    def moved(label, word, gait="RUN"):
        """The checks every moving stretch shares."""
        seen = results[label]
        p.check(f"{label}: the gait is {gait}, the body strafes, and the pick is a "
                f"'{word}' clip of the sample's",
                seen["gait"] == {gait} and seen["rotation"] == {"STRAFE"}
                and seen["moving"] == {"MOVING"} and word in seen["names"], seen["told"])
        p.check(f"{label}: the legs move (a foot travels over {FEET_MOVE_CM:.0f} cm "
                "against the hips)", seen["feet_cm"] > FEET_MOVE_CM, f"{seen['feet_cm']:.0f} cm")
        p.check(f"{label}: the hips face the way the player faces, within "
                f"{STRAFE_HIPS_WITHIN_DEG:.0f} degrees", seen["hips_deg"] < STRAFE_HIPS_WITHIN_DEG,
                f"{seen['hips_deg']:.0f} deg")
        if body is not None:
            p.check(f"{label}: the MetaHuman drawn over the hidden mesh keeps to it (every "
                    f"bone within {FOLLOW_CM:.0f} cm, the hips turned as its are)",
                    seen["gap_cm"] < FOLLOW_CM
                    and abs(seen["drawn_deg"] - seen["hips_deg"]) < 5.0,
                    f"{seen['gap_cm']:.1f} cm; hips {seen['drawn_deg']:.0f} against "
                    f"{seen['hips_deg']:.0f} deg")

    # A game run from the editor binary builds the databases' search indices
    # as it starts (out of the derived-data cache after the first time), and
    # until they are there the motion matching is handed nothing to pick
    # from. A packaged game has them cooked.
    t0 = now()
    yield lambda: read("CurrentSelectedAnim") is not None or now() - t0 > INDEX_WAIT_S
    p.check("the motion matching has picked a clip (the databases are indexed)",
            read("CurrentSelectedAnim") is not None, f"after {now() - t0:.1f} game seconds")
    results = {}
    yield from stretch("standing")
    seen = results["standing"]
    p.check("standing: an idle of the sample's, and the feet are still",
            seen["moving"] == {"IDLE"} and "Idle" in seen["names"]
            and seen["feet_cm"] < FEET_STILL_CM, seen["told"])

    for label, fwd, right in (("jogging forward", 1.0, 0.0), ("sidestepping right", 0.0, 1.0),
                              ("sidestepping left", 0.0, -1.0), ("backing up", -1.0, 0.0)):
        yield from stretch(label, fwd=fwd, right=right)
        moved(label, "Run")
        yield from stretch("a rest", seconds=REST_S)
    jog = results["jogging forward"]
    p.check("jogging: BP_FootstepComponent still plays its footfalls (the ground covered "
            "wraps at each stride)", jog["footfalls"] >= 3, f"{jog['footfalls']} in {STRETCH_S:g} s")

    p.set(wc, SPRINT_FORCED_VAR, True)
    yield from stretch("sprinting", fwd=1.0)
    p.set(wc, SPRINT_FORCED_VAR, False)
    moved("sprinting", "Sprint", gait="SPRINT")
    yield from stretch("stopped", seconds=2.5, settle=2.0)

    pawn.jump()
    yield lambda: move.is_falling()
    yield from stretch("in the air", seconds=0.3, settle=0.1)
    pawn.stop_jumping()
    seen = results["in the air"]
    p.check("a jump: the movement mode is InAir and the pick is a 'Jump' clip",
            "IN_AIR" in seen["mode"] and "Jump" in seen["names"], seen["told"])
    yield lambda: not move.is_falling()
    yield from stretch("landed", seconds=0.25, settle=0.05)
    seen = results["landed"]
    p.check("landed: the landing is kept (its time, and a velocity that was falling) "
            "and the pick is a 'Land' clip",
            read(LANDED_AT) > 0.0 and read(LAND_VELOCITY).z < 0.0 and "Land" in seen["names"],
            f"landed at {read(LANDED_AT):.2f} s, velocity z {read(LAND_VELOCITY).z:.0f}; "
            f"{seen['told']}")
    yield from stretch("standing again", seconds=4.0, settle=3.5)
    seen = results["standing again"]
    p.check("standing again: back to an idle", seen["moving"] == {"IDLE"}
            and "Idle" in seen["names"], seen["told"])
    for label in ("stopped",):
        p.note(f"{label}: {results[label]['told']}")
    p.note(f"the movement orients to its velocity: "
           f"{move.get_editor_property('orient_rotation_to_movement')}; the pawn takes the "
           f"controller's yaw: {pawn.get_editor_property('use_controller_rotation_yaw')}")
