"""Do the legs stay where they stood while save and exit counts down? The
feet on sloping ground, standing and then counting down.

    python3 Scripts/dev/uepy.py --game --probe Scripts/probes/probe_save_exit_legs.py

The countdown used to disable the character's movement, and the motion
matching's Foot Placement node takes a movement that is not walking for a
body in the air: it stopped fitting the feet to the ground, so on a slope
the legs snapped to the flat pose as the countdown began and back when it
was called off (combat/weapon_component/save_exit.py). On flat ground there
is nothing to see, so the probe finds a slope near the player and stands on
it (the 200 m forest: the probe level is flat).

It adds up how far each foot and the pelvis move from one frame to the next
over a stretch of standing, and how far one foot is above the other; then it
starts the countdown and measures the same from its first frame. An idle
breathes, so the standing stretch is the measure of still. Last, with
nothing holding the character down any more, it is thrown into the air: that
calls the exit off.
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"     # sloping ground: the probe level is flat
SYSTEMS = ('animation', 'movement')

import math

import unreal

from combat.ask_consts import (
    EXIT_AT_VAR, EXIT_CALLED_OFF_VAR, EXIT_PENDING_VAR, EXIT_STARTED_VAR,
)
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH

RUNS_ON = ("standalone",)
WRITABLE = [(WEAPON_COMP_BP_PATH, EXIT_PENDING_VAR), (WEAPON_COMP_BP_PATH, EXIT_AT_VAR),
            (WEAPON_COMP_BP_PATH, EXIT_STARTED_VAR)]

INDEX_WAIT_S = 60.0
SETTLE_S = 2.0
STRETCH_S = 4.0
BONES = ("foot_l", "foot_r", "pelvis")
# Frozen against standing: the feet may travel this many times the idle's
# own, plus a floor for an idle that barely moves at all.
TIMES_IDLE = 1.5
FLOOR_CM_S = 0.5
SLOPE_DEG = (10.0, 25.0)
SEARCH_STEP_CM = 200.0
SEARCH_STEPS = 15
FIT_CM = 3.0
FITTED_CM = 10.0
LAUNCH_CMS = 400.0


def _clear(p):
    """No wanderer comes for the player while it is measured: a blow would
    call the exit off, and a death freezes the body by itself."""
    for ctrl in unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController):
        npc = ctrl.get_controlled_pawn()
        if npc is not None:
            npc.destroy_actor()


def _measure(p, pawn, mesh, inst, out, seconds=STRETCH_S):
    """Fills ``out``: each bone's travel in cm per second, its largest single
    step, the clips picked and how many times the pick changed."""
    _clear(p)
    t0 = p.time()
    last = {b: mesh.get_socket_location(b) for b in BONES}
    path = dict.fromkeys(BONES, 0.0)
    step = dict.fromkeys(BONES, 0.0)
    clips, changes, was, frames = [], 0, None, 0
    modes = set()
    while p.time() - t0 < seconds:
        yield 0.0
        frames += 1
        for b in BONES:
            at = mesh.get_socket_location(b)
            d = (at - last[b]).length()
            path[b] += d
            step[b] = max(step[b], d)
            last[b] = at
        anim = inst.get_editor_property("CurrentSelectedAnim")
        name = anim.get_name() if anim is not None else None
        if name != was:
            changes += was is not None
            was = name
            if name not in clips:
                clips.append(name)
        modes.add(str(pawn.get_editor_property("character_movement").movement_mode))
    span = p.time() - t0
    out.update(rate={b: path[b] / span for b in BONES}, step=step, clips=clips,
               changes=changes, frames=frames, modes=sorted(modes),
               feet_dz=last["foot_l"].z - last["foot_r"].z)
    out["told"] = (", ".join(f"{b} {out['rate'][b]:.2f} cm/s (largest step "
                             f"{step[b]:.2f} cm)" for b in BONES)
                   + f"; left foot {out['feet_dz']:+.1f} cm above the right"
                   + f"; {changes} clip changes over {frames} frames, {clips}; {out['modes']}")


def _start(p, wc):
    now = p.time()
    p.set(wc, EXIT_STARTED_VAR, now)
    p.set(wc, EXIT_AT_VAR, now + 100.0)
    p.set(wc, EXIT_PENDING_VAR, True)


def _slope(p, pawn):
    """A spot of sloping ground near the player, to stand on: (point, degrees),
    or (None, 0.0). The feet are fitted to the ground there, which is where a
    body that stops fitting them shows."""
    here = pawn.get_actor_location()
    best = (None, 0.0)
    for ix in range(-SEARCH_STEPS, SEARCH_STEPS + 1):
        for iy in range(-SEARCH_STEPS, SEARCH_STEPS + 1):
            x, y = here.x + ix * SEARCH_STEP_CM, here.y + iy * SEARCH_STEP_CM
            hit = unreal.SystemLibrary.line_trace_single(
                p.world(), unreal.Vector(x, y, here.z + 2000.0),
                unreal.Vector(x, y, here.z - 2000.0),
                unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [pawn],
                unreal.DrawDebugTrace.NONE, True)
            if hit is None:
                continue
            got = hit.to_tuple()
            point, normal = got[4], got[7]
            deg = math.degrees(math.acos(max(-1.0, min(1.0, normal.z))))
            if SLOPE_DEG[0] <= deg <= SLOPE_DEG[1] and deg > best[1]:
                best = (point, deg)
    return best


def probe(p):
    yield 0.5
    pawn = p.pawn()
    mesh = pawn.get_editor_property("mesh")
    inst = mesh.get_anim_instance()
    wc = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    _clear(p)
    t0 = p.time()
    yield lambda: (inst.get_editor_property("CurrentSelectedAnim") is not None
                   or p.time() - t0 > INDEX_WAIT_S)
    point, deg = _slope(p, pawn)
    if not p.check(f"there is ground sloping {SLOPE_DEG[0]:.0f} to {SLOPE_DEG[1]:.0f} "
                   "degrees near the player to stand on", point is not None):
        return
    half = pawn.get_editor_property("capsule_component").get_scaled_capsule_half_height()
    pawn.set_actor_location(unreal.Vector(point.x, point.y, point.z + half + 5.0),
                            False, True)
    yield SETTLE_S
    moves = pawn.get_editor_property("character_movement")
    p.note(f"standing on a {deg:.0f} degree slope, floor normal "
           f"z {moves.current_floor.hit_result.to_tuple()[7].z:.3f}")

    standing, frozen = {}, {}
    yield from _measure(p, pawn, mesh, inst, standing)
    p.note(f"standing: {standing['told']}")

    p.check(f"standing there, one foot is more than {FITTED_CM:.0f} cm above the "
            "other: the feet are fitted to the slope, which is what is held",
            abs(standing["feet_dz"]) > FITTED_CM, f"{standing['feet_dz']:+.1f} cm")
    _start(p, wc)
    _clear(p)
    beginning = {}
    yield from _measure(p, pawn, mesh, inst, beginning, seconds=SETTLE_S)
    p.check("the countdown is running for the measure", p.get(wc, EXIT_PENDING_VAR) is True)
    yield from _measure(p, pawn, mesh, inst, frozen)
    p.note(f"as the countdown begins: {beginning['told']}")
    p.note(f"counting down: {frozen['told']}")

    p.check("the movement stays in the walking mode while the exit counts down (out "
            "of it the Foot Placement node takes the body for one in the air)",
            frozen["modes"] == [str(unreal.MovementMode.MOVE_WALKING)], str(frozen["modes"]))
    p.check("the feet stay fitted to the slope: one as far above the other as it "
            f"stood before the countdown, within {FIT_CM} cm (let go, they were level: "
            "39 cm out on a 25 degree slope)",
            abs(frozen["feet_dz"] - standing["feet_dz"]) <= FIT_CM,
            f"standing {standing['feet_dz']:+.1f} cm, counting down {frozen['feet_dz']:+.1f}")
    for b in BONES:
        allowed = standing["rate"][b] * TIMES_IDLE + FLOOR_CM_S
        p.check(f"{b} is as still as at an idle from the moment the countdown begins "
                f"(within {TIMES_IDLE} times its travel, plus {FLOOR_CM_S} cm/s)",
                max(beginning["rate"][b], frozen["rate"][b]) <= allowed,
                f"beginning {beginning['rate'][b]:.2f} cm/s, counting down "
                f"{frozen['rate'][b]:.2f}, standing {standing['rate'][b]:.2f}")
    p.check("the motion matching keeps to its idle while the exit counts down: "
            "no more changes of clip than standing, and one at most",
            frozen["changes"] + beginning["changes"] <= max(1, standing["changes"]),
            f"counting down {frozen['changes'] + beginning['changes']} ({frozen['clips']}), "
            f"standing {standing['changes']} ({standing['clips']})")

    # Nothing holds the character down, so leaving the ground calls it off.
    p.check("...and it is still running", p.get(wc, EXIT_PENDING_VAR) is True)
    pawn.launch_character(unreal.Vector(0.0, 0.0, LAUNCH_CMS), False, True)
    t0 = p.time()
    yield lambda: not p.get(wc, EXIT_PENDING_VAR) or p.time() - t0 > 3.0
    p.check("thrown off the ground, the exit is called off",
            not p.get(wc, EXIT_PENDING_VAR) and p.get(wc, EXIT_CALLED_OFF_VAR) >= t0,
            f"pending {p.get(wc, EXIT_PENDING_VAR)}, called off at "
            f"{p.get(wc, EXIT_CALLED_OFF_VAR):.2f}, thrown at {t0:.2f}")
