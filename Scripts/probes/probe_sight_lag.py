"""Down the sights, at real time, standing and walking: the camera is on the
gun's eye point as the frame ends, and the front sight on the middle of the
view, on every frame.

sights.py puts the camera on Held's SightOffset and turns it down the sight
line, so the two agree by construction -- unless the hand the gun rides is
posed after the weapon component has placed the camera. Then the sights leave
the middle of the view by however far the pose moved since. The component
ticks after the owner's mesh for this (sights._author_tick_order). Without
that, on this level, on about one frame in seven, the gun left the crosshair
by up to 2.5 degrees walking (3.4 cm off the eye point); on Lvl_Forest_1000m
it never did, with the same code: an order nothing asked for differs by
level. probe_sight_align cannot see it: it measures walking at a
ten-thousandth of real time, where one frame's walk is nothing.

Run it --windowed. Headless (-nullrhi, ~700 fps) the race is still there but
rare and small -- with the mesh rule taken out it missed on 1 frame of 2110,
by 0.06 cm -- so a headless pass is weak evidence. Windowed (~21 fps here) it
missed on 3 of 36 frames standing and by 2.3 cm walking.

    uepy.py --game --windowed --probe Scripts/probes/probe_sight_lag.py

Measured from the Slate post-tick (probes/boot.py), after the world's tick and
the camera's update, so it reads what was drawn. The sights come up by
SightsForced, the key's own path.
"""

LEVEL = "/Game/Maps/Lvl_Horde_Survival"  # where the race was seen; 1000m was clean
SYSTEMS = ('weapons',)

import math
import statistics

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import SIGHTS_FORCED_VAR

WRITABLE = [(WEAPON_COMP_BP_PATH, SIGHTS_FORCED_VAR)]
ML = unreal.MathLibrary

# In order the misses are float noise (0.0000 cm, 0.0001 deg at worst, either
# way); out of order one frame's was 0.06 cm headless and 2.3 cm windowed.
EYE_CM = 0.01       # the camera off the eye point by more: not on the gun
FRONT_DEG = 0.005   # the front sight off the middle of the view by more
STAND_S = 1.5
WALK_S = 3.0
WALK_SETTLE_S = 0.6


def _angle(a, b):
    return math.degrees(math.atan2(a.cross(b).length(), a.dot(b)))


class _Samples(object):
    def __init__(self):
        self.eye, self.front, self.dt, self.speed = [], [], [], []

    def take(self, p, wc, cam):
        held = p.get(wc, "Held")
        xf = held.get_actor_transform()
        at = cam.get_world_location()
        eye = ML.inverse_transform_location(xf, at)
        self.eye.append((eye - held.get_editor_property("SightOffset")).length())
        tip = ML.transform_location(xf, held.get_editor_property("SightAim"))
        self.front.append(_angle(tip - at, cam.get_forward_vector()))
        self.dt.append(unreal.GameplayStatics.get_world_delta_seconds(p.world()))
        self.speed.append(p.pawn().get_velocity().length())

    def line(self, what):
        fps = 1.0 / max(statistics.mean(self.dt), 1e-6)
        missed = sum(e >= EYE_CM for e in self.eye)
        return (f"{what}: {len(self.eye)} frames at {fps:.0f} fps, "
                f"{statistics.mean(self.speed):.0f} cm/s; {missed} off the eye point; "
                f"worst {max(self.eye):.4f} cm, {max(self.front):.4f} deg")


def _for(p, seconds, each):
    t0 = [None]

    def step():
        now = unreal.GameplayStatics.get_time_seconds(p.world())
        t0[0] = now if t0[0] is None else t0[0]
        each()
        return now - t0[0] >= seconds
    yield step


def probe(p):
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    cam = p.pawn().get_component_by_class(unreal.CameraComponent)
    yield lambda: p.get(wc, "Held") is not None
    p.set(wc, SIGHTS_FORCED_VAR, True)
    yield lambda: p.get(wc, "SightAiming") and p.get(wc, "SightBlend") > 0.999
    yield 0.5

    still = _Samples()
    yield from _for(p, STAND_S, lambda: still.take(p, wc, cam))

    def walk():
        p.pawn().add_movement_input(p.pawn().get_actor_forward_vector(), 1.0)
    yield from _for(p, WALK_SETTLE_S, walk)
    moving = _Samples()
    yield from _for(p, WALK_S, lambda: (walk(), moving.take(p, wc, cam)))
    p.set(wc, SIGHTS_FORCED_VAR, False)

    gun = p.get(wc, "Held").get_class().get_name()
    p.note(f"{gun}; " + still.line("standing"))
    p.note(f"{gun}; " + moving.line("walking"))
    p.check("walking: the pawn really walked", statistics.mean(moving.speed) > 100.0,
            f"{statistics.mean(moving.speed):.0f} cm/s")
    for s, what in ((still, "standing"), (moving, "walking")):
        p.check(f"{what}: the camera is on the gun's eye point as each frame ends",
                max(s.eye) < EYE_CM, f"worst {max(s.eye):.4f} cm")
        p.check(f"{what}: ...and the front sight on the middle of the view",
                max(s.front) < FRONT_DEG, f"worst {max(s.front):.4f} deg")
