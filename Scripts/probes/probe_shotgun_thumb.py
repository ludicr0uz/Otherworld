"""With the shotgun down its sights the right thumb is over the stock's wrist
and the left along the pump, both out of the sight picture; the rifle keeps
the rifle pose's thumbs (combat/shotgun_pose.py).

The sights are raised the real way, by SightsForced (the probes' stand-in for
the sights key). Seated, the live mesh's thumb joints are read in the held
gun's own frame (+X down the barrel, +Y right, +Z up; the gun is rigid in the
hand, so this is what the eye on its sight line sees):

  - the shotgun plays A_AimShotgun, the rifle the skin's rifle pose;
  - the shotgun's middle thumb joint is over the top of the wrist, the last
    one down its left side, and the tip's line points down, not up the barrel;
  - seen from the eye (SightOffset), the last joint and the tip stand further
    off the sight line than the rifle pose's thumb did on this gun;
  - the support hand's thumb runs forward along the pump, all of it under the
    barrel's top, so under the sight line (the rifle pose stood it up beside
    the bead, 3-5 cm above the line);
  - the rifle's thumb still lies forward along its grip, and its support
    thumb still stands up the handguard.

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
from combat.paths import SHOTGUN_AIM_ANIM_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import SEAT_VAR, SIGHTS_FORCED_VAR
from combat.shotgun_pose import THUMB_TIP_CM
from combat.skin import skin_of_mesh
from combat.weapon_models import SHOTGUN_WRIST, shotgun_outline
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
# A joint axis may sit this far inside the wood: a thumb pressed on it (cm).
SINK_CM = 1.0
# The rifle pose's thumb tip stood this far off the shotgun's sight line, seen
# from the eye (measured, degrees): what the new pose has to beat.
OLD_TIP_OFF_DEG = 22.0
# ...and where it stood the support thumb's last joint (cm up, weapon frame).
OLD_SUPPORT_END_Z = 9.9


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
    # its parent's line runs down (shotgun_pose.thumb_lines).
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
    want = SHOTGUN_AIM_ANIM_PATH.rsplit("/", 1)[-1]
    p.check(f"the shotgun's ready pose is its own, {want}",
            pose is not None and pose.get_name() == want, str(pose))
    (base, mid, end, tip), lines = _thumb(mesh, held, skin.grip_thumb)
    (lo_x, lo_y, _lo_z), (hi_x, hi_y, top) = SHOTGUN_WRIST
    p.check("down the shotgun's sights the thumb's middle joint is over the "
            "top of the stock's wrist",
            lo_x <= mid.x <= hi_x and lo_y <= mid.y <= hi_y and mid.z > top - SINK_CM,
            f"{_fmt(mid)}; the wrist's top is z {top:g}, x {lo_x:g}..{hi_x:g}, "
            f"y {lo_y:g}..{hi_y:g}")
    p.check("...its last joint is down the wrist's left side, below the top",
            end.y < lo_y and end.z < top and end.z < mid.z, _fmt(end))
    p.check("...and the tip points down that side, not up the barrel",
            lines[2].z < -0.5 and tip.z < end.z,
            f"tip line {_fmt(lines[2])}, tip {_fmt(tip)}")
    off = {name: _off_line(held, point) for name, point in (("last joint", end), ("tip", tip))}
    p.check(f"...both further off the sight line than the rifle pose's thumb "
            f"tip stood on this gun ({OLD_TIP_OFF_DEG:g} deg)",
            min(off.values()) > OLD_TIP_OFF_DEG + 5.0,
            ", ".join(f"{k} {v:.1f} deg" for k, v in off.items()))
    # The other hand's, under the pump.
    (_base, mid, end, tip), lines = _thumb(mesh, held, skin.support_thumb)
    centre, _rot, half = part_placement(shotgun_outline(), "Barrel")
    barrel_top = centre.z + half.z
    line_z = held.get_editor_property("SightAim").z
    p.check("the support hand's thumb lies along the pump: every line of it "
            "runs up the barrel", all(line.x > 0.8 for line in lines),
            ", ".join(_fmt(line) for line in lines))
    p.check(f"...under the barrel's top (z {barrel_top:g}), so under the sight "
            f"line (z {line_z:.1f}): the rifle pose stood its last joint at "
            f"{OLD_SUPPORT_END_Z:g}",
            max(mid.z, end.z, tip.z) < barrel_top < line_z,
            f"middle {_fmt(mid)}, last {_fmt(end)}, tip {_fmt(tip)}")
    if SHOTS:
        unreal.SystemLibrary.execute_console_command(p.world(), "shot")
        yield 0.3
    p.set(wc, SIGHTS_FORCED_VAR, False)
    yield lambda: p.get(wc, SEAT_VAR) < HOME

    # ── the rifle: the pistol-grip thumb is left alone ──
    yield from _sights(p, wc, bag.index("BP_AssaultRifle_C"))
    held = p.get(wc, "Held")
    pose = held.get_editor_property("AimPose")
    want = skin.aim_rifle.rsplit("/", 1)[-1]
    p.check(f"the rifle's ready pose is still {want}",
            pose is not None and pose.get_name() == want, str(pose))
    _at, lines = _thumb(mesh, held, skin.grip_thumb)
    p.check("...and its thumb lies forward along the grip: every line of it "
            "runs up the barrel",
            all(line.x > 0.7 for line in lines),
            ", ".join(_fmt(line) for line in lines))
    _at, lines = _thumb(mesh, held, skin.support_thumb)
    p.check("...and its support thumb still stands up the handguard",
            all(line.z > 0.5 for line in lines),
            ", ".join(_fmt(line) for line in lines))
    p.set(wc, SIGHTS_FORCED_VAR, False)
    yield lambda: p.get(wc, SEAT_VAR) < HOME
