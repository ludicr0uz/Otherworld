"""The carry in the running game: a gun rides lowered, and an aim, a shot or
the guard raises it.

For the shotgun and the pistol in turn: at rest and jogging the ready pose is
not playing, the barrel is off the horizon and the hand is low. The pistol
hangs in the locomotion's hand, the barrel at the ground. The shotgun, a long
gun, is in the carry (combat/carry_pose.py): CarryPose is up on the weapon
layers, the barrel a little under the horizon, the left hand as far from the
right as in the ready pose (on the gun), standing, jogging and at a sprint,
where CarrySprint brings the sprint's own carry; crouched it stays up, at rest
and creeping, the barrel in the same band and the hands as far apart, over the
crouched clips (PoseCrouch); raised, CarryPose is down again. The
probes' stand-in for an aim key (RaiseForced) brings the ready pose up and the
barrel level, with the muzzle near where a lowered gun's shot starts; letting
go lowers it. A forced shot raises it too, and it comes
down once the hold after NextFireTime has passed (written back, because a
headless game's clock is slow). The knife is never lowered. (Prone keeps a
gun up: probe_stance_clips.py.)

Run with --windowed and OW_CARRY_SHOTS=1 to save a picture of each gun at
rest, jogging and raised to Saved/Screenshots/MacEditor.

Any profile on disk is set aside first, so the game starts on the issued
loadout, and put back at the end.
"""

LEVEL = "/Game/Maps/Lvl_Forest_200m"  # passes here, fails on the 50 m probe level (T11)
SYSTEMS = ('weapons',)

import math
import os
import shutil
import time

import unreal

from combat.anim_blueprint import AIM_SLOT
from combat.body_pose import POSE_CROUCH
from combat.carry_pose_consts import CARRY_FOR_VAR, CARRY_POSE, CARRY_SPRINT
from combat.carry_tuning import (
    CARRY_GRIP, CARRY_RAISE_HOLD_S, LOWERED_VAR, RAISE_FORCED_VAR,
)
from combat.paths import ITEM_BP_PATH, WEAPON_COMP_BP_PATH, WEAPON_COMP_CLASS_PATH
from combat.skin import SKINS
from combat.sprint_tuning import SPRINT_FORCED_VAR
from combat.weapon_component.stance import CROUCH, STAND
from combat.weapon_component.tick import FIRE_FORCED_VAR
from graphics_menu.profile_consts import PROFILE_SLOT
from combat import item_vars as IV
from combat.weapon_component import vars as WV

WRITABLE = [(WEAPON_COMP_BP_PATH, v) for v in
            (WV.EquippedIndex, WV.NeedsRefresh, RAISE_FORCED_VAR, FIRE_FORCED_VAR,
             SPRINT_FORCED_VAR, WV.Stance)] + [
    (ITEM_BP_PATH, IV.NextFireTime)]

SETTLE_S = 0.4          # the ready pose's blend, and a little
JOG_S = 0.6
STOP_S = 1.2            # the motion matching's stop out of a jog, played out
LOWERED_DEG = 35.0      # the barrel hangs at least this far below the horizon
RAISED_DEG = 20.0       # ...and raised, sits within this of it
ORIGIN_NEAR_CM = 32.0    # the stand-in muzzle against the raised gun's own
HAND_RISE_CM = 15.0     # how far the hand comes up with the gun
# A long gun's carry: the barrel sits in this band under the horizon standing
# and jogging (the clips have it some 15 deg down), and the hands are as far
# apart as the ready pose has them, within this.
CARRY_DEG = (3.0, 35.0)
CARRY_HANDS_CM = 8.0
SPRINT_S = 1.2
CREEP_S = 1.0
SHOTS = bool(os.environ.get("OW_CARRY_SHOTS"))
WALL_WAIT_S = 20.0      # a headless game's clock is slow: bound waits by the wall


def _file():
    return os.path.join(unreal.Paths.project_saved_dir(), "SaveGames",
                        f"{PROFILE_SLOT}.sav")


def _until(cond):
    end = time.time() + WALL_WAIT_S
    return lambda: cond() or time.time() > end


def probe(p):
    backup = _file() + ".probe-backup"
    if os.path.exists(_file()):
        shutil.move(_file(), backup)
    try:
        yield from _run(p)
    finally:
        if os.path.exists(backup):
            shutil.move(backup, _file())


def _barrel_pitch(p, held):
    """Degrees the barrel points above the horizon (+X is the weapon's frame)."""
    return math.degrees(math.asin(held.get_actor_forward_vector().z))


def _hand_z(player):
    mesh = player.get_editor_property("mesh")
    bone = next(s.pose_bones["hand_r"] for s in SKINS
                if mesh.get_bone_index(s.pose_bones["hand_r"]) >= 0)
    return mesh.get_socket_location(bone).z - player.get_actor_location().z


def _hands_apart(player):
    mesh = player.get_editor_property("mesh")
    at = [mesh.get_socket_location(next(
        s.pose_bones[b] for s in SKINS if mesh.get_bone_index(s.pose_bones[b]) >= 0))
        for b in ("hand_r", "hand_l")]
    return (at[0] - at[1]).length()


def _in_carry_band(pitch):
    return -CARRY_DEG[1] < pitch < -CARRY_DEG[0]


def _posing(anim, held):
    return anim.is_playing_slot_animation(held.get_editor_property("AimPose"), AIM_SLOT)


def _shot(p):
    """Save a picture of this frame (windowed runs only)."""
    if SHOTS:
        unreal.SystemLibrary.execute_console_command(p.world(), "shot")
        yield 0.05


def _rest(p, held):
    """Put the last shot well in the past: nothing but a key holds the gun up."""
    now = unreal.GameplayStatics.get_time_seconds(p.world())
    p.set(held, "NextFireTime", now - CARRY_RAISE_HOLD_S - 1.0)


def _sprint(p, player, wc, layers, held, label):
    """A long gun at a sprint: the sprint's own carry comes in, and goes."""
    p.set(wc, SPRINT_FORCED_VAR, True)
    t0 = unreal.GameplayStatics.get_time_seconds(p.world())
    top, seen = [0.0, 0.0], []

    def run():
        player.add_movement_input(player.get_actor_forward_vector(), 1.0)
        top[0] = max(top[0], p.get(layers, CARRY_SPRINT))
        top[1] = max(top[1], player.get_velocity().length())
        seen.append((p.get(layers, CARRY_POSE), _hands_apart(player)))
        return unreal.GameplayStatics.get_time_seconds(p.world()) - t0 >= SPRINT_S
    yield _until(run)
    p.set(wc, SPRINT_FORCED_VAR, False)
    late = seen[len(seen) // 2:]
    p.check(f"{label}, sprinting: {CARRY_SPRINT} brings the sprint's carry in, "
            f"{CARRY_POSE} stays up",
            top[0] > 0.9 and min(c for c, _ in late) > 0.9 and p.get(wc, LOWERED_VAR),
            f"{CARRY_SPRINT} {top[0]:.2f} at {top[1]:.0f} cm/s, "
            f"{CARRY_POSE} >= {min(c for c, _ in late):.2f}")
    yield _until(lambda: player.get_velocity().length() < 5.0
                 and p.get(layers, CARRY_SPRINT) < 0.05)
    p.check(f"...and out of the sprint {CARRY_SPRINT} goes again",
            p.get(layers, CARRY_SPRINT) < 0.05, f"{p.get(layers, CARRY_SPRINT):.2f}")
    return [h for _, h in late]


def _crouched(p, player, wc, anim, layers, held, label, up_apart):
    """Crouched, a long gun is carried too: the crouched clips' carry, at
    rest and creeping. ``up_apart``: the hands' distance in the ready pose."""
    p.set(wc, "Stance", CROUCH)
    yield _until(lambda: p.get(layers, POSE_CROUCH) > 0.98)
    yield SETTLE_S
    yield from _shot(p)
    pitch, apart = _barrel_pitch(p, held), _hands_apart(player)
    p.check(f"{label}, crouched at rest: {CARRY_POSE} stays up over the crouched "
            f"clip ({POSE_CROUCH}), lowered, no ready pose",
            p.get(layers, CARRY_POSE) > 0.98 and p.get(layers, POSE_CROUCH) > 0.98
            and p.get(wc, LOWERED_VAR) and not _posing(anim, held),
            f"{CARRY_POSE} {p.get(layers, CARRY_POSE):.2f}, "
            f"{POSE_CROUCH} {p.get(layers, POSE_CROUCH):.2f}")
    p.check(f"...the barrel {CARRY_DEG[0]:g} to {CARRY_DEG[1]:g} deg under the horizon "
            f"and the left hand on the gun (within {CARRY_HANDS_CM:g} cm of the ready "
            "pose's distance)",
            _in_carry_band(pitch) and abs(apart - up_apart) < CARRY_HANDS_CM,
            f"{pitch:+.1f} deg, hands {apart:.1f} cm apart against {up_apart:.1f}")
    t0 = unreal.GameplayStatics.get_time_seconds(p.world())
    fastest, seen = [0.0], []

    def creep():
        player.add_movement_input(player.get_actor_forward_vector(), 1.0)
        seen.append((_barrel_pitch(p, held), _hands_apart(player),
                     p.get(layers, CARRY_POSE)))
        fastest[0] = max(fastest[0], player.get_velocity().length())
        return unreal.GameplayStatics.get_time_seconds(p.world()) - t0 >= CREEP_S
    yield _until(creep)
    late = seen[len(seen) // 2:]
    median = sorted(s[0] for s in late)[len(late) // 2]
    p.check(f"{label}, creeping crouched: still carried, the barrel in the band "
            "and the left hand on the gun",
            fastest[0] > 50.0 and p.get(wc, "Stance") == CROUCH
            and min(s[2] for s in late) > 0.98 and _in_carry_band(median)
            and all(abs(s[1] - up_apart) < CARRY_HANDS_CM for s in late),
            f"{fastest[0]:.0f} cm/s, median {median:+.1f} deg, hands "
            f"{min(s[1] for s in late):.1f}..{max(s[1] for s in late):.1f} cm apart")
    yield _until(lambda: player.get_velocity().length() < 5.0)
    p.set(wc, RAISE_FORCED_VAR, True)
    yield _until(lambda: _posing(anim, held) and p.get(layers, CARRY_POSE) < 0.05)
    p.check(f"{label}, crouched and aimed: raised, the ready pose plays and "
            f"{CARRY_POSE} is down",
            not p.get(wc, LOWERED_VAR) and _posing(anim, held)
            and p.get(layers, CARRY_POSE) < 0.05, f"{p.get(layers, CARRY_POSE):.2f}")
    p.set(wc, RAISE_FORCED_VAR, False)
    yield _until(lambda: not _posing(anim, held) and p.get(layers, CARRY_POSE) > 0.95)
    p.set(wc, "Stance", STAND)
    yield _until(lambda: p.get(layers, POSE_CROUCH) < 0.02)
    yield SETTLE_S
    p.check("...and standing up, the carry is the standing one again",
            p.get(layers, CARRY_POSE) > 0.95 and p.get(layers, POSE_CROUCH) < 0.02
            and _in_carry_band(_barrel_pitch(p, held)),
            f"{CARRY_POSE} {p.get(layers, CARRY_POSE):.2f}, "
            f"{_barrel_pitch(p, held):+.1f} deg")


def _gun(p, player, wc, anim, layers, label, index):
    p.set(wc, "EquippedIndex", index)
    p.set(wc, "NeedsRefresh", True)
    yield lambda: p.get(wc, "Held") == p.get(wc, "Inventory")[index]
    held = p.get(wc, "Held")
    pose = p.get(wc, CARRY_FOR_VAR)
    carried = pose is not None and held.get_editor_property("AimPose") == pose
    _rest(p, held)
    yield _until(lambda: p.get(wc, LOWERED_VAR))
    if carried:
        yield _until(lambda: p.get(layers, CARRY_POSE) > 0.98)
    yield SETTLE_S
    yield from _shot(p)
    low_hand, low_pitch = _hand_z(player), _barrel_pitch(p, held)
    p.check(f"{label}, at rest: lowered, the ready pose is not playing",
            p.get(wc, LOWERED_VAR) and not _posing(anim, held)
            and held.get_attach_parent_actor() == player)
    low_apart = _hands_apart(player)
    if carried:
        p.check(f"...in the carry: {CARRY_POSE} is up and the barrel is {CARRY_DEG[0]:g} "
                f"to {CARRY_DEG[1]:g} deg under the horizon",
                p.get(layers, CARRY_POSE) > 0.98 and _in_carry_band(low_pitch),
                f"{CARRY_POSE} {p.get(layers, CARRY_POSE):.2f}, {low_pitch:+.1f} deg")
    else:
        p.check(f"...and the barrel hangs more than {LOWERED_DEG:g} deg below the "
                f"horizon, {CARRY_POSE} never up",
                low_pitch < -LOWERED_DEG and p.get(layers, CARRY_POSE) < 0.02,
                f"{low_pitch:+.1f} deg, {CARRY_POSE} {p.get(layers, CARRY_POSE):.2f}")

    # Jogging: the locomotion's own arms, the gun still down.
    t0 = unreal.GameplayStatics.get_time_seconds(p.world())
    fastest, seen = [0.0], []

    def jog():
        player.add_movement_input(player.get_actor_forward_vector(), 1.0)
        seen.append(_barrel_pitch(p, held))
        if SHOTS and len(seen) % 12 == 0:
            unreal.SystemLibrary.execute_console_command(p.world(), "shot")
        fastest[0] = max(fastest[0], player.get_velocity().length())
        return unreal.GameplayStatics.get_time_seconds(p.world()) - t0 >= JOG_S
    yield _until(jog)
    seen.sort()
    median = seen[len(seen) // 2]
    p.note(f"{label}, jogging: the barrel swings {seen[0]:+.1f} to {seen[-1]:+.1f} deg "
           f"(median {median:+.1f}) over {len(seen)} frames")
    if carried:
        p.check(f"{label}, jogging: still lowered, no ready pose, and the barrel "
                "stays in the carry's band",
                p.get(wc, LOWERED_VAR) and not _posing(anim, held)
                and fastest[0] > 100.0 and _in_carry_band(median)
                and p.get(layers, CARRY_POSE) > 0.98,
                f"{fastest[0]:.0f} cm/s, median {median:+.1f} deg")
        fast_apart = yield from _sprint(p, player, wc, layers, held, label)
    else:
        p.check(f"{label}, jogging: still lowered, no ready pose, and the barrel "
                f"swings with the arm, mostly more than {LOWERED_DEG:g} deg below the "
                "horizon",
                p.get(wc, LOWERED_VAR) and not _posing(anim, held)
                and fastest[0] > 100.0 and median < -LOWERED_DEG,
                f"{fastest[0]:.0f} cm/s, median {median:+.1f} deg")
    yield _until(lambda: player.get_velocity().length() < 5.0)
    # The stop is a clip of its own (the body leans back out of the run), and
    # the muzzle is measured standing.
    yield STOP_S

    # An aim key (its stand-in) raises it, and letting go lowers it.
    p.set(wc, RAISE_FORCED_VAR, True)
    yield _until(lambda: _posing(anim, held))
    yield SETTLE_S
    yield from _shot(p)
    up_hand, up_pitch = _hand_z(player), _barrel_pitch(p, held)
    off = p.get(held, "MuzzleOffset")
    real = held.get_actor_transform().transform_location(off)
    stood_in = player.get_actor_transform().transform_location(
        off + unreal.Vector(*CARRY_GRIP))
    fist = player.get_actor_transform().inverse_transform_location(real) - off
    p.check(f"...and its muzzle is within {ORIGIN_NEAR_CM:g} cm of where a lowered "
            "gun's shot starts (CARRY_GRIP + MuzzleOffset in the body's frame), "
            "and no nearer the body",
            (real - stood_in).length() < ORIGIN_NEAR_CM
            and fist.x > CARRY_GRIP[0] - 2.0,       # never past the real muzzle
            f"{(real - stood_in).length():.1f} cm; the fist is at "
            f"({fist.x:.0f}, {fist.y:.0f}, {fist.z:.0f})")
    p.check(f"{label}, aimed: raised, the ready pose plays in {AIM_SLOT}",
            not p.get(wc, LOWERED_VAR) and _posing(anim, held))
    p.check(f"...the barrel within {RAISED_DEG:g} deg of the horizon and the hand "
            f"{HAND_RISE_CM:g} cm higher",
            abs(up_pitch) < RAISED_DEG and up_hand > low_hand + HAND_RISE_CM,
            f"{up_pitch:+.1f} deg, hand {low_hand:.1f} -> {up_hand:.1f} cm")
    if carried:
        up_apart = _hands_apart(player)
        p.check(f"...{CARRY_POSE} is down under the ready pose, and the carry had the "
                f"left hand where that has it, within {CARRY_HANDS_CM:g} cm (on the gun), "
                "standing and at the sprint",
                p.get(layers, CARRY_POSE) < 0.05
                and abs(low_apart - up_apart) < CARRY_HANDS_CM
                and all(abs(h - up_apart) < CARRY_HANDS_CM for h in fast_apart),
                f"{CARRY_POSE} {p.get(layers, CARRY_POSE):.2f}; hands {up_apart:.1f} cm "
                f"apart raised, {low_apart:.1f} carried, "
                f"{min(fast_apart):.1f}..{max(fast_apart):.1f} sprinting")
    p.set(wc, RAISE_FORCED_VAR, False)
    yield _until(lambda: not _posing(anim, held))
    p.check(f"{label}, the aim let go: lowered again",
            p.get(wc, LOWERED_VAR) and not _posing(anim, held))
    if carried:
        yield from _crouched(p, player, wc, anim, layers, held, label, up_apart)

    # A shot raises it, and it stays up until the hold has passed.
    loaded = p.get(held, "Loaded")
    p.set(wc, FIRE_FORCED_VAR, True)
    yield _until(lambda: p.get(held, "Loaded") < loaded)
    p.set(wc, FIRE_FORCED_VAR, False)
    yield _until(lambda: _posing(anim, held))
    now = unreal.GameplayStatics.get_time_seconds(p.world())
    p.check(f"{label}, a shot: the round leaves and the gun comes up",
            p.get(held, "Loaded") < loaded and not p.get(wc, LOWERED_VAR)
            and _posing(anim, held) and p.get(held, "NextFireTime") > now - 0.5,
            f"{loaded} -> {p.get(held, 'Loaded')}")
    yield 0.2
    p.check(f"...and stays up between shots ({CARRY_RAISE_HOLD_S:g} s past "
            "NextFireTime)", not p.get(wc, LOWERED_VAR) and _posing(anim, held))
    _rest(p, held)
    yield _until(lambda: not _posing(anim, held))
    p.check(f"{label}, the hold over: lowered again",
            p.get(wc, LOWERED_VAR) and not _posing(anim, held))


def _run(p):
    yield 0.5
    player = p.pawn()
    wc = p.component(player, WEAPON_COMP_CLASS_PATH)
    p.check("the player has a weapon component", wc is not None)
    if wc is None:
        return
    mesh = player.get_editor_property("mesh")
    # A headless game renders nothing, and by default an unrendered mesh
    # never refreshes its bones: the hand and the gun would never move.
    mesh.set_editor_property(
        "visibility_based_anim_tick_option",
        unreal.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES,
        unreal.PropertyAccessChangeNotifyMode.NEVER)
    anim = mesh.get_anim_instance()
    layers = p.pose_instance(mesh)
    p.check(f"the build has the long gun's carry ({CARRY_FOR_VAR} is set)",
            p.get(wc, CARRY_FOR_VAR) is not None)
    names = [i.get_class().get_name() for i in p.get(wc, "Inventory")]
    for label, cls in (("shotgun", "BP_Shotgun_C"), ("pistol", "BP_Pistol_C")):
        yield from _gun(p, player, wc, anim, layers, label, names.index(cls))

    index = names.index("BP_Knife_C")
    p.set(wc, "EquippedIndex", index)
    p.set(wc, "NeedsRefresh", True)
    yield lambda: p.get(wc, "Held") == p.get(wc, "Inventory")[index]
    yield SETTLE_S
    knife = p.get(wc, "Held")
    p.check("the knife is never lowered: its hold pose plays with no key held",
            not p.get(wc, LOWERED_VAR) and _posing(anim, knife))
