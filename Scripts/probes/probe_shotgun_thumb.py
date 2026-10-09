"""Down the shotgun's sights both thumbs are out of the sight picture
(combat/shotgun_hold.py). The shotgun is held in the rifle's ready pose, a
shipped clip; what keeps the left thumb from standing beside the bead is the
shotgun's own support point, which the IK holds the left hand on.

The sights are raised the real way, by SightsForced (the probes' stand-in for
the sights key). Seated, the live mesh's thumb joints are read in the held
gun's own frame (+X down the barrel, +Y right, +Z up; the gun is rigid in the
hand, so this is what the eye on its sight line sees):

  - the shotgun and the rifle both play the skin's rifle pose;
  - the shotgun's grip thumb, as the clip lays it along the stock's wrist, is
    at least 2.5 cm under the sight line, joints and tip;
  - the support hand's thumb is all of it under the sight line, its joints
    under the barrel's top (the clip stands its tip 3.7 cm above the line);
  - the rifle's support thumb still stands up the handguard, where the clip
    has it: its sight line is 14 cm above the grip.

Run with --windowed and OW_SIGHT_SHOTS=1 to save the shotgun's sight picture
to Saved/Screenshots/MacEditor.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

import math
import os
import shutil

import unreal

from combat.grip import part_placement
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import SEAT_VAR, SIGHTS_FORCED_VAR
from combat.shotgun_hold import THUMB_TIP_CM
from combat.skin import skin_of_mesh
from combat.weapon_models import shotgun_outline
from graphics_menu.dev_consts import DEV_GUNS_REQUEST_VAR
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR, PROFILE_SLOT
from combat.weapon_component import vars as WV

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, DEV_GUNS_REQUEST_VAR),
            (WEAPON_COMP_BP_PATH, WV.EquippedIndex),
            (WEAPON_COMP_BP_PATH, WV.NeedsRefresh),
            (WEAPON_COMP_BP_PATH, SIGHTS_FORCED_VAR)]
SHOTS = bool(os.environ.get("OW_SIGHT_SHOTS"))
SEATED = 0.99           # the camera is on the sights
HOME = 0.01             # ...and back on the boom
# The grip thumb lies along the top of the stock's wrist: this far under the
# sight line at least (cm; verify/shotgun_pose.py asks 3 of the clip).
GRIP_THUMB_UNDER_CM = 2.5


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _sights(p, wc, index):
    """Equip the bag's item ``index`` and bring its sights up."""
    item = p.get(wc, "Inventory")[index]
    p.set(wc, "EquippedIndex", index)
    p.set(wc, "NeedsRefresh", True)
    yield lambda: p.get(wc, "Held") == item
    p.set(wc, SIGHTS_FORCED_VAR, True)
    yield lambda: p.get(wc, SEAT_VAR) > SEATED
    yield 0.3


def _thumb(mesh, held, bones):
    """The thumb's three joints and its tip in ``held``'s frame, and the line
    of each joint to the next (the last: down its bone's long axis)."""
    into = held.get_actor_transform().inverse()
    at = [unreal.MathLibrary.transform_location(into, mesh.get_socket_location(b))
          for b in bones]
    lines = [(b - a).normal() for a, b in zip(at, at[1:])]
    # The last joint has no child: its line is the bone's long axis, the one
    # its parent's line runs down (shotgun_hold.thumb_lines).
    mid = mesh.get_socket_rotation(bones[1]).quaternion()
    end = mesh.get_socket_rotation(bones[2]).quaternion()
    axis = mid.unrotate_vector(mesh.get_socket_location(bones[2])
                               - mesh.get_socket_location(bones[1])).normal()
    tip_line = unreal.MathLibrary.transform_direction(into, end.rotate_vector(axis))
    return at + [at[-1] + tip_line * THUMB_TIP_CM], lines + [tip_line]


def _off_line(held, point):
    """How far off the sight line ``point`` (weapon frame) is seen from the
    eye, degrees."""
    eye = held.get_editor_property("SightOffset")
    line = (held.get_editor_property("SightAim") - eye).normal()
    to = (point - eye).normal()
    return math.degrees(math.acos(max(-1.0, min(1.0, line.dot(to)))))


def _fmt(v):
    return f"({v.x:.1f}, {v.y:.1f}, {v.z:.1f})"


def _run(p):
    yield lambda: _live_hud(p) is not None
    hud = _live_hud(p)
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    mesh = p.pawn().get_editor_property("mesh")
    # player_skin() asks the editor's asset subsystem, which a game has not.
    worn = mesh.get_skeletal_mesh_asset().get_path_name().split(".")[0]
    skin = skin_of_mesh(worn)
    p.check("the player wears a known skin", skin is not None, worn)
    if skin is None:
        return
    p.set(hud, DEV_GUNS_REQUEST_VAR, True)
    yield lambda: not p.get(hud, DEV_GUNS_REQUEST_VAR)
    bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    p.check("the shotgun and the rifle are in the bag",
            {"BP_Shotgun_C", "BP_AssaultRifle_C"} <= set(bag), str(bag))

    # ── the shotgun ──
    yield from _sights(p, wc, bag.index("BP_Shotgun_C"))
    held = p.get(wc, "Held")
    pose = held.get_editor_property("AimPose")
    want = skin.aim_rifle.rsplit("/", 1)[-1]
    p.check(f"the shotgun is held in the rifle's ready pose, {want}",
            pose is not None and pose.get_name() == want, str(pose))
    line_z = min(held.get_editor_property("SightAim").z,
                 held.get_editor_property("SightOffset").z)
    (_base, mid, end, tip), _lines = _thumb(mesh, held, skin.grip_thumb)
    off = {name: _off_line(held, point) for name, point in (("last joint", end), ("tip", tip))}
    p.check(f"down the shotgun's sights the grip thumb is at least "
            f"{GRIP_THUMB_UNDER_CM:g} cm under the sight line (z {line_z:.1f})",
            max(mid.z, end.z, tip.z) < line_z - GRIP_THUMB_UNDER_CM,
            f"middle {_fmt(mid)}, last {_fmt(end)}, tip {_fmt(tip)}; seen from the eye "
            + ", ".join(f"{k} {v:.1f} deg off the line" for k, v in off.items()))
    # The other hand's, held on the pump by the shotgun's own point.
    (_base, mid, end, tip), _lines = _thumb(mesh, held, skin.support_thumb)
    centre, _rot, half = part_placement(shotgun_outline(), "Barrel")
    barrel_top = centre.z + half.z
    p.check(f"the support hand's thumb is under the sight line, its joints under "
            f"the barrel's top (z {barrel_top:g})",
            max(mid.z, end.z) < barrel_top < line_z and tip.z < line_z,
            f"middle {_fmt(mid)}, last {_fmt(end)}, tip {_fmt(tip)}")
    if SHOTS:
        unreal.SystemLibrary.execute_console_command(p.world(), "shot")
        yield 0.3
    p.set(wc, SIGHTS_FORCED_VAR, False)
    yield lambda: p.get(wc, SEAT_VAR) < HOME

    # ── the rifle: the same clip, its hand where the clip has it ──
    yield from _sights(p, wc, bag.index("BP_AssaultRifle_C"))
    held = p.get(wc, "Held")
    pose = held.get_editor_property("AimPose")
    want = skin.aim_rifle.rsplit("/", 1)[-1]
    p.check(f"the rifle's ready pose is {want} too",
            pose is not None and pose.get_name() == want, str(pose))
    _at, lines = _thumb(mesh, held, skin.grip_thumb)
    p.check("...and its thumb lies forward along the grip: every line of it "
            "runs up the barrel",
            all(line.x > 0.6 for line in lines),
            ", ".join(_fmt(line) for line in lines))
    _at, lines = _thumb(mesh, held, skin.support_thumb)
    p.check("...and its support thumb stands up the handguard, as the clip has it",
            all(line.z > 0.4 for line in lines),
            ", ".join(_fmt(line) for line in lines))
    p.set(wc, SIGHTS_FORCED_VAR, False)
    yield lambda: p.get(wc, SEAT_VAR) < HOME
