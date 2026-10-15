"""The cut to the sights keeps the point aimed at (weapon_component/sight_cut.py).

Before the cut the camera is on the boom, behind and beside the shoulder, and
the crosshair is on ViewPoint (what the camera's trace hit). The cut puts the
camera at the head bone; with the boom's rotation kept, the middle of the
view moved by the shoulder's offset and the target jumped aside. Now the view
turns on the cut's frame from the anchor onto ViewPoint.

Per case (from the hip, and from the shoulder aim; the view tipped down so the
crosshair is on the ground a few metres out, where the old jump was degrees):
  - on the cut's frame (SightCut) the control rotation turns, by more than
    MIN_TURN_DEG (the gate opens: the turn is the fix, not nothing), and the
    camera, now at the head, looks at the point the boom's view was on
    (within CUT_FRAME_DEG: from the hip the body's own turn to the new yaw
    carries the camera about half a degree on that one frame);
  - the next frame's camera trace lands on that point (within CUT_DEG, seen
    from the camera);
  - from the cut until the gun is up and the camera on its sight line, the
    middle of the view stays within RAISE_DEG of the point (the turn onto the
    sight line takes the last of it), and the gun's sights end on it.

SightsForced and AimForced stand in for the keys. Creatures are taken away
first, so nothing walks into the line or kills the player.
"""

SYSTEMS = ('weapons',)

import math
import os
import shutil
import time

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import LOOK_VAR, SEATED_VAR, SIGHTS_FORCED_VAR
from graphics_menu.dev_consts import DEV_GUNS_REQUEST_VAR
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR, PROFILE_SLOT
from combat.weapon_component import vars as WV

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, DEV_GUNS_REQUEST_VAR)] + [
    (WEAPON_COMP_BP_PATH, str(v)) for v in
    (WV.EquippedIndex, WV.NeedsRefresh, WV.AimForced, SIGHTS_FORCED_VAR)]
ML = unreal.MathLibrary
GS = unreal.GameplayStatics

GUN = "BP_Shotgun_C"
PITCH = -14.0           # the crosshair on the ground a few metres out
CASES = (("from the hip", False), ("from the shoulder aim", True))
SETTLE_S = 0.8
MIN_TURN_DEG = 0.3      # the cut turns the view at least this much here
CUT_DEG = 0.25          # the next frame's trace on the point
CUT_FRAME_DEG = 1.0     # the view on the point on the cut's own frame: from the
                        # hip the body turns after the camera is placed that
                        # frame (0.52 deg measured), the boom's turn the next
RAISE_DEG = 1.5         # ...and while the gun rises and the view takes its line
SEATED_S = 0.4          # watched on after the turn onto the sight line ends
WALL_WAIT_S = 25.0


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


def _clear_creatures(p):
    ctrls = GS.get_all_actors_of_class(p.world(), unreal.AIController)
    for c in ctrls:
        pawn = c.get_controlled_pawn()
        if pawn is not None:
            pawn.destroy_actor()
        c.destroy_actor()


def _look(p, pitch):
    rot = p.controller().get_control_rotation()
    p.controller().set_control_rotation(unreal.Rotator(roll=rot.roll, pitch=pitch,
                                                       yaw=rot.yaw))


def _off(cam, point):
    """How far the middle of the camera's view is off ``point`` (deg)."""
    return _angle(cam.get_forward_vector(), point - cam.get_world_location())


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
    _clear_creatures(p)
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    cam = p.pawn().get_component_by_class(unreal.CameraComponent)
    p.set(hud, DEV_GUNS_REQUEST_VAR, True)
    yield lambda: not p.get(hud, DEV_GUNS_REQUEST_VAR)
    bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    if not p.check(f"{GUN} is in the bag", GUN in bag, str(bag)):
        return
    p.set(wc, str(WV.EquippedIndex), bag.index(GUN))
    p.set(wc, str(WV.NeedsRefresh), True)
    held = lambda: p.get(wc, "Held")
    yield _until(lambda: held() is not None and held().get_class().get_name() == GUN)
    for label, shoulder in CASES:
        yield from _case(p, wc, cam, label, shoulder)


def _case(p, wc, cam, label, shoulder):
    _look(p, PITCH)
    p.set(wc, str(WV.AimForced), shoulder)
    yield SETTLE_S
    _look(p, PITCH)
    yield 0.2

    p.set(wc, SIGHTS_FORCED_VAR, True)
    rot_was = [p.controller().get_control_rotation()]

    def cut():
        if p.get(wc, "SightSnapped"):
            return True
        rot_was[0] = p.controller().get_control_rotation()
        return False
    yield _until(cut)
    point = p.get(wc, str(WV.ViewPoint))
    rot = p.controller().get_control_rotation()
    turn = _angle(ML.get_forward_vector(rot_was[0]), ML.get_forward_vector(rot))
    at_cut = _off(cam, point)
    out = (point - cam.get_world_location()).length()
    p.check(f"{label}: on the cut's frame (SightCut) the view turns onto what the "
            f"boom's view was on: more than {MIN_TURN_DEG:g} deg here, and the "
            f"camera at the head looks at that point (within {CUT_FRAME_DEG:g} deg)",
            p.get(wc, str(WV.SightCut)) and turn > MIN_TURN_DEG
            and at_cut < CUT_FRAME_DEG,
            f"SightCut {p.get(wc, str(WV.SightCut))}, turned {turn:.2f} deg, the "
            f"middle of the view {at_cut:.3f} deg off a point {out / 100:.1f} m out")

    yield       # one frame: the camera trace from the new view
    seen = p.get(wc, str(WV.ViewPoint))
    next_off = _angle(seen - cam.get_world_location(), point - cam.get_world_location())
    p.check(f"{label}: ...the next frame's camera trace lands on the same point "
            f"(within {CUT_DEG:g} deg), and SightCut is over",
            next_off < CUT_DEG and not p.get(wc, str(WV.SightCut)),
            f"{next_off:.3f} deg apart, {(seen - point).length():.1f} cm")

    worst = [next_off]
    done = [None]

    def raised():
        worst[0] = max(worst[0], _off(cam, point))
        if p.get(wc, SEATED_VAR) and p.get(wc, LOOK_VAR) > 0.9999:
            done[0] = done[0] or time.time()
        return done[0] is not None and time.time() - done[0] > SEATED_S
    yield _until(raised)
    final = _off(cam, point)
    p.check(f"{label}: ...from the cut until the gun is up and the view on its "
            f"sight line, the middle of the view stays within {RAISE_DEG:g} deg "
            f"of the point",
            done[0] is not None and worst[0] < RAISE_DEG,
            f"worst {worst[0]:.3f} deg, {final:.3f} deg at the end")

    p.set(wc, SIGHTS_FORCED_VAR, False)
    p.set(wc, str(WV.AimForced), False)
    yield _until(lambda: p.get(wc, "SightSeat") < 1e-4)
    yield 0.3
