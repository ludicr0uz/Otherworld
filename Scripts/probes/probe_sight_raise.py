"""Bringing the sights up from a lowered gun: the view stays on the target
and the gun rises to it; the camera does not ride the gun up from the hip.

SightsForced stands in for the sights key (no key can be injected into a
headless game), so the whole path runs as it does for a player: the aim state,
the carry raising the gun, SightBlend, the seat (weapon_component/seat.py)
and the camera.

Per gun (the shotgun, level and looking down; the pistol; the sniper):
  - carried, the gun's sight line is far off the view (what a camera riding it
    would have looked along);
  - sights held: every frame until the camera is on the sights, the camera
    looks where the control rotation does, within VIEW_DEG; it does not leave
    the boom before SightSeated, and SightSeated is not set before the gun's
    line is within SIGHT_SEAT_DEG of the view;
  - seated: the camera is at the eye point with the front sight's tip on the
    middle of the view;
  - the sniper zooms no further than the shoulder's zoom until seated;
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

import math
import os
import shutil
import time

import unreal

from combat.carry_tuning import LOWERED_VAR
from combat.game_state import DEBUG_MODE_VAR
from combat.paths import GAME_MODE_BP_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import (
    SEAT_HOLD, SEAT_VAR, SEATED_VAR, SIGHT_SEAT_DEG, SIGHTS_FORCED_VAR,
)
from combat.tuning import COMBAT
from combat import weapon_models as M
from graphics_menu.dev_consts import DEV_GUNS_REQUEST_VAR
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR, PROFILE_SLOT

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, DEV_GUNS_REQUEST_VAR),
            (GAME_MODE_BP_PATH, DEBUG_MODE_VAR)] + [
    (WEAPON_COMP_BP_PATH, v) for v in
    ("EquippedIndex", "NeedsRefresh", SIGHTS_FORCED_VAR)]
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
    p.set(p.game_mode(), DEBUG_MODE_VAR, debug)
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
        self.view = self.zoom_unseated = 0.0
        self.early = 0.0            # off the boom before SightSeated
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
        if not seated and seat == 0.0:
            self.early = max(self.early, self.off_boom())
            self.zoom_unseated = max(self.zoom_unseated,
                                     p.get(wc, "BaseFOV") / p.get(wc, "CurrentFOV"))
        if seated and self.seated_at is None:
            self.seated_at = self.line_off()
            self.t_seated = GS.get_time_seconds(p.world()) - self.t0
        if seat > SEAT_HOLD and p.get(wc, LOWERED_VAR):
            self.held_up = False
        self.n += 1

    def took(self):
        return GS.get_time_seconds(self.p.world()) - self.t0


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
        return p.get(wc, SEAT_VAR) > 0.9999
    yield _until(up)
    seat = p.get(wc, SEAT_VAR)
    p.check(f"{label}: the sights key brings the camera onto the gun "
            f"(SightAiming, {SEATED_VAR}, {SEAT_VAR} 1)",
            p.get(wc, "SightAiming") and p.get(wc, SEATED_VAR) and seat > 0.9999,
            f"{SEAT_VAR} {seat:.4f} after {watch.took():.2f} s, {watch.n} frames")
    p.check(f"{label}: ...and the whole way there the view stays where the player "
            f"is looking (camera within {VIEW_DEG:g} deg of the control rotation)",
            watch.n > 5 and watch.view < VIEW_DEG,
            f"worst {watch.view:.2f} deg over {watch.n} frames "
            f"(the gun came up from {carried:.1f} deg off)")
    p.check(f"{label}: ...the camera waits on the boom until the gun is up",
            watch.early < BOOM_CM, f"{watch.early:.2f} cm off the boom before {SEATED_VAR}")
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
    if abs(held().get_editor_property("AdsZoom") - COMBAT.shoulder_zoom) > 0.1:
        yield _until(lambda: p.get(wc, "BaseFOV") / p.get(wc, "CurrentFOV")
                     > held().get_editor_property("AdsZoom") - 0.05)
        zoom = p.get(wc, "BaseFOV") / p.get(wc, "CurrentFOV")
        p.check(f"{label}: the scope's zoom waits for the camera: no more than "
                f"the shoulder's {COMBAT.shoulder_zoom:g}x before {SEATED_VAR}, "
                f"its own after",
                watch.zoom_unseated < COMBAT.shoulder_zoom + 0.01
                and zoom > held().get_editor_property("AdsZoom") - 0.05,
                f"{watch.zoom_unseated:.3f}x before, {zoom:.3f}x after")

    if SHOTS and first:
        yield from _shot(p, False, f"{label}, down the sights: no crosshair")
        yield from _shot(p, True, f"{label}, down the sights, debug mode: the crosshair")

    # --- and is let go ----------------------------------------------------------
    p.set(wc, SIGHTS_FORCED_VAR, False)
    down = _Watch(p, wc, cam, sights)

    def home():
        down.sample()
        return (max(p.get(wc, SEAT_VAR), p.get(wc, "SightBlend")) < 1e-4
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
