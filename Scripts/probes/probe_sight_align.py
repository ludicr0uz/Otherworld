"""Down the sights the view runs along the gun's own sight line, and the sway
moves the view, the sights and the shot together.

No key can be injected into a headless game, so the probe holds SightBlend
(the body's share of the sights), SightSeat and SightLook (the camera's: where
it is and which way it looks) at 1 by writing them every frame, as
probe_scope_hide does. The Tick then eases the seat and the look
one step towards 0 (SightAiming is false), so to settle a pose the probe
writes the value that step lands near 1 from, and to MEASURE it slows the
game to a ten-thousandth (global time dilation): the step is then a millionth
and the blend is 1, which each scenario's first check confirms.

Per gun, standing, looking up and down, crouched, prone and walking:
  - the camera is at the weapon's SightOffset;
  - the front sight's tip (SightAim) and the rear sight are both on the
    middle of the view, so eye, rear and front are one line and the view runs
    down it;
  - AimPoint, where the shot goes, is on that line too.
Then the sway: at a clock where the sideways sine is at its peak the view has
turned by SWAY_YAW_DEG off where it was left, the sights still on the middle;
crouched and prone it is steadier by their scales; and letting go gives the
turn back and takes the camera home, level with the boom.

Run with --windowed and OW_SIGHT_SHOTS=1 to save each gun's sight picture to
Saved/Screenshots/MacEditor.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # passes here, fails on the 50 m probe level (T11)
SYSTEMS = ('weapons',)

import math
import os
import shutil

import unreal

from combat.carry_tuning import RAISE_FORCED_VAR
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import LOOK_VAR, SEAT_VAR
from combat.sway_tuning import (
    SWAY_CROUCH_SCALE, SWAY_MIN_STEP_DEG, SWAY_PITCH_VAR, SWAY_PRONE_SCALE, SWAY_TIME_VAR,
    SWAY_YAW_DEG, SWAY_YAW_PERIOD_S, SWAY_YAW_VAR, sway_at,
)
from combat.tuning import COMBAT
from combat import weapon_models as M
from graphics_menu.dev_consts import DEV_GUNS_REQUEST_VAR
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR, PROFILE_SLOT
from combat.weapon_component import vars as WV

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, DEV_GUNS_REQUEST_VAR)] + [
    (WEAPON_COMP_BP_PATH, v) for v in
    (WV.EquippedIndex, WV.NeedsRefresh, WV.Stance, WV.SightBlend, SEAT_VAR, LOOK_VAR,
     SWAY_TIME_VAR, RAISE_FORCED_VAR)]
ML = unreal.MathLibrary
# weapon_specs needs the editor (it solves the grips), so the sight lines are
# read where they are written. Class name -> the gun's row.
GUNS = {f"BP_{cls}_C": dict(display=cls, sight=getattr(M, f"{g}_SIGHT"),
                            sight_rear=getattr(M, f"{g}_SIGHT_REAR"),
                            sight_front=getattr(M, f"{g}_SIGHT_FRONT"))
        for cls, g in (("Shotgun", "SHOTGUN"), ("Pistol", "PISTOL"), ("SMG", "SMG"),
                       ("AssaultRifle", "RIFLE"), ("SniperRifle", "SNIPER"))}
SHOTS = bool(os.environ.get("OW_SIGHT_SHOTS"))

ON_LINE_DEG = 0.02      # a sight off the middle of the view by less: on it
EYE_CM = 0.02
SHOT_DEG = 0.1          # AimPoint is traced from last frame's camera
SWAY_DEG = 0.0005       # the view against the sway's own account of itself
VIEW_DEG = 4.0          # the gun's pose sits this near the control rotation
SETTLE_S = 0.5          # the stance's ease, the equip
SAMPLES = 12
STILL = 0.0001          # the engine's smallest time dilation


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def _held_name(p, wc):
    held = p.get(wc, "Held")
    return held.get_class().get_name() if held else None


def _angle(a, b):
    return math.degrees(math.atan2(a.cross(b).length(), a.dot(b)))


def _hold(p, wc, frames=None, seconds=None, each=None, walk=False, still=False):
    """Keep the sights up, for some frames or some game time. `each` runs
    first every frame, on what the last Tick left. `still`: the blend is
    written as 1 (the game is slowed, so the Tick's ease takes nothing off)."""
    left = [frames]
    t0 = [None]

    def step():
        world = p.world()
        if each:
            each()
        dt = unreal.GameplayStatics.get_world_delta_seconds(world)
        eased = 0.0 if still else min(dt * COMBAT.ads_interp_speed, 0.9)
        p.set(wc, SEAT_VAR, 1.0 / (1.0 - eased))
        p.set(wc, LOOK_VAR, 1.0 / (1.0 - eased))
        p.set(wc, "SightBlend", 1.0)    # held there by the seat (sights.py)
        if walk:
            p.pawn().add_movement_input(p.pawn().get_actor_forward_vector(), 1.0)
        if seconds is not None:
            now = unreal.GameplayStatics.get_time_seconds(world)
            t0[0] = now if t0[0] is None else t0[0]
            return now - t0[0] >= seconds
        left[0] -= 1
        return left[0] < 0
    yield step


def _slow(p, on):
    unreal.GameplayStatics.set_global_time_dilation(p.world(), STILL if on else 1.0)


class _Worst(object):
    """The worst of each measure over the frames sampled."""

    def __init__(self, p, wc, cam, spec):
        self.p, self.wc, self.cam, self.spec = p, wc, cam, spec
        self.blend = self.eye = self.front = self.rear = self.shot = 0.0
        self.n = 0

    def sample(self):
        p, wc = self.p, self.wc
        xf = p.get(wc, "Held").get_actor_transform()
        at = self.cam.get_world_location()
        fwd = self.cam.get_forward_vector()

        def off(point):
            world = ML.transform_location(xf, unreal.Vector(*point))
            return _angle(world - at, fwd)

        eye = ML.inverse_transform_location(xf, at)
        if self.n == 0:
            self.pitch = self.cam.get_world_rotation().pitch
            self.view = _view(p)
            self.sway = (p.get(wc, SWAY_YAW_VAR), p.get(wc, SWAY_PITCH_VAR),
                         p.get(wc, SWAY_TIME_VAR))
        self.blend = max(self.blend, abs(p.get(wc, "SightBlend") - 1.0),
                         abs(p.get(wc, SEAT_VAR) - 1.0),
                         abs(p.get(wc, LOOK_VAR) - 1.0))
        self.eye = max(self.eye, (eye - unreal.Vector(*self.spec["sight"])).length())
        self.front = max(self.front, off(self.spec["sight_front"]))
        self.rear = max(self.rear, off(self.spec["sight_rear"]))
        self.shot = max(self.shot, _angle(p.get(wc, "AimPoint") - at, fwd))
        self.n += 1

    def report(self, what):
        p = self.p
        p.check(f"{what}: the sights are held (SightBlend, {SEAT_VAR} and {LOOK_VAR} 1 over "
                f"{self.n} frames)",
                self.n >= SAMPLES and self.blend < 1e-4, f"off by {self.blend:.6f}")
        p.check(f"{what}: the camera is at the eye point",
                self.eye < EYE_CM, f"{self.eye:.4f} cm off")
        p.check(f"{what}: the front sight's tip is the middle of the view",
                self.front < ON_LINE_DEG, f"{self.front:.4f} deg off")
        p.check(f"{what}: ...and the rear sight is on it too (one line)",
                self.rear < ON_LINE_DEG, f"{self.rear:.4f} deg off")
        p.check(f"{what}: ...and so is AimPoint, where the shot goes",
                self.shot < SHOT_DEG, f"{self.shot:.4f} deg off")


def _measure(p, wc, cam, spec, what, walk=False, clock=None):
    """Settle the pose with the sights up, then measure it with the game slowed.
    `clock`: the sway's clock, held there while measuring."""
    def held():
        if clock is not None:
            p.set(wc, SWAY_TIME_VAR, clock)

    yield from _hold(p, wc, seconds=SETTLE_S, walk=walk, each=held)
    _slow(p, True)
    try:
        yield from _hold(p, wc, frames=4, each=held, still=True)
        worst = _Worst(p, wc, cam, spec)
        yield from _hold(p, wc, frames=SAMPLES, still=True,
                         each=lambda: (worst.sample(), held()))
    finally:
        _slow(p, False)
    worst.report(what)
    return worst


def _look(p, pitch):
    rot = p.controller().get_control_rotation()
    p.controller().set_control_rotation(unreal.Rotator(roll=rot.roll, pitch=pitch,
                                                       yaw=rot.yaw))


def _view(p):
    rot = p.controller().get_control_rotation()
    return rot.yaw, ML.normalize_axis(rot.pitch)


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
    # The sights are held up by writing SightBlend, with no aim key down:
    # this is what the key would do to the carry (the gun is raised).
    p.set(wc, RAISE_FORCED_VAR, True)
    p.set(hud, DEV_GUNS_REQUEST_VAR, True)
    yield lambda: not p.get(hud, DEV_GUNS_REQUEST_VAR)
    bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    specs = GUNS
    p.check("all five guns are in the bag", set(specs) <= set(bag), str(bag))

    for name in [n for n in bag if n in specs]:
        spec, gun = specs[name], specs[name]["display"]
        p.set(wc, "EquippedIndex", bag.index(name))
        p.set(wc, "NeedsRefresh", True)
        yield lambda: _held_name(p, wc) == name
        yield from _measure(p, wc, cam, spec, f"{gun}, standing")
        if SHOTS:
            _slow(p, True)
            yield from _hold(p, wc, frames=4, still=True)
            unreal.SystemLibrary.execute_console_command(p.world(), "shot")
            yield from _hold(p, wc, frames=8, still=True)
            _slow(p, False)
        for pitch in (25.0, -35.0):
            _look(p, pitch)
            worst = yield from _measure(p, wc, cam, spec, f"{gun}, looking {pitch:+.0f}")
            p.check(f"{gun}, looking {pitch:+.0f}: the gun, and the view down it, "
                    "went where the mouse did",
                    abs(worst.pitch - worst.view[1]) < VIEW_DEG,
                    f"camera pitch {worst.pitch:.2f}, control {worst.view[1]:.2f}")
        _look(p, 0.0)
        yield from _measure(p, wc, cam, spec, f"{gun}, walking", walk=True)
        for stance, label in ((1, "crouched"), (2, "prone")):
            p.set(wc, "Stance", stance)
            yield from _measure(p, wc, cam, spec, f"{gun}, {label}")
        p.set(wc, "Stance", 0)
        yield lambda: max(p.get(wc, "SightBlend"), p.get(wc, SEAT_VAR), p.get(wc, LOOK_VAR)) < 1e-3

    yield from _sway(p, wc, cam, specs[name])


def _sway(p, wc, cam, spec):
    """With the last gun in hand: the sway turns the view, sights and all."""
    yield 0.2
    def swayed():
        return p.get(wc, SWAY_YAW_VAR), p.get(wc, SWAY_PITCH_VAR)

    def at_rest():
        """Where the mouse left the view: the view less what the sway holds."""
        (yaw, pitch), (sy, sp) = _view(p), swayed()
        return yaw - sy, pitch - sp

    # A last step too small for the controller to take is never taken back.
    slack = SWAY_MIN_STEP_DEG + 1e-6
    p.check(f"at the hip nothing sways (within the {SWAY_MIN_STEP_DEG:g} deg step)",
            max(abs(v) for v in swayed()) <= slack, "%.5f %.5f" % swayed())
    yaw0, pitch0 = at_rest()
    peak = SWAY_YAW_PERIOD_S / 4.0      # the sideways sine at its most

    for stance, scale, label in ((0, 1.0, "standing"), (1, SWAY_CROUCH_SCALE, "crouched"),
                                 (2, SWAY_PRONE_SCALE, "prone")):
        p.set(wc, "Stance", stance)
        worst = yield from _measure(p, wc, cam, spec, f"swayed, {label}", clock=peak)
        got_yaw, got_pitch, clock = worst.sway
        want_yaw, want_pitch = sway_at(clock, 1.0, scale)
        p.check(f"{label}: at the sideways peak the sway is {SWAY_YAW_DEG * scale:.3f} deg "
                "of yaw, and the pitch its own sine",
                abs(got_yaw - want_yaw) <= SWAY_MIN_STEP_DEG + 1e-6
                and abs(got_pitch - want_pitch) <= SWAY_MIN_STEP_DEG + 1e-6
                and abs(abs(got_yaw) - SWAY_YAW_DEG * scale) < 0.01,
                f"yaw {got_yaw:.4f} (want {want_yaw:.4f}) pitch {got_pitch:.4f} "
                f"(want {want_pitch:.4f})")
        yaw, pitch = worst.view
        p.check(f"{label}: ...and the view has turned by exactly that",
                abs(ML.normalize_axis(yaw - yaw0) - got_yaw) < SWAY_DEG
                and abs(pitch - pitch0 - got_pitch) < SWAY_DEG,
                f"view moved {ML.normalize_axis(yaw - yaw0):.4f}, {pitch - pitch0:.4f}")
    p.set(wc, "Stance", 0)

    yield lambda: max(p.get(wc, "SightBlend"), p.get(wc, SEAT_VAR), p.get(wc, LOOK_VAR)) < 1e-4
    yield 0.1
    yaw, pitch = at_rest()
    p.check("sights down: the sway gave the view back",
            abs(ML.normalize_axis(yaw - yaw0)) < SWAY_DEG and abs(pitch - pitch0) < SWAY_DEG
            and max(abs(v) for v in swayed()) <= slack,
            f"view off by {ML.normalize_axis(yaw - yaw0):.5f}, {pitch - pitch0:.5f}; "
            "still swayed %.5f %.5f" % swayed())
    yaw, pitch = _view(p)
    rot = cam.get_world_rotation()
    p.check("...and the camera is level with the boom again (the control rotation)",
            abs(ML.normalize_axis(rot.yaw - yaw)) < 0.01 and abs(rot.pitch - pitch) < 0.01
            and abs(rot.roll) < 0.01, f"camera {rot.pitch:.3f} {rot.yaw:.3f} {rot.roll:.3f}")
    off = cam.get_editor_property("relative_location")
    p.check("...and back on the boom's end",
            max(abs(off.x), abs(off.y), abs(off.z)) < 0.5, str(off.to_tuple()))
