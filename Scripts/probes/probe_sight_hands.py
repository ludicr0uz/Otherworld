"""Down the sights both hands move with the gun.

The gun is attached to the right hand; the left is held on it by the anim
BP's Two Bone IK, weighted by SupportHand (combat/support_hand.py). Measured
in the gun's own space, which is what the sight camera rides: without the
hold the left hand slid 0.4 cm on the rifle standing and 1 cm walking.

With the rifle and with the pistol (the two ready poses):
  - at the hip the hold is off (SupportHand 0), so the pose is left alone;
  - down the sights it is on, and over SAMPLE_S of standing and then of
    walking neither hand moves in the gun's space;
  - the left hand is at the same place on the gun walking as standing;
  - sights down: the hold is let go again.

No key can be injected into a headless game: the sights are held up as
probe_sight_align holds them.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

import os
import shutil

import unreal

from combat.carry_tuning import RAISE_FORCED_VAR
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import LOOK_VAR, SEAT_VAR
from combat.skin import SKIN_ADVENTURER, SKIN_QUINN
from combat.support_hand import SUPPORT_HAND_VAR, SUPPORT_RIFLE_VAR
from combat.sway_tuning import SWAY_TIME_VAR
from graphics_menu.dev_consts import DEV_GUNS_REQUEST_VAR
from probes.probe_sight_align import HUD_BP_PATH, _file, _held_name, _hold, _live_hud

WRITABLE = [(HUD_BP_PATH, DEV_GUNS_REQUEST_VAR)] + [
    (WEAPON_COMP_BP_PATH, v) for v in
    ("EquippedIndex", "NeedsRefresh", "Stance", "SightBlend", SEAT_VAR, LOOK_VAR,
     SWAY_TIME_VAR, RAISE_FORCED_VAR)]
ML = unreal.MathLibrary
GUNS = (("BP_AssaultRifle_C", "rifle", True), ("BP_Pistol_C", "pistol", False))
SETTLE_S = 0.5
SAMPLE_S = 3.0          # the sway, the ready clip's breath and several strides
HELD_CM = 0.05          # a hand that moved less in the gun's space: held
FREE = 1e-3             # SupportHand at the hip


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _spread(points):
    """How far apart the points get, on the worst axis."""
    return max(max(getattr(v, a) for v in points) - min(getattr(v, a) for v in points)
               for a in "xyz")


def _run(p):
    yield lambda: _live_hud(p) is not None
    hud = _live_hud(p)
    wc = p.component(p.pawn(), WEAPON_COMP_CLASS_PATH)
    mesh = p.get(wc, "OwnerMesh")
    # player_skin() needs the editor's asset subsystem; read the worn rig.
    skin = next(s for s in (SKIN_ADVENTURER, SKIN_QUINN)
                if mesh.get_bone_index(s.pose_bones["hand_r"]) >= 0)
    hands = (("right", skin.pose_bones["hand_r"]), ("left", skin.pose_bones["hand_l"]))
    anim = mesh.get_anim_instance()
    # The gun is up, as an aim key would have it, the whole run.
    p.set(wc, RAISE_FORCED_VAR, True)
    p.set(hud, DEV_GUNS_REQUEST_VAR, True)
    yield lambda: not p.get(hud, DEV_GUNS_REQUEST_VAR)
    bag = [i.get_class().get_name() for i in p.get(wc, "Inventory")]

    for name, gun, two_handed in GUNS:
        p.set(wc, "EquippedIndex", bag.index(name))
        p.set(wc, "NeedsRefresh", True)
        yield lambda: _held_name(p, wc) == name
        yield SETTLE_S
        p.check(f"{gun}, at the hip: the hold is off ({SUPPORT_HAND_VAR} 0)",
                abs(p.get(anim, SUPPORT_HAND_VAR)) < FREE,
                f"{p.get(anim, SUPPORT_HAND_VAR):.4f}")

        where = {}
        for walk, label in ((False, "standing"), (True, "walking")):
            yield from _hold(p, wc, seconds=SETTLE_S, walk=walk)
            seen = {hand: [] for hand, _bone in hands}
            weights = []

            def sample():
                gun_xf = p.get(wc, "Held").get_actor_transform()
                for hand, bone in hands:
                    seen[hand].append(ML.make_relative_transform(
                        mesh.get_socket_transform(bone), gun_xf).translation)
                weights.append(p.get(anim, SUPPORT_HAND_VAR))

            start = p.pawn().get_actor_location()
            yield from _hold(p, wc, seconds=SAMPLE_S, walk=walk, each=sample)
            walked = (p.pawn().get_actor_location() - start).length()
            if walk:
                p.check(f"{gun}, walking: the player did walk", walked > 100.0,
                        f"{walked:.0f} cm")
            p.check(f"{gun}, {label}, down the sights: the hold is on "
                    f"({SUPPORT_HAND_VAR} 1, {SUPPORT_RIFLE_VAR} {two_handed}) over "
                    f"{len(weights)} frames",
                    len(weights) > 10 and min(weights) > 1.0 - FREE
                    and p.get(anim, SUPPORT_RIFLE_VAR) == two_handed,
                    f"least {min(weights):.4f}, {SUPPORT_RIFLE_VAR} "
                    f"{p.get(anim, SUPPORT_RIFLE_VAR)}")
            for hand, _bone in hands:
                moved = _spread(seen[hand])
                p.check(f"{gun}, {label}: the {hand} hand does not move in the gun's "
                        f"space (under {HELD_CM:g} cm)", moved < HELD_CM,
                        f"{moved:.3f} cm, at ({seen[hand][0].x:.2f}, "
                        f"{seen[hand][0].y:.2f}, {seen[hand][0].z:.2f})")
            where[label] = seen["left"][-1]
        apart = (where["walking"] - where["standing"]).length()
        p.check(f"{gun}: the left hand is at the same place on the gun walking as "
                "standing", apart < HELD_CM, f"{apart:.3f} cm apart")

        yield lambda: max(p.get(wc, "SightBlend"), p.get(wc, SEAT_VAR)) < 1e-3
        yield 0.1
        p.check(f"{gun}, sights down: the hold is let go",
                abs(p.get(anim, SUPPORT_HAND_VAR)) < FREE,
                f"{p.get(anim, SUPPORT_HAND_VAR):.4f}")
