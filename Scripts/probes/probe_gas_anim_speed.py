"""Does the motion matching's pick move the legs at the pace the ground goes
by? The cadence of the body against the cadence the clip was captured at.

    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_gas_anim_speed.py

For a stretch of holding one input the probe measures, frame by frame, how far
the body travelled and how often the feet swapped (the forward separation of
the two feet crossing zero is one step). That gives the stride the body takes
on the ground. The clip the motion matching picked is sampled the same way,
for the stride it was captured with. The ratio of the two is what the eye
sees: 1 is a stride that fits the ground, 2 is legs cycling twice for every
stride the ground allows -- running on the spot.

What it found, and guards: 4.1 to 4.3 at the jog, the sprint and the crouch
alike. The weapon layers' graph fed one pose to two inputs in two places, the
engine updates what is under such a pose once per link, and the motion
matching under both ran its clips four times a frame's worth every frame
(uebp/pose_share.py, which makes each a cached pose). With that, 1.0 to 1.15:
the motion matching plays a clip at 0.85 to 1.15 of its speed to fit the pace
(the jog is 400 cm/s on clips shot at 500), which is the band checked, with
room for the measure.
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"
SYSTEMS = ('animation', 'movement')

import math

import unreal

from asset_pipeline.rig_util import _bone_world
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.sprint_tuning import SPRINT_FORCED_VAR

RUNS_ON = ("standalone",)
WRITABLE = [(WEAPON_COMP_BP_PATH, SPRINT_FORCED_VAR), (WEAPON_COMP_BP_PATH, "Stance")]

INDEX_WAIT_S = 60.0
# The legs' pace over the ground's: the motion matching's own play rate range
# (0.85 to 1.15) and a step's worth of error in a count of four to eight.
CADENCE = (0.7, 1.4)
STRETCH_S = 4.0
SETTLE_S = 1.5


def _steps(sig, times):
    """(steps, seconds) of a signal that crosses its mean once a step."""
    m = sum(sig) / len(sig)
    cross = [i for i in range(1, len(sig)) if (sig[i - 1] - m) * (sig[i] - m) < 0]
    if len(cross) < 2:
        return 0, 0.0
    return len(cross) - 1, times[cross[-1]] - times[cross[0]]


def clip_stride(anim):
    """(seconds, cm) of one step of a clip: the time between two crossings of
    its feet, and the ground its root covers in that time."""
    n, L = 120, anim.get_play_length()
    times = [L * i / (n - 1) for i in range(n)]
    sig = []
    for t in times:
        a, b = _bone_world(anim, "foot_l", t), _bone_world(anim, "foot_r", t)
        sig.append(a.y - b.y)       # the clips are captured facing +Y
    steps, span = _steps(sig, times)
    if not steps:
        return None, None
    AL = unreal.AnimationLibrary
    p0 = AL.get_bone_pose_for_time(anim, "root", 0.0, False)
    p1 = AL.get_bone_pose_for_time(anim, "root", max(0.0, L - 1e-3), False)
    d = p1.translation - p0.translation
    speed = math.hypot(d.x, d.y) / L if L else 0.0
    return span / steps, speed * span / steps


def probe(p):
    yield 0.5
    pawn = p.pawn()
    mesh = pawn.get_editor_property("mesh")
    inst = mesh.get_anim_instance()
    wc = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    world = p.world()
    now = lambda: unreal.GameplayStatics.get_time_seconds(world)
    read = lambda var: inst.get_editor_property(var)
    t0 = now()
    yield lambda: read("CurrentSelectedAnim") is not None or now() - t0 > INDEX_WAIT_S

    def stretch(label, fwd=0.0, right=0.0, seconds=STRETCH_S, settle=SETTLE_S):
        sig, times, clips = [], [], []
        t0 = now()
        travelled = 0.0
        where = None
        while now() - t0 < seconds:
            if fwd:
                pawn.add_movement_input(pawn.get_actor_forward_vector(), fwd)
            if right:
                pawn.add_movement_input(pawn.get_actor_right_vector(), right)
            yield 0.0
            loc = pawn.get_actor_location()
            if now() - t0 < settle:
                where = loc
                continue
            fwd_v = pawn.get_actor_forward_vector()
            a, b = mesh.get_socket_location("foot_l"), mesh.get_socket_location("foot_r")
            sig.append((a.x - b.x) * fwd_v.x + (a.y - b.y) * fwd_v.y)
            times.append(now())
            travelled += math.hypot(loc.x - where.x, loc.y - where.y)
            where = loc
            anim = read("CurrentSelectedAnim")
            if anim is not None and anim not in clips:
                clips.append(anim)
        steps, span = _steps(sig, times)
        results[label] = seen = dict(clips=[c.get_name() for c in clips], steps=steps)
        if not steps or span <= 0.0 or travelled <= 1.0:
            seen["told"] = (f"{len(sig)} frames, {steps} steps, {travelled:.0f} cm "
                            f"travelled; {seen['clips']}")
            return
        ground_step_s = span / steps
        ground_step_cm = travelled * (span / (times[-1] - times[0])) / steps
        clip_s, clip_cm = clip_stride(clips[-1])
        seen.update(ground_step_s=ground_step_s, ground_step_cm=ground_step_cm,
                    clip_step_s=clip_s, clip_step_cm=clip_cm)
        if clip_cm:
            seen["cadence"] = clip_cm / ground_step_cm
        seen["told"] = (f"a step every {ground_step_s * 1000:.0f} ms and "
                        f"{ground_step_cm:.0f} cm of ground ({steps} steps in "
                        f"{span:.1f} s at {travelled / (times[-1] - times[0]):.0f} cm/s); "
                        f"{clips[-1].get_name()} was captured a step every "
                        f"{(clip_s or 0) * 1000:.0f} ms and {clip_cm or 0:.0f} cm; "
                        f"legs x{seen.get('cadence', 0):.2f} the ground's pace")

    results = {}
    yield from stretch("jogging", fwd=1.0)
    p.note(f"jogging: {results['jogging']['told']}")
    p.set(wc, SPRINT_FORCED_VAR, True)
    yield from stretch("sprinting", fwd=1.0, seconds=5.0, settle=2.5)
    p.set(wc, SPRINT_FORCED_VAR, False)
    p.note(f"sprinting: {results['sprinting']['told']}")
    p.set(wc, "Stance", 1)
    yield 0.6
    yield from stretch("crouch-walking", fwd=1.0)
    p.set(wc, "Stance", 0)
    p.note(f"crouch-walking: {results['crouch-walking']['told']}")
    for label, seen in results.items():
        cadence = seen.get("cadence")
        p.check(f"{label}, the legs keep the ground's pace: the clip's stride is "
                f"{CADENCE[0]} to {CADENCE[1]} of the stride the body takes (4 was every "
                "clip played four times too fast)",
                cadence is not None and CADENCE[0] <= cadence <= CADENCE[1], seen["told"])
