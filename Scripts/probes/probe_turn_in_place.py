"""Standing still, the legs step round after the view (combat/gas_turn.py).

The capsule takes the view's yaw at once and the motion matching's Offset Root
Bone leaves the legs where they stood. With InputState.WantsToAim filled, the
sample's chooser offers its turn-in-place clips once the legs are 50 degrees
behind, and they step round. Before, the idle loop was the only clip on offer
and the legs stayed planted while the body wound up over them.

With empty hands, with the shotgun carried lowered, and with it down the
sights, the view is turned 180 degrees one way and then 360 the other. In
each turn:

  - the actor's yaw is the view's on every frame (the body faces the camera at
    once), and with the gun up its barrel stays on the view;
  - a clip of the sample's turn-in-place database is picked, and the idle loop
    comes back afterwards;
  - the legs catch up: the root the motion matching draws is back under the
    actor, and the line of the hips is where it was before the turn;
  - the legs are never a half circle behind (they step during a long turn,
    not after it);
  - the feet step, and the one on the ground stays where it is: frame by
    frame, the ball of the foot that moves less hardly travels at all (the
    clips lift a foot 4-5 cm, so height does not say which one is down).

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end. Another player's copy:
probe_net_turn_in_place.py.
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # the carry's probe passes here only (T11)
SYSTEMS = ('animation', 'movement', 'weapons')

import math
import os
import shutil
import time

import unreal

from combat.carry_pose_consts import CARRY_POSE
from combat.carry_tuning import LOWERED_VAR
from combat.paths import WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.seat_tuning import SIGHTS_FORCED_VAR
from combat.slot_tuning import HAND_FROM_VAR
from combat.weapon_component import vars as WV
from graphics_menu.profile_consts import PROFILE_SLOT

RUNS_ON = ("standalone",)
WRITABLE = [(WEAPON_COMP_BP_PATH, v) for v in
            (WV.EquippedIndex, WV.NeedsRefresh, SIGHTS_FORCED_VAR)]

TURNS = ((180.0, 1.0), (-360.0, 2.0))   # degrees, over this many seconds
SETTLE_S = 3.0          # the last step and the blend back to the idle
FACE_DEG = 1.0          # the actor against the view, any frame
BARREL_DEG = 12.0       # the raised gun's barrel against the view, any frame
CAUGHT_UP_DEG = 10.0    # the drawn root against the actor, after the turn
HIPS_DEG = 12.0         # the hips' line against where it was before the turn
BEHIND_DEG = 150.0      # the legs are never this far behind the body
STEP_CM = 40.0          # each ball of the foot goes at least this far round
# Of the two balls of the feet, the one that moves less in a frame is the one
# on the ground. Its travel summed over the turn and the settling: under this.
# (Legs that spin with the capsule move both alike: 70 cm in a half circle,
# measured down the sights before the root's mode was patched.)
PLANTED_CM = 12.0
TURN_TAG = "TurnInPlace"
WALL_WAIT_S = 20.0


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _until(cond):
    end = time.time() + WALL_WAIT_S
    return lambda: cond() or time.time() > end


def _yaw(v):
    return math.degrees(math.atan2(v.y, v.x))


def _d(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


class _Body:
    """What the probe reads off the player each frame."""

    def __init__(self, p):
        self.p, self.pawn, self.pc = p, p.pawn(), p.controller()
        self.mesh = self.pawn.get_editor_property("mesh")
        # A headless game renders nothing, and by default an unrendered mesh
        # never refreshes its bones.
        self.mesh.set_editor_property(
            "visibility_based_anim_tick_option",
            unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
            unreal.PropertyAccessChangeNotifyMode.NEVER)
        self.inst = self.mesh.get_anim_instance()

    def now(self):
        return unreal.GameplayStatics.get_time_seconds(self.p.world())

    def view(self):
        return self.pc.get_control_rotation().yaw

    def actor(self):
        return self.pawn.get_actor_rotation().yaw

    def root_behind(self):
        """Degrees from the actor to the root the motion matching draws."""
        root = self.inst.get_editor_property("RootTransform").rotation.rotator().yaw
        return _d(root, self.actor())

    def hips(self):
        a, b = (self.mesh.get_socket_location(s) for s in ("thigh_l", "thigh_r"))
        return _d(_yaw(b - a), self.actor())

    def clip(self):
        anim = self.inst.get_editor_property("CurrentSelectedAnim")
        return anim.get_name() if anim else "None"

    def turning(self):
        return TURN_TAG in [str(t) for t in self.inst.get_editor_property("CurrentDatabaseTags")]

    def balls(self):
        return [self.mesh.get_socket_location(s) for s in ("ball_l", "ball_r")]


def _turn(p, body, label, degrees, seconds, barrel):
    hips0 = body.hips()
    seen = dict(face=0.0, barrel=0.0, behind=0.0, clips=[], planted=0.0,
                all=[0.0, 0.0], frames=0)
    y0, start, last = body.view(), body.now(), body.balls()
    while body.now() - start < seconds + SETTLE_S:
        part = min(1.0, (body.now() - start) / seconds)
        body.pc.set_control_rotation(
            unreal.Rotator(pitch=0.0, yaw=y0 + degrees * part, roll=0.0))
        yield 0.0
        seen["frames"] += 1
        seen["face"] = max(seen["face"], abs(_d(body.actor(), body.view())))
        if barrel is not None:
            seen["barrel"] = max(seen["barrel"], abs(_d(barrel(), body.view())))
        seen["behind"] = max(seen["behind"], abs(body.root_behind()))
        if body.turning() and body.clip() not in seen["clips"]:
            seen["clips"].append(body.clip())
        balls = body.balls()
        steps = [math.hypot(at.x - was.x, at.y - was.y) for was, at in zip(last, balls)]
        seen["all"] = [a + s for a, s in zip(seen["all"], steps)]
        seen["planted"] += min(steps)
        last = balls

    turn = f"{label}, the view turned {degrees:+.0f} deg in {seconds:g} s"
    p.check(f"{turn}: the actor's yaw is the view's on every frame",
            seen["face"] < FACE_DEG, f"at most {seen['face']:.2f} deg apart, "
            f"{seen['frames']} frames")
    if barrel is not None:
        p.check(f"...and the raised gun's barrel stays within {BARREL_DEG:g} deg of it",
                seen["barrel"] < BARREL_DEG, f"at most {seen['barrel']:.1f} deg")
    p.check("...a clip of the sample's turn-in-place database is picked",
            bool(seen["clips"]), ", ".join(seen["clips"]) or "none")
    p.check(f"...the legs are never {BEHIND_DEG:g} deg behind the body",
            seen["behind"] < BEHIND_DEG, f"at most {seen['behind']:.1f} deg")
    p.check(f"...and they catch up: the drawn root is within {CAUGHT_UP_DEG:g} deg of "
            f"the actor, the hips within {HIPS_DEG:g} deg of where they were, the idle "
            "is back",
            abs(body.root_behind()) < CAUGHT_UP_DEG
            and abs(_d(body.hips(), hips0)) < HIPS_DEG and not body.turning(),
            f"root {body.root_behind():+.1f} deg, hips {_d(body.hips(), hips0):+.1f} deg, "
            f"{body.clip()}")
    p.check(f"...the feet step (each over {STEP_CM:g} cm) and the one on the ground "
            f"does not slide: frame by frame, the slower foot travels under "
            f"{PLANTED_CM:g} cm in all",
            min(seen["all"]) > STEP_CM and seen["planted"] < PLANTED_CM,
            "left {:.0f} cm, right {:.0f} cm, the slower one {:.1f} cm".format(
                *seen["all"], seen["planted"]))


def _run(p):
    yield 0.5
    body = _Body(p)
    wc = p.component(body.pawn, WEAPON_COMP_CLASS_PATH)
    layers = p.pose_instance(body.mesh)
    yield _until(lambda: body.clip() != "None")
    yield 2.0

    def stage(label, barrel=None):
        for degrees, seconds in TURNS:
            yield from _turn(p, body, label, degrees, seconds, barrel)

    # Empty hands: the slot the hand's item came from, asked again, puts it away.
    if p.get(wc, WV.Held) is not None:
        p.ask_slot(wc, p.get(wc, HAND_FROM_VAR))
    yield _until(lambda: p.get(wc, WV.Held) is None)
    yield 1.0
    p.check("the hands are empty", p.get(wc, WV.Held) is None)
    yield from stage("empty hands")

    names = [i.get_class().get_name() for i in p.get(wc, WV.Inventory)]
    p.hold(wc, names.index("BP_Shotgun_C"))
    yield _until(lambda: p.get(wc, WV.Held) is not None
                 and p.get(wc, LOWERED_VAR) and p.get(layers, CARRY_POSE) > 0.98)
    yield 1.0
    held = p.get(wc, WV.Held)
    p.check("the shotgun is carried lowered",
            held is not None and held.get_class().get_name() == "BP_Shotgun_C"
            and p.get(wc, LOWERED_VAR) and p.get(layers, CARRY_POSE) > 0.98,
            f"{CARRY_POSE} {p.get(layers, CARRY_POSE):.2f}")
    yield from stage("the shotgun carried")

    p.set(wc, SIGHTS_FORCED_VAR, True)
    yield _until(lambda: p.get(wc, "SightAiming") and p.get(wc, "SightBlend") > 0.99)
    yield 1.0
    p.check("the shotgun is down the sights",
            bool(p.get(wc, "SightAiming")) and p.get(wc, "SightBlend") > 0.99,
            f"SightBlend {p.get(wc, 'SightBlend'):.2f}")
    yield from stage("down the sights",
                     lambda: _yaw(held.get_actor_forward_vector()))
    p.set(wc, SIGHTS_FORCED_VAR, False)
