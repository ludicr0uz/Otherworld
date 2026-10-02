"""Down the sights the camera's near plane cuts no hand open.

The eye is on the gun, and the pistol's is a hand's length behind the grip:
both thumbs lie beside the slide 6-10 cm from the eye, inside the view. At the
engine's default near plane (10 cm) the plane went through them, and the
player saw into the hand and out the other side. Config/DefaultEngine.ini now
sets it to seat_tuning.NEAR_CLIP_CM.

  - The game's near plane is NEAR_CLIP_CM: read off the camera's own
    projection matrix, since an ini key in the wrong section is ignored
    without a word.
  - With each gun in the bag that has a sight line (so one added later is
    covered unnamed), standing, crouched and prone, the sights up: no part of
    either hand or forearm crosses the piece of the near plane that is in
    view. A hand is its skeleton, each bone a run of spheres from its parent
    (SKIN_CM, the forearm FOREARM_CM).
  - The positive case: the same test at the engine's default plane finds the
    pistol's hands cut, so the test can fail.

Nothing here renders. Run with --windowed and OW_SIGHT_SHOTS=1 to save each
gun's sight picture to Saved/Screenshots/MacEditor and look at the hands.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

import os
import shutil

import unreal

from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import (
    NEAR_CLIP_CM, NEAR_CLIP_DEFAULT_CM, SEAT_VAR, SIGHTS_FORCED_VAR,
)
from combat.weapon_component.sights import SIGHT_LINE_MIN_CM
from graphics_menu.dev_consts import DEV_GUNS_REQUEST_VAR
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR, PROFILE_SLOT

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, DEV_GUNS_REQUEST_VAR),
            (WEAPON_COMP_BP_PATH, "EquippedIndex"),
            (WEAPON_COMP_BP_PATH, "NeedsRefresh"),
            (WEAPON_COMP_BP_PATH, "Stance"),
            (WEAPON_COMP_BP_PATH, SIGHTS_FORCED_VAR)]
SHOTS = bool(os.environ.get("OW_SIGHT_SHOTS"))
SEATED = 0.99           # the camera is on the sights
HOME = 0.01             # ...and back on the boom
SETTLE_S = 0.5          # the stance's ease
# The wrist bones, by skin (the adventurer's, the mannequin's).
HANDS = ("RightHand", "LeftHand", "hand_r", "hand_l")
# How far the skin stands off a bone (cm): a finger or the palm, the forearm.
SKIN_CM = 2.0
FOREARM_CM = 4.0
STEPS = 8               # spheres per bone
# The tallest window the view is tested for (4:3): the near plane's piece in
# view is as wide as the field of view makes it and this much of that high.
TALLEST = 0.75
STANCES = ((0, "standing"), (1, "crouched"), (2, "prone"))


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def _has_sights(item):
    line = item.get_editor_property("SightAim") - item.get_editor_property("SightOffset")
    return line.length() > SIGHT_LINE_MIN_CM


def _arm_bones(mesh):
    """(parent, bone, skin radius) for each wrist, with the forearm it hangs
    off, and every bone under it."""
    names = [str(mesh.get_bone_name(i)) for i in range(mesh.get_num_bones())]
    parent = {n: str(mesh.get_parent_bone(n)) for n in names}
    runs = []
    for name in names:
        if name in HANDS:
            runs.append((parent[name], name, FOREARM_CM))
            continue
        up = parent[name]
        while up in parent and up not in HANDS:
            up = parent[up]
        if up in HANDS:
            runs.append((parent[name], name, SKIN_CM))
    return runs


def _projection(cam):
    """(the near plane, half the view's width per cm of depth), off the
    camera's projection matrix."""
    _view, proj, _both = unreal.GameplayStatics.get_view_projection_matrix(
        cam.get_camera_view(0.0))
    return proj.w_plane.z, 1.0 / proj.x_plane.x


def _spheres(mesh, cam, runs):
    """(bone, centre in the camera's space, radius): x is the depth."""
    into = cam.get_world_transform().inverse()
    out = []
    for parent, bone, radius in runs:
        a = unreal.MathLibrary.transform_location(into, mesh.get_socket_location(parent))
        b = unreal.MathLibrary.transform_location(into, mesh.get_socket_location(bone))
        out.extend((bone, a + (b - a) * (i / STEPS), radius) for i in range(STEPS + 1))
    return out


def _cut(spheres, near, half):
    """The bones the near plane cuts in view: a sphere that straddles the
    plane and reaches into the piece of it the view sees."""
    wide, high = near * half, near * half * TALLEST
    return sorted({bone for bone, at, r in spheres
                   if abs(at.x - near) < r and abs(at.y) < wide + r and abs(at.z) < high + r})


def _nearest_seen(spheres, half):
    """(depth of its near side, bone) of the sphere in view nearest the eye."""
    seen = [(at.x - r, bone) for bone, at, r in spheres
            if at.x > 0.0 and abs(at.y) < at.x * half + r
            and abs(at.z) < at.x * half * TALLEST + r]
    return min(seen) if seen else (float("inf"), "none")


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
    mesh = p.pawn().get_editor_property("mesh")
    cam = p.pawn().get_component_by_class(unreal.CameraComponent)
    runs = _arm_bones(mesh)
    wrists = sorted(bone for _parent, bone, _r in runs if bone in HANDS)
    p.check("the player's mesh has two wrists, and fingers under them",
            len(wrists) == 2 and len(runs) > 20, f"{wrists}, {len(runs)} bones")
    near, _half = _projection(cam)
    p.check(f"the game's near plane is {NEAR_CLIP_CM:g} cm: the engine took the ini's "
            "NearClipPlane", abs(near - NEAR_CLIP_CM) < 1e-4, f"{near:g}")

    p.set(hud, DEV_GUNS_REQUEST_VAR, True)
    yield lambda: not p.get(hud, DEV_GUNS_REQUEST_VAR)
    bag = p.get(wc, "Inventory")
    guns = [(i, item) for i, item in enumerate(bag) if _has_sights(item)]
    p.check("the bag holds the five guns, each with a sight line", len(guns) == 5,
            str([item.get_class().get_name() for _i, item in guns]))

    closest = (float("inf"), "none", "none")
    default_cuts = {}
    for index, item in guns:
        gun = item.get_class().get_name()[3:-2]
        p.set(wc, "EquippedIndex", index)
        p.set(wc, "NeedsRefresh", True)
        yield lambda: p.get(wc, "Held") == item
        p.set(wc, SIGHTS_FORCED_VAR, True)
        yield lambda: p.get(wc, SEAT_VAR) > SEATED
        for stance, label in STANCES:
            p.set(wc, "Stance", stance)
            yield SETTLE_S
            near, half = _projection(cam)
            spheres = _spheres(mesh, cam, runs)
            cut = _cut(spheres, near, half)
            depth, bone = _nearest_seen(spheres, half)
            closest = min(closest, (depth, bone, f"{gun}, {label}"))
            p.check(f"{gun}, {label}, down the sights: the near plane ({near:g} cm) "
                    "cuts no hand or forearm in view",
                    p.get(wc, SEAT_VAR) > SEATED and not cut,
                    f"cut: {cut}" if cut else
                    f"the nearest in view is {bone}, {depth:.1f} cm from the eye")
            if stance == 0:
                default_cuts[gun] = _cut(spheres, NEAR_CLIP_DEFAULT_CM, half)
                if SHOTS:
                    unreal.SystemLibrary.execute_console_command(p.world(), "shot")
                    yield 0.4
        p.set(wc, "Stance", 0)
        p.set(wc, SIGHTS_FORCED_VAR, False)
        yield lambda: p.get(wc, SEAT_VAR) < HOME

    was = default_cuts.get("Pistol", [])
    p.check(f"the test can fail: at the engine's default plane ({NEAR_CLIP_DEFAULT_CM:g} cm) "
            "the pistol's hands are cut, both thumbs among them",
            any("Right" in b or b.endswith("_r") for b in was)
            and any("Left" in b or b.endswith("_l") for b in was)
            and any("thumb" in b.lower() for b in was), str(was))
    depth, bone, where = closest
    p.check("no skin in view comes within a centimetre of the plane, on any gun",
            depth > NEAR_CLIP_CM + 1.0, f"{bone}, {depth:.1f} cm from the eye ({where})")
