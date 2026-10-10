"""Down any gun's sights the player's own head is out of the view
(combat/weapon_component/head_hide.py), and back when the sights come down.

The sights are raised the real way, by SightsForced (the probes' stand-in for
the sights key), for every item in the bag that has a sight line -- so a gun
added later is covered without being named here. Frame by frame through the
raise and the release:

  - the head is hidden exactly while SightSeat is past HEAD_HIDE_SEAT;
  - until it goes, the camera is still well behind it (the body is never seen
    with the head filling the view, nor headless from far behind): the nearest
    the camera came to a head still drawn is reported;
  - seated, the rest of the body is still drawn (the arms are the sight
    picture) unless the gun is scoped.

All of it once more with the jacket worn (probes/dressed.py): the hoodie on
the body is hidden from its owner exactly when the body is.

Then the player is killed down a scope: the dead gate shows the head, the
body and the jacket again (the Tick that would have no longer runs).

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end. What the picture looks like is
probe_sight_align.py with --windowed and OW_SIGHT_SHOTS=1.
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # passes here, fails on the 50 m probe level (T11)
SYSTEMS = ('animation',)

import os
import shutil

import unreal

from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.seat_tuning import HEAD_HIDE_SEAT, SEAT_VAR, SIGHTS_FORCED_VAR
from combat.skin import skin_of_mesh
from combat.weapon_component.dead import OWNER_DEAD_VAR
from combat.weapon_component.sights import SIGHT_LINE_MIN_CM
from graphics_menu.dev_consts import DEV_GUNS_REQUEST_VAR
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR, PROFILE_SLOT
from combat import health_vars as HV
from combat.weapon_component import vars as WV
from probes import dressed
from probes.dressed import drawn, part, put_on

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, DEV_GUNS_REQUEST_VAR),
            (WEAPON_COMP_BP_PATH, WV.EquippedIndex),
            (WEAPON_COMP_BP_PATH, WV.NeedsRefresh),
            (WEAPON_COMP_BP_PATH, SIGHTS_FORCED_VAR),
            (HEALTH_BP_PATH, HV.Health)] + dressed.WRITABLE
GARMENT = "Jacket"
SEATED = 0.99           # the camera is on the sights
HOME = 0.01             # ...and back on the boom
# A head still drawn is never nearer the camera than this (cm): it goes before
# the camera, coming from behind, reaches it.
CLEAR_CM = 25.0


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


class _Watch:
    """Each frame of a raise or a release: is the head hidden exactly when the
    seat says so, and how near the camera came to a head still drawn."""

    def __init__(self, p, wc, mesh, cam, head):
        self.p, self.wc, self.mesh, self.cam, self.head = p, wc, mesh, cam, head
        self.frames = 0
        self.wrong = []
        self.nearest = float("inf")

    def hidden(self):
        """On the mannequin, and on every skinned mesh drawn under it (a
        MetaHuman skin's body and face: weapon_component/body_parts.py)."""
        return all(m.is_bone_hidden_by_name(self.head)
                   for m in _skinned(self.mesh, self.head))

    def sample(self):
        seat = self.p.get(self.wc, SEAT_VAR)
        self.frames += 1
        if self.hidden() != (seat > HEAD_HIDE_SEAT):
            self.wrong.append(round(seat, 3))
        if not self.hidden():
            gap = (self.cam.get_world_location()
                   - self.mesh.get_socket_location(self.head)).length()
            self.nearest = min(self.nearest, gap)
        return seat


def _skinned(mesh, head):
    """The mannequin and the skinned meshes under it that have the head bone."""
    return [mesh] + [c for c in mesh.get_children_components(True)
                     if isinstance(c, unreal.SkinnedMeshComponent)
                     and c.get_bone_index(head) >= 0]


def _drawn(mesh):
    """What is drawn: the mannequin, or the MetaHuman body hung under it
    (combat/metahuman_body.py), which is then the one hidden from its owner."""
    body = next((c for c in mesh.get_children_components(False)
                 if c.get_name() == "Body"), None)
    return body or mesh


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _equip(p, wc, index):
    item = p.get(wc, "Inventory")[index]
    p.set(wc, "EquippedIndex", index)
    p.set(wc, "NeedsRefresh", True)
    yield lambda: p.get(wc, "Held") == item
    yield 0.3


def _raise(p, wc, watch):
    p.set(wc, SIGHTS_FORCED_VAR, True)
    yield lambda: watch.sample() > SEATED


def _run(p):
    yield lambda: _live_hud(p) is not None
    hud = _live_hud(p)
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    mesh = p.pawn().get_editor_property("mesh")
    cam = p.pawn().get_component_by_class(unreal.CameraComponent)
    # player_skin() asks the editor's asset subsystem, which a game has not.
    worn = mesh.get_skeletal_mesh_asset().get_path_name().split(".")[0]
    head = getattr(skin_of_mesh(worn), "head", None)
    p.check("the player wears a known skin", head is not None, worn)
    if head is None:
        return
    p.check(f"the player's mesh has the head bone ({head})",
            mesh.get_bone_index(head) >= 0, str(mesh.get_bone_index(head)))
    p.set(hud, DEV_GUNS_REQUEST_VAR, True)
    yield lambda: not p.get(hud, DEV_GUNS_REQUEST_VAR)
    bag = p.get(wc, "Inventory")
    guns = [i for i, item in enumerate(bag) if _has_sights(item)]
    p.check("the bag holds guns with sights to look down", len(guns) >= 5,
            str([bag[i].get_class().get_name() for i in guns]))

    yield from _guns(p, wc, mesh, cam, head, bag, guns, "", None)

    # Once more dressed: the hoodie is a component of its own under the body
    # (it has the head bone too, so _Watch.hidden() holds it to the head's
    # rule), reached only by body_parts.py's loop.
    jacket = yield from put_on(p, p.pawn(), wc, GARMENT)
    torso = part(p.pawn(), GARMENT)
    p.check("the jacket is picked up and worn, and drawn on the body",
            jacket is not None and drawn(torso, GARMENT), str(jacket))
    if jacket is None or torso is None:
        return
    bag = p.get(wc, "Inventory")
    guns = [i for i, item in enumerate(bag) if _has_sights(item)]
    yield from _guns(p, wc, mesh, cam, head, bag, guns, "dressed: ", torso)

    # Killed down a scope (the body and the jacket out of the owner's view):
    # the Tick stops at its dead gate, which shows them again.
    scoped = [i for i in guns if bag[i].get_editor_property("Scoped")]
    p.check("the bag holds a scoped gun to die behind", bool(scoped))
    if scoped:
        yield from _equip(p, wc, scoped[0])
    watch = _Watch(p, wc, mesh, cam, head)
    yield from _raise(p, wc, watch)
    p.check("down the sights again, the head is hidden", watch.hidden())
    p.check("...and the body and the jacket are out of the owner's view",
            _drawn(mesh).get_editor_property("owner_no_see")
            and torso.get_editor_property("owner_no_see"))
    health = p.component(p.pawn(), HEALTH_CLASS_PATH)
    p.set(health, "Health", 0.0)
    yield lambda: p.get(wc, OWNER_DEAD_VAR)
    yield 0.1
    p.check("killed down the sights, the corpse has its head",
            p.get(wc, OWNER_DEAD_VAR) and not watch.hidden(),
            f"OwnerDead {p.get(wc, OWNER_DEAD_VAR)}, hidden {watch.hidden()}")
    p.check("...and its body and its jacket are back in its owner's view, the "
            "jacket still on it",
            not _drawn(mesh).get_editor_property("owner_no_see")
            and not torso.get_editor_property("owner_no_see") and drawn(torso, GARMENT),
            f"body {_drawn(mesh).get_editor_property('owner_no_see')}, jacket "
            f"{torso.get_editor_property('owner_no_see')}, drawn {drawn(torso, GARMENT)}")
    p.set(wc, SIGHTS_FORCED_VAR, False)


def _guns(p, wc, mesh, cam, head, bag, guns, tag, garment):
    """Every gun's sights, raised and let go. ``garment``: the worn garment's
    component, held to what the body gets."""
    for index in guns:
        gun = bag[index].get_class().get_name()[3:-2]
        yield from _equip(p, wc, index)
        watch = _Watch(p, wc, mesh, cam, head)
        p.check(f"{tag}{gun}: carried, the head is drawn", not watch.hidden())
        yield from _raise(p, wc, watch)
        p.check(f"{tag}{gun}: down the sights the head is hidden",
                watch.hidden(), f"SightSeat {p.get(wc, SEAT_VAR):.3f}")
        p.check(f"{tag}{gun}: ...from SightSeat {HEAD_HIDE_SEAT:g} on, and not before "
                f"({watch.frames} frames)", not watch.wrong, str(watch.wrong[:6]))
        p.check(f"{tag}{gun}: ...before the camera, coming from behind, was within "
                f"{CLEAR_CM:g} cm of it", watch.nearest > CLEAR_CM,
                f"nearest to a head still drawn {watch.nearest:.1f} cm")
        scoped = bag[index].get_editor_property("Scoped")
        p.check(f"{tag}{gun}: ...and the rest of the body is "
                + ("behind the scope's glass" if scoped else "still drawn: the "
                   "arms are the sight picture"),
                _drawn(mesh).get_editor_property("owner_no_see") == scoped
                and _drawn(mesh).is_visible(),
                f"owner_no_see {_drawn(mesh).get_editor_property('owner_no_see')}")
        if garment is not None:
            p.check(f"{tag}{gun}: ...and the jacket with it",
                    garment.get_editor_property("owner_no_see") == scoped
                    and drawn(garment, GARMENT),
                    f"owner_no_see {garment.get_editor_property('owner_no_see')}, "
                    f"drawn {drawn(garment, GARMENT)}")
        back = _Watch(p, wc, mesh, cam, head)
        p.set(wc, SIGHTS_FORCED_VAR, False)
        yield lambda: back.sample() < HOME
        p.check(f"{tag}{gun}: sights down, the head is back", not back.hidden()
                and not back.wrong, str(back.wrong[:6]))
