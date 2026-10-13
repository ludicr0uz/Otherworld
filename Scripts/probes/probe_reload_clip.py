"""The magazine change: the AKM and the sniper reload in one clip, the pistol
and the SMG in another.

Each gun comes from the dev-all-guns request and is brought to hand as Q does
(EquippedIndex + NeedsRefresh); its magazine is emptied and the reload key's
stand-in held (ReloadForced), so the whole path is run: the Tick's key,
Server_Reload, the native ReloadNow, Reloaded, Fx_Reload.

    the AKM, raised     its row's clip (ReloadClips beside its ready pose in
                        ReloadFor: Lyra's rifle reload) is in the upper-body
                        slot with the reload, timed to end with it; the left
                        hand leaves the gun for the pouch; the keep-alive
                        leaves the clip in the slot; at its end the gun's
                        ready pose has the slot again, which was never empty
                        in between
    the sniper, raised  the same clip, at the sniper's rate
    the pistol, the SMG the same, in Lyra's pistol reload, each at its rate
    the AKM, carried    the clip plays over the carry, and ends by itself
    the pistol, lowered the clip plays over the empty slot, and ends by itself
    down the sights     the left hand's hold on the gun (SupportHand) lets go
                        for the clip and comes back after it: the AKM's on
                        the handguard, the pistol's on the right fist
    another gun taken   the pistol taken out mid-way through the AKM's reload
                        cuts the AKM's clip (the pistol has one of its own:
                        it is ReloadPose that is asked, not ReloadFor)
    the shotgun         reloads, and plays no clip (its own is not made yet)

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end; the level's creatures are removed, since a
probe this long is found and killed, and the death menu pauses the game.
"""

SYSTEMS = ('weapons',)

import os
import shutil

import unreal

from combat import item_vars as IV
from combat.anim_blueprint import AIM_SLOT
from combat.carry_tuning import RAISE_FORCED_VAR
from combat.paths import ITEM_BP_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.reload_tuning import RELOAD_HANDOVER_S
from combat.seat_tuning import SEAT_VAR, SIGHTS_FORCED_VAR
from combat.shot_vars import ReloadForced
from combat.support_hand import SUPPORT_HAND_VAR
from combat.weapon_component import vars as WV
from combat.weapon_component.look_vars import HandPose
from graphics_menu.dev_consts import DEV_GUNS_REQUEST_VAR
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR, PROFILE_SLOT

HUD_BP_PATH = "/Game/UI/BP_GraphicsMenuHUD"
WRITABLE = [(HUD_BP_PATH, DEV_GUNS_REQUEST_VAR),
            (WEAPON_COMP_BP_PATH, WV.EquippedIndex),
            (WEAPON_COMP_BP_PATH, WV.NeedsRefresh),
            (WEAPON_COMP_BP_PATH, ReloadForced),
            (WEAPON_COMP_BP_PATH, SIGHTS_FORCED_VAR),
            (WEAPON_COMP_BP_PATH, RAISE_FORCED_VAR),
            (ITEM_BP_PATH, IV.Loaded), (ITEM_BP_PATH, IV.Reserve)]
AKM, SNIPER = "BP_AssaultRifle_C", "BP_SniperRifle_C"
PISTOL, SMG = "BP_Pistol_C", "BP_SMG_C"
OTHERS = ("BP_Shotgun_C",)
RIFLE_CLIP, PISTOL_CLIP = "MM_Rifle_Reload", "MM_Pistol_Reload"
SPARE = 50
TIMEOUT = 300.0    # wall seconds: a dozen reloads of two seconds and more
SAMPLE_S = 0.03
START_S = 0.5      # by when the clip is in the slot after the key
REACH_CM = 25.0    # how much further from the right hand the left must get
SEATED = 0.99
HELD_ON = 0.9      # SupportHand with the hand on the handguard
SLOT_HELD = 0.9   # the slot's weight through the handover
LET_GO = 0.2       # ...and with it off for the clip


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
    if name not in bag:
        return False
    p.set(wc, "EquippedIndex", bag.index(name))
    p.set(wc, "NeedsRefresh", True)
    yield lambda: _held_name(p, wc) == name
    yield 0.6
    return True


def _in_slot(mesh, clip):
    """Is ``clip`` (or any of a tuple of them) in the upper-body slot?"""
    anim = mesh.get_anim_instance()
    clips = clip if isinstance(clip, (tuple, list)) else (clip,)
    return bool(anim and any(c and anim.is_playing_slot_animation(c, AIM_SLOT)
                             for c in clips))


def _row(p, wc):
    """(clip, rate) of the gun in hand: the row of its ready pose (HandPose
    in ReloadFor), or (None, 1.0)."""
    poses, pose = list(p.get(wc, WV.ReloadFor)), p.get(wc, HandPose)
    if pose is None or pose not in poses:
        return None, 1.0
    at = poses.index(pose)
    return list(p.get(wc, WV.ReloadClips))[at], float(list(p.get(wc, WV.ReloadRates))[at])


def _hands_apart(mesh):
    return (mesh.get_socket_location("hand_l") - mesh.get_socket_location("hand_r")).length()


def _now(p):
    return unreal.GameplayStatics.get_time_seconds(p.world())


def _send_away(p):
    """The level's creatures: gone, so nothing hunts the player meanwhile (a
    death opens the menu, which pauses the game)."""
    for ctrl in unreal.GameplayStatics.get_all_actors_of_class(p.world(), unreal.AIController):
        body = ctrl.get_controlled_pawn()
        if ctrl.get_class().get_name().startswith("BP_ForestWandererAI") and body:
            body.destroy_actor()


def _press(p, wc, mesh, clip):
    """Empty the held gun, hold the reload key until the clip is in the slot
    (or START_S has gone), and say whether a reload was counted and whether
    the clip came."""
    gun = p.get(wc, "Held")
    p.set(gun, IV.Loaded, 0)
    p.set(gun, IV.Reserve, SPARE)
    yield 0.1
    count = int(p.get(wc, "Reloads"))
    p.set(wc, ReloadForced, True)
    t = 0.0
    while t < START_S and not _in_slot(mesh, clip):
        yield SAMPLE_S
        t += SAMPLE_S
    p.set(wc, ReloadForced, False)
    return int(p.get(wc, "Reloads")) - count, _in_slot(mesh, clip)


def _watch(p, wc, mesh, clip, weight=None):
    """Sample until the pose's time has come (ReloadClipEnds): the widest the
    hands got apart, whether the clip held the slot throughout, and the least
    of ``weight()``."""
    widest, held, least = _hands_apart(mesh), True, 1.0
    while _now(p) < float(p.get(wc, WV.ReloadClipEnds)) - 2 * SAMPLE_S:
        yield SAMPLE_S
        widest = max(widest, _hands_apart(mesh))
        held = held and _in_slot(mesh, clip)
        if weight:
            least = min(least, weight())
    return widest, held, least


def _raised(p, wc, mesh, name, label, source):
    """A reload with the gun raised: the clip, the hand, and the pose after."""
    if not (yield from _equip(p, wc, name)):
        p.check(f"{label}: in the bag after the dev-all-guns request", False)
        return
    anim = mesh.get_anim_instance()
    pose = p.get(wc, HandPose)
    clip, rate = _row(p, wc)
    if not p.check(f"{label}: its reload's clip is Lyra's {source}",
                   clip is not None and clip.get_name().endswith(source), str(clip)):
        return
    p.check(f"{label}: raised, its ready pose is in {AIM_SLOT} and the reload's clip is not",
            _in_slot(mesh, pose) and not _in_slot(mesh, clip), str(pose))
    before = _hands_apart(mesh)
    counted, came = yield from _press(p, wc, mesh, clip)
    p.check(f"{label}: the key reloads once, and the reload's clip is in {AIM_SLOT} with it",
            counted == 1 and came, f"{counted} reload(s), clip in slot: {came}")
    if not came:
        return
    length = clip.get_play_length() / rate
    secs = float(p.get(p.get(wc, "Held"), IV.ReloadSeconds))
    p.check(f"{label}: ...played at {rate:.2f}, to end with the gun's reload ({secs:g} s)",
            abs(length - secs) < 0.02 and p.get(wc, WV.ReloadAnim) == clip
            and p.get(wc, WV.ReloadPose) == pose, f"the clip lasts {length:.2f} s")
    left = float(p.get(wc, WV.ReloadClipEnds)) - _now(p)
    p.check(f"{label}: ...and the pose's time is set to the clip's end less the handover "
            f"({length:.2f} - {RELOAD_HANDOVER_S:g} s)",
            length - RELOAD_HANDOVER_S - START_S <= left <= length - RELOAD_HANDOVER_S + 0.05,
            f"{left:.2f} s from now")
    widest, held, _ = yield from _watch(p, wc, mesh, clip)
    p.check(f"{label}: the left hand leaves the gun: at least {REACH_CM:g} cm further from "
            "the right than it was", widest - before >= REACH_CM,
            f"{before:.0f} cm apart before, {widest:.0f} cm at the widest")
    p.check(f"{label}: ...and the clip stays in the slot until the pose's time: the "
            "keep-alive leaves it be", held)
    least, trace, t = 1.0, [], 0.0
    while t < RELOAD_HANDOVER_S + 0.6:
        yield SAMPLE_S
        t += SAMPLE_S
        weight = anim.blueprint_get_slot_montage_local_weight(AIM_SLOT)
        least = min(least, weight)
        trace.append(f"{weight:.2f}")
    p.check(f"{label}: at the clip's end the ready pose has the slot again, and the slot "
            f"stayed at {SLOT_HELD:g} of its weight or more in between (no dip to the hip)",
            _in_slot(mesh, pose) and not _in_slot(mesh, clip) and least >= SLOT_HELD,
            f"pose in slot: {_in_slot(mesh, pose)}, clip: {_in_slot(mesh, clip)}, "
            f"least weight {least:.2f} of {' '.join(trace[::3])}")
    p.check(f"{label}: ...and the left hand is back on the gun",
            abs(_hands_apart(mesh) - before) < 8.0,
            f"{_hands_apart(mesh):.0f} cm apart against {before:.0f}")
    p.check(f"{label}: the magazine is full",
            int(p.get(p.get(wc, 'Held'), IV.Loaded))
            == int(p.get(p.get(wc, 'Held'), IV.MagazineSize)))


def _sighted(p, wc, mesh, label):
    """Down the sights the left hand's hold lets go for the clip."""
    layers = p.pose_instance(mesh)
    clip, _rate = _row(p, wc)

    def weight():
        return float(p.get(layers, SUPPORT_HAND_VAR))
    p.set(wc, SIGHTS_FORCED_VAR, True)
    t = 0.0
    while t < 3.0 and not (p.get(wc, SEAT_VAR) > SEATED and weight() > HELD_ON):
        yield SAMPLE_S
        t += SAMPLE_S
    p.check(f"{label}: down the sights the left hand holds the gun ({SUPPORT_HAND_VAR} 1)",
            weight() > HELD_ON, f"{weight():.2f}")
    _counted, came = yield from _press(p, wc, mesh, clip)
    _widest, _held, least = yield from _watch(p, wc, mesh, clip, weight)
    p.check(f"{label}: ...lets go for the reload's clip", came and least < LET_GO,
            f"clip in slot: {came}, least {SUPPORT_HAND_VAR} {least:.2f}")
    yield RELOAD_HANDOVER_S + 0.8
    p.check(f"{label}: ...and takes it again after", weight() > HELD_ON, f"{weight():.2f}")
    p.set(wc, SIGHTS_FORCED_VAR, False)
    yield 0.5


def _carried(p, wc, mesh, label):
    """Lowered, no pose is owed: the clip plays over the carry (a pistol's
    over the empty slot) and ends."""
    clip, rate = _row(p, wc)
    p.set(wc, RAISE_FORCED_VAR, False)
    yield 1.0
    counted, came = yield from _press(p, wc, mesh, clip)
    p.check(f"{label}, lowered: the reload plays the clip too",
            counted == 1 and came, f"{counted} reload(s), clip in slot: {came}")
    yield clip.get_play_length() / rate + 0.5
    p.check(f"{label}, lowered: ...which ends by itself", not _in_slot(mesh, clip))
    p.set(wc, RAISE_FORCED_VAR, True)
    yield 0.5


def _switched(p, wc, mesh):
    """Another gun taken out mid-reload cuts the clip, though it has a reload
    clip of its own."""
    if not (yield from _equip(p, wc, AKM)):
        return
    clip, _rate = _row(p, wc)
    _counted, came = yield from _press(p, wc, mesh, clip)
    yield 0.3
    taken = yield from _equip(p, wc, PISTOL)
    pose = p.get(wc, HandPose)
    p.check("the pistol taken out mid-way through the AKM's reload cuts the AKM's clip: "
            f"the pistol's ready pose has {AIM_SLOT}",
            came and taken and _in_slot(mesh, pose) and not _in_slot(mesh, clip),
            f"clip came: {came}, pose in slot: {_in_slot(mesh, pose)}, "
            f"clip: {_in_slot(mesh, clip)}")
    yield float(RELOAD_HANDOVER_S) + 2.0


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
    clips = tuple(p.get(wc, WV.ReloadClips))
    if not p.check("the worn skin has the reload clips: the rifles' and the pistols'",
                   len(set(clips)) == 2, str([c.get_name() for c in clips if c])):
        return
    _send_away(p)
    # No aim key is down in a probe: raise the gun as the key would.
    p.set(wc, RAISE_FORCED_VAR, True)
    p.set(hud, DEV_GUNS_REQUEST_VAR, True)
    yield lambda: not p.get(hud, DEV_GUNS_REQUEST_VAR)
    yield 0.3

    yield from _raised(p, wc, mesh, AKM, "the AKM", RIFLE_CLIP)
    if _held_name(p, wc) == AKM:
        yield from _sighted(p, wc, mesh, "the AKM")
        yield from _carried(p, wc, mesh, "the AKM")
    yield from _raised(p, wc, mesh, SNIPER, "the sniper", RIFLE_CLIP)
    yield from _raised(p, wc, mesh, PISTOL, "the pistol", PISTOL_CLIP)
    if _held_name(p, wc) == PISTOL:
        yield from _sighted(p, wc, mesh, "the pistol")
        yield from _carried(p, wc, mesh, "the pistol")
    yield from _raised(p, wc, mesh, SMG, "the SMG", PISTOL_CLIP)
    yield from _switched(p, wc, mesh)

    for name in OTHERS:
        if not (yield from _equip(p, wc, name)):
            p.check(f"{name}: in the bag", False)
            continue
        counted, came = yield from _press(p, wc, mesh, clips)
        yield 0.3
        p.check(f"{name}: reloads, and plays no clip of the rifles' or the pistols'",
                counted == 1 and not came and not _in_slot(mesh, clips),
                f"{counted} reload(s), clip in slot: {came}")
        yield float(p.get(p.get(wc, "Held"), IV.ReloadSeconds))
