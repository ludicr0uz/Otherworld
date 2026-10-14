"""The empty-handed sprint straight ahead is the sample's relaxed loop, on the
sprinter's own copy, another client's copy and the server's
(combat/gas_sprint.py).

    python3 Scripts/dev/uepy.py --net --clients 2 --probe Scripts/probes/probe_net_relaxed_sprint.py

Client 1 sprints straight ahead, veers to the forward-right diagonal and back,
posting each phase. Every machine reads the motion matching's pick on its copy
of client 1's character through each one, counted from SETTLE_S into the
first phase and PICK_AFTER_S into the others (the start and the turn come first): M_Relaxed_Sprint_Loop_F ahead, a
neutral sprint clip on the diagonal (the _FL/_FR loops, or the diamond the
motion matching passes through on the way) and none of the relaxed one, the
relaxed one again after. The databases are assets every machine has; the pick
reads the movement's sprint, which another player's copy, running no moves,
takes from the server (AOtherworldCharacter::bSprinting, IsSprintPosed).

On its own copy client 1 also measures:
    the cadence  the relaxed loop's stride against the ground the body covers
                 (probe_gas_anim_speed's measure): 1 is feet that keep the
                 ground, the band is the motion matching's play-rate range
                 with a step's error. The loop travels 585 cm/s, the sprint
                 is 600: about 1.03
    the posture  the head against the pelvis and the pelvis's height, in the
                 mesh's space, frame to frame: the fastest it changes in the
                 half second after each veer against the fastest in steady
                 sprinting. A pop between the two styles is a jump the
                 steady loop never makes
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # 7 s of sprint is 42 m, most of the 50 m level
SYSTEMS = ('net', 'animation', 'movement')

import time

import unreal

from combat.gas_sprint import DIAGONALS, RELAXED_F
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.sprint_tuning import SPRINT_FORCED_VAR
from probes.crawl_watch import always_pose
from probes.probe_net_crawl import _clear_pack
from probes.probe_gas_anim_speed import CADENCE, _steps, clip_stride

RUNS_ON = ("server", "client")
WRITABLE = [(WEAPON_COMP_BP_PATH, SPRINT_FORCED_VAR)]
WAIT = 60.0             # wall seconds any one step may take (the index rebuilds)
# Game seconds of each phase: within the 8 s a full stamina bar sprints for.
# From a stand the sample's start and its run-to-sprint play for about 2 s.
PHASES = (("ahead", 4.0, 0.0), ("veer", 1.6, 1.0), ("back", 2.0, 0.0))
SETTLE_S = 2.4          # of the first phase, before the stride and the picks count
AFTER_VEER_S = 0.5      # the window after a change of direction
POP_RATIO = 1.5         # the posture may change this much faster than steady
PICK_AFTER_S = 1.0      # of a later phase, before the picks are counted
NEUTRAL = "M_Neutral_Sprint"
RELAXED = RELAXED_F.rsplit("/", 1)[1]
DIAGONAL_NAMES = tuple(d.rsplit("/", 1)[1] for d in DIAGONALS)
SPACE = unreal.RelativeTransformSpace.RTS_COMPONENT


def _await(ready, seconds=WAIT):
    until = time.time() + seconds
    yield lambda: ready() or time.time() > until


def _pick(mesh):
    clip = mesh.get_anim_instance().get_editor_property("CurrentSelectedAnim")
    return clip.get_name() if clip else None


def _count(seen, phase, clip, since):
    if clip and since >= (SETTLE_S if phase == "ahead" else PICK_AFTER_S):
        counts = seen.setdefault(phase, {})
        counts[clip] = counts.get(clip, 0) + 1


def _check_picks(p, whose, seen):
    """seen: {phase: {clip name: frames it was the pick}}."""
    main = lambda ph: max(seen.get(ph) or {None: 0}, key=lambda c: (seen.get(ph) or {}).get(c, 0))
    p.check(f"{p.where}: {whose} sprinting straight ahead plays {RELAXED} (the pick "
            "held longest, ahead and back again)",
            main("ahead") == RELAXED and main("back") == RELAXED, str(seen))
    veer = seen.get("veer") or {}
    p.check(f"{p.where}: {whose} on the diagonal plays a neutral sprint clip "
            f"(held longest; the loops are {' or '.join(DIAGONAL_NAMES)}), and never "
            "the relaxed one",
            str(main("veer")).startswith(NEUTRAL) and RELAXED not in veer, str(veer))


def _posture(mesh):
    pelvis = mesh.get_socket_transform("pelvis", SPACE).translation
    head = mesh.get_socket_transform("head", SPACE).translation
    return head - pelvis, pelvis.z


def probe_client(p):
    yield from _await(lambda: p.pawn() is not None)
    me = p.pawn()
    if p.client != 1:
        yield from _watch_other(p, me.get_class(), "its copy of client 1's character",
                                lambda a: a != me)
        return
    mesh = me.get_editor_property("mesh")
    always_pose(mesh)
    wc = p.component(me, WEAPON_COMP_CLASS_PATH)
    world = p.world()
    now = lambda: unreal.GameplayStatics.get_time_seconds(world)
    # The pack goes first: the index of a changed database rebuilds as the
    # game starts, and the wanderers kill a player standing that long.
    yield from _await(lambda: p.posted("server", "cleared"))
    t0 = time.time()
    yield from _await(lambda: _pick(mesh) is not None)
    p.note(f"the motion matching's first pick came {time.time() - t0:.0f} s after the "
           "pack was cleared")
    yield 1.0
    p.set(wc, SPRINT_FORCED_VAR, True)
    seen, frames = {}, []          # frames: (t, phase, since change, posture, height)
    sig, times, travelled, where = [], [], 0.0, None
    # The ways are the world's, taken once: the body turns to its movement.
    ahead, side = me.get_actor_forward_vector(), me.get_actor_right_vector()
    for phase, seconds, right in PHASES:
        p.post("phase", phase)
        t0 = now()
        while now() - t0 < seconds:
            way = ahead + side * right
            me.add_movement_input(way, 1.0, False)
            yield 0.0
            _count(seen, phase, _pick(mesh), now() - t0)
            body, height = _posture(mesh)
            frames.append((now(), phase, now() - t0, body, height))
            loc = me.get_actor_location()
            if phase == "ahead" and now() - t0 >= SETTLE_S:
                fwd = me.get_actor_forward_vector()
                a, b = mesh.get_socket_location("foot_l"), mesh.get_socket_location("foot_r")
                sig.append((a.x - b.x) * fwd.x + (a.y - b.y) * fwd.y)
                times.append(now())
                if where is not None:
                    travelled += ((loc.x - where.x) ** 2 + (loc.y - where.y) ** 2) ** 0.5
                where = loc
    p.set(wc, SPRINT_FORCED_VAR, False)
    p.post("phase", "done")
    _check_picks(p, "its own character", seen)
    _check_cadence(p, sig, times, travelled)
    _check_posture(p, frames)


def _check_cadence(p, sig, times, travelled):
    steps, span = _steps(sig, times) if sig else (0, 0.0)
    clip = unreal.load_asset(RELAXED_F)
    if not steps or span <= 0 or travelled <= 1.0:
        p.check(f"{p.where}: sprinting ahead, the legs keep the ground's pace", False,
                f"{len(sig)} frames, {steps} steps, {travelled:.0f} cm")
        return
    speed = travelled / (times[-1] - times[0])
    ground_cm = travelled * (span / (times[-1] - times[0])) / steps
    clip_s, clip_cm = clip_stride(clip)
    cadence = clip_cm / ground_cm if clip_cm else 0.0
    p.check(f"{p.where}: sprinting ahead, {RELAXED}'s stride is {CADENCE[0]} to "
            f"{CADENCE[1]} of the stride the body takes (the feet keep the ground)",
            CADENCE[0] <= cadence <= CADENCE[1],
            f"{speed:.0f} cm/s over the ground, a step every {span / steps * 1000:.0f} ms "
            f"and {ground_cm:.0f} cm; the clip's every {clip_s * 1000:.0f} ms and "
            f"{clip_cm:.0f} cm; legs x{cadence:.2f} the ground's pace")


def _check_posture(p, frames):
    """The fastest the posture changes just after a veer, against steady."""
    rates = {"steady": [0.0, 0.0], "veer": [0.0, 0.0]}
    for (t0, ph0, _s0, b0, h0), (t1, ph1, s1, b1, h1) in zip(frames, frames[1:]):
        dt = t1 - t0
        if dt <= 0:
            continue
        kind = "veer" if (ph1 != "ahead" and s1 < AFTER_VEER_S) else (
            "steady" if s1 >= AFTER_VEER_S + 0.3 else None)
        if kind is None:
            continue
        r = rates[kind]
        r[0] = max(r[0], (b1 - b0).length() / dt)
        r[1] = max(r[1], abs(h1 - h0) / dt)
    st, ve = rates["steady"], rates["veer"]
    told = (f"head against the pelvis: {ve[0]:.0f} cm/s at most after a veer, {st[0]:.0f} "
            f"steady; the pelvis's height: {ve[1]:.0f} after, {st[1]:.0f} steady")
    p.note(f"posture: {told}")
    p.check(f"{p.where}: veering between the relaxed loop and a neutral diagonal does not "
            f"pop the posture (it changes at most {POP_RATIO}x as fast as in steady "
            "sprinting)",
            st[0] > 0 and ve[0] <= POP_RATIO * st[0] and ve[1] <= POP_RATIO * st[1], told)


def _watch_other(p, cls, whose, which):
    others = lambda: [a for a in unreal.GameplayStatics.get_all_actors_of_class(
        p.world(), cls) if which(a)]
    yield from _await(lambda: p.posted("client 1", "phase") == "ahead")
    yield from _await(lambda: any(a.get_velocity().length() > 100.0 for a in others()))
    mover = max(others(), key=lambda a: a.get_velocity().length(), default=None)
    if not p.check(f"{p.where} sees client 1's character sprint", mover is not None):
        return
    mesh = mover.get_editor_property("mesh")
    always_pose(mesh)
    seen, last, since = {}, None, time.time()
    until = time.time() + WAIT
    while time.time() < until:
        if p.where == "server":
            _clear_pack(p)       # one that respawns
        phase = p.posted("client 1", "phase")
        if phase == "done":
            break
        if phase != last:
            last, since = phase, time.time()
        yield 0.0
        _count(seen, phase, _pick(mesh), time.time() - since)
    _check_picks(p, whose, seen)


def probe_server(p):
    yield from _await(lambda: len(p.players()) >= 2 and all(
        c.get_controlled_pawn() for c in p.players()))
    cls = p.players()[0].get_controlled_pawn().get_class()
    _clear_pack(p)
    p.post("cleared")
    yield from _watch_other(p, cls, "the server's copy of client 1's character",
                            lambda a: True)
