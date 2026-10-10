"""Down the sniper's scope: the rifle and the player's own body leave the view.

No key can be injected into a headless game, so the probe holds the sights
key's stand-in (SightsForced) until SightSeat has carried the camera to the
eye point; verify/sights.py checks the key and the ease. (It used to write
SightSeat itself every frame: the Tick eases it one step home before it
reads it, and at a headless frame of 10 ms that step is past the 0.9 the
scope hides at.) The sniper comes from the dev-all-guns request and is equipped the
way Q does (EquippedIndex + NeedsRefresh).

Scoped: the sniper hidden, the body OwnerNoSee. Let go: both back. The
shotgun (irons) held at the same blend: nothing hidden.

Then all of it once more with the jacket worn (probes/dressed.py): the hoodie
on the body goes out of the owner's view with the body and comes back with it.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

SYSTEMS = ('weapons',)

import os
import shutil

import unreal

from combat.carry_tuning import RAISE_FORCED_VAR
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import SEAT_VAR, SIGHTS_FORCED_VAR
from combat.weapon_component.sights import SCOPE_HIDE_BLEND
from graphics_menu.dev_consts import DEV_GUNS_REQUEST_VAR
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR, PROFILE_SLOT
from combat.weapon_component import vars as WV
from probes import dressed
from probes.dressed import drawn, part, put_on

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, DEV_GUNS_REQUEST_VAR),
            (WEAPON_COMP_BP_PATH, WV.EquippedIndex),
            (WEAPON_COMP_BP_PATH, WV.NeedsRefresh),
            (WEAPON_COMP_BP_PATH, SIGHTS_FORCED_VAR),
            (WEAPON_COMP_BP_PATH, RAISE_FORCED_VAR)] + dressed.WRITABLE
GARMENT = "Jacket"
SNIPER = "BP_SniperRifle_C"
SHOTGUN = "BP_Shotgun_C"
SEATED = 0.99


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


def _equip(p, wc, name):
    bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    p.set(wc, "EquippedIndex", bag.index(name))
    p.set(wc, "NeedsRefresh", True)
    yield lambda: _held_name(p, wc) == name
    yield 0.3


def _hold_sights(p, wc):
    """Hold the sights key's stand-in until the camera is on the gun."""
    p.set(wc, SIGHTS_FORCED_VAR, True)
    yield lambda: p.get(wc, SEAT_VAR) > SEATED
    yield 0.05


def _drawn(mesh):
    """The body that is drawn: the mannequin, or the MetaHuman's Body under a
    hidden one (weapon_component/body_parts.py reaches every such part)."""
    if mesh.is_visible():
        return mesh
    return next((c for c in mesh.get_children_components(True)
                 if isinstance(c, unreal.SkeletalMeshComponent) and c.is_visible()), mesh)


def _state(p, wc, mesh):
    return (p.get(wc, "Held").get_editor_property("hidden"),
            _drawn(mesh).get_editor_property("owner_no_see"), p.get(wc, SEAT_VAR))


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
    # No aim key is down in a probe: raise the gun as the key would.
    p.set(wc, RAISE_FORCED_VAR, True)
    p.set(hud, DEV_GUNS_REQUEST_VAR, True)
    yield lambda: not p.get(hud, DEV_GUNS_REQUEST_VAR)
    ok = yield from _scoped(p, wc, mesh, "", None)
    if not ok:
        return
    # Once more dressed: the hoodie hangs under the body as a component of
    # its own, which the hides reach only through body_parts.py's loop.
    jacket = yield from put_on(p, p.pawn(), wc, GARMENT)
    torso = part(p.pawn(), GARMENT)
    p.check("the jacket is picked up and worn, and drawn on the body",
            jacket is not None and drawn(torso, GARMENT), str(jacket))
    if jacket is not None and torso is not None:
        yield from _scoped(p, wc, mesh, "dressed: ", torso)


def _scoped(p, wc, mesh, tag, garment):
    """The sniper's scope and the shotgun's irons. ``garment``: the worn
    garment's component, held to what the body gets. False: no sniper."""
    def seen():
        return garment is None or (not garment.get_editor_property("owner_no_see")
                                   and drawn(garment, GARMENT))

    yield from _equip(p, wc, SNIPER)
    p.check(f"{tag}the sniper is in hand", _held_name(p, wc) == SNIPER, str(_held_name(p, wc)))
    if _held_name(p, wc) != SNIPER:
        return False
    p.check(f"{tag}...seen, body and all, before the sights come up",
            _state(p, wc, mesh)[:2] == (False, False) and seen(), str(_state(p, wc, mesh)))

    yield from _hold_sights(p, wc)
    hidden, no_see, blend = _state(p, wc, mesh)
    p.check(f"{tag}down the scope ({SEAT_VAR} {blend:.3f} > {SCOPE_HIDE_BLEND:g}) the "
            "sniper is hidden", blend > SCOPE_HIDE_BLEND and hidden, str(hidden))
    p.check(f"{tag}...and the player's body is hidden from their own camera",
            no_see, str(no_see))
    p.check(f"{tag}...but still drawn for everyone else (not hidden in game)",
            not p.pawn().get_editor_property("hidden") and _drawn(mesh).is_visible(),
            f"{p.pawn().get_editor_property('hidden')} {_drawn(mesh).is_visible()}")
    if garment is not None:
        p.check(f"{tag}...and so is the jacket: out of its owner's view, still drawn "
                "for everyone else",
                garment.get_editor_property("owner_no_see") and drawn(garment, GARMENT),
                f"owner_no_see {garment.get_editor_property('owner_no_see')}, "
                f"drawn {drawn(garment, GARMENT)}")

    p.set(wc, SIGHTS_FORCED_VAR, False)
    yield lambda: p.get(wc, SEAT_VAR) < 0.05
    hidden, no_see, _ = _state(p, wc, mesh)
    p.check(f"{tag}sights down: the sniper and the body are back",
            not hidden and not no_see and seen(), f"{hidden} {no_see} {seen()}")

    yield from _equip(p, wc, SHOTGUN)
    yield from _hold_sights(p, wc)
    hidden, no_see, blend = _state(p, wc, mesh)
    p.check(f"{tag}the shotgun's irons ({SEAT_VAR} {blend:.3f}) hide nothing",
            blend > SCOPE_HIDE_BLEND and not hidden and not no_see and seen(),
            f"{hidden} {no_see} {seen()}")
    p.set(wc, SIGHTS_FORCED_VAR, False)
    yield lambda: p.get(wc, SEAT_VAR) < 0.05
    return True
