"""Bringing the sights up from a lowered gun: one motion from the key, the
camera travelling from the boom to the eye point and zooming as it goes, with
the view on the target all the way; it does not ride the gun's line up from
the hip.

SightsForced stands in for the sights key (no key can be injected into a
headless game), so the whole path runs as it does for a player: the aim state,
the carry raising the gun, SightBlend, the seat and the look
(weapon_component/seat.py) and the camera.

Per gun (the shotgun, level and looking down; the pistol; the sniper):
  - carried, the gun's sight line is far off the view (what a camera riding it
    would have looked along);
  - sights held: every frame until the camera is on the sights, the camera
    looks where the control rotation does, within VIEW_DEG;
  - it is one motion: SightSeat rises on every frame from the key (the camera
    is well on its way before the gun is up), the camera only ever gets
    nearer to where it ends up, and the zoom goes with it, frame for frame,
    to the weapon's own (the sniper's 4x: no stop at the shoulder's);
  - the turn onto the sight line (SightLook) waits for SightSeated, and
    SightSeated is not set before the gun's line is within SIGHT_SEAT_DEG of
    the view;
  - seated: the camera is at the eye point with the front sight's tip on the
    middle of the view;
  - let go: the view stays on the control rotation all the way home, the gun
    stays up until the camera has left it (SightSeat under SEAT_HOLD), and is
    lowered after.

Run with --windowed and OW_RAISE_SHOTS=1 to save the first gun's view to
Saved/Screenshots/MacEditor: carried (the crosshair), then down the sights
with debug mode off (no crosshair: the sights are the reticle) and on (the
crosshair over them). A headless run draws nothing, so the crosshair's gate is
otherwise checked on the graph only (graphics_menu/reticle_checks.py).

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

SYSTEMS = ('weapons',)

import math
import os
import shutil
import time

import unreal

from combat.carry_tuning import LOWERED_VAR
from combat.game_state import DEBUG_MODE_VAR
from net.state_consts import GAME_STATE_BP_PATH
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import (
    LOOK_VAR, SEAT_HOLD, SEAT_VAR, SEATED_VAR, SIGHT_SEAT_DEG, SIGHTS_FORCED_VAR,
)
from combat import weapon_models as M
from graphics_menu.dev_consts import DEV_GUNS_REQUEST_VAR
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR, PROFILE_SLOT
from combat.weapon_component import vars as WV

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, DEV_GUNS_REQUEST_VAR),
            (GAME_STATE_BP_PATH, DEBUG_MODE_VAR)] + [
    (WEAPON_COMP_BP_PATH, v) for v in
    (WV.EquippedIndex, WV.NeedsRefresh, SIGHTS_FORCED_VAR)]
ML = unreal.MathLibrary
GS = unreal.GameplayStatics
# (class, label, the view's pitch when the key goes down)
CASES = (("BP_Shotgun_C", "Shotgun", "SHOTGUN", 0.0),
         ("BP_Shotgun_C", "Shotgun, looking -25", "SHOTGUN", -25.0),
         ("BP_Pistol_C", "Pistol", "PISTOL", 0.0),
         ("BP_SniperRifle_C", "Sniper", "SNIPER", 0.0))

SETTLE_S = 0.6          # the equip, the gun coming down
LOWERED_DEG = 25.0      # carried, the sight line is at least this far off the view
VIEW_DEG = 4.0          # the camera against the control rotation, all the way
BOOM_CM = 0.5           # the camera is on the boom's end
EYE_CM = 0.5            # ...or at the eye point
FRONT_DEG = 0.1         # the front sight on the middle of the view
SEAT_AT_LATCH = 0.5     # the camera is this far to the gun before the gun is up
BACK_CM = 0.5           # the camera never backs away from where it ends up
ZOOM_LAG = 0.05         # the zoom's progress against SightSeat, any frame
WALL_WAIT_S = 25.0      # a headless game's clock is slow: bound waits by the wall
SHOTS = bool(os.environ.get("OW_RAISE_SHOTS"))


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def _until(cond):
    end = time.time() + WALL_WAIT_S
    return lambda: cond() or time.time() > end


def _angle(a, b):
    return math.degrees(math.atan2(a.cross(b).length(), a.dot(b)))


def _shot(p, debug, what):
    """Save the view with its HUD, debug mode as given."""
    p.set(p.game_state(), DEBUG_MODE_VAR, debug)
    yield 0.3
    unreal.SystemLibrary.execute_console_command(p.world(), "shot showui")
    p.note(f"shot showui: {what}")
    yield 0.5


def _look(p, pitch):
    rot = p.controller().get_control_rotation()
    p.controller().set_control_rotation(unreal.Rotator(roll=rot.roll, pitch=pitch,
                                                       yaw=rot.yaw))


class _Watch(object):
    """Each frame of a transition: the camera against the control rotation,
    the boom and the gun."""

    def __init__(self, p, wc, cam, sights):
        self.p, self.wc, self.cam = p, wc, cam
        self.eye, self.front = (unreal.Vector(*v) for v in sights)
        self.view = 0.0
        self.look_early = 0.0       # SightLook before SightSeated
        self.seat_at_latch = None   # SightSeat when it latched
        self.stalls = 0             # frames SightSeat did not rise, short of 1
        self.seat = p.get(wc, SEAT_VAR)
        self.zoom_lag = 0.0         # the zoom's progress against SightSeat
        self.path = []              # the camera, in the world
        self.seated_at = None       # the gun's line off the view when it latched
        self.held_up = True         # never Lowered with the camera still on it
        self.n = 0
        self.t0 = GS.get_time_seconds(p.world())
        self.t_seated = None

    def aim(self):
        return ML.get_forward_vector(self.p.controller().get_control_rotation())

    def line_off(self):
        xf = self.p.get(self.wc, "Held").get_actor_transform()
        return _angle(ML.transform_location(xf, self.front)
                      - ML.transform_location(xf, self.eye), self.aim())

    def off_boom(self):
        return self.cam.get_editor_property("relative_location").length()

    def sample(self):
        p, wc = self.p, self.wc
        seated, seat = p.get(wc, SEATED_VAR), p.get(wc, SEAT_VAR)
        self.view = max(self.view, _angle(self.cam.get_forward_vector(), self.aim()))
        if not seated:
            self.look_early = max(self.look_early, p.get(wc, LOOK_VAR))
        if 0.0 < seat <= self.seat and seat < 0.999:
            self.stalls += 1
        self.seat = seat
        self.path.append(self.cam.get_world_location())
        if p.get(wc, "SightAiming"):
            base, zoom = p.get(wc, "BaseFOV"), p.get(wc, "AimZoom")
            went = (base - p.get(wc, "CurrentFOV")) / (base - base / zoom)
            self.zoom_lag = max(self.zoom_lag, abs(went - seat))
        if seated and self.seated_at is None:
            self.seated_at = self.line_off()
            self.seat_at_latch = seat
            self.t_seated = GS.get_time_seconds(p.world()) - self.t0
        if seat > SEAT_HOLD and p.get(wc, LOWERED_VAR):
            self.held_up = False
        self.n += 1

    def took(self):
        return GS.get_time_seconds(self.p.world()) - self.t0

    def backed(self):
        """The furthest the camera ever moved away from where it ended up,
        between two frames (cm)."""
        far = [(q - self.path[-1]).length() for q in self.path]
        return max([b - a for a, b in zip(far, far[1:])] + [0.0])

    def off_line(self):
        """The furthest the camera strayed from the straight line between
        where it started and where it ended up (cm)."""
        a, b = self.path[0], self.path[-1]
        along = (b - a).normal()
        return max(((q - a) - along * (q - a).dot(along)).length()
                   for q in self.path)


def _case(p, wc, cam, bag, cls, label, key, pitch, first):
    sights = (getattr(M, f"{key}_SIGHT"), getattr(M, f"{key}_SIGHT_FRONT"))
    p.set(wc, "EquippedIndex", bag.index(cls))
    p.set(wc, "NeedsRefresh", True)
    held = lambda: p.get(wc, "Held")
    yield _until(lambda: held() is not None and held().get_class().get_name() == cls)
    _look(p, pitch)
    # Lowered first (a game's first 1.5 s count as just after a shot), then
    # the ready pose's blend out.
    yield _until(lambda: p.get(wc, LOWERED_VAR) and p.get(wc, SEAT_VAR) == 0.0)
    yield SETTLE_S

    # --- carried ---------------------------------------------------------------
    watch = _Watch(p, wc, cam, sights)
    carried = watch.line_off()
    p.check(f"{label}: carried, the gun is lowered and its sight line is far off "
            f"the view (> {LOWERED_DEG:g} deg)",
            p.get(wc, LOWERED_VAR) and carried > LOWERED_DEG and watch.off_boom() < BOOM_CM,
            f"{carried:.1f} deg off, camera {watch.off_boom():.2f} cm off the boom")

    if SHOTS and first:
        yield from _shot(p, False, f"{label}, carried: the crosshair")

    # --- the sights key goes down ----------------------------------------------
    p.set(wc, SIGHTS_FORCED_VAR, True)

    def up():
        watch.sample()
        return min(p.get(wc, SEAT_VAR), p.get(wc, LOOK_VAR)) > 0.9999
    yield _until(up)
    seat, look = p.get(wc, SEAT_VAR), p.get(wc, LOOK_VAR)
    p.check(f"{label}: the sights key brings the camera onto the gun "
            f"(SightAiming, {SEATED_VAR}, {SEAT_VAR} and {LOOK_VAR} 1)",
            p.get(wc, "SightAiming") and p.get(wc, SEATED_VAR)
            and min(seat, look) > 0.9999,
            f"{SEAT_VAR} {seat:.4f}, {LOOK_VAR} {look:.4f} after "
            f"{watch.took():.2f} s, {watch.n} frames")
    p.check(f"{label}: ...and the whole way there the view stays where the player "
            f"is looking (camera within {VIEW_DEG:g} deg of the control rotation)",
            watch.n > 5 and watch.view < VIEW_DEG,
            f"worst {watch.view:.2f} deg over {watch.n} frames "
            f"(the gun came up from {carried:.1f} deg off)")
    p.check(f"{label}: ...in one motion from the key: {SEAT_VAR} rises on every "
            f"frame, and is past {SEAT_AT_LATCH:g} before the gun is up",
            watch.stalls == 0 and (watch.seat_at_latch or 0.0) > SEAT_AT_LATCH,
            f"{watch.stalls} frames without a rise, {SEAT_VAR} "
            f"{watch.seat_at_latch} when {SEATED_VAR} latched")
    p.check(f"{label}: ...the camera only ever nearer to where it ends up "
            f"(never {BACK_CM:g} cm back in a frame)",
            watch.backed() < BACK_CM,
            f"worst {watch.backed():.3f} cm back; {watch.off_line():.1f} cm at most "
            f"off the straight line, over {(watch.path[-1] - watch.path[0]).length():.0f} cm")
    p.check(f"{label}: ...and the zoom goes with it to the weapon's own "
            f"{held().get_editor_property('AdsZoom'):g}x, frame for frame (its "
            f"progress within {ZOOM_LAG:g} of {SEAT_VAR})",
            watch.zoom_lag < ZOOM_LAG
            and abs(p.get(wc, "AimZoom") - held().get_editor_property("AdsZoom")) < 1e-6
            and abs(p.get(wc, "BaseFOV") / p.get(wc, "CurrentFOV")
                    - held().get_editor_property("AdsZoom")) < 0.01,
            f"worst {watch.zoom_lag:.4f} apart, "
            f"{p.get(wc, 'BaseFOV') / p.get(wc, 'CurrentFOV'):.3f}x at the end")
    p.check(f"{label}: ...the turn onto the sight line ({LOOK_VAR}) waits until "
            f"the gun is up",
            watch.look_early == 0.0,
            f"{LOOK_VAR} {watch.look_early:.4f} before {SEATED_VAR}")
    p.check(f"{label}: ...which is when its sight line is within "
            f"{SIGHT_SEAT_DEG:g} deg of the view",
            watch.seated_at is not None and watch.seated_at < SIGHT_SEAT_DEG,
            f"{watch.seated_at} deg off when {SEATED_VAR} latched, "
            f"{watch.t_seated} s after the key")
    xf = held().get_actor_transform()
    at = cam.get_world_location()
    eye = (ML.inverse_transform_location(xf, at) - watch.eye).length()
    front = _angle(ML.transform_location(xf, watch.front) - at, cam.get_forward_vector())
    p.check(f"{label}: seated, the camera is at the eye point with the front "
            f"sight's tip on the middle of the view",
            eye < EYE_CM and front < FRONT_DEG,
            f"{eye:.3f} cm from the eye point, the tip {front:.4f} deg off the middle")
    if SHOTS and first:
        yield from _shot(p, False, f"{label}, down the sights: no crosshair")
        yield from _shot(p, True, f"{label}, down the sights, debug mode: the crosshair")

    # --- and is let go ----------------------------------------------------------
    p.set(wc, SIGHTS_FORCED_VAR, False)
    down = _Watch(p, wc, cam, sights)

    def home():
        down.sample()
        return (max(p.get(wc, SEAT_VAR), p.get(wc, LOOK_VAR),
                    p.get(wc, "SightBlend")) < 1e-4
                and p.get(wc, LOWERED_VAR))
    yield _until(home)
    p.check(f"{label}: let go, the camera goes home to the boom and the gun is "
            f"lowered again",
            p.get(wc, SEAT_VAR) < 1e-4 and p.get(wc, LOWERED_VAR)
            and not p.get(wc, SEATED_VAR) and down.off_boom() < BOOM_CM,
            f"{SEAT_VAR} {p.get(wc, SEAT_VAR):.5f}, {down.off_boom():.2f} cm off the "
            f"boom after {down.took():.2f} s")
    p.check(f"{label}: ...with the view on the control rotation all the way",
            down.n > 5 and down.view < VIEW_DEG,
            f"worst {down.view:.2f} deg over {down.n} frames")
    p.check(f"{label}: ...the gun kept up until the camera had left it "
            f"({SEAT_VAR} under {SEAT_HOLD:g})", down.held_up)
    _look(p, 0.0)


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _run(p):
    yield lambda: _live_hud(p) is not None
    hud = _live_hud(p)
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    cam = p.pawn().get_component_by_class(unreal.CameraComponent)
    p.set(hud, DEV_GUNS_REQUEST_VAR, True)
    yield lambda: not p.get(hud, DEV_GUNS_REQUEST_VAR)
    bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    wanted = {c[0] for c in CASES}
    p.check("the shotgun, the pistol and the sniper are in the bag",
            wanted <= set(bag), str(bag))
    for i, (cls, label, key, pitch) in enumerate(CASES):
        if cls in bag:
            yield from _case(p, wc, cam, bag, cls, label, key, pitch, i == 0)
