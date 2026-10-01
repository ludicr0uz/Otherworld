"""A hit taken down the sights leaves the view where it was.

The view down the sights rides the gun (sights.py), and a flinch takes the
arms: its montage stops the ready pose (one montage group), so the gun fell
to the carry at the knee and the camera went with it. So a body whose sights
are up does not flinch (hit_reaction.py, steady.py).

No key can be injected into a headless game, so the sights are held up by
writing SightBlend every frame, as probe_sight_align does.

  - sights up, a hit: Health drops, no flinch plays, the camera stays where
    the idle left it (height and direction);
  - at the hip, a hit: the flinch plays (the gate does open);
  - the sights come up in the middle of that flinch: it is ended, the ready
    pose is put straight back and the camera settles where it was.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

import math
import os
import shutil

import unreal

from combat.anim_blueprint import AIM_SLOT, HIT_SLOT
from combat.carry_tuning import RAISE_FORCED_VAR
from combat.hit_reaction import STEADY_VAR, PREV_HEALTH_VAR
from combat.paths import (
    HEALTH_BP_PATH, HEALTH_CLASS_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH,
)
from combat.tuning import COMBAT
from combat.weapon_component.common import AIM_BLEND
from graphics_menu.profile_consts import PROFILE_CHECKED_VAR, PROFILE_SLOT

WRITABLE = [(HEALTH_BP_PATH, "Health"),
            (WEAPON_COMP_BP_PATH, "SightBlend"),
            (WEAPON_COMP_BP_PATH, RAISE_FORCED_VAR)]

HIT_HP = 5.0
SETTLE_S = 0.6          # the equip, the ready pose's blend
WATCH_S = 1.0           # longer than a flinch (a clip is 0.7-1.2 s at 1.4x)
# The idle breathes: the eye rides the gun a few millimetres. A flinch that
# drops the gun to the carry moves it tens of centimetres and degrees.
FLINCH_CUT_S = AIM_BLEND + 0.15   # the ready pose's blend in, and a little
HEIGHT_CM = 3.0
TURN_DEG = 2.0


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _live_hud(p):
    try:
        hud = p.hud()
    except Exception:
        return None
    return hud if hud is not None and p.get(hud, PROFILE_CHECKED_VAR) else None


def _angle(a, b):
    return math.degrees(math.atan2(a.cross(b).length(), a.dot(b)))


def _hold(p, wc, seconds, each=None):
    """Keep the sights up for some game time. `each` runs first every frame,
    on what the last Tick left."""
    t0 = [None]

    def step():
        world = p.world()
        if each:
            each()
        dt = unreal.GameplayStatics.get_world_delta_seconds(world)
        eased = min(dt * COMBAT.ads_interp_speed, 0.9)
        p.set(wc, "SightBlend", 1.0 / (1.0 - eased))
        now = unreal.GameplayStatics.get_time_seconds(world)
        t0[0] = now if t0[0] is None else t0[0]
        return now - t0[0] >= seconds
    yield step


class _View(object):
    """Where the camera is over the capsule's middle, and which way it looks, frame by
    frame; and whether a flinch was ever playing."""

    def __init__(self, p, cam):
        self.p, self.cam = p, cam
        self.heights, self.looks = [], []
        self.flinched = False

    def sample(self):
        pawn = self.p.pawn()
        self.heights.append(self.cam.get_world_location().z
                            - pawn.get_actor_location().z)
        self.looks.append(self.cam.get_forward_vector())
        anim = pawn.mesh.get_anim_instance()
        self.flinched = self.flinched or anim.is_slot_active(HIT_SLOT)

    def mean_height(self):
        return sum(self.heights) / len(self.heights)

    def mean_look(self):
        total = unreal.Vector(0, 0, 0)
        for v in self.looks:
            total = total + v
        return total.normal()

    def off(self, rest):
        """The furthest this view got from `rest`: (cm of height, degrees)."""
        h, look = rest.mean_height(), rest.mean_look()
        return (max(abs(x - h) for x in self.heights),
                max(_angle(v, look) for v in self.looks))


def _hit(p, health):
    p.set(health, "Health", p.get(health, "Health") - HIT_HP)


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
    pawn = p.pawn()
    wc = p.component(pawn, WEAPON_COMP_CLASS_PATH)
    health = p.component(pawn, HEALTH_CLASS_PATH)
    cam = pawn.get_component_by_class(unreal.CameraComponent)
    anim = pawn.mesh.get_anim_instance()
    yield lambda: p.get(wc, "Held") is not None
    gun = p.get(wc, "Held").get_class().get_name()
    # The sights are held by writing SightBlend, with no aim key down: this
    # is what the key would do to the carry (the gun is raised).
    p.set(wc, RAISE_FORCED_VAR, True)

    # --- sights up, then a hit ------------------------------------------------
    yield from _hold(p, wc, SETTLE_S)
    rest = _View(p, cam)
    yield from _hold(p, wc, 0.3, each=rest.sample)
    p.check(f"{gun}: the sights are up and the body is marked steady",
            p.get(health, STEADY_VAR) and not rest.flinched,
            f"{STEADY_VAR} {p.get(health, STEADY_VAR)}, eye "
            f"{rest.mean_height():.1f} cm over the capsule's middle")

    before = p.get(health, "Health")
    _hit(p, health)
    hit = _View(p, cam)
    yield from _hold(p, wc, WATCH_S, each=hit.sample)
    took = (p.get(health, "Health") < before
            and p.get(health, PREV_HEALTH_VAR) == p.get(health, "Health"))
    p.check("down the sights the hit is taken (Health fell, and was seen)", took,
            f"Health {before:g} -> {p.get(health, 'Health'):g}, "
            f"{PREV_HEALTH_VAR} {p.get(health, PREV_HEALTH_VAR):g}")
    p.check("down the sights a hit plays no flinch", not hit.flinched,
            f"{HIT_SLOT} active over {len(hit.heights)} frames: {hit.flinched}")
    height, turn = hit.off(rest)
    p.check(f"down the sights a hit leaves the view where it was "
            f"(< {HEIGHT_CM:g} cm, < {TURN_DEG:g} deg)",
            height < HEIGHT_CM and turn < TURN_DEG,
            f"moved {height:.2f} cm in height, turned {turn:.2f} deg")

    # --- at the hip the flinch still plays ------------------------------------
    yield lambda: p.get(wc, "SightBlend") < 1e-3
    yield 0.6           # past the reaction's cooldown
    p.check("at the hip the body is not steady", not p.get(health, STEADY_VAR),
            f"{STEADY_VAR} {p.get(health, STEADY_VAR)}")
    _hit(p, health)
    yield lambda: anim.is_slot_active(HIT_SLOT)
    p.check("at the hip a hit plays the flinch", anim.is_slot_active(HIT_SLOT),
            f"{HIT_SLOT} active")

    # --- the sights come up in the middle of it -------------------------------
    # The shortest flinch is 0.7 s at 1.4x: 0.5 s, and its blend out. Left
    # alone it is still playing at FLINCH_CUT_S.
    yield from _hold(p, wc, FLINCH_CUT_S)
    p.check(f"raising the sights mid-flinch ends it and puts the ready pose "
            f"straight back (within {FLINCH_CUT_S:g} s)",
            anim.is_slot_active(AIM_SLOT) and not anim.is_slot_active(HIT_SLOT),
            f"{AIM_SLOT} active {anim.is_slot_active(AIM_SLOT)}, {HIT_SLOT} "
            f"active {anim.is_slot_active(HIT_SLOT)}")
    late = _View(p, cam)
    yield from _hold(p, wc, 0.3, each=late.sample)
    height, turn = late.off(rest)
    p.check("and the view settles where it was, with no flinch left",
            height < HEIGHT_CM and turn < TURN_DEG and not late.flinched,
            f"{height:.2f} cm, {turn:.2f} deg off; {HIT_SLOT} active "
            f"{late.flinched}")
