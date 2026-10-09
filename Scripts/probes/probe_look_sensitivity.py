"""The mouse turns the view by the same amount standing, walking and running.

Walking is what aiming does to the legs (half speed, on the shoulder or down
the irons), and aiming used to slow the mouse with its zoom as well, so the
mouse read as slower walking than standing or running. Only the sniper's
scope slows it now (weapon_component/ads.py).

No key can be injected into a headless game, so the probe holds the zoom
itself: it writes CurrentFOV before each frame, which is what the look scales
are computed from, and steers the pawn for the gaits. The same look input is
fed each frame and the turn it gives is read back off the control rotation.
The scope's case is the positive one: there the turn must be smaller.
"""

SYSTEMS = ('menu',)

import math

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.tuning import COMBAT
from combat.weapon_component import vars as WV

WRITABLE = [(WEAPON_COMP_BP_PATH, "CurrentFOV")]
SETTLE_FRAMES, READ_FRAMES = 20, 10
LOOK = 1.0
# (label, steering the pawn, the zoom held; None leaves the camera alone)
CASES = (("standing", False, None),
         ("running (the jog, no aim)", True, None),
         ("standing, aimed on the shoulder", False, COMBAT.shoulder_zoom),
         ("walking, aimed on the shoulder", True, COMBAT.shoulder_zoom),
         ("walking, down the irons", True, COMBAT.ads_zoom_irons))


def _steer(pawn):
    yaw = math.radians(pawn.get_actor_rotation().yaw)
    pawn.add_movement_input(unreal.Vector(math.cos(yaw), math.sin(yaw), 0.0), 1.0, False)


def _turns(p, pawn, pc, wc, moving, zoom):
    """Hold the case, feed LOOK each frame; the yaw turned per frame, and the
    yaw scale and CurrentFOV the last frame left."""
    base = p.get(wc, "BaseFOV")
    steps = []
    for frame in range(SETTLE_FRAMES + READ_FRAMES):
        if moving:
            _steer(pawn)
        if zoom is not None:
            p.set(wc, "CurrentFOV", base / zoom)
        before = pc.get_control_rotation().yaw
        pawn.add_controller_yaw_input(LOOK)
        yield 0.0
        if frame >= SETTLE_FRAMES:
            steps.append((pc.get_control_rotation().yaw - before + 540.0) % 360.0 - 180.0)
    return steps, pc.get_deprecated_input_yaw_scale(), p.get(wc, "CurrentFOV")


def probe(p):
    yield 0.5
    pawn, pc = p.pawn(), p.controller()
    wc = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    base = p.get(wc, "BaseFOV")
    full = p.get(wc, WV.BaseYawScale) * p.get(wc, WV.MouseSensitivity) * LOOK
    p.check("the unaimed turn is the base yaw scale x the mouse sensitivity",
            full > 0.0, f"{full:.4f} degrees per unit of look")

    for label, moving, zoom in CASES:
        steps, _scale, fov = yield from _turns(p, pawn, pc, wc, moving, zoom)
        p.check(f"{label}: the same turn per unit of look",
                all(abs(s - full) < 1e-3 for s in steps),
                f"{min(steps):.4f}..{max(steps):.4f} against {full:.4f}"
                + ("" if zoom is None else f", zoomed {base / fov:.2f}x"))
        if zoom is not None:
            p.check(f"...and the zoom was really held ({zoom:g}x asked)",
                    base / fov > 1.0 + 0.5 * (zoom - 1.0), f"{base / fov:.2f}x")

    # The positive case: the scope does slow the mouse, by what its zoom gives
    # back x the player's ScopeSensitivity.
    steps, scale, fov = yield from _turns(p, pawn, pc, wc, False, COMBAT.ads_zoom_scope)
    span = COMBAT.ads_zoom_scope - COMBAT.ads_zoom_irons
    past = min(max((base / fov - COMBAT.ads_zoom_irons) / span, 0.0), 1.0)
    want = full * (1.0 + past * (COMBAT.scope_sens_base()
                                 * p.get(wc, WV.ScopeSensitivity) - 1.0))
    p.check("down the scope the mouse is slower", max(steps) < 0.6 * full,
            f"{max(steps):.4f} against {full:.4f}, zoomed {base / fov:.2f}x")
    p.check("...by the scope's base x ScopeSensitivity, past the irons",
            abs(scale * LOOK - want) < 1e-3, f"{scale * LOOK:.4f} against {want:.4f}")

    # And letting go gives it back.
    steps, _scale, fov = yield from _turns(p, pawn, pc, wc, False, 1.0)
    p.check("off the scope the turn is whole again",
            all(abs(s - full) < 1e-3 for s in steps), f"{min(steps):.4f}..{max(steps):.4f}")
